from __future__ import annotations

import asyncio
import json
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from daytona import AsyncDaytona

from go_explore.events import EVENT_LOG_FILENAME, append_event, base_event
from go_explore.fixed_budget import BudgetAllocation
from go_explore.harbor import (
    HarborRunConfig,
    build_harbor_command,
    environment_with_repo_path,
    with_agent_kwarg,
)
from go_explore.results import BudgetSummary, JobSummary, TrialSummary, summarize_job
from go_explore.snapshots.command_log import build_command_log
from go_explore.snapshots.command_replay import (
    DEFAULT_MAX_COMMANDS as DEFAULT_REPLAY_MAX_COMMANDS,
)
from go_explore.snapshots.command_replay import (
    build_replay_manifest,
    write_replay_manifest,
)
from go_explore.snapshots.models import context_from_atif_step
from go_explore.snapshots.replay import (
    extract_signals_from_atif_step,
    load_atif_trajectory_steps,
)
from go_explore.snapshots.transcript import build_transcript_summary, parent_outcome

# Agent kwargs deliberately NOT carried from a root job into its branch
# children when reconstructing config via harbor_config_from_job:
# - token_budget, context_mode, parent_context, parent_context_path are
#   re-injected explicitly downstream (plan_snapshot_continuations /
#   build_snapshot_continuation_config) with child-specific values, so
#   forwarding the root's own values here would just be overwritten anyway.
# - diff_path/diff_apply_timeout_sec and replay_manifest_path/
#   replay_command_timeout_sec/replay_total_budget_sec are one-time root
#   setup actions against a *clean* start state. A child already restores
#   from a later snapshot that (if the root progressed at all) likely
#   already reflects that diff/replay, so re-running them against the
#   child would at best no-op and at worst fail (e.g. `git apply` on an
#   already-applied diff) or corrupt state.
# - snapshot_policy is a root-only concept (what counts as an archive-worthy
#   step during the root's own rollout); children don't build their own
#   archive in this experiment design.
# Every other agent kwarg (e.g. verify_before_complete, hooks_debug) is
# forwarded as-is, since it's meant to apply uniformly across a run.
_ROOT_ONLY_AGENT_KWARGS = frozenset(
    {
        "token_budget",
        "context_mode",
        "parent_context",
        "parent_context_path",
        "diff_path",
        "diff_apply_timeout_sec",
        "replay_manifest_path",
        "replay_command_timeout_sec",
        "replay_total_budget_sec",
        "snapshot_policy",
    }
)


class ContinuationError(ValueError):
    """Raised when a continuation run cannot be planned from job metadata."""


StartStateType = Literal["clean", "diff_only", "full_snapshot", "command_replay"]
ContextMode = Literal[
    "original_task_only",
    "parent_summary",
    "critical_parent_summary",
    "failure_symptom",
    "resume_notice",
    "preflight_verification",
    "full_transcript_summary",
    "command_log",
    "none",
]

FAILURE_SYMPTOM_MAX_CHARS = 800


def snapshot_prefix_for_trial(
    trial_name: str,
    *,
    name_prefix: str = "go-explore",
) -> str:
    return f"{name_prefix}-{trial_name}-step-"


def snapshot_belongs_to_trial(snapshot_name: str, trial_name: str) -> bool:
    """Return whether a Go-Explore snapshot name carries this trial identity."""

    prefix = "go-explore-"
    return not snapshot_name.startswith(prefix) or snapshot_name.startswith(
        f"{prefix}{trial_name}-step-"
    )


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
    budget: BudgetAllocation = field(
        default_factory=lambda: BudgetAllocation(None, 0.0)
    )

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
            "budget": self.budget.to_json_dict(),
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
    planned_budget: BudgetAllocation = field(
        default_factory=lambda: BudgetAllocation(None, 0.0)
    )
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
    for key, value in (agent_config.get("kwargs") or {}).items():
        if key in _ROOT_ONLY_AGENT_KWARGS:
            continue
        if isinstance(value, bool):
            formatted = "true" if value else "false"
        else:
            formatted = str(value)
        base_extra_args.extend(["--ak", f"{key}={formatted}"])
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
    context_mode: ContextMode = "parent_summary",
    parent_context_path: Path | None = None,
    agent: str | None = None,
    model: str | None = None,
    extra_args: Sequence[str] = (),
    token_budget: int | None = None,
) -> HarborRunConfig:
    """Build a Harbor job that starts Daytona from a saved snapshot."""

    combined_extra_args = _with_context_mode_extra_args(
        tuple(root_config.extra_args) + tuple(extra_args),
        context_mode=context_mode,
        parent_context_path=parent_context_path,
    )
    if token_budget is not None:
        combined_extra_args = with_agent_kwarg(
            combined_extra_args, "token_budget", str(token_budget)
        )

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
        # Never let Harbor silently replace a requested parent snapshot with a
        # declarative build. A missing snapshot must make the child fail so the
        # experiment cannot record a clean run as a restore run.
        environment_kwargs=(
            f"snapshot_template_name={snapshot_name}",
            "assume_global_snapshot=true",
        ),
        extra_args=combined_extra_args,
    )


def build_clean_start_config(
    *,
    root_config: HarborRunConfig,
    job_name: str,
    context_mode: ContextMode = "original_task_only",
    parent_context_path: Path | None = None,
    diff_path: Path | None = None,
    replay_manifest_path: Path | None = None,
    agent: str | None = None,
    model: str | None = None,
    extra_args: Sequence[str] = (),
    token_budget: int | None = None,
) -> HarborRunConfig:
    """Build a Harbor job that starts from the original clean task state."""

    combined_extra_args = _with_clean_context_extra_args(
        tuple(root_config.extra_args) + tuple(extra_args),
        context_mode=context_mode,
        parent_context_path=parent_context_path,
        diff_path=diff_path,
        replay_manifest_path=replay_manifest_path,
    )
    if token_budget is not None:
        combined_extra_args = with_agent_kwarg(
            combined_extra_args, "token_budget", str(token_budget)
        )

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


def _with_context_mode_extra_args(
    args: Sequence[str],
    *,
    context_mode: ContextMode,
    parent_context_path: Path | None = None,
) -> tuple[str, ...]:
    """Return Harbor extra args with exactly one snapshot-agent context mode.

    A restored snapshot already carries its own baked-in `/tmp/go_explore_context.md`
    written mid-trajectory, before the parent's final outcome was known. When
    `parent_context_path` is given (e.g. a post-hoc failure-symptom file), it
    takes precedence over that baked-in file - see
    `SnapshotAwareAgent._load_parent_context`.
    """

    cleaned: list[str] = []
    replaced_keys = {"context_mode", "parent_context_path"}
    index = 0
    while index < len(args):
        current = args[index]
        if current == "--ak" and index + 1 < len(args):
            key = str(args[index + 1]).split("=", 1)[0]
            if key in replaced_keys:
                index += 2
                continue
            cleaned.extend([current, args[index + 1]])
            index += 2
            continue
        if str(current).split("=", 1)[0] in replaced_keys:
            index += 1
            continue
        cleaned.append(current)
        index += 1

    cleaned.extend(["--ak", f"context_mode={context_mode}"])
    if parent_context_path is not None:
        cleaned.extend(["--ak", f"parent_context_path={parent_context_path}"])
    return tuple(cleaned)


