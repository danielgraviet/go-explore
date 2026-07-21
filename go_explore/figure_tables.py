from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


FIGURE_NAMES = (
    "solve_rate_by_method",
    "cost_per_solved_task",
    "unique_task_overlap",
    "branch_success_by_snapshot_event_type",
    "promising_vs_random_branch_lift",
    "repeated_setup_work",
    "snapshot_overhead",
    "oracle_gap",
)


@dataclass(frozen=True)
class FigureTableInputs:
    task_summary_paths: tuple[Path, ...] = ()
    run_summary_paths: tuple[Path, ...] = ()
    execution_status_path: Path | None = None


@dataclass(frozen=True)
class FigureTableReport:
    tables: dict[str, tuple[dict[str, Any], ...]]
    statuses: tuple[dict[str, Any], ...]


def build_figure_tables(inputs: FigureTableInputs) -> FigureTableReport:
    task_rows = _read_csvs(inputs.task_summary_paths)
    run_rows = _read_csvs(inputs.run_summary_paths)
    execution_rows = (
        _read_csv(inputs.execution_status_path)
        if inputs.execution_status_path is not None
        else ()
    )

    tables = {
        "solve_rate_by_method": _solve_rate_by_method(task_rows),
        "cost_per_solved_task": _cost_per_solved_task(task_rows),
        "unique_task_overlap": _unique_task_overlap(task_rows),
        "branch_success_by_snapshot_event_type": (
            _branch_success_by_snapshot_event_type(run_rows)
        ),
        "promising_vs_random_branch_lift": _branch_lift(task_rows),
        "repeated_setup_work": _repeated_setup_work(run_rows),
        "snapshot_overhead": _snapshot_overhead(run_rows),
        "oracle_gap": _oracle_gap(task_rows),
        "planned_job_status": _planned_job_status(execution_rows),
    }

    statuses = tuple(
        _status_for_figure(name, tables[name], task_rows, run_rows)
        for name in FIGURE_NAMES
    )
    return FigureTableReport(tables=tables, statuses=statuses)


