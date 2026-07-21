from __future__ import annotations

import asyncio
import json
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal, Sequence

from daytona import AsyncDaytona

from go_explore.events import EVENT_LOG_FILENAME, append_event, base_event
from go_explore.harbor import HarborRunConfig, build_harbor_command
from go_explore.results import BudgetSummary, JobSummary, TrialSummary, summarize_job


class ContinuationError(ValueError):
    """Raised when a continuation run cannot be planned from job metadata."""


StartStateType = Literal["clean", "diff_only", "full_snapshot"]
ContextMode = Literal["original_task_only", "parent_summary"]


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
    snapshot_name: str | None
    job_name: str
    command: tuple[str, ...]
    start_state_type: StartStateType = "full_snapshot"
    context_mode: ContextMode = "parent_summary"
    parent_artifacts: tuple[str, ...] = ()
    executor_status: str = "ready"

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "parent_job_dir": str(self.parent_job_dir),
            "parent_trial_name": self.parent_trial_name,
            "parent_snapshot": self.snapshot_name,
            "job_name": self.job_name,
            "command": list(self.command),
            "start_state_type": self.start_state_type,
            "context_mode": self.context_mode,
            "parent_artifacts": list(self.parent_artifacts),
            "executor_status": self.executor_status,
        }


@dataclass(frozen=True)
class SnapshotSelectionMetadata:
    """Selector metadata associated with one planned snapshot continuation."""

    snapshot_name: str
    selector_mode: str
    cell_key: str | None = None
    priority: float | None = None
    score: float | None = None
    times_selected: int | None = None
    selector_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class ContinuationAttempt:
    """Result lineage for a continuation trial."""

    parent_job_dir: str
    parent_trial_name: str
    snapshot_name: str | None
    continuation_job_dir: str
    continuation_trial_name: str | None
    reward: float | None
    exception_type: str | None
    budget: BudgetSummary = field(default_factory=BudgetSummary)
    start_state_type: StartStateType = "full_snapshot"
    context_mode: ContextMode = "parent_summary"
    parent_artifacts: tuple[str, ...] = ()

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
    root_budget: BudgetSummary = field(default_factory=BudgetSummary)

    @property
    def any_success(self) -> bool:
        return any(attempt.succeeded for attempt in self.attempts)

    def to_json_dict(self) -> dict:
        return {
            "root_job_dir": self.root_job_dir,
            "root_trial_name": self.root_trial_name,
            "root_reward": self.root_reward,
            "root_budget": asdict(self.root_budget),
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
    agent_import_path = None

    if agent is None and import_path:
        root_agent_name = None
        agent_import_path = str(import_path)
    elif agent is None and isinstance(root_agent_name, str) and ":" in root_agent_name:
        agent_import_path = root_agent_name
        root_agent_name = None

    return HarborRunConfig(
        jobs_dir=Path(root_config.get("jobs_dir") or job_dir.parent),
        agent=agent if agent is not None else root_agent_name,
        agent_import_path=agent_import_path,
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
        agent_import_path=None if agent is not None else root_config.agent_import_path,
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


def build_clean_start_config(
    *,
    root_config: HarborRunConfig,
    job_name: str,
    agent: str | None = None,
    model: str | None = None,
    extra_args: Sequence[str] = (),
) -> HarborRunConfig:
    """Build a Harbor job that starts from the original clean task state."""

    combined_extra_args = tuple(root_config.extra_args) + tuple(extra_args)

    return HarborRunConfig(
        agent=agent if agent is not None else root_config.agent,
        agent_import_path=None if agent is not None else root_config.agent_import_path,
        model=model if model is not None else root_config.model,
        env=root_config.env,
        jobs_dir=root_config.jobs_dir,
        n_attempts=1,
        n_concurrent=1,
        dataset=root_config.dataset,
        path=root_config.path,
        task_name=root_config.task_name,
        n_tasks=1,
        job_name=job_name,
        export_traces=root_config.export_traces,
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
    event_log_path: Path | None = None,
    experiment_id: str | None = None,
    selector_mode: str = "list_order",
    selection_metadata: Sequence[SnapshotSelectionMetadata] = (),
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
                start_state_type="full_snapshot",
                context_mode="parent_summary",
            )
        )

    if event_log_path is not None:
        metadata_by_snapshot = {
            metadata.snapshot_name: metadata for metadata in selection_metadata
        }
        for index, plan in enumerate(plans):
            metadata = metadata_by_snapshot.get(plan.snapshot_name)
            log_snapshot_selected(
                plan,
                event_log_path=event_log_path,
                experiment_id=experiment_id,
                selector_mode=(
                    metadata.selector_mode if metadata else selector_mode
                ),
                selection_index=index,
                cell_key=metadata.cell_key if metadata else None,
                priority=metadata.priority if metadata else None,
                score=metadata.score if metadata else None,
                times_selected=metadata.times_selected if metadata else None,
                selector_reasons=(
                    metadata.selector_reasons if metadata else ()
                ),
            )

    return plans


def plan_start_state_baselines(
    *,
    root_config: HarborRunConfig,
    root_summary: JobSummary,
    continuation_job_prefix: str,
    start_state_types: Sequence[StartStateType],
    snapshots: Sequence[str] = (),
    diff_path: Path | None = None,
    agent: str | None = None,
    model: str | None = None,
    extra_args: Sequence[str] = (),
    max_snapshots: int | None = None,
    parent_trial_name: str | None = None,
) -> list[ContinuationPlan]:
    """Plan Claim 1 child-start conditions without executing them.

    `diff_only` is intentionally manifest-only for now: the plan records the
    parent diff artifact and the clean Harbor command shape, but no executor
    applies the diff yet.
    """

    parent_trial = select_trial(root_summary, parent_trial_name)
    plans: list[ContinuationPlan] = []

    for start_state_type in start_state_types:
        if start_state_type == "clean":
            config = build_clean_start_config(
                root_config=root_config,
                job_name=f"{continuation_job_prefix}-clean",
                agent=agent,
                model=model,
                extra_args=extra_args,
            )
            plans.append(
                ContinuationPlan(
                    parent_job_dir=root_summary.job_dir,
                    parent_trial_name=parent_trial.trial_name,
                    snapshot_name=None,
                    job_name=config.job_name or f"{continuation_job_prefix}-clean",
                    command=tuple(build_harbor_command(config)),
                    start_state_type="clean",
                    context_mode="original_task_only",
                )
            )

        elif start_state_type == "diff_only":
            artifact_path = diff_path or root_summary.job_dir / "parent.diff"
            config = build_clean_start_config(
                root_config=root_config,
                job_name=f"{continuation_job_prefix}-diff-only",
                agent=agent,
                model=model,
                extra_args=extra_args,
            )
            plans.append(
                ContinuationPlan(
                    parent_job_dir=root_summary.job_dir,
                    parent_trial_name=parent_trial.trial_name,
                    snapshot_name=None,
                    job_name=(
                        config.job_name or f"{continuation_job_prefix}-diff-only"
                    ),
                    command=tuple(build_harbor_command(config)),
                    start_state_type="diff_only",
                    context_mode="original_task_only",
                    parent_artifacts=(str(artifact_path),),
                    executor_status="manifest_only",
                )
            )

        elif start_state_type == "full_snapshot":
            selected_snapshots = (
                list(snapshots[:max_snapshots])
                if max_snapshots
                else list(snapshots)
            )
            for index, snapshot_name in enumerate(selected_snapshots):
                config = build_snapshot_continuation_config(
                    root_config=root_config,
                    snapshot_name=snapshot_name,
                    job_name=f"{continuation_job_prefix}-full-snapshot-{index}",
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
                            or f"{continuation_job_prefix}-full-snapshot-{index}"
                        ),
                        command=tuple(build_harbor_command(config)),
                        start_state_type="full_snapshot",
                        context_mode="parent_summary",
                    )
                )

        else:
            raise ContinuationError(f"Unsupported start_state_type: {start_state_type}")

    return plans


