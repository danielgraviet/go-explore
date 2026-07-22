from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from go_explore.events import EVENT_LOG_FILENAME


@dataclass(frozen=True)
class BudgetSummary:
    n_input_tokens: int | None = None
    n_output_tokens: int | None = None
    n_cache_tokens: int | None = None
    total_tokens: int | None = None
    cost_usd: float | None = None
    duration_seconds: float | None = None
    agent_execution_seconds: float | None = None
    environment_setup_seconds: float | None = None
    snapshot_overhead_seconds: float | None = None
    restore_overhead_seconds: float | None = None
    total_tokens_status: str = "unknown"
    cost_usd_status: str = "unknown"
    duration_seconds_status: str = "unknown"
    snapshot_overhead_seconds_status: str = "unknown"
    restore_overhead_seconds_status: str = "unknown"


@dataclass(frozen=True)
class TrialSummary:
    trial_name: str
    task_name: str | None
    source: str | None
    reward: float | None
    exception_type: str | None
    exception_message: str | None
    budget: BudgetSummary = field(default_factory=BudgetSummary)

    @property
    def succeeded(self) -> bool:
        return self.reward == 1.0 and self.exception_type is None


@dataclass(frozen=True)
class JobSummary:
    job_dir: Path
    n_total_trials: int
    n_errors: int
    mean: float | None
    trials: tuple[TrialSummary, ...]


def _read_json(path: Path) -> dict[str, Any]:
    with path.open() as file:
        return json.load(file)


def _read_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return _read_json(path)


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _duration_seconds(started_at: str | None, finished_at: str | None) -> float | None:
    started = _parse_timestamp(started_at)
    finished = _parse_timestamp(finished_at)
    if started is None or finished is None:
        return None
    return (finished - started).total_seconds()


def _section_duration_seconds(section: dict[str, Any] | None) -> float | None:
    if not isinstance(section, dict):
        return None
    return _duration_seconds(section.get("started_at"), section.get("finished_at"))


def budget_from_trial_result(trial: dict[str, Any]) -> BudgetSummary:
    agent_result = trial.get("agent_result") or {}
    n_input_tokens = agent_result.get("n_input_tokens")
    n_output_tokens = agent_result.get("n_output_tokens")
    n_cache_tokens = agent_result.get("n_cache_tokens")
    cost_usd = agent_result.get("cost_usd")
    parsed_cost_usd = cost_usd if isinstance(cost_usd, int | float) else None

    total_tokens = None
    total_tokens_status = "unknown"
    if isinstance(n_input_tokens, int) and isinstance(n_output_tokens, int):
        total_tokens = n_input_tokens + n_output_tokens
        if isinstance(n_cache_tokens, int):
            total_tokens += n_cache_tokens
            total_tokens_status = "complete"
        else:
            total_tokens_status = "partial"

    cost_usd_status = "complete" if parsed_cost_usd is not None else "unknown"

    duration_seconds = _duration_seconds(
        trial.get("started_at"),
        trial.get("finished_at"),
    )
    duration_seconds_status = "complete" if duration_seconds is not None else "unknown"

    return BudgetSummary(
        n_input_tokens=n_input_tokens if isinstance(n_input_tokens, int) else None,
        n_output_tokens=n_output_tokens if isinstance(n_output_tokens, int) else None,
        n_cache_tokens=n_cache_tokens if isinstance(n_cache_tokens, int) else None,
        total_tokens=total_tokens,
        cost_usd=parsed_cost_usd,
        duration_seconds=duration_seconds,
        agent_execution_seconds=_section_duration_seconds(trial.get("agent_execution")),
        environment_setup_seconds=_section_duration_seconds(
            trial.get("environment_setup")
        ),
        total_tokens_status=total_tokens_status,
        cost_usd_status=cost_usd_status,
        duration_seconds_status=duration_seconds_status,
    )