def write_figure_tables(report: FigureTableReport, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, rows in sorted(report.tables.items()):
        _write_csv(output_dir / f"{name}.csv", rows)
    _write_csv(output_dir / "figure-status.csv", report.statuses)
    _write_readme(output_dir / "README.md", report)


def _solve_rate_by_method(
    task_rows: Sequence[Mapping[str, str]],
) -> tuple[dict[str, Any], ...]:
    by_method: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for row in task_rows:
        by_method[row.get("method") or "unknown"].append(row)

    rows: list[dict[str, Any]] = []
    for method in sorted(by_method):
        items = by_method[method]
        solved = sum(1 for row in items if _bool(row.get("solved")))
        rows.append(
            {
                "method": method,
                "n_tasks": len({row.get("task_id") for row in items}),
                "n_solved": solved,
                "solve_rate": _ratio(solved, len(items)),
            }
        )
    return tuple(rows)


def _cost_per_solved_task(
    task_rows: Sequence[Mapping[str, str]],
) -> tuple[dict[str, Any], ...]:
    by_method: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for row in task_rows:
        by_method[row.get("method") or "unknown"].append(row)

    rows: list[dict[str, Any]] = []
    for method in sorted(by_method):
        items = by_method[method]
        solved = sum(1 for row in items if _bool(row.get("solved")))
        total_cost = sum(
            value
            for value in (_float(row.get("total_cost_usd")) for row in items)
            if value is not None
        )
        rows.append(
            {
                "method": method,
                "n_solved": solved,
                "total_cost_usd": total_cost if total_cost else None,
                "cost_per_solved_task": (
                    total_cost / solved if solved and total_cost else None
                ),
            }
        )
    return tuple(rows)


def _unique_task_overlap(
    task_rows: Sequence[Mapping[str, str]],
) -> tuple[dict[str, Any], ...]:
    solved_by_task: dict[str, set[str]] = defaultdict(set)
    for row in task_rows:
        if _bool(row.get("solved")):
            solved_by_task[row.get("task_id") or "unknown"].add(
                row.get("method") or "unknown"
            )

    rows: list[dict[str, Any]] = []
    for task_id in sorted(solved_by_task):
        methods = sorted(solved_by_task[task_id])
        rows.append(
            {
                "task_id": task_id,
                "n_solving_methods": len(methods),
                "solving_methods": "|".join(methods),
                "unique_success_method": methods[0] if len(methods) == 1 else None,
            }
        )
    return tuple(rows)


def _branch_success_by_snapshot_event_type(
    run_rows: Sequence[Mapping[str, str]],
) -> tuple[dict[str, Any], ...]:
    by_key: dict[tuple[str, str], list[Mapping[str, str]]] = defaultdict(list)
    for row in run_rows:
        if row.get("role") != "continuation":
            continue
        method = row.get("method") or "unknown"
        if method not in {"random_branch", "promising_branch", "oracle_branch"}:
            continue
        cell_key = row.get("snapshot_cell_key") or "unknown"
        by_key[(method, cell_key)].append(row)

    rows: list[dict[str, Any]] = []
    for method, cell_key in sorted(by_key):
        items = by_key[(method, cell_key)]
        successes = sum(1 for row in items if row.get("outcome") == "success")
        rows.append(
            {
                "method": method,
                "snapshot_cell_key": cell_key,
                "n_branch_runs": len(items),
                "n_successes": successes,
                "success_rate": _ratio(successes, len(items)),
            }
        )
    return tuple(rows)


def _branch_lift(
    task_rows: Sequence[Mapping[str, str]],
) -> tuple[dict[str, Any], ...]:
    by_task: dict[str, dict[str, bool]] = defaultdict(dict)
    for row in task_rows:
        method = row.get("method") or "unknown"
        if method in {"random_branch", "promising_branch"}:
            by_task[row.get("task_id") or "unknown"][method] = _bool(row.get("solved"))

    rows: list[dict[str, Any]] = []
    for task_id in sorted(by_task):
        methods = by_task[task_id]
        random_solved = methods.get("random_branch")
        promising_solved = methods.get("promising_branch")
        if random_solved is None and promising_solved is None:
            continue
        rows.append(
            {
                "task_id": task_id,
                "random_branch_solved": random_solved,
                "promising_branch_solved": promising_solved,
                "promising_minus_random": (
                    int(bool(promising_solved)) - int(bool(random_solved))
                    if random_solved is not None and promising_solved is not None
                    else None
                ),
            }
        )
    return tuple(rows)


def _repeated_setup_work(
    run_rows: Sequence[Mapping[str, str]],
) -> tuple[dict[str, Any], ...]:
    by_method: dict[str, list[float]] = defaultdict(list)
    missing = Counter()
    for row in run_rows:
        method = row.get("method") or "unknown"
        value = _float(row.get("repeated_setup_score"))
        if value is None:
            missing[method] += 1
        else:
            by_method[method].append(value)

    methods = sorted(set(by_method) | set(missing))
    rows: list[dict[str, Any]] = []
    for method in methods:
        values = by_method.get(method, [])
        rows.append(
            {
                "method": method,
                "n_runs_with_metric": len(values),
                "n_runs_missing_metric": missing[method],
                "mean_repeated_setup_score": (
                    sum(values) / len(values) if values else None
                ),
            }
        )
    return tuple(rows)


def _snapshot_overhead(
    run_rows: Sequence[Mapping[str, str]],
) -> tuple[dict[str, Any], ...]:
    by_method: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for row in run_rows:
        by_method[row.get("method") or "unknown"].append(row)

    rows: list[dict[str, Any]] = []
    for method in sorted(by_method):
        items = by_method[method]
        snapshot_values = [
            value
            for value in (
                _float(row.get("snapshot_overhead_seconds")) for row in items
            )
            if value is not None
        ]
        restore_values = [
            value
            for value in (
                _float(row.get("restore_overhead_seconds")) for row in items
            )
            if value is not None
        ]
        rows.append(
            {
                "method": method,
                "n_runs": len(items),
                "n_snapshot_overhead_values": len(snapshot_values),
                "total_snapshot_overhead_seconds": (
                    sum(snapshot_values) if snapshot_values else None
                ),
                "n_restore_overhead_values": len(restore_values),
                "total_restore_overhead_seconds": (
                    sum(restore_values) if restore_values else None
                ),
            }
        )
    return tuple(rows)


def _oracle_gap(
    task_rows: Sequence[Mapping[str, str]],
) -> tuple[dict[str, Any], ...]:
    oracle_tasks = {
        row.get("task_id") or "unknown"
        for row in task_rows
        if row.get("method") == "oracle_branch" and _bool(row.get("solved"))
    }
    if not oracle_tasks:
        return ()

    rows: list[dict[str, Any]] = []
    by_method: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for row in task_rows:
        by_method[row.get("method") or "unknown"].append(row)
    for method in sorted(by_method):
        if method == "oracle_branch":
            continue
        solved_tasks = {
            row.get("task_id") or "unknown"
            for row in by_method[method]
            if _bool(row.get("solved"))
        }
        rows.append(
            {
                "method": method,
                "oracle_solved_tasks": len(oracle_tasks),
                "method_solved_tasks": len(solved_tasks),
                "oracle_gap_tasks": len(oracle_tasks - solved_tasks),
            }
        )
    return tuple(rows)


def _planned_job_status(
    execution_rows: Sequence[Mapping[str, str]],
) -> tuple[dict[str, Any], ...]:
    counts: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for row in execution_rows:
        key = (row.get("group") or "unknown", row.get("method") or "unknown")
        counts[key][row.get("artifact_status") or "unknown"] += 1

    rows: list[dict[str, Any]] = []
    for group, method in sorted(counts):
        counter = counts[(group, method)]
        rows.append(
            {
                "group": group,
                "method": method,
                "n_jobs": sum(counter.values()),
                "not_started": counter["not_started"],
                "blocked_pending_root_archive": counter[
                    "blocked_pending_root_archive"
                ],
                "completed": counter["completed"],
                "failed": counter["failed"],
            }
        )
    return tuple(rows)


def _status_for_figure(
    name: str,
    rows: Sequence[Mapping[str, Any]],
    task_rows: Sequence[Mapping[str, str]],
    run_rows: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
    if not task_rows and name in {
        "solve_rate_by_method",
        "cost_per_solved_task",
        "unique_task_overlap",
        "promising_vs_random_branch_lift",
        "oracle_gap",
    }:
        return _status(name, "deferred_no_task_summary", 0, _interpretation(name))
    if not run_rows and name in {
        "branch_success_by_snapshot_event_type",
        "repeated_setup_work",
        "snapshot_overhead",
    }:
        return _status(name, "deferred_no_run_summary", 0, _interpretation(name))
    if not rows:
        return _status(name, "deferred_no_observed_signal", 0, _interpretation(name))
    if _all_unsolved_missing(task_rows, run_rows):
        return _status(name, "planned_only", len(rows), _interpretation(name))
    return _status(name, "ready", len(rows), _interpretation(name))


def _status(
    name: str,
    status: str,
    source_rows: int,
    interpretation: str,
) -> dict[str, Any]:
    return {
        "figure": name,
        "artifact": f"{name}.csv",
        "status": status,
        "source_rows": source_rows,
        "interpretation": interpretation,
    }


def _interpretation(name: str) -> str:
    return {
        "solve_rate_by_method": "Requires completed task-summary rows.",
        "cost_per_solved_task": "Requires solved tasks with cost fields.",
        "unique_task_overlap": "Requires at least one solved task.",
        "branch_success_by_snapshot_event_type": (
            "Requires continuation run rows joined with snapshot cell keys."
        ),
        "promising_vs_random_branch_lift": (
            "Requires paired random_branch and promising_branch task outcomes."
        ),
        "repeated_setup_work": "Requires repeated-work metrics joined into run rows.",
        "snapshot_overhead": "Requires persisted snapshot/restore overhead fields.",
        "oracle_gap": "Requires oracle_branch rows or precomputed oracle labels.",
    }[name]


def _all_unsolved_missing(
    task_rows: Sequence[Mapping[str, str]],
    run_rows: Sequence[Mapping[str, str]],
) -> bool:
    if task_rows and any(_bool(row.get("solved")) for row in task_rows):
        return False
    if run_rows and any(row.get("outcome") not in {"missing_result", ""} for row in run_rows):
        return False
    return bool(task_rows or run_rows)


def _read_csvs(paths: Sequence[Path]) -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []
    for path in paths:
        rows.extend(_read_csv(path))
    return tuple(rows)


def _read_csv(path: Path | None) -> tuple[dict[str, str], ...]:
    if path is None or not path.exists():
        return ()
    with path.open(newline="") as file:
        return tuple(dict(row) for row in csv.DictReader(file))


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    fields = sorted({field for row in rows for field in row})
    if not fields:
        fields = ["status"]
        rows = ({"status": "no_rows"},)
    with path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in fields})


def _write_readme(path: Path, report: FigureTableReport) -> None:
    lines = [
        "# Figure Tables",
        "",
        "These artifacts are generated from normalized analysis tables.",
        "",
        "| Figure | Status | Interpretation |",
        "| --- | --- | --- |",
    ]
    for status in report.statuses:
        lines.append(
            "| `{figure}` | `{status}` | {interpretation} |".format(**status)
        )
    lines.extend(
        [
            "",
            "When the benchmark has only planned manifests and no completed run",
            "summaries, evidence-dependent figures are intentionally marked as",
            "deferred rather than plotted from missing data.",
            "",
        ]
    )
    path.write_text("\n".join(lines))


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    return value


def _bool(value: str | None) -> bool:
    return str(value).lower() == "true"


def _float(value: str | None) -> float | None:
    if value in {None, ""}:
        return None
    try:
        return float(str(value))
    except ValueError:
        return None


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator
