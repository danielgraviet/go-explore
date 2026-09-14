"""Diagnostic-only comparison of a root checkpoint, restore, and clean retry."""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from go_explore.continuations import (
    ContextMode,
    build_clean_start_config,
    build_snapshot_continuation_config,
    harbor_config_from_job,
    select_trial,
    snapshot_belongs_to_trial,
)
from go_explore.harbor import build_harbor_command, environment_with_repo_path
from go_explore.results import BudgetSummary, TrialSummary, summarize_job
from go_explore.snapshots.archive import SnapshotArchive


DiagnosticOutcome = Literal[
    "root_only_progress",
    "snapshot_transfer_value",
    "state_value_without_transfer_gap",
    "restart_preferred",
    "inconclusive",
]


@dataclass(frozen=True)
class CheckpointDiagnosticConfig:
    root_job_dir: Path
    snapshot_name: str
    remaining_token_budget: int
    child_job_name: str
    clean_job_name: str
    context_mode: ContextMode = "preflight_verification"
    output_path: Path | None = None
    execute: bool = False

    def validate(self) -> None:
        if not self.snapshot_name:
            raise ValueError("snapshot_name must not be empty.")
        if self.remaining_token_budget < 1:
            raise ValueError("remaining_token_budget must be positive.")
        if not self.child_job_name or not self.clean_job_name:
            raise ValueError("child_job_name and clean_job_name must not be empty.")
        if self.child_job_name == self.clean_job_name:
            raise ValueError("child_job_name and clean_job_name must differ.")


@dataclass(frozen=True)
class DiagnosticArm:
    name: str
    start_state_type: str
    job_name: str | None
    reward: float | None
    exception_type: str | None
    total_tokens: int | None
    duration_seconds: float | None
    status: str
    comparable_remaining_cap: bool
    planned_token_cap: int | None = None
    restore_overhead_seconds: float | None = None
    details: str | None = None


@dataclass(frozen=True)
class CheckpointDiagnosticReport:
    schema_version: str
    diagnostic_only: bool
    root_job_dir: str
    root_trial_name: str
    task_name: str | None
    model: str | None
    snapshot_name: str
    checkpoint_cell_key: str
    checkpoint_score: float
    checkpoint_tokens: int | None
    checkpoint_elapsed_seconds: float | None
    checkpoint_verification: dict | None
    remaining_token_budget: int
    root: DiagnosticArm
    restored_child: DiagnosticArm
    clean_retry: DiagnosticArm
    outcome: DiagnosticOutcome
    root_continuation_note: str

    def to_json_dict(self) -> dict:
        return asdict(self)


def run_checkpoint_diagnostic(
    config: CheckpointDiagnosticConfig,
    *,
    command_runner=subprocess.run,
) -> CheckpointDiagnosticReport:
    config.validate()

    archive = SnapshotArchive.load(config.root_job_dir / "archive.json")
    entry = next(
        (item for item in archive.entries() if item.snapshot_name == config.snapshot_name),
        None,
    )
    if entry is None:
        raise ValueError(f"Snapshot {config.snapshot_name!r} is not in the root archive.")

    root_summary = summarize_job(config.root_job_dir)
    root_trial = select_trial(root_summary)
    if not snapshot_belongs_to_trial(config.snapshot_name, root_trial.trial_name):
        raise ValueError(
            f"Snapshot {config.snapshot_name!r} does not belong to root trial "
            f"{root_trial.trial_name!r}."
        )
    root_config = harbor_config_from_job(config.root_job_dir)
    child_config = build_snapshot_continuation_config(
        root_config=root_config,
        snapshot_name=config.snapshot_name,
        job_name=config.child_job_name,
        context_mode=config.context_mode,
        token_budget=config.remaining_token_budget,
    )
    clean_config = build_clean_start_config(
        root_config=root_config,
        job_name=config.clean_job_name,
        context_mode="original_task_only",
        token_budget=config.remaining_token_budget,
    )

    if config.execute:
        _run(child_config, command_runner)
        _run(clean_config, command_runner)

    root = _root_arm(
        root_trial,
        entry.checkpoint_tokens,
        entry.checkpoint_elapsed_seconds,
    )
    child = _job_arm(
        root_config.jobs_dir / config.child_job_name,
        "restored_child",
        "full_snapshot",
        config.execute,
        config.remaining_token_budget,
    )
    clean = _job_arm(
        root_config.jobs_dir / config.clean_job_name,
        "clean_retry",
        "clean",
        config.execute,
        config.remaining_token_budget,
    )
    report = CheckpointDiagnosticReport(
        schema_version="go-explore-checkpoint-diagnostic-v1",
        diagnostic_only=True,
        root_job_dir=str(config.root_job_dir),
        root_trial_name=root_trial.trial_name,
        task_name=root_config.task_name,
        model=root_config.model,
        snapshot_name=config.snapshot_name,
        checkpoint_cell_key=entry.cell_key,
        checkpoint_score=entry.score,
        checkpoint_tokens=entry.checkpoint_tokens,
        checkpoint_elapsed_seconds=entry.checkpoint_elapsed_seconds,
        checkpoint_verification=(
            asdict(entry.grounded_verification)
            if entry.grounded_verification is not None
            else None
        ),
        remaining_token_budget=config.remaining_token_budget,
        root=root,
        restored_child=child,
        clean_retry=clean,
        outcome=_classify(root, child, clean),
        root_continuation_note=(
            "The root continued with its in-memory context, but this v1 report "
            "observes its final result rather than enforcing the same remaining cap."
        ),
    )
    output_path = config.output_path or config.root_job_dir / "checkpoint-diagnostic.json"
    output_path.write_text(json.dumps(report.to_json_dict(), indent=2) + "\n")
    return report


