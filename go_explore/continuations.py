from __future__ import annotations

import asyncio
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

from daytona import AsyncDaytona

from go_explore.harbor import HarborRunConfig, build_harbor_command
from go_explore.results import JobSummary, TrialSummary, summarize_job


class ContinuationError(ValueError):
    """Raised when a continuation run cannot be planned from job metadata."""


def snapshot_prefix_for_trial(
    trial_name: str,
    *,
    name_prefix: str = "go-explore",
) -> str:
    return f"{name_prefix}-{trial_name}-step-"


@dataclass(frozen=True)
class ContinuationPlan:
    """One continuation job launched from one Daytona snapshot."""

    parent_job_dir: Path
    parent_trial_name: str
    snapshot_name: str
    job_name: str
    command: tuple[str, ...]


@dataclass(frozen=True)
class ContinuationAttempt:
    """Result lineage for a continuation trial."""

    parent_job_dir: str
    parent_trial_name: str
    snapshot_name: str
    continuation_job_dir: str
    continuation_trial_name: str | None
    reward: float | None
    exception_type: str | None

    @property
    def succeeded(self) -> bool:
        return self.reward == 1.0 and self.exception_type is None


@dataclass(frozen=True)
class ContinuationReport:
    """Phase 1 report: external continuation attempts grouped by root trial."""

    root_job_dir: str
    root_trial_name: str
    root_reward: float | None
    attempts: tuple[ContinuationAttempt, ...]

    @property
    def any_success(self) -> bool:
        return any(attempt.succeeded for attempt in self.attempts)

    def to_json_dict(self) -> dict:
        return {
            "root_job_dir": self.root_job_dir,
            "root_trial_name": self.root_trial_name,
            "root_reward": self.root_reward,
            "any_success": self.any_success,
            "attempts": [
                asdict(attempt) | {"succeeded": attempt.succeeded}
                for attempt in self.attempts
            ],
        }


async def list_daytona_snapshots_for_trial(
    trial_name: str,
    *,
    limit: int = 200,
    name_prefix: str = "go-explore",
) -> list[str]:
    expected_prefix = snapshot_prefix_for_trial(trial_name, name_prefix=name_prefix)
    async with AsyncDaytona() as daytona:
        snapshots_page = await daytona.snapshot.list(limit=limit)
        return sorted(
            snapshot.name
            for snapshot in snapshots_page.items
            if snapshot.name.startswith(expected_prefix)
        )


def _read_json(path: Path) -> dict[str, Any]:
    with path.open() as file:
        return json.load(file)


def _dataset_arg(dataset_config: dict[str, Any]) -> str:
    name = dataset_config.get("name")
    if not name:
        raise ContinuationError("Root Harbor config is missing dataset name.")

    version = dataset_config.get("version")
    if version:
        return f"{name}@{version}"
    return str(name)


def _single_task_name(dataset_config: dict[str, Any]) -> str | None:
    task_names = dataset_config.get("task_names") or ()
    if len(task_names) == 1:
        return str(task_names[0])
    return None


def harbor_config_from_job(
    job_dir: Path,
    *,
    agent: str | None = None,
    model: str | None = None,
    extra_args: Sequence[str] = (),
) -> HarborRunConfig:
    """Reconstruct the Harbor command shape needed for continuation jobs."""

    root_config = _read_json(job_dir / "config.json")
    agents = root_config.get("agents") or ()
    agent_config = agents[0] if agents else {}
    datasets = root_config.get("datasets") or ()
    tasks = root_config.get("tasks") or ()
    environment = root_config.get("environment") or {}

    dataset = None
    path = None
    task_name = None

    if datasets:
        dataset_config = datasets[0]
        dataset = _dataset_arg(dataset_config)
        task_name = _single_task_name(dataset_config)
    elif tasks:
        task_config = tasks[0]
        path_value = task_config.get("path")
        if not path_value:
            raise ContinuationError("Root Harbor task config is missing path.")
        path = Path(path_value)
    else:
        raise ContinuationError("Root Harbor config has neither datasets nor tasks.")

    base_extra_args: list[str] = []
    import_path = agent_config.get("import_path")
    root_agent_name = agent_config.get("name")

    if import_path and agent is None:
        root_agent_name = str(import_path)

    return HarborRunConfig(
        jobs_dir=Path(root_config.get("jobs_dir") or job_dir.parent),
        agent=agent if agent is not None else root_agent_name,
        env=environment.get("type") or "daytona",
        dataset=dataset,
        path=path,
        model=model if model is not None else agent_config.get("model_name"),
        task_name=task_name,
        n_tasks=1,
        n_attempts=1,
        n_concurrent=1,
        export_traces=True,
        extra_args=tuple(base_extra_args) + tuple(extra_args),
    )


def select_trial(summary: JobSummary, trial_name: str | None = None) -> TrialSummary:
    if not summary.trials:
        raise ContinuationError(f"No trials found in {summary.job_dir}.")

    if trial_name is None:
        return summary.trials[0]

    for trial in summary.trials:
        if trial.trial_name == trial_name:
            return trial

    raise ContinuationError(f"Trial {trial_name!r} not found in {summary.job_dir}.")


