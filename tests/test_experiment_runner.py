from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path
from typing import Sequence

from go_explore.continuations import (
    ContinuationAttempt,
    ContinuationPlan,
    ContinuationReport,
    write_continuation_report,
)
from go_explore.experiment_runner import RunExperimentConfig, run_fixed_budget_experiment
from go_explore.harbor import HarborRunConfig
from go_explore.results import BudgetSummary, JobSummary, TrialSummary
from go_explore.snapshots.archive import SnapshotArchive
from go_explore.snapshots.models import SnapshotCandidate, SnapshotEvent


def _write_harbor_job(
    job_dir: Path,
    *,
    job_name: str,
    task_name: str = "fix-git",
    reward: float = 0.0,
) -> None:
    trial_name = f"{task_name}__{job_name}"
    trial_dir = job_dir / trial_name
    trial_dir.mkdir(parents=True)
    (job_dir / "config.json").write_text(
        json.dumps(
            {
                "jobs_dir": str(job_dir.parent),
                "environment": {"type": "daytona"},
                "agents": [
                    {
                        "name": None,
                        "import_path": "go_explore.agents.factory:SnapshotAwareTerminus2",
                        "model_name": "model-a",
                    }
                ],
                "datasets": [
                    {
                        "name": "terminal-bench",
                        "version": "2.0",
                        "task_names": [task_name],
                    }
                ],
                "tasks": [],
            }
        )
    )
    (job_dir / "result.json").write_text(
        json.dumps({"n_total_trials": 1, "stats": {"n_errors": 0}})
    )
    (trial_dir / "result.json").write_text(
        json.dumps(
            {
                "trial_name": trial_name,
                "task_name": task_name,
                "verifier_result": {"reward": reward},
                "agent_result": {
                    "n_input_tokens": 10,
                    "n_output_tokens": 2,
                    "n_cache_tokens": 1,
                    "cost_usd": 0.01,
                },
            }
        )
    )


def _fake_harbor_run(
    cmd: list[str],
    *,
    check: bool,
    text: bool,
) -> subprocess.CompletedProcess[str]:
    del check, text
    jobs_dir = Path(cmd[cmd.index("--jobs-dir") + 1])
    job_name = cmd[cmd.index("--job-name") + 1]
    task_name = cmd[cmd.index("--include-task-name") + 1]
    job_dir = jobs_dir / job_name
    _write_harbor_job(job_dir, job_name=job_name, task_name=task_name)

    if job_name.endswith("-root"):
        archive = SnapshotArchive(path=job_dir / "archive.json")
        archive.add(
            SnapshotCandidate(
                id=f"{task_name}__{job_name}:step-0",
                event=SnapshotEvent.TEST_RUN,
                restore_ref=f"go-explore-{task_name}__{job_name}-step-0",
                metadata={"trial_name": f"{task_name}__{job_name}", "step_id": "0"},
            )
        )
        archive.save()

    return subprocess.CompletedProcess(cmd, 0)


def _fake_continuation_runner(
    plans: Sequence[ContinuationPlan],
    *,
    root_summary: JobSummary,
    root_trial: TrialSummary,
    report_path: Path,
    event_log_path: Path,
    experiment_id: str,
) -> ContinuationReport:
    del event_log_path, experiment_id
    attempts = []
    for plan in plans:
        job_dir = root_summary.job_dir.parent / plan.job_name
        _write_harbor_job(job_dir, job_name=plan.job_name, reward=1.0)
        trial = f"fix-git__{plan.job_name}"
        attempts.append(
            ContinuationAttempt(
                parent_job_dir=str(root_summary.job_dir),
                parent_trial_name=root_trial.trial_name,
                snapshot_name=plan.snapshot_name,
                continuation_job_dir=str(job_dir),
                continuation_trial_name=trial,
                reward=1.0,
                exception_type=None,
                budget=BudgetSummary(
                    total_tokens=13,
                    cost_usd=0.01,
                    total_tokens_status="complete",
                    cost_usd_status="complete",
                ),
            )
        )
    report = ContinuationReport(
        root_job_dir=str(root_summary.job_dir),
        root_trial_name=root_trial.trial_name,
        root_reward=root_trial.reward,
        attempts=tuple(attempts),
        root_budget=root_trial.budget,
    )
    write_continuation_report(report, report_path)
    return report


def test_run_fixed_budget_experiment_executes_branch_and_builds_analysis(tmp_path):
    report = run_fixed_budget_experiment(
        RunExperimentConfig(
            experiment_id="exp-1",
            base_config=HarborRunConfig(
                jobs_dir=tmp_path / "jobs",
                agent_import_path="go_explore.agents.factory:SnapshotAwareTerminus2",
                agent=None,
                env="daytona",
                dataset="terminal-bench@2.0",
                model="model-a",
                task_name="fix-git",
            ),
            total_token_budget=100_000,
            methods=("single", "promising_branch"),
            seeds=(0,),
            job_prefix="exp",
            manifest_path=tmp_path / "manifest.json",
            analysis_dir=tmp_path / "analysis",
            n_branch_continuations=1,
            execute=True,
        ),
        command_runner=_fake_harbor_run,
        continuation_runner=_fake_continuation_runner,
    )

    assert report.has_infrastructure_failures is False
    assert (tmp_path / "manifest.json").exists()
    assert (tmp_path / "analysis" / "execution-report.json").exists()
    assert (tmp_path / "analysis" / "run-summary.csv").exists()

    rows = list(csv.DictReader((tmp_path / "analysis" / "run-summary.csv").open()))
    rows_by_run = {row["run_id"]: row for row in rows}
    assert rows_by_run["exp-single-seed-0"]["method"] == "single"
    assert rows_by_run["exp-promising-branch-seed-0-root"]["method"] == "promising_branch"
    child = rows_by_run["exp-promising-branch-seed-0-cont-0"]
    assert child["method"] == "promising_branch"
    assert child["role"] == "continuation"
    assert child["outcome"] == "success"