def _with_clean_context_extra_args(
    args: Sequence[str],
    *,
    context_mode: ContextMode,
    parent_context_path: Path | None = None,
    diff_path: Path | None = None,
    replay_manifest_path: Path | None = None,
) -> tuple[str, ...]:
    """Return Harbor extra args for a clean child context mode.

    Clean children cannot inherit `/tmp/go_explore_context.md` from a restored
    snapshot, so parent-summary modes use an explicit host-side context path.
    `diff_path` (diff_only start states only) tells `SnapshotAwareAgent.setup`
    to apply that parent diff onto the clean checkout before the agent runs.
    `replay_manifest_path` (command_replay start states only) tells it to
    replay the manifest's allowlisted commands in that same fresh sandbox -
    independent of `context_mode`, since command_replay is a filesystem/
    environment operation, not a prompt-context one.
    """

    cleaned: list[str] = []
    replaced_keys = {
        "context_mode",
        "parent_context",
        "parent_context_path",
        "diff_path",
        "replay_manifest_path",
    }
    index = 0
    while index < len(args):
        current = args[index]
        if current == "--ak" and index + 1 < len(args):
            key = str(args[index + 1]).split("=", 1)[0]
            if key in replaced_keys:
                index += 2
                continue
            cleaned.extend([current, args[index + 1]])
            index += 2
            continue
        if str(current).split("=", 1)[0] in replaced_keys:
            index += 1
            continue
        cleaned.append(current)
        index += 1

    cleaned.extend(["--ak", f"context_mode={context_mode}"])
    if (
        parent_context_path is not None
        and context_mode
        in {
            "parent_summary",
            "critical_parent_summary",
            "full_transcript_summary",
            "command_log",
        }
    ):
        cleaned.extend(["--ak", f"parent_context_path={parent_context_path}"])
    if diff_path is not None:
        cleaned.extend(["--ak", f"diff_path={diff_path}"])
    if replay_manifest_path is not None:
        cleaned.extend(["--ak", f"replay_manifest_path={replay_manifest_path}"])
    return tuple(cleaned)


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
    context_mode: ContextMode = "parent_summary",
    child_budgets: Sequence[BudgetAllocation] | None = None,
) -> list[ContinuationPlan]:
    parent_trial = select_trial(root_summary, parent_trial_name)
    selected_snapshots = (
        list(snapshots[:max_snapshots])
        if max_snapshots
        else list(snapshots)
    )
    plans: list[ContinuationPlan] = []

    failure_symptom_path = (
        write_failure_symptom_context(root_summary, parent_trial)
        if context_mode == "failure_symptom"
        else None
    )

    for index, snapshot_name in enumerate(selected_snapshots):
        budget = (
            child_budgets[index]
            if child_budgets is not None and index < len(child_budgets)
            else BudgetAllocation(None, 0.0)
        )
        if not snapshot_belongs_to_trial(snapshot_name, parent_trial.trial_name):
            plans.append(
                ContinuationPlan(
                    parent_job_dir=root_summary.job_dir,
                    parent_trial_name=parent_trial.trial_name,
                    snapshot_name=snapshot_name,
                    job_name=f"{continuation_job_prefix}-snapshot-{index}",
                    command=(),
                    executor_status="snapshot_parent_mismatch",
                    budget=budget,
                )
            )
            continue
        config = build_snapshot_continuation_config(
            root_config=root_config,
            snapshot_name=snapshot_name,
            job_name=f"{continuation_job_prefix}-snapshot-{index}",
            context_mode=context_mode,
            parent_context_path=failure_symptom_path,
            agent=agent,
            model=model,
            extra_args=extra_args,
            token_budget=budget.token_budget,
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
                context_mode=context_mode,
                budget=budget,
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
    clean_context_mode: ContextMode = "original_task_only",
    full_snapshot_context_mode: ContextMode = "parent_summary",
    diff_only_context_mode: ContextMode = "original_task_only",
    replay_max_commands: int = DEFAULT_REPLAY_MAX_COMMANDS,
) -> list[ContinuationPlan]:
    """Plan Claim 1 child-start conditions without executing them.

    `diff_only` starts from the same clean Harbor command shape as `clean`,
    plus a `diff_path` agent kwarg that `SnapshotAwareAgent.setup` uses to
    `git apply` the parent diff before the agent's first turn. If the diff
    artifact doesn't exist on disk yet, the plan is recorded as
    `executor_status="pending_parent_diff"` so runners skip it until the
    artifact is produced, mirroring `full_snapshot`'s
    `pending_root_archive` status.

    `diff_only_context_mode` in `_DIFF_ONLY_MEMORY_ARMS` additionally writes a
    deterministic, rule-based text-memory artifact of the parent trajectory
    (see `go_explore.snapshots.transcript` / `go_explore.snapshots.command_log`)
    and attaches it as `parent_context_path`, giving the child code state
    (diff) plus text memory without restoring a full sandbox. Each mode is a
    distinct experiment arm from plain `diff_only` - plan it with its own
    `continuation_job_prefix` (or rely on the automatic job-name suffix) so
    they can all be planned from the same parent root without colliding.

    `command_replay` starts from a fresh (`clean`) sandbox and replays a
    conservative, allowlisted set of the parent's dependency-install commands
    (see `go_explore.snapshots.command_replay`) before the agent's first
    turn. This tests whether rebuilding setup state by rerunning commands is
    a credible substitute for a `full_snapshot` restore - always
    `context_mode="original_task_only"`, since this arm is about environment
    state, not text memory.
    """

    parent_trial = select_trial(root_summary, parent_trial_name)
    parent_context_path = _parent_context_path(root_summary, parent_trial.trial_name)
    plans: list[ContinuationPlan] = []

    for start_state_type in start_state_types:
        if start_state_type == "clean":
            config = build_clean_start_config(
                root_config=root_config,
                job_name=f"{continuation_job_prefix}-clean",
                context_mode=clean_context_mode,
                parent_context_path=parent_context_path,
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
                    context_mode=clean_context_mode,
                    parent_artifacts=(
                        (str(parent_context_path),)
                        if clean_context_mode
                        in {"parent_summary", "critical_parent_summary"}
                        else ()
                    ),
                )
            )

        elif start_state_type == "diff_only":
            artifact_path = diff_path or root_summary.job_dir / "parent.diff"
            memory_arm = _DIFF_ONLY_MEMORY_ARMS.get(diff_only_context_mode)
            job_name = (
                f"{continuation_job_prefix}-{memory_arm[0]}"
                if memory_arm is not None
                else f"{continuation_job_prefix}-diff-only"
            )
            memory_artifact_path = (
                memory_arm[1](root_summary, parent_trial)
                if memory_arm is not None
                else None
            )
            parent_artifacts = [str(artifact_path)]
            if memory_artifact_path is not None:
                parent_artifacts.append(str(memory_artifact_path))

            config = build_clean_start_config(
                root_config=root_config,
                job_name=job_name,
                context_mode=diff_only_context_mode,
                parent_context_path=memory_artifact_path,
                diff_path=artifact_path,
                agent=agent,
                model=model,
                extra_args=extra_args,
            )
            plans.append(
                ContinuationPlan(
                    parent_job_dir=root_summary.job_dir,
                    parent_trial_name=parent_trial.trial_name,
                    snapshot_name=None,
                    job_name=config.job_name or job_name,
                    command=tuple(build_harbor_command(config)),
                    start_state_type="diff_only",
                    context_mode=diff_only_context_mode,
                    parent_artifacts=tuple(parent_artifacts),
                    executor_status=(
                        "ready" if artifact_path.exists() else "pending_parent_diff"
                    ),
                )
            )

        elif start_state_type == "full_snapshot":
            selected_snapshots = (
                list(snapshots[:max_snapshots])
                if max_snapshots
                else list(snapshots)
            )
            for index, snapshot_name in enumerate(selected_snapshots):
                if not snapshot_belongs_to_trial(snapshot_name, parent_trial.trial_name):
                    plans.append(
                        ContinuationPlan(
                            parent_job_dir=root_summary.job_dir,
                            parent_trial_name=parent_trial.trial_name,
                            snapshot_name=snapshot_name,
                            job_name=f"{continuation_job_prefix}-full-snapshot-{index}",
                            command=(),
                            start_state_type="full_snapshot",
                            context_mode=full_snapshot_context_mode,
                            executor_status="snapshot_parent_mismatch",
                        )
                    )
                    continue
                config = build_snapshot_continuation_config(
                    root_config=root_config,
                    snapshot_name=snapshot_name,
                    job_name=f"{continuation_job_prefix}-full-snapshot-{index}",
                    context_mode=full_snapshot_context_mode,
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
                        context_mode=full_snapshot_context_mode,
                    )
                )

        elif start_state_type == "command_replay":
            manifest_path = write_replay_manifest_context(
                root_summary, parent_trial, max_commands=replay_max_commands
            )
            job_name = f"{continuation_job_prefix}-command-replay"
            config = build_clean_start_config(
                root_config=root_config,
                job_name=job_name,
                context_mode="original_task_only",
                replay_manifest_path=manifest_path,
                agent=agent,
                model=model,
                extra_args=extra_args,
            )
            plans.append(
                ContinuationPlan(
                    parent_job_dir=root_summary.job_dir,
                    parent_trial_name=parent_trial.trial_name,
                    snapshot_name=None,
                    job_name=config.job_name or job_name,
                    command=tuple(build_harbor_command(config)),
                    start_state_type="command_replay",
                    context_mode="original_task_only",
                    parent_artifacts=(str(manifest_path),),
                    executor_status="ready",
                )
            )

        else:
            raise ContinuationError(f"Unsupported start_state_type: {start_state_type}")

    return plans


