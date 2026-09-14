"""Claim 1 ablation: same checkpoint, same remaining cap, five start states."""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from go_explore.checkpoint_diagnostic import DiagnosticArm, _job_arm
from go_explore.continuations import (
    ContinuationPlan,
    harbor_config_from_job,
    plan_start_state_baselines,
    select_trial,
    snapshot_belongs_to_trial,
)
from go_explore.harbor import environment_with_repo_path, with_agent_kwarg
from go_explore.results import summarize_job
from go_explore.snapshots.archive import SnapshotArchive

CLAIM1_ARMS: tuple[tuple[str, str, str], ...] = (
    ("clean", "clean", "original_task_only"),
    ("diff_only", "diff_only", "original_task_only"),
    ("diff_transcript", "diff_only", "full_transcript_summary"),
    ("command_replay", "command_replay", "original_task_only"),
    ("full_snapshot", "full_snapshot", "none"),
)


@dataclass(frozen=True)
class RepresentationAblationConfig:
    root_job_dir: Path
    snapshot_name: str
    remaining_token_budget: int
    job_prefix: str
    diff_path: Path | None = None
    output_path: Path | None = None
    execute: bool = False
    include_arms: tuple[str, ...] | None = None

    def validate(self) -> None:
        if not self.snapshot_name:
            raise ValueError("snapshot_name must not be empty.")
        if self.remaining_token_budget < 1:
            raise ValueError("remaining_token_budget must be positive.")
        if not self.job_prefix:
            raise ValueError("job_prefix must not be empty.")
        if self.include_arms:
            known = {name for name, _, _ in CLAIM1_ARMS}
            unknown = set(self.include_arms) - known
            if unknown:
                raise ValueError(f"Unknown ablation arms: {sorted(unknown)}")


@dataclass(frozen=True)
class RepresentationAblationReport:
    schema_version: str
    diagnostic_only: bool
    root_job_dir: str
    task_name: str | None
    model: str | None
    snapshot_name: str
    remaining_token_budget: int
    arms: tuple[DiagnosticArm, ...]
    plans: tuple[dict, ...]

    def to_json_dict(self) -> dict:
        return asdict(self)


def run_representation_ablation(
    config: RepresentationAblationConfig,
    *,
    command_runner=subprocess.run,
) -> RepresentationAblationReport:
    config.validate()

    archive = SnapshotArchive.load(config.root_job_dir / "archive.json")
    entry = next(
        (
            item
            for item in archive.entries()
            if item.snapshot_name == config.snapshot_name
        ),
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
    extra_args = with_agent_kwarg((), "token_budget", str(config.remaining_token_budget))
    extra_args = with_agent_kwarg(extra_args, "snapshot_policy", "none")
    jobs_dir = root_config.jobs_dir
    planned: list[ContinuationPlan] = []

    for arm_name, start_state_type, context_mode in CLAIM1_ARMS:
        if config.include_arms is not None and arm_name not in config.include_arms:
            continue
        kwargs: dict = {
            "root_config": root_config,
            "root_summary": root_summary,
            "continuation_job_prefix": f"{config.job_prefix}-{arm_name}",
            "start_state_types": (start_state_type,),
            "extra_args": extra_args,
            "parent_trial_name": root_trial.trial_name,
        }
        if start_state_type == "clean":
            kwargs["clean_context_mode"] = context_mode
        elif start_state_type == "diff_only":
            kwargs["diff_only_context_mode"] = context_mode
            kwargs["diff_path"] = config.diff_path or config.root_job_dir / "parent.diff"
        elif start_state_type == "full_snapshot":
            kwargs["snapshots"] = (config.snapshot_name,)
            kwargs["full_snapshot_context_mode"] = context_mode
            kwargs["max_snapshots"] = 1
        planned.extend(plan_start_state_baselines(**kwargs))

    if config.execute:
        for plan in planned:
            if plan.executor_status != "ready" or not plan.command:
                continue
            command_runner(
                list(plan.command),
                check=False,
                text=True,
                env=environment_with_repo_path(),
            )

    arms = []
    for plan in planned:
        executed = config.execute and plan.executor_status == "ready"
        arms.append(
            _job_arm(
                jobs_dir / plan.job_name,
                plan.job_name,
                plan.start_state_type,
                executed,
                config.remaining_token_budget,
            )
        )

    report = RepresentationAblationReport(
        schema_version="go-explore-claim1-ablation-v1",
        diagnostic_only=True,
        root_job_dir=str(config.root_job_dir),
        task_name=root_config.task_name,
        model=root_config.model,
        snapshot_name=config.snapshot_name,
        remaining_token_budget=config.remaining_token_budget,
        arms=tuple(arms),
        plans=tuple(plan.to_json_dict() for plan in planned),
    )
    output_path = (
        config.output_path or config.root_job_dir / "representation-ablation.json"
    )
    output_path.write_text(json.dumps(report.to_json_dict(), indent=2) + "\n")
    return report