def build_snapshot_continuation_config(
    *,
    root_config: HarborRunConfig,
    snapshot_name: str,
    job_name: str,
    agent: str | None = None,
    model: str | None = None,
    extra_args: Sequence[str] = (),
) -> HarborRunConfig:
    """Build a Harbor job that starts Daytona from a saved snapshot."""

    combined_extra_args = tuple(root_config.extra_args) + tuple(extra_args)

    return HarborRunConfig(
        agent=agent if agent is not None else root_config.agent,
        model=model if model is not None else root_config.model,
        env="daytona",
        jobs_dir=root_config.jobs_dir,
        n_attempts=1,
        n_concurrent=1,
        dataset=root_config.dataset,
        path=root_config.path,
        task_name=root_config.task_name,
        n_tasks=1,
        job_name=job_name,
        export_traces=root_config.export_traces,
        environment_kwargs=(f"snapshot_template_name={snapshot_name}",),
        extra_args=combined_extra_args,
    )


def plan_snapshot_continuations(
    *,
    root_config: HarborRunConfig,
    root_summary: JobSummary,
    snapshots: Sequence[str],
    continuation_job_prefix: str,
    agent: str | None = None,
    model: str | None = None,
    extra_args: Sequence[str] = (),
    max_snapshots: int | None = None,
    parent_trial_name: str | None = None,
) -> list[ContinuationPlan]:
    parent_trial = select_trial(root_summary, parent_trial_name)
    selected_snapshots = (
        list(snapshots[:max_snapshots])
        if max_snapshots
        else list(snapshots)
    )
    plans: list[ContinuationPlan] = []

    for index, snapshot_name in enumerate(selected_snapshots):
        config = build_snapshot_continuation_config(
            root_config=root_config,
            snapshot_name=snapshot_name,
            job_name=f"{continuation_job_prefix}-snapshot-{index}",
            agent=agent,
            model=model,
            extra_args=extra_args,
        )
        plans.append(
            ContinuationPlan(
                parent_job_dir=root_summary.job_dir,
                parent_trial_name=parent_trial.trial_name,
                snapshot_name=snapshot_name,
                job_name=(
                    config.job_name
                    or f"{continuation_job_prefix}-snapshot-{index}"
                ),
                command=tuple(build_harbor_command(config)),
            )
        )

    return plans


def _attempt_from_summary(
    *,
    plan: ContinuationPlan,
    trial: TrialSummary | None,
) -> ContinuationAttempt:
    return ContinuationAttempt(
        parent_job_dir=str(plan.parent_job_dir),
        parent_trial_name=plan.parent_trial_name,
        snapshot_name=plan.snapshot_name,
        continuation_job_dir=str(plan.parent_job_dir.parent / plan.job_name),
        continuation_trial_name=trial.trial_name if trial else None,
        reward=trial.reward if trial else None,
        exception_type=trial.exception_type if trial else "missing-trial-result",
    )


def run_continuation_plan(
    plan: ContinuationPlan,
    *,
    env: dict[str, str] | None = None,
    capture_output: bool = True,
) -> ContinuationAttempt:
    result = subprocess.run(
        list(plan.command),
        check=False,
        capture_output=capture_output,
        text=True,
        env=env,
    )
    job_dir = plan.parent_job_dir.parent / plan.job_name
    if result.returncode != 0 or not (job_dir / "result.json").exists():
        return ContinuationAttempt(
            parent_job_dir=str(plan.parent_job_dir),
            parent_trial_name=plan.parent_trial_name,
            snapshot_name=plan.snapshot_name,
            continuation_job_dir=str(job_dir),
            continuation_trial_name=None,
            reward=None,
            exception_type=f"harbor-return-code-{result.returncode}",
        )

    summary = summarize_job(job_dir)
    trial = summary.trials[0] if summary.trials else None
    return _attempt_from_summary(plan=plan, trial=trial)


def write_continuation_report(report: ContinuationReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_json_dict(), indent=2) + "\n")


def run_continuation_plans(
    plans: Sequence[ContinuationPlan],
    *,
    root_summary: JobSummary,
    root_trial: TrialSummary,
    report_path: Path,
    env: dict[str, str] | None = None,
) -> ContinuationReport:
    attempts = tuple(run_continuation_plan(plan, env=env) for plan in plans)
    report = ContinuationReport(
        root_job_dir=str(root_summary.job_dir),
        root_trial_name=root_trial.trial_name,
        root_reward=root_trial.reward,
        attempts=attempts,
    )
    write_continuation_report(report, report_path)
    return report


def list_daytona_snapshots_for_trial_sync(
    trial_name: str,
    *,
    limit: int = 200,
    name_prefix: str = "go-explore",
) -> list[str]:
    return asyncio.run(
        list_daytona_snapshots_for_trial(
            trial_name,
            limit=limit,
            name_prefix=name_prefix,
        )
    )
