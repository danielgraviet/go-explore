from __future__ import annotations

import argparse
import csv
from pathlib import Path

from go_explore.cli import build_figure_tables_cmd
from go_explore.figure_tables import FigureTableInputs, build_figure_tables


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({field for row in rows for field in row})
    with path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as file:
        return list(csv.DictReader(file))


def test_build_figure_tables_derives_core_result_tables(tmp_path):
    task_summary = tmp_path / "task-summary.csv"
    run_summary = tmp_path / "run-summary.csv"
    execution_status = tmp_path / "execution-status.csv"

    _write_csv(
        task_summary,
        [
            {
                "task_id": "task-a",
                "method": "random_branch",
                "solved": "false",
                "total_cost_usd": "0.40",
            },
            {
                "task_id": "task-a",
                "method": "promising_branch",
                "solved": "true",
                "total_cost_usd": "0.50",
            },
            {
                "task_id": "task-b",
                "method": "random_branch",
                "solved": "true",
                "total_cost_usd": "0.20",
            },
            {
                "task_id": "task-b",
                "method": "promising_branch",
                "solved": "true",
                "total_cost_usd": "0.30",
            },
            {
                "task_id": "task-b",
                "method": "oracle_branch",
                "solved": "true",
                "total_cost_usd": "",
            },
        ],
    )
    _write_csv(
        run_summary,
        [
            {
                "method": "promising_branch",
                "role": "continuation",
                "outcome": "success",
                "snapshot_cell_key": "<test_run>",
                "repeated_setup_score": "1",
                "snapshot_overhead_seconds": "2.5",
                "restore_overhead_seconds": "1.5",
            },
            {
                "method": "random_branch",
                "role": "continuation",
                "outcome": "fail",
                "snapshot_cell_key": "<command>",
                "repeated_setup_score": "3",
                "snapshot_overhead_seconds": "",
                "restore_overhead_seconds": "",
            },
        ],
    )
    _write_csv(
        execution_status,
        [
            {
                "group": "smoke",
                "method": "single",
                "artifact_status": "not_started",
            },
            {
                "group": "smoke",
                "method": "promising_branch",
                "artifact_status": "blocked_pending_root_archive",
            },
        ],
    )

    report = build_figure_tables(
        FigureTableInputs(
            task_summary_paths=(task_summary,),
            run_summary_paths=(run_summary,),
            execution_status_path=execution_status,
        )
    )

    solve_rate = {
        row["method"]: row for row in report.tables["solve_rate_by_method"]
    }
    assert solve_rate["promising_branch"]["n_solved"] == 2
    assert solve_rate["promising_branch"]["solve_rate"] == 1.0
    assert solve_rate["random_branch"]["n_solved"] == 1

    cost = {
        row["method"]: row for row in report.tables["cost_per_solved_task"]
    }
    assert cost["promising_branch"]["cost_per_solved_task"] == 0.4

    overlap = {
        row["task_id"]: row for row in report.tables["unique_task_overlap"]
    }
    assert overlap["task-a"]["unique_success_method"] == "promising_branch"

    branch_lift = {
        row["task_id"]: row
        for row in report.tables["promising_vs_random_branch_lift"]
    }
    assert branch_lift["task-a"]["promising_minus_random"] == 1
    assert branch_lift["task-b"]["promising_minus_random"] == 0

    by_cell = {
        (row["method"], row["snapshot_cell_key"]): row
        for row in report.tables["branch_success_by_snapshot_event_type"]
    }
    assert by_cell[("promising_branch", "<test_run>")]["success_rate"] == 1.0
    assert by_cell[("random_branch", "<command>")]["success_rate"] == 0.0

    repeated = {
        row["method"]: row for row in report.tables["repeated_setup_work"]
    }
    assert repeated["random_branch"]["mean_repeated_setup_score"] == 3.0

    overhead = {row["method"]: row for row in report.tables["snapshot_overhead"]}
    assert overhead["promising_branch"]["total_snapshot_overhead_seconds"] == 2.5
    assert overhead["promising_branch"]["total_restore_overhead_seconds"] == 1.5

    planned = {
        (row["group"], row["method"]): row
        for row in report.tables["planned_job_status"]
    }
    assert planned[("smoke", "single")]["not_started"] == 1
    assert planned[("smoke", "promising_branch")][
        "blocked_pending_root_archive"
    ] == 1

    statuses = {row["figure"]: row["status"] for row in report.statuses}
    assert statuses["solve_rate_by_method"] == "ready"
    assert statuses["oracle_gap"] == "ready"


def test_build_figure_tables_cli_writes_outputs_and_deferred_status(tmp_path, capsys):
    execution_status = tmp_path / "execution-status.csv"
    _write_csv(
        execution_status,
        [
            {
                "group": "primary",
                "method": "retry",
                "artifact_status": "not_started",
            }
        ],
    )
    output_dir = tmp_path / "figures"

    exit_code = build_figure_tables_cmd(
        argparse.Namespace(
            task_summary=[],
            run_summary=[],
            execution_status=execution_status,
            output_dir=output_dir,
        )
    )

    assert exit_code == 0
    stdout = capsys.readouterr().out
    assert f"figure_dir: {output_dir}" in stdout
    assert (output_dir / "figure-status.csv").exists()
    assert (output_dir / "planned_job_status.csv").exists()
    assert (output_dir / "README.md").exists()

    statuses = {
        row["figure"]: row["status"]
        for row in _read_csv(output_dir / "figure-status.csv")
    }
    assert statuses["solve_rate_by_method"] == "deferred_no_task_summary"
    assert statuses["snapshot_overhead"] == "deferred_no_run_summary"

    planned = _read_csv(output_dir / "planned_job_status.csv")
    assert planned[0]["group"] == "primary"
    assert planned[0]["not_started"] == "1"