def _parent_context_path(
    root_summary: JobSummary,
    parent_trial_name: str,
) -> Path:
    return root_summary.job_dir / parent_trial_name / "agent" / "trajectory.json"


def _last_test_observation(trajectory_path: Path, *, trial_name: str) -> str | None:
    """The raw observation text of the last test/verifier-classified step.

    Rule-based extraction only: no inference about the true cause of failure
    is attempted, since that would require either the fix (oracle leakage) or
    a guess that could mislead a child down a worse path than no signal at
    all. This surfaces what the parent actually observed, nothing more.
    """
    try:
        steps = load_atif_trajectory_steps(trajectory_path)
    except (OSError, ValueError):
        return None

    last_signal = None
    last_observation = None
    for step in steps:
        if step.get("source") != "agent":
            continue
        test_signals = [
            signal
            for signal in extract_signals_from_atif_step(step)
            if signal.event_type == "test_run"
        ]
        if not test_signals:
            continue
        last_signal = test_signals[-1]
        last_observation = context_from_atif_step(
            step, trial_name=trial_name
        ).observation_text

    if last_signal is None or not last_observation:
        return None

    counts = (
        f"{last_signal.tests_passed or 0} passed, "
        f"{last_signal.tests_failed or 0} failed"
    )
    return f"{counts}\n{last_observation.strip()[:FAILURE_SYMPTOM_MAX_CHARS]}"


