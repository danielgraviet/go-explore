from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Sequence

from go_explore.harbor import HarborRunConfig, build_harbor_command


ExperimentMethod = Literal["single", "retry", "random_branch", "promising_branch"]
PlannedJobRole = Literal["single", "retry_attempt", "root", "continuation"]


@dataclass(frozen=True)
class BudgetAllocation:
    """Planning-level budget assignment for one job."""

    token_budget: int | None
    budget_fraction: float
    enforcement: str = "planning_only"

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "token_budget": self.token_budget,
            "budget_fraction": self.budget_fraction,
            "enforcement": self.enforcement,
        }


@dataclass(frozen=True)
class PlannedExperimentJob:
    method: ExperimentMethod
    role: PlannedJobRole
    seed: int
    job_name: str
    command: tuple[str, ...]
    budget: BudgetAllocation
    start_state_type: str
    context_mode: str
    selector_mode: str | None = None
    parent_run_id: str | None = None
    parent_snapshot: str | None = None
    executor_status: str = "ready"

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "role": self.role,
            "seed": self.seed,
            "job_name": self.job_name,
            "command": list(self.command),
            "budget": self.budget.to_json_dict(),
            "start_state_type": self.start_state_type,
            "context_mode": self.context_mode,
            "selector_mode": self.selector_mode,
            "parent_run_id": self.parent_run_id,
            "parent_snapshot": self.parent_snapshot,
            "executor_status": self.executor_status,
        }


@dataclass(frozen=True)
class FixedBudgetPlanConfig:
    experiment_id: str
    base_config: HarborRunConfig
    job_prefix: str
    total_token_budget: int | None
    methods: tuple[ExperimentMethod, ...] = (
        "single",
        "retry",
        "random_branch",
        "promising_branch",
    )
    seeds: tuple[int, ...] = (0,)
    n_retries: int = 5
    n_branch_continuations: int = 2
    branch_root_fraction: float = 0.3
    snapshots: tuple[str, ...] = ()
    branch_context_mode: str = "parent_summary"


@dataclass(frozen=True)
class FixedBudgetManifest:
    experiment_id: str
    task_id: str | None
    model: str | None
    total_token_budget: int | None
    methods: tuple[ExperimentMethod, ...]
    seeds: tuple[int, ...]
    jobs: tuple[PlannedExperimentJob, ...]

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "go-explore-fixed-budget-plan-v1",
            "experiment_id": self.experiment_id,
            "task_id": self.task_id,
            "model": self.model,
            "budget": {
                "total_token_budget": self.total_token_budget,
                "enforcement": "planning_only",
            },
            "methods": list(self.methods),
            "seeds": list(self.seeds),
            "jobs": [job.to_json_dict() for job in self.jobs],
        }


def plan_fixed_budget_runs(config: FixedBudgetPlanConfig) -> FixedBudgetManifest:
    _validate_config(config)
    jobs: list[PlannedExperimentJob] = []

    for seed in config.seeds:
        for method in config.methods:
            if method == "single":
                jobs.extend(_plan_single(config, seed=seed))
            elif method == "retry":
                jobs.extend(_plan_retry(config, seed=seed))
            elif method == "random_branch":
                jobs.extend(_plan_branch(config, method=method, seed=seed))
            elif method == "promising_branch":
                jobs.extend(_plan_branch(config, method=method, seed=seed))
            else:
                raise ValueError(f"Unsupported method: {method}")

    return FixedBudgetManifest(
        experiment_id=config.experiment_id,
        task_id=config.base_config.task_name,
        model=config.base_config.model,
        total_token_budget=config.total_token_budget,
        methods=config.methods,
        seeds=config.seeds,
        jobs=tuple(jobs),
    )


def write_fixed_budget_manifest(
    manifest: FixedBudgetManifest,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest.to_json_dict(), indent=2) + "\n")


