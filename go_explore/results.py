from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TrialSummary:
    trial_name: str
    task_name: str | None
    source: str | None
    reward: float | None
    exception_type: str | None
    exception_message: str | None

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


def summarize_job(job_dir: Path) -> JobSummary:
    result = _read_json(job_dir / "result.json")
    trials: list[TrialSummary] = []

    for trial_result_path in sorted(job_dir.glob("*/result.json")):
        trial = _read_json(trial_result_path)
        exception = trial.get("exception_info") or {}
        verifier = trial.get("verifier_result") or {}
        rewards = verifier.get("rewards") or {}
        reward = verifier.get("reward", rewards.get("reward"))

        trials.append(
            TrialSummary(
                trial_name=trial.get("trial_name") or trial_result_path.parent.name,
                task_name=trial.get("task_name"),
                source=trial.get("source"),
                reward=reward,
                exception_type=exception.get("exception_type"),
                exception_message=exception.get("exception_message"),
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
