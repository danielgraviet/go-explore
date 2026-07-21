from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from go_explore.analysis_tables import AnalysisInputs, build_analysis_tables
from go_explore.cli import build_analysis_tables_cmd


def _write_job(
    job_dir: Path,
    *,
    trial_name: str,
    task_name: str = "fix-git",
    reward: float | None = 0.0,
    tokens: bool = True,
) -> None:
    trial_dir = job_dir / trial_name
    trial_dir.mkdir(parents=True)
    (job_dir / "result.json").write_text(
        json.dumps({"n_total_trials": 1, "stats": {"n_errors": 0}})
    )
    trial: dict[str, object] = {
        "trial_name": trial_name,
        "task_name": task_name,
        "verifier_result": {"reward": reward},
        "started_at": "2026-07-06T16:01:38Z",
        "finished_at": "2026-07-06T16:01:48Z",
    }
    if tokens:
        trial["agent_result"] = {
            "n_input_tokens": 10,
            "n_output_tokens": 3,
            "n_cache_tokens": 2,
            "cost_usd": 0.25,
        }
    (trial_dir / "result.json").write_text(json.dumps(trial))


def _write_manifest(path: Path, jobs_dir: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "go-explore-fixed-budget-plan-v1",
                "experiment_id": "exp-1",
                "task_id": "fix-git",
                "model": "model-a",
                "budget": {
                    "total_token_budget": 100_000,
                    "enforcement": "planning_only",
                },
                "methods": ["promising_branch", "retry"],
                "seeds": [0],
                "jobs": [
                    {
                        "method": "promising_branch",
                        "role": "root",
                        "seed": 0,
                        "job_name": "root-job",
                        "command": [],
                        "budget": {
                            "token_budget": 30_000,
                            "budget_fraction": 0.3,
                            "enforcement": "planning_only",
                        },
                        "start_state_type": "clean",
                        "context_mode": "original_task_only",
                        "selector_mode": "archive_priority",
                        "parent_run_id": None,
                        "parent_snapshot": None,
                        "executor_status": "ready",
                    },
                    {
                        "method": "promising_branch",
                        "role": "continuation",
                        "seed": 0,
                        "job_name": "child-job",
                        "command": [],
                        "budget": {
                            "token_budget": 70_000,
                            "budget_fraction": 0.7,
                            "enforcement": "planning_only",
                        },
                        "start_state_type": "full_snapshot",
                        "context_mode": "parent_summary",
                        "selector_mode": "archive_priority",
                        "parent_run_id": "root-job",
                        "parent_snapshot": "snap-a",
                        "executor_status": "ready",
                    },
                    {
                        "method": "retry",
                        "role": "retry_attempt",
                        "seed": 0,
                        "job_name": "missing-retry",
                        "command": [],
                        "budget": {
                            "token_budget": 50_000,
                            "budget_fraction": 0.5,
                            "enforcement": "planning_only",
                        },
                        "start_state_type": "clean",
                        "context_mode": "original_task_only",
                        "selector_mode": None,
                        "parent_run_id": None,
                        "parent_snapshot": None,
                        "executor_status": "ready",
                    },
                ],
            }
        )
        + "\n"
    )
    assert jobs_dir.name == "jobs"