def _failure_symptom_text(
    root_trial: TrialSummary,
    trajectory_path: Path,
) -> str:
    if root_trial.succeeded:
        status_line = "The prior attempt from this sandbox state solved the task."
    else:
        status_line = (
            f"The prior attempt from this sandbox state did not solve the task "
            f"(reward: {root_trial.reward})."
        )

    observation = _last_test_observation(trajectory_path, trial_name=root_trial.trial_name)
    if observation is None:
        return status_line

    return f"{status_line}\n\nLast observed test/verifier output:\n{observation}"


def write_failure_symptom_context(
    root_summary: JobSummary,
    root_trial: TrialSummary,
) -> Path:
    """Write the parent's observed (not inferred) failure symptom to a host file.

    Distinct from `_parent_context_path`'s full trajectory.json: this captures
    only the final test/verifier evidence, deliberately excluding the command
    sequence that produced it, so a child cannot anchor on the parent's
    specific approach.
    """
    trajectory_path = _parent_context_path(root_summary, root_trial.trial_name)
    text = _failure_symptom_text(root_trial, trajectory_path)

    output_path = (
        root_summary.job_dir / root_trial.trial_name / "agent" / "failure-symptom.md"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text)
    return output_path


def write_transcript_summary_context(
    root_summary: JobSummary,
    root_trial: TrialSummary,
) -> Path:
    """Write a deterministic, rule-based transcript summary of the parent's
    run to a host file, for `diff_only` children using
    `context_mode="full_transcript_summary"`. No model call - see
    `go_explore.snapshots.transcript.build_transcript_summary`.
    """
    trajectory_path = _parent_context_path(root_summary, root_trial.trial_name)
    text = build_transcript_summary(
        trajectory_path,
        trial_name=root_trial.trial_name,
        task_name=root_trial.task_name,
        outcome=parent_outcome(root_trial.reward, root_trial.exception_type),
        reward=root_trial.reward,
    )

    output_path = (
        root_summary.job_dir / root_trial.trial_name / "agent" / "transcript-summary.md"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text)
    return output_path