def _validate_config(config: FixedBudgetPlanConfig) -> None:
    if config.total_token_budget is not None and config.total_token_budget < 1:
        raise ValueError("total_token_budget must be positive when set.")
    if not config.seeds:
        raise ValueError("At least one seed is required.")
    if config.n_retries < 1:
        raise ValueError("n_retries must be >= 1.")
    if config.n_branch_continuations < 1:
        raise ValueError("n_branch_continuations must be >= 1.")
    if not 0 < config.branch_root_fraction < 1:
        raise ValueError("branch_root_fraction must be between 0 and 1.")
    if config.branch_context_mode not in {"parent_summary", "none"}:
        raise ValueError("branch_context_mode must be 'parent_summary' or 'none'.")


def _plan_single(
    config: FixedBudgetPlanConfig,
    *,
    seed: int,
) -> tuple[PlannedExperimentJob, ...]:
    job_name = f"{config.job_prefix}-single-seed-{seed}"
    run_config = _with_job_name(config.base_config, job_name)
    return (
        PlannedExperimentJob(
            method="single",
            role="single",
            seed=seed,
            job_name=job_name,
            command=tuple(build_harbor_command(run_config)),
            budget=BudgetAllocation(
                token_budget=config.total_token_budget,
                budget_fraction=1.0,
            ),
            start_state_type="clean",
            context_mode="original_task_only",
        ),
    )


def _plan_retry(
    config: FixedBudgetPlanConfig,
    *,
    seed: int,
) -> tuple[PlannedExperimentJob, ...]:
    token_budgets = _split_tokens(config.total_token_budget, config.n_retries)
    budget_fraction = 1.0 / config.n_retries
    jobs: list[PlannedExperimentJob] = []
    for index, token_budget in enumerate(token_budgets):
        job_name = f"{config.job_prefix}-retry-seed-{seed}-attempt-{index}"
        run_config = _with_job_name(config.base_config, job_name)
        jobs.append(
            PlannedExperimentJob(
                method="retry",
                role="retry_attempt",
                seed=seed,
                job_name=job_name,
                command=tuple(build_harbor_command(run_config)),
                budget=BudgetAllocation(
                    token_budget=token_budget,
                    budget_fraction=budget_fraction,
                ),
                start_state_type="clean",
                context_mode="original_task_only",
            )
        )
    return tuple(jobs)


def _plan_branch(
    config: FixedBudgetPlanConfig,
    *,
    method: Literal["random_branch", "promising_branch"],
    seed: int,
) -> tuple[PlannedExperimentJob, ...]:
    root_budget = _multiply_tokens(
        config.total_token_budget,
        config.branch_root_fraction,
    )
    child_total_budget = (
        None
        if config.total_token_budget is None or root_budget is None
        else config.total_token_budget - root_budget
    )
    child_budgets = _split_tokens(
        child_total_budget,
        config.n_branch_continuations,
    )
    selector_mode = "random" if method == "random_branch" else "archive_priority"
    selected_snapshots = _select_branch_snapshots(
        snapshots=config.snapshots,
        method=method,
        seed=seed,
        limit=config.n_branch_continuations,
    )
    method_slug = method.replace("_", "-")
    root_job_name = f"{config.job_prefix}-{method_slug}-seed-{seed}-root"
    jobs: list[PlannedExperimentJob] = [
        PlannedExperimentJob(
            method=method,
            role="root",
            seed=seed,
            job_name=root_job_name,
            command=tuple(
                build_harbor_command(
                    _with_job_name(config.base_config, root_job_name)
                )
            ),
            budget=BudgetAllocation(
                token_budget=root_budget,
                budget_fraction=config.branch_root_fraction,
            ),
            start_state_type="clean",
            context_mode="original_task_only",
            selector_mode=selector_mode,
        )
    ]

    child_fraction = (
        1.0 - config.branch_root_fraction
    ) / config.n_branch_continuations
    for index, token_budget in enumerate(child_budgets):
        snapshot_name = (
            selected_snapshots[index] if index < len(selected_snapshots) else None
        )
        job_name = f"{config.job_prefix}-{method_slug}-seed-{seed}-cont-{index}"
        if snapshot_name is None:
            command: tuple[str, ...] = ()
            executor_status = "pending_root_archive"
        else:
            child_config = _snapshot_child_config(
                config.base_config,
                job_name=job_name,
                snapshot_name=snapshot_name,
                context_mode=config.branch_context_mode,
            )
            command = tuple(build_harbor_command(child_config))
            executor_status = "ready"

        jobs.append(
            PlannedExperimentJob(
                method=method,
                role="continuation",
                seed=seed,
                job_name=job_name,
                command=command,
                budget=BudgetAllocation(
                    token_budget=token_budget,
                    budget_fraction=child_fraction,
                ),
                start_state_type="full_snapshot",
                context_mode=config.branch_context_mode,
                selector_mode=selector_mode,
                parent_run_id=root_job_name,
                parent_snapshot=snapshot_name,
                executor_status=executor_status,
            )
        )

    return tuple(jobs)