def test_build_analysis_tables_joins_manifest_lineage_events_and_repeated_work(tmp_path):
    jobs_dir = tmp_path / "jobs"
    root_job = jobs_dir / "root-job"
    child_job = jobs_dir / "child-job"
    _write_job(root_job, trial_name="root-trial", reward=0.0)
    _write_job(child_job, trial_name="child-trial", reward=1.0)

    manifest_path = tmp_path / "fixed-budget.json"
    _write_manifest(manifest_path, jobs_dir)

    continuation_report_path = root_job / "continuation-report.json"
    continuation_report_path.write_text(
        json.dumps(
            {
                "root_job_dir": str(root_job),
                "root_trial_name": "root-trial",
                "root_reward": 0.0,
                "any_success": True,
                "attempts": [
                    {
                        "parent_job_dir": str(root_job),
                        "parent_trial_name": "root-trial",
                        "snapshot_name": "snap-a",
                        "continuation_job_dir": str(child_job),
                        "continuation_trial_name": "child-trial",
                        "reward": 1.0,
                        "exception_type": None,
                        "start_state_type": "full_snapshot",
                        "context_mode": "parent_summary",
                    }
                ],
            }
        )
        + "\n"
    )

    event_log = root_job / "events.jsonl"
    event_log.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "event_type": "snapshot_created",
                        "experiment_id": "exp-1",
                        "run_id": "root-trial",
                        "job_dir": str(root_job),
                        "trial_name": "root-trial",
                        "snapshot_name": "snap-a",
                        "cell_key": "<test_run>",
                        "score": 3.0,
                        "selector_reasons": ["has validation signal"],
                    }
                ),
                json.dumps(
                    {
                        "event_type": "snapshot_selected",
                        "experiment_id": "exp-1",
                        "run_id": "root-trial",
                        "job_dir": str(root_job),
                        "trial_name": "root-trial",
                        "snapshot_name": "snap-a",
                        "cell_key": "<test_run>",
                        "selector_mode": "archive_priority",
                        "score": 3.0,
                        "selector_reasons": ["priority=3"],
                    }
                ),
                json.dumps(
                    {
                        "event_type": "continuation_started",
                        "experiment_id": "exp-1",
                        "run_id": "root-trial",
                        "job_dir": str(root_job),
                        "trial_name": "root-trial",
                        "child_run_id": "child-job",
                        "child_job_dir": str(child_job),
                        "parent_run_id": "root-job",
                        "parent_snapshot": "snap-a",
                    }
                ),
            ]
        )
        + "\n"
    )

    repeated_work_path = tmp_path / "repeated-work.json"
    repeated_work_path.write_text(
        json.dumps(
            {
                "schema_version": "go-explore-repeated-work-v1",
                "runs": [
                    {"run_id": "root-job", "repeated_setup_score": 1},
                    {"run_id": "child-job", "repeated_setup_score": 2},
                ],
            }
        )
        + "\n"
    )

    tables = build_analysis_tables(
        AnalysisInputs(
            manifest_path=manifest_path,
            job_dirs=(root_job, child_job),
            continuation_report_paths=(continuation_report_path,),
            repeated_work_report_paths=(repeated_work_path,),
            jobs_dir=jobs_dir,
        )
    )

    rows_by_run = {row["run_id"]: row for row in tables.run_rows}
    assert set(rows_by_run) == {"root-job", "child-job", "missing-retry"}

    root = rows_by_run["root-job"]
    assert root["method"] == "promising_branch"
    assert root["outcome"] == "fail"
    assert root["planned_token_budget"] == 30_000
    assert root["n_snapshots_created"] == 1
    assert root["n_snapshots_forked"] == 1
    assert root["repeated_setup_score"] == 1

    child = rows_by_run["child-job"]
    assert child["outcome"] == "success"
    assert child["parent_run_id"] == "root-job"
    assert child["parent_job_dir"] == str(root_job)
    assert child["parent_snapshot"] == "snap-a"
    assert child["snapshot_cell_key"] == "<test_run>"
    assert child["selector_mode"] == "archive_priority"
    assert child["selector_score"] == 3.0
    assert child["selector_reasons"] == "priority=3"
    assert child["repeated_setup_score"] == 2

    missing = rows_by_run["missing-retry"]
    assert missing["method"] == "retry"
    assert missing["outcome"] == "missing_result"
    assert missing["total_tokens_status"] == "unknown"

    task_rows = {
        (row["method"], row["task_id"]): row for row in tables.task_rows
    }
    branch = task_rows[("promising_branch", "fix-git")]
    assert branch["solved"] is True
    assert branch["n_runs"] == 2
    assert branch["n_snapshots_created"] == 1
    assert branch["n_snapshots_forked"] == 1
    assert branch["total_tokens"] == 30
    assert branch["total_cost_usd"] == 0.5
    assert branch["model_class"] == "model-a"

    assert any(
        warning.field == "job_dir" and "missing-retry" in warning.artifact
        for warning in tables.warnings
    )


def test_build_analysis_tables_cli_writes_csv_and_warnings(tmp_path, capsys):
    jobs_dir = tmp_path / "jobs"
    root_job = jobs_dir / "root-job"
    _write_job(root_job, trial_name="root-trial", reward=1.0, tokens=False)
    manifest_path = tmp_path / "fixed-budget.json"
    _write_manifest(manifest_path, jobs_dir)
    output_dir = tmp_path / "analysis"

    exit_code = build_analysis_tables_cmd(
        argparse.Namespace(
            manifest=manifest_path,
            job_dir=[root_job],
            continuation_report=[],
            event_log=[],
            repeated_work_report=[],
            jobs_dir=jobs_dir,
            output_dir=output_dir,
            only_observed_runs=True,
        )
    )

    assert exit_code == 0
    stdout = capsys.readouterr().out
    assert f"run_summary: {output_dir / 'run-summary.csv'}" in stdout
    assert (output_dir / "run-summary.csv").exists()
    assert (output_dir / "task-summary.csv").exists()
    assert (output_dir / "warnings.json").exists()

    run_rows = list(csv.DictReader((output_dir / "run-summary.csv").open()))
    assert run_rows[0]["run_id"] == "root-job"
    assert run_rows[0]["total_tokens_status"] == "unknown"

    warnings = json.loads((output_dir / "warnings.json").read_text())["warnings"]
    assert any(warning["field"] == "total_tokens" for warning in warnings)