def write_command_log_context(
    root_summary: JobSummary,
    root_trial: TrialSummary,
) -> Path:
    """Write a deterministic, ordered command+output log of the parent's run
    to a host file, for `diff_only` children using
    `context_mode="command_log"`. No model call - see
    `go_explore.snapshots.command_log.build_command_log`.
    """
    trajectory_path = _parent_context_path(root_summary, root_trial.trial_name)
    text = build_command_log(
        trajectory_path,
        trial_name=root_trial.trial_name,
        task_name=root_trial.task_name,
        outcome=parent_outcome(root_trial.reward, root_trial.exception_type),
        reward=root_trial.reward,
    )

    output_path = (
        root_summary.job_dir / root_trial.trial_name / "agent" / "command-log.md"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text)
    return output_path


def write_replay_manifest_context(
    root_summary: JobSummary,
    root_trial: TrialSummary,
    *,
    max_commands: int = DEFAULT_REPLAY_MAX_COMMANDS,
) -> Path:
    """Write a conservative, allowlisted replay plan (dependency installs
    only) derived from the parent's run to a host file, for
    `start_state_type="command_replay"` children. This is the plan-time
    artifact - every entry starts `planned` or `skipped` (with a reason);
    `SnapshotAwareAgent.setup` fills in `replayed`/`failed` once it actually
    execs the planned commands in the child's fresh sandbox. No model call.
    See `go_explore.snapshots.command_replay.build_replay_manifest`.
    """
    trajectory_path = _parent_context_path(root_summary, root_trial.trial_name)
    manifest = build_replay_manifest(
        trajectory_path,
        parent_job_dir=root_summary.job_dir,
        parent_trial_name=root_trial.trial_name,
        max_commands=max_commands,
    )

    output_path = (
        root_summary.job_dir / root_trial.trial_name / "agent" / "replay-manifest.json"
    )
    write_replay_manifest(manifest, output_path)
    return output_path


# Maps a `diff_only_context_mode` to the (job-name suffix, artifact writer)
# for its text-memory arm. Modes not listed here (e.g. "original_task_only")
# get plain `diff_only` behavior - no artifact, no parent_context_path.
_DIFF_ONLY_MEMORY_ARMS: dict[
    ContextMode, tuple[str, Callable[[JobSummary, TrialSummary], Path]]
] = {
    "full_transcript_summary": ("diff-only-transcript", write_transcript_summary_context),
    "command_log": ("diff-only-command-log", write_command_log_context),
}


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
        planned_budget=plan.budget,
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
        env=environment_with_repo_path(env),
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
            planned_budget=plan.budget,
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