def _restore_overhead_from_job_config(
    job_dir: Path,
    budget: BudgetSummary,
) -> tuple[float | None, str]:
    config = _read_optional_json(job_dir / "config.json")
    environment = config.get("environment") or {}
    if not isinstance(environment, dict):
        return None, "unknown"

    kwargs = environment.get("kwargs") or {}
    if not isinstance(kwargs, dict):
        return None, "unknown"
    if not kwargs.get("snapshot_template_name"):
        return None, "unknown"

    if budget.environment_setup_seconds is None:
        return None, "unknown"
    return budget.environment_setup_seconds, "complete"


def _snapshot_overhead_from_events(
    job_dir: Path,
    *,
    trial_name: str,
) -> tuple[float | None, str]:
    event_log_path = job_dir / EVENT_LOG_FILENAME
    if not event_log_path.exists():
        return None, "unknown"

    seen_snapshot_event = False
    missing_overhead = 0
    overhead_values: list[float] = []

    for line in event_log_path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("event_type") != "snapshot_created":
            continue
        if event.get("trial_name") != trial_name and event.get("run_id") != trial_name:
            continue

        seen_snapshot_event = True
        overhead = _optional_float(event.get("overhead_seconds"))
        if overhead is None:
            overhead = _optional_float(event.get("snapshot_backend_seconds"))
        if overhead is None:
            missing_overhead += 1
        else:
            overhead_values.append(overhead)

    if not seen_snapshot_event:
        return 0.0, "complete"
    if missing_overhead and overhead_values:
        return sum(overhead_values), "partial"
    if missing_overhead:
        return None, "unknown"
    return sum(overhead_values), "complete"


def _optional_float(value: Any) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def summarize_job(job_dir: Path) -> JobSummary:
    result = _read_json(job_dir / "result.json")
    trials: list[TrialSummary] = []

    for trial_result_path in sorted(job_dir.glob("*/result.json")):
        trial = _read_json(trial_result_path)
        trial_name = trial.get("trial_name") or trial_result_path.parent.name
        exception = trial.get("exception_info") or {}
        verifier = trial.get("verifier_result") or {}
        rewards = verifier.get("rewards") or {}
        reward = verifier.get("reward", rewards.get("reward"))
        budget = budget_from_trial_result(trial)
        restore_overhead_seconds, restore_overhead_status = (
            _restore_overhead_from_job_config(job_dir, budget)
        )
        snapshot_overhead_seconds, snapshot_overhead_status = (
            _snapshot_overhead_from_events(job_dir, trial_name=str(trial_name))
        )
        budget = replace(
            budget,
            snapshot_overhead_seconds=snapshot_overhead_seconds,
            snapshot_overhead_seconds_status=snapshot_overhead_status,
            restore_overhead_seconds=restore_overhead_seconds,
            restore_overhead_seconds_status=restore_overhead_status,
        )

        trials.append(
            TrialSummary(
                trial_name=str(trial_name),
                task_name=trial.get("task_name"),
                source=trial.get("source"),
                reward=reward,
                exception_type=exception.get("exception_type"),
                exception_message=exception.get("exception_message"),
                budget=budget,
            )
        )

    stats = result.get("stats", {})
    mean = None
    for eval_stats in stats.get("evals", {}).values():
        metrics = eval_stats.get("metrics") or []
        if metrics and "mean" in metrics[0]:
            mean = metrics[0]["mean"]
            break

    return JobSummary(
        job_dir=job_dir,
        n_total_trials=result.get("n_total_trials", len(trials)),
        n_errors=stats.get("n_errors", 0),
        mean=mean,
        trials=tuple(trials),
    )


def format_job_summary(summary: JobSummary) -> str:
    lines = [
        f"job_dir: {summary.job_dir}",
        f"trials: {len(summary.trials)}/{summary.n_total_trials}",
        f"errors: {summary.n_errors}",
        f"mean: {summary.mean}",
    ]

    for trial in summary.trials:
        status = "pass" if trial.succeeded else "error" if trial.exception_type else "fail"
        lines.append(
            f"- {trial.trial_name}: {status}"
            f" task={trial.task_name}"
            f" reward={trial.reward}"
            f" exception={trial.exception_type}"
        )

    return "\n".join(lines)
