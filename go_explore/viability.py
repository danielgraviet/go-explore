from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from go_explore.fixed_budget import (
    DEFAULT_BRANCH_CONTEXT_MODE,
    ExperimentMethod,
    FixedBudgetManifest,
    FixedBudgetPlanConfig,
    plan_fixed_budget_runs,
    write_fixed_budget_manifest,
)
from go_explore.harbor import HarborRunConfig


MAIN_PROMISING_CONTEXTS = ("none", "critical_parent_summary")
PARENT_SUMMARY_DIAGNOSTIC_CONTEXT = "parent_summary"


@dataclass(frozen=True)
class ViabilityPlanConfig:
    experiment_id: str
    base_config: HarborRunConfig
    task_names: tuple[str, ...]
    output_dir: Path = Path("docs/experiments/viability")
    total_token_budget: int | None = None
    seeds: tuple[int, ...] = (0,)
    n_retries: int = 5
    n_branch_continuations: int = 2
    branch_root_fraction: float = 0.3
    include_random_control: bool = False
    include_parent_summary_diagnostic: bool = False


@dataclass(frozen=True)
class ViabilityManifestRecord:
    task_id: str
    arm: str
    context_mode: str
    manifest_path: Path
    manifest: FixedBudgetManifest

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "arm": self.arm,
            "context_mode": self.context_mode,
            "manifest_path": str(self.manifest_path),
            "experiment_id": self.manifest.experiment_id,
            "methods": list(self.manifest.methods),
            "n_jobs": len(self.manifest.jobs),
        }


@dataclass(frozen=True)
class ViabilityPlan:
    experiment_id: str
    output_dir: Path
    records: tuple[ViabilityManifestRecord, ...]
    index_path: Path

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "go-explore-viability-plan-v1",
            "experiment_id": self.experiment_id,
            "output_dir": str(self.output_dir),
            "records": [record.to_json_dict() for record in self.records],
            "notes": {
                "default_branch_context_mode": DEFAULT_BRANCH_CONTEXT_MODE,
                "main_promising_contexts": list(MAIN_PROMISING_CONTEXTS),
                "parent_summary": (
                    "diagnostic only; omitted unless explicitly requested"
                ),
            },
        }


def plan_viability_manifests(config: ViabilityPlanConfig) -> ViabilityPlan:
    _validate_config(config)
    output_dir = config.output_dir / config.experiment_id
    records: list[ViabilityManifestRecord] = []

    for task_name in config.task_names:
        records.extend(_plan_task_manifests(config, output_dir, task_name))

    index_path = output_dir / "viability-plan.json"
    return ViabilityPlan(
        experiment_id=config.experiment_id,
        output_dir=output_dir,
        records=tuple(records),
        index_path=index_path,
    )


def write_viability_plan(plan: ViabilityPlan) -> None:
    for record in plan.records:
        write_fixed_budget_manifest(record.manifest, record.manifest_path)
    plan.index_path.parent.mkdir(parents=True, exist_ok=True)
    plan.index_path.write_text(json.dumps(plan.to_json_dict(), indent=2) + "\n")


def _plan_task_manifests(
    config: ViabilityPlanConfig,
    output_dir: Path,
    task_name: str,
) -> tuple[ViabilityManifestRecord, ...]:
    task_slug = _slug(task_name)
    arms: list[tuple[str, tuple[ExperimentMethod, ...], str]] = [
        ("retry", ("retry",), "original_task_only"),
        ("promising-branch-none", ("promising_branch",), "none"),
        (
            "promising-branch-critical-parent-summary",
            ("promising_branch",),
            "critical_parent_summary",
        ),
    ]
    if config.include_random_control:
        arms.append(("random-branch-none", ("random_branch",), "none"))
    if config.include_parent_summary_diagnostic:
        arms.append(
            (
                "promising-branch-parent-summary-diagnostic",
                ("promising_branch",),
                PARENT_SUMMARY_DIAGNOSTIC_CONTEXT,
            )
        )

    records: list[ViabilityManifestRecord] = []
    for arm, methods, context_mode in arms:
        experiment_id = f"{config.experiment_id}-{task_slug}-{arm}"
        job_prefix = experiment_id
        manifest = plan_fixed_budget_runs(
            FixedBudgetPlanConfig(
                experiment_id=experiment_id,
                base_config=_with_task_name(config.base_config, task_name),
                job_prefix=job_prefix,
                total_token_budget=config.total_token_budget,
                methods=methods,
                seeds=config.seeds,
                n_retries=config.n_retries,
                n_branch_continuations=config.n_branch_continuations,
                branch_root_fraction=config.branch_root_fraction,
                branch_context_mode=(
                    "none" if context_mode == "original_task_only" else context_mode
                ),
            )
        )
        records.append(
            ViabilityManifestRecord(
                task_id=task_name,
                arm=arm,
                context_mode=context_mode,
                manifest_path=output_dir / "manifests" / f"{task_slug}-{arm}.json",
                manifest=manifest,
            )
        )
    return tuple(records)


def _validate_config(config: ViabilityPlanConfig) -> None:
    if not config.task_names:
        raise ValueError("At least one task name is required.")
    if config.base_config.task_name is not None:
        raise ValueError("Set task_names on ViabilityPlanConfig, not base_config.")


def _with_task_name(config: HarborRunConfig, task_name: str) -> HarborRunConfig:
    return HarborRunConfig(
        jobs_dir=config.jobs_dir,
        agent=config.agent,
        agent_import_path=config.agent_import_path,
        env=config.env,
        dataset=config.dataset,
        path=config.path,
        model=config.model,
        task_name=task_name,
        n_tasks=1,
        n_attempts=1,
        n_concurrent=1,
        job_name=config.job_name,
        export_traces=config.export_traces,
        environment_kwargs=config.environment_kwargs,
        extra_args=config.extra_args,
    )


def _slug(value: str) -> str:
    return value.replace("_", "-").replace("/", "-")