def write_plan_manifest(plans: Sequence[ContinuationPlan], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "go-explore-start-state-plan-v1",
                "plans": [plan.to_json_dict() for plan in plans],
            },
            indent=2,
        )
        + "\n"
    )


def log_snapshot_selected(
    plan: ContinuationPlan,
    *,
    event_log_path: Path,
    experiment_id: str | None = None,
    selector_mode: str = "list_order",
    selection_index: int = 0,
    cell_key: str | None = None,
    priority: float | None = None,
    score: float | None = None,
    times_selected: int | None = None,
    selector_reasons: Sequence[str] = (),
) -> None:
    event = base_event(
        event_type="snapshot_selected",
        event_id=(
            f"{plan.parent_trial_name}:snapshot_selected:"
            f"{selection_index}:{plan.snapshot_name}"
        ),
        experiment_id=experiment_id,
        run_id=plan.parent_trial_name,
        job_dir=plan.parent_job_dir,
        trial_name=plan.parent_trial_name,
    )
    event.update(
        {
            "snapshot_name": plan.snapshot_name,
            "cell_key": cell_key,
            "priority": priority,
            "score": score,
            "times_selected": times_selected,
            "selector_mode": selector_mode,
            "selector_reasons": list(selector_reasons),
        }
    )
    append_event(event_log_path, event)