def _split_tokens(total_tokens: int | None, n: int) -> tuple[int | None, ...]:
    if total_tokens is None:
        return tuple(None for _ in range(n))
    base = total_tokens // n
    remainder = total_tokens % n
    return tuple(base + (1 if index < remainder else 0) for index in range(n))


def _multiply_tokens(total_tokens: int | None, fraction: float) -> int | None:
    if total_tokens is None:
        return None
    return int(total_tokens * fraction)


def _select_branch_snapshots(
    *,
    snapshots: Sequence[str],
    method: Literal["random_branch", "promising_branch"],
    seed: int,
    limit: int,
) -> tuple[str, ...]:
    selected = list(snapshots)
    if method == "random_branch":
        rng = random.Random(seed)
        rng.shuffle(selected)
    return tuple(selected[:limit])


def _with_job_name(config: HarborRunConfig, job_name: str) -> HarborRunConfig:
    return HarborRunConfig(
        jobs_dir=config.jobs_dir,
        agent=config.agent,
        agent_import_path=config.agent_import_path,
        env=config.env,
        dataset=config.dataset,
        path=config.path,
        model=config.model,
        task_name=config.task_name,
        n_tasks=1,
        n_attempts=1,
        n_concurrent=1,
        job_name=job_name,
        export_traces=config.export_traces,
        environment_kwargs=config.environment_kwargs,
        extra_args=config.extra_args,
    )


def _snapshot_child_config(
    config: HarborRunConfig,
    *,
    job_name: str,
    snapshot_name: str,
    context_mode: str,
) -> HarborRunConfig:
    return HarborRunConfig(
        jobs_dir=config.jobs_dir,
        agent=config.agent,
        agent_import_path=config.agent_import_path,
        env="daytona",
        dataset=config.dataset,
        path=config.path,
        model=config.model,
        task_name=config.task_name,
        n_tasks=1,
        n_attempts=1,
        n_concurrent=1,
        job_name=job_name,
        export_traces=config.export_traces,
        environment_kwargs=(f"snapshot_template_name={snapshot_name}",),
        extra_args=_with_context_mode_extra_args(config.extra_args, context_mode),
    )


def _with_context_mode_extra_args(
    args: Sequence[str],
    context_mode: str,
) -> tuple[str, ...]:
    cleaned: list[str] = []
    index = 0
    while index < len(args):
        current = args[index]
        if current == "--ak" and index + 1 < len(args):
            if str(args[index + 1]).startswith("context_mode="):
                index += 2
                continue
            cleaned.extend([current, args[index + 1]])
            index += 2
            continue
        if str(current).startswith("context_mode="):
            index += 1
            continue
        cleaned.append(current)
        index += 1
    cleaned.extend(["--ak", f"context_mode={context_mode}"])
    return tuple(cleaned)