def _run(config, command_runner) -> None:
    command_runner(
        build_harbor_command(config),
        check=False,
        text=True,
        env=environment_with_repo_path(),
    )


def _root_arm(
    trial: TrialSummary,
    checkpoint_tokens: int | None,
    checkpoint_elapsed_seconds: float | None,
) -> DiagnosticArm:
    budget = trial.budget
    invalid_token_boundary = (
        budget.total_tokens is not None
        and checkpoint_tokens is not None
        and checkpoint_tokens > budget.total_tokens
    )
    invalid_time_boundary = (
        budget.duration_seconds is not None
        and checkpoint_elapsed_seconds is not None
        and checkpoint_elapsed_seconds > budget.duration_seconds
    )
    incremental_tokens = (
        budget.total_tokens - checkpoint_tokens
        if not invalid_token_boundary
        and budget.total_tokens is not None
        and checkpoint_tokens is not None
        else None
    )
    incremental_seconds = (
        budget.duration_seconds - checkpoint_elapsed_seconds
        if not invalid_time_boundary
        and budget.duration_seconds is not None
        and checkpoint_elapsed_seconds is not None
        else None
    )
    status = "observed" if incremental_tokens is not None else "unavailable"
    details = "post-checkpoint totals are observed deltas, not an enforced cap"
    if invalid_token_boundary or invalid_time_boundary:
        details = "checkpoint counters exceed final root counters"
    return DiagnosticArm(
        name="root_continuation",
        start_state_type="live_root",
        job_name=None,
        reward=trial.reward,
        exception_type=trial.exception_type,
        total_tokens=incremental_tokens,
        duration_seconds=incremental_seconds,
        status=status,
        comparable_remaining_cap=False,
        planned_token_cap=None,
        details=details,
    )


def _job_arm(
    job_dir: Path,
    name: str,
    start_state_type: str,
    executed: bool,
    remaining_token_budget: int,
) -> DiagnosticArm:
    if not executed:
        return DiagnosticArm(
            name=name,
            start_state_type=start_state_type,
            job_name=job_dir.name,
            reward=None,
            exception_type=None,
            total_tokens=None,
            duration_seconds=None,
            status="planned",
            comparable_remaining_cap=True,
            planned_token_cap=remaining_token_budget,
        )
    summary = summarize_job(job_dir)
    trial = select_trial(summary)
    arm = _arm_from_trial(name, start_state_type, job_dir.name, trial, comparable=True)
    return DiagnosticArm(**(asdict(arm) | {"planned_token_cap": remaining_token_budget}))


def _arm_from_trial(
    name: str,
    start_state_type: str,
    job_name: str,
    trial: TrialSummary,
    *,
    comparable: bool,
) -> DiagnosticArm:
    budget: BudgetSummary = trial.budget
    return DiagnosticArm(
        name=name,
        start_state_type=start_state_type,
        job_name=job_name,
        reward=trial.reward,
        exception_type=trial.exception_type,
        total_tokens=budget.total_tokens,
        duration_seconds=budget.duration_seconds,
        status="complete",
        comparable_remaining_cap=comparable,
        planned_token_cap=None,
        restore_overhead_seconds=budget.restore_overhead_seconds,
    )


def _classify(
    root: DiagnosticArm,
    child: DiagnosticArm,
    clean: DiagnosticArm,
) -> DiagnosticOutcome:
    if any(arm.status in {"planned", "unavailable"} for arm in (root, child, clean)):
        return "inconclusive"
    if any(arm.exception_type for arm in (root, child, clean)):
        return "inconclusive"

    root_succeeded = root.reward == 1.0
    child_succeeded = child.reward == 1.0
    clean_succeeded = clean.reward == 1.0
    if root_succeeded and child_succeeded and not clean_succeeded:
        return "state_value_without_transfer_gap"
    if root_succeeded and not child_succeeded and not clean_succeeded:
        return "root_only_progress"
    if child_succeeded and not clean_succeeded:
        return "snapshot_transfer_value"
    if clean_succeeded and not root_succeeded and not child_succeeded:
        return "restart_preferred"
    return "inconclusive"