def log_continuation_started(
    plan: ContinuationPlan,
    *,
    event_log_path: Path,
    experiment_id: str | None = None,
    start_state_type: str | None = None,
    context_mode: str | None = None,
) -> None:
    child_job_dir = plan.parent_job_dir.parent / plan.job_name
    event = base_event(
        event_type="continuation_started",
        event_id=f"{plan.job_name}:continuation_started",
        experiment_id=experiment_id,
        run_id=plan.parent_trial_name,
        job_dir=plan.parent_job_dir,
        trial_name=plan.parent_trial_name,
    )
    event.update(
        {
            "child_run_id": plan.job_name,
            "child_job_dir": str(child_job_dir),
            "parent_run_id": plan.parent_trial_name,
            "parent_snapshot": plan.snapshot_name,
            "start_state_type": start_state_type or plan.start_state_type,
            "context_mode": context_mode or plan.context_mode,
            "parent_artifacts": list(plan.parent_artifacts),
            "executor_status": plan.executor_status,
        }
    )
    append_event(event_log_path, event)


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
        budget=trial.budget if trial else BudgetSummary(),
        start_state_type=plan.start_state_type,
        context_mode=plan.context_mode,
        parent_artifacts=plan.parent_artifacts,
    )


def run_continuation_plan(
    plan: ContinuationPlan,
    *,
    env: dict[str, str] | None = None,
    capture_output: bool = True,
    event_log_path: Path | None = None,
    experiment_id: str | None = None,
) -> ContinuationAttempt:
    if event_log_path is not None:
        log_continuation_started(
            plan,
            event_log_path=event_log_path,
            experiment_id=experiment_id,
        )

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
            budget=BudgetSummary(),
            start_state_type=plan.start_state_type,
            context_mode=plan.context_mode,
            parent_artifacts=plan.parent_artifacts,
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
    event_log_path: Path | None = None,
    experiment_id: str | None = None,
) -> ContinuationReport:
    events_path = event_log_path or report_path.parent / EVENT_LOG_FILENAME
    attempts = tuple(
        run_continuation_plan(
            plan,
            env=env,
            event_log_path=events_path,
            experiment_id=experiment_id,
        )
        for plan in plans
    )
    report = ContinuationReport(
        root_job_dir=str(root_summary.job_dir),
        root_trial_name=root_trial.trial_name,
        root_reward=root_trial.reward,
        attempts=attempts,
        root_budget=root_trial.budget,
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
