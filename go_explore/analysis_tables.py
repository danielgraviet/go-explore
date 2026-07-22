from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from go_explore.events import EVENT_LOG_FILENAME, UNKNOWN_EXPERIMENT_ID
from go_explore.results import BudgetSummary, TrialSummary, summarize_job


RUN_SUMMARY_FIELDS = (
    "experiment_id",
    "run_id",
    "job_dir",
    "trial_name",
    "task_id",
    "method",
    "role",
    "seed",
    "start_state_type",
    "context_mode",
    "parent_run_id",
    "parent_job_dir",
    "parent_trial_name",
    "parent_snapshot",
    "snapshot_cell_key",
    "selector_mode",
    "selector_score",
    "selector_reasons",
    "planned_token_budget",
    "budget_enforcement",
    "reward",
    "outcome",
    "exception_type",
    "n_input_tokens",
    "n_output_tokens",
    "n_cache_tokens",
    "total_tokens",
    "total_tokens_status",
    "cost_usd",
    "cost_usd_status",
    "duration_seconds",
    "duration_seconds_status",
    "agent_execution_seconds",
    "environment_setup_seconds",
    "snapshot_overhead_seconds",
    "snapshot_overhead_seconds_status",
    "restore_overhead_seconds",
    "restore_overhead_seconds_status",
    "repeated_setup_score",
    "n_snapshots_created",
    "n_snapshots_forked",
    "failure_mode",
)

TASK_SUMMARY_FIELDS = (
    "experiment_id",
    "task_id",
    "difficulty",
    "category",
    "method",
    "model_class",
    "solved",
    "n_runs",
    "n_attempts",
    "n_snapshots_created",
    "n_snapshots_forked",
    "total_tokens",
    "total_cost_usd",
    "wall_clock_seconds",
    "snapshot_overhead_seconds",
    "restore_overhead_seconds",
    "unique_success_beyond_baselines",
)


@dataclass(frozen=True)
class AnalysisWarning:
    artifact: str
    field: str
    message: str
    severity: str = "warning"

    def to_json_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class AnalysisTables:
    run_rows: tuple[dict[str, Any], ...]
    task_rows: tuple[dict[str, Any], ...]
    warnings: tuple[AnalysisWarning, ...]


@dataclass(frozen=True)
class AnalysisInputs:
    manifest_path: Path | None = None
    job_dirs: tuple[Path, ...] = ()
    continuation_report_paths: tuple[Path, ...] = ()
    event_log_paths: tuple[Path, ...] = ()
    repeated_work_report_paths: tuple[Path, ...] = ()
    jobs_dir: Path = Path("jobs")
    include_missing_planned: bool = True


@dataclass(frozen=True)
class PlannedJobMetadata:
    experiment_id: str
    task_id: str | None
    model: str | None
    method: str
    role: str
    seed: int | None
    job_name: str
    planned_token_budget: int | None
    budget_enforcement: str
    start_state_type: str
    context_mode: str
    selector_mode: str | None
    parent_run_id: str | None
    parent_snapshot: str | None


@dataclass(frozen=True)
class ContinuationLineage:
    parent_job_dir: str
    parent_trial_name: str
    parent_snapshot: str | None
    parent_run_id: str | None
    start_state_type: str
    context_mode: str


@dataclass(frozen=True)
class SnapshotSelection:
    snapshot_name: str
    cell_key: str | None
    selector_mode: str | None
    selector_score: float | None
    selector_reasons: tuple[str, ...]


def build_analysis_tables(inputs: AnalysisInputs) -> AnalysisTables:
    warnings: list[AnalysisWarning] = []
    manifest = _load_manifest(inputs.manifest_path, warnings)
    planned_jobs = _planned_jobs_from_manifest(manifest)
    _warn_for_planning_only_budgets(
        planned_jobs,
        warnings,
        artifact=str(inputs.manifest_path) if inputs.manifest_path else "manifest",
    )
    planned_by_job_name = {job.job_name: job for job in planned_jobs}
    planned_by_job_dir = {
        _normalize_path(inputs.jobs_dir / job.job_name): job for job in planned_jobs
    }
    experiment_id = manifest.get("experiment_id") or UNKNOWN_EXPERIMENT_ID
    model = manifest.get("model")

    event_paths = _dedupe_paths(
        tuple(inputs.event_log_paths)
        + tuple(job_dir / EVENT_LOG_FILENAME for job_dir in inputs.job_dirs)
    )
    events = _read_events(event_paths, warnings)
    event_experiment_id = _first_str(event.get("experiment_id") for event in events)
    if experiment_id == UNKNOWN_EXPERIMENT_ID and event_experiment_id:
        experiment_id = event_experiment_id

    continuation_reports = _read_continuation_reports(
        inputs.continuation_report_paths,
        warnings,
    )
    lineages = _lineages_from_reports(
        continuation_reports,
        planned_by_job_dir=planned_by_job_dir,
        planned_by_job_name=planned_by_job_name,
    )
    planned_aliases = _planned_aliases_from_reports(
        continuation_reports,
        planned_jobs=planned_jobs,
        planned_by_job_dir=planned_by_job_dir,
        planned_by_job_name=planned_by_job_name,
    )
    repeated_work = _read_repeated_work(inputs.repeated_work_report_paths, warnings)
    archive_entries = _read_archive_entries(inputs.job_dirs, warnings)
    selection_by_snapshot = _snapshot_selections(events, archive_entries)

    run_rows: list[dict[str, Any]] = []
    seen_job_names: set[str] = set()
    seen_job_dirs: set[str] = set()

    for job_dir in sorted(_dedupe_paths(inputs.job_dirs), key=_normalize_path):
        job_dir_key = _normalize_path(job_dir)
        planned = (
            planned_by_job_dir.get(job_dir_key)
            or planned_by_job_name.get(job_dir.name)
            or planned_aliases.get(job_dir_key)
            or planned_aliases.get(job_dir.name)
        )
        if planned is not None:
            seen_job_names.add(planned.job_name)
        seen_job_dirs.add(job_dir_key)
        run_rows.extend(
            _rows_from_job_dir(
                job_dir,
                planned=planned,
                experiment_id=experiment_id,
                manifest_task_id=manifest.get("task_id"),
                model=model,
                lineages=lineages,
                events=events,
                selection_by_snapshot=selection_by_snapshot,
                repeated_work=repeated_work,
                warnings=warnings,
            )
        )

    if inputs.include_missing_planned:
        for planned in sorted(planned_jobs, key=lambda job: job.job_name):
            planned_job_dir = inputs.jobs_dir / planned.job_name
            planned_job_dir_key = _normalize_path(planned_job_dir)
            if planned.job_name in seen_job_names or planned_job_dir_key in seen_job_dirs:
                continue
            run_rows.append(_missing_planned_row(planned, planned_job_dir))
            warnings.append(
                AnalysisWarning(
                    artifact=str(planned_job_dir),
                    field="job_dir",
                    message="planned job result is missing",
                )
            )

    _warn_for_partial_rows(run_rows, warnings)
    task_rows = _task_rows(
        run_rows,
        model=model,
        manifest_task_id=manifest.get("task_id"),
    )

    return AnalysisTables(
        run_rows=tuple(_ordered_row(row, RUN_SUMMARY_FIELDS) for row in run_rows),
        task_rows=tuple(_ordered_row(row, TASK_SUMMARY_FIELDS) for row in task_rows),
        warnings=tuple(warnings),
    )


def write_analysis_tables(tables: AnalysisTables, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "run-summary.csv", RUN_SUMMARY_FIELDS, tables.run_rows)
    _write_csv(output_dir / "task-summary.csv", TASK_SUMMARY_FIELDS, tables.task_rows)
    (output_dir / "warnings.json").write_text(
        json.dumps(
            {
                "schema_version": "go-explore-analysis-warnings-v1",
                "warnings": [warning.to_json_dict() for warning in tables.warnings],
            },
            indent=2,
        )
        + "\n"
    )


def _rows_from_job_dir(
    job_dir: Path,
    *,
    planned: PlannedJobMetadata | None,
    experiment_id: str,
    manifest_task_id: str | None,
    model: str | None,
    lineages: Mapping[str, ContinuationLineage],
    events: Sequence[Mapping[str, Any]],
    selection_by_snapshot: Mapping[str, SnapshotSelection],
    repeated_work: Mapping[str, Mapping[str, Any]],
    warnings: list[AnalysisWarning],
) -> list[dict[str, Any]]:
    try:
        job_summary = summarize_job(job_dir)
    except FileNotFoundError:
        warnings.append(
            AnalysisWarning(
                artifact=str(job_dir),
                field="result.json",
                message="job result.json is missing",
            )
        )
        return []

    rows: list[dict[str, Any]] = []
    lineage = lineages.get(_normalize_path(job_dir)) or lineages.get(job_dir.name)
    for trial in sorted(job_summary.trials, key=lambda item: item.trial_name):
        run_id = _run_id_for_trial(job_dir, trial, planned)
        parent_snapshot = (
            lineage.parent_snapshot
            if lineage is not None
            else planned.parent_snapshot if planned is not None else None
        )
        selection = selection_by_snapshot.get(parent_snapshot or "")
        budget = trial.budget
        row = {
            "experiment_id": (
                planned.experiment_id
                if planned is not None
                else _experiment_id_for_run(events, run_id, trial.trial_name)
                or experiment_id
            ),
            "run_id": run_id,
            "job_dir": str(job_dir),
            "trial_name": trial.trial_name,
            "task_id": trial.task_name or manifest_task_id,
            "method": planned.method if planned is not None else "unknown",
            "role": planned.role if planned is not None else "unknown",
            "seed": planned.seed if planned is not None else None,
            "start_state_type": _start_state_type(planned, lineage),
            "context_mode": _context_mode(planned, lineage),
            "parent_run_id": _parent_run_id(planned, lineage),
            "parent_job_dir": lineage.parent_job_dir if lineage else None,
            "parent_trial_name": lineage.parent_trial_name if lineage else None,
            "parent_snapshot": parent_snapshot,
            "snapshot_cell_key": selection.cell_key if selection else None,
            "selector_mode": _selector_mode(planned, selection),
            "selector_score": selection.selector_score if selection else None,
            "selector_reasons": (
                "|".join(selection.selector_reasons) if selection else None
            ),
            "planned_token_budget": (
                planned.planned_token_budget if planned is not None else None
            ),
            "budget_enforcement": (
                planned.budget_enforcement if planned is not None else None
            ),
            "reward": trial.reward,
            "outcome": _outcome_for_trial(trial),
            "exception_type": trial.exception_type,
            "failure_mode": _failure_mode_for_trial(trial),
            "n_snapshots_created": _count_events(
                events,
                event_type="snapshot_created",
                run_id=run_id,
                trial_name=trial.trial_name,
                job_dir=job_dir,
            ),
            "n_snapshots_forked": _count_forks(
                events,
                run_id=run_id,
                trial_name=trial.trial_name,
                job_dir=job_dir,
            ),
            **_budget_columns(budget),
            "repeated_setup_score": _repeated_value(
                repeated_work,
                run_id,
                trial.trial_name,
                job_dir.name,
                key="repeated_setup_score",
            ),
        }
        if model is not None:
            row["_model"] = model
        rows.append(row)

    if not rows:
        warnings.append(
            AnalysisWarning(
                artifact=str(job_dir),
                field="trial_result",
                message="job has no trial result rows",
            )
        )

    return rows


def _missing_planned_row(
    planned: PlannedJobMetadata,
    planned_job_dir: Path,
) -> dict[str, Any]:
    return {
        "experiment_id": planned.experiment_id,
        "run_id": planned.job_name,
        "job_dir": str(planned_job_dir),
        "trial_name": None,
        "task_id": planned.task_id,
        "method": planned.method,
        "role": planned.role,
        "seed": planned.seed,
        "start_state_type": planned.start_state_type,
        "context_mode": planned.context_mode,
        "parent_run_id": planned.parent_run_id,
        "parent_job_dir": None,
        "parent_trial_name": None,
        "parent_snapshot": planned.parent_snapshot,
        "snapshot_cell_key": None,
        "selector_mode": planned.selector_mode,
        "selector_score": None,
        "selector_reasons": None,
        "planned_token_budget": planned.planned_token_budget,
        "budget_enforcement": planned.budget_enforcement,
        "reward": None,
        "outcome": "missing_result",
        "exception_type": None,
        "failure_mode": "missing_result",
        "n_snapshots_created": 0,
        "n_snapshots_forked": 0,
        "repeated_setup_score": None,
        **_budget_columns(BudgetSummary()),
        "_model": planned.model,
    }


def _task_rows(
    run_rows: Sequence[Mapping[str, Any]],
    *,
    model: str | None,
    manifest_task_id: str | None,
) -> list[dict[str, Any]]:
    rows_by_key: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in run_rows:
        task_id = row.get("task_id") or manifest_task_id or "unknown"
        key = (
            str(row.get("experiment_id") or UNKNOWN_EXPERIMENT_ID),
            str(task_id),
            str(row.get("method") or "unknown"),
        )
        rows_by_key[key].append(row)

    solved_by_experiment_task: dict[tuple[str, str], set[str]] = defaultdict(set)
    for (experiment_id, task_id, method), rows in rows_by_key.items():
        if any(row.get("outcome") == "success" for row in rows):
            solved_by_experiment_task[(experiment_id, task_id)].add(method)

    task_rows: list[dict[str, Any]] = []
    for key in sorted(rows_by_key):
        experiment_id, task_id, method = key
        rows = rows_by_key[key]
        solved = any(row.get("outcome") == "success" for row in rows)
        baseline_solved = bool(
            solved_by_experiment_task[(experiment_id, task_id)]
            & {"single", "retry", "best_of_n"}
        )
        unique_success_beyond_baselines = None
        if method in {"single", "retry", "best_of_n"}:
            unique_success_beyond_baselines = False
        elif method != "unknown":
            unique_success_beyond_baselines = solved and not baseline_solved

        task_rows.append(
            {
                "experiment_id": experiment_id,
                "task_id": task_id,
                "difficulty": None,
                "category": None,
                "method": method,
                "model_class": _first_str(row.get("_model") for row in rows) or model,
                "solved": solved,
                "n_runs": len(rows),
                "n_attempts": len(rows),
                "n_snapshots_created": _sum_known(rows, "n_snapshots_created") or 0,
                "n_snapshots_forked": _sum_known(rows, "n_snapshots_forked") or 0,
                "total_tokens": _sum_known(rows, "total_tokens"),
                "total_cost_usd": _sum_known(rows, "cost_usd"),
                "wall_clock_seconds": _sum_known(rows, "duration_seconds"),
                "snapshot_overhead_seconds": _sum_known(
                    rows,
                    "snapshot_overhead_seconds",
                ),
                "restore_overhead_seconds": _sum_known(
                    rows,
                    "restore_overhead_seconds",
                ),
                "unique_success_beyond_baselines": unique_success_beyond_baselines,
            }
        )
    return task_rows


def _load_manifest(
    manifest_path: Path | None,
    warnings: list[AnalysisWarning],
) -> dict[str, Any]:
    if manifest_path is None:
        return {}
    if not manifest_path.exists():
        warnings.append(
            AnalysisWarning(
                artifact=str(manifest_path),
                field="manifest",
                message="manifest path does not exist",
            )
        )
        return {}
    with manifest_path.open() as file:
        return json.load(file)


def _planned_jobs_from_manifest(
    manifest: Mapping[str, Any],
) -> tuple[PlannedJobMetadata, ...]:
    experiment_id = str(manifest.get("experiment_id") or UNKNOWN_EXPERIMENT_ID)
    task_id = manifest.get("task_id")
    model = manifest.get("model")
    jobs: list[PlannedJobMetadata] = []
    for raw in manifest.get("jobs") or ():
        budget = raw.get("budget") or {}
        jobs.append(
            PlannedJobMetadata(
                experiment_id=experiment_id,
                task_id=str(task_id) if task_id is not None else None,
                model=str(model) if model is not None else None,
                method=str(raw.get("method") or "unknown"),
                role=str(raw.get("role") or "unknown"),
                seed=raw.get("seed") if isinstance(raw.get("seed"), int) else None,
                job_name=str(raw.get("job_name") or ""),
                planned_token_budget=(
                    budget.get("token_budget")
                    if isinstance(budget.get("token_budget"), int)
                    else None
                ),
                budget_enforcement=str(budget.get("enforcement") or "unknown"),
                start_state_type=str(raw.get("start_state_type") or "unknown"),
                context_mode=str(raw.get("context_mode") or "unknown"),
                selector_mode=(
                    str(raw["selector_mode"])
                    if raw.get("selector_mode") is not None
                    else None
                ),
                parent_run_id=(
                    str(raw["parent_run_id"])
                    if raw.get("parent_run_id") is not None
                    else None
                ),
                parent_snapshot=(
                    str(raw["parent_snapshot"])
                    if raw.get("parent_snapshot") is not None
                    else None
                ),
            )
        )
    return tuple(job for job in jobs if job.job_name)


def _read_continuation_reports(
    paths: Sequence[Path],
    warnings: list[AnalysisWarning],
) -> tuple[dict[str, Any], ...]:
    reports: list[dict[str, Any]] = []
    for path in _dedupe_paths(paths):
        if not path.exists():
            warnings.append(
                AnalysisWarning(
                    artifact=str(path),
                    field="continuation_report",
                    message="continuation report path does not exist",
                )
            )
            continue
        with path.open() as file:
            reports.append(json.load(file))
    return tuple(reports)


def _lineages_from_reports(
    reports: Sequence[Mapping[str, Any]],
    *,
    planned_by_job_dir: Mapping[str, PlannedJobMetadata],
    planned_by_job_name: Mapping[str, PlannedJobMetadata],
) -> dict[str, ContinuationLineage]:
    lineages: dict[str, ContinuationLineage] = {}
    for report in reports:
        parent_job_dir = str(report.get("root_job_dir") or "")
        parent_trial_name = str(report.get("root_trial_name") or "")
        parent_plan = (
            planned_by_job_dir.get(_normalize_path(Path(parent_job_dir)))
            if parent_job_dir
            else None
        )
        for attempt in report.get("attempts") or ():
            child_job_dir = str(attempt.get("continuation_job_dir") or "")
            if not child_job_dir:
                continue
            child_plan = planned_by_job_dir.get(
                _normalize_path(Path(child_job_dir))
            ) or planned_by_job_name.get(Path(child_job_dir).name)
            if child_plan is not None and child_plan.parent_run_id is not None:
                parent_run_id = child_plan.parent_run_id
            elif parent_plan is not None:
                parent_run_id = parent_plan.job_name
            else:
                parent_run_id = parent_trial_name
            lineage = ContinuationLineage(
                parent_job_dir=parent_job_dir,
                parent_trial_name=parent_trial_name,
                parent_snapshot=attempt.get("snapshot_name"),
                parent_run_id=parent_run_id or None,
                start_state_type=str(
                    attempt.get("start_state_type") or "full_snapshot"
                ),
                context_mode=str(attempt.get("context_mode") or "parent_summary"),
            )
            lineages[_normalize_path(Path(child_job_dir))] = lineage
            lineages[Path(child_job_dir).name] = lineage
    return lineages


def _planned_aliases_from_reports(
    reports: Sequence[Mapping[str, Any]],
    *,
    planned_jobs: Sequence[PlannedJobMetadata],
    planned_by_job_dir: Mapping[str, PlannedJobMetadata],
    planned_by_job_name: Mapping[str, PlannedJobMetadata],
) -> dict[str, PlannedJobMetadata]:
    aliases: dict[str, PlannedJobMetadata] = {}
    for report in reports:
        parent_job_dir = str(report.get("root_job_dir") or "")
        if not parent_job_dir:
            continue
        parent_job_name = Path(parent_job_dir).name
        parent_plan = planned_by_job_dir.get(
            _normalize_path(Path(parent_job_dir))
        ) or planned_by_job_name.get(parent_job_name)
        parent_run_ids = {parent_job_name}
        if parent_plan is not None:
            parent_run_ids.add(parent_plan.job_name)

        planned_children = sorted(
            (
                planned
                for planned in planned_jobs
                if planned.role == "continuation"
                and planned.parent_run_id in parent_run_ids
                and (parent_plan is None or planned.method == parent_plan.method)
            ),
            key=lambda planned: planned.job_name,
        )

        for index, attempt in enumerate(report.get("attempts") or ()):
            child_job_dir = str(attempt.get("continuation_job_dir") or "")
            if not child_job_dir:
                continue
            child_job_path = Path(child_job_dir)
            child_job_dir_key = _normalize_path(child_job_path)
            if (
                child_job_dir_key in planned_by_job_dir
                or child_job_path.name in planned_by_job_name
            ):
                continue
            if index >= len(planned_children):
                continue

            planned = planned_children[index]
            parent_snapshot = attempt.get("snapshot_name")
            if planned.parent_snapshot is None and isinstance(parent_snapshot, str):
                planned = replace(planned, parent_snapshot=parent_snapshot)

            aliases[child_job_dir_key] = planned
            aliases[child_job_path.name] = planned
    return aliases


def _read_events(
    paths: Sequence[Path],
    warnings: list[AnalysisWarning],
) -> tuple[dict[str, Any], ...]:
    events: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            continue
        for line_number, line in enumerate(path.read_text().splitlines(), start=1):
            if not line.strip():
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError as error:
                warnings.append(
                    AnalysisWarning(
                        artifact=f"{path}:{line_number}",
                        field="event",
                        message=f"invalid JSONL event: {error}",
                    )
                )
    return tuple(events)


def _read_repeated_work(
    paths: Sequence[Path],
    warnings: list[AnalysisWarning],
) -> dict[str, Mapping[str, Any]]:
    metrics: dict[str, Mapping[str, Any]] = {}
    for path in _dedupe_paths(paths):
        if not path.exists():
            warnings.append(
                AnalysisWarning(
                    artifact=str(path),
                    field="repeated_work_report",
                    message="repeated-work report path does not exist",
                )
            )
            continue
        data = json.loads(path.read_text())
        for run in data.get("runs") or ():
            run_id = run.get("run_id")
            if isinstance(run_id, str):
                metrics[run_id] = run
    return metrics


def _read_archive_entries(
    job_dirs: Sequence[Path],
    warnings: list[AnalysisWarning],
) -> dict[str, Mapping[str, Any]]:
    entries: dict[str, Mapping[str, Any]] = {}
    for job_dir in _dedupe_paths(job_dirs):
        path = job_dir / "archive.json"
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as error:
            warnings.append(
                AnalysisWarning(
                    artifact=str(path),
                    field="archive",
                    message=f"invalid archive JSON: {error}",
                )
            )
            continue
        for entry in data.get("entries") or ():
            snapshot_name = entry.get("snapshot_name")
            if isinstance(snapshot_name, str):
                entries[snapshot_name] = entry
    return entries


def _snapshot_selections(
    events: Sequence[Mapping[str, Any]],
    archive_entries: Mapping[str, Mapping[str, Any]],
) -> dict[str, SnapshotSelection]:
    selections: dict[str, SnapshotSelection] = {}
    for event in events:
        if event.get("event_type") not in {"snapshot_selected", "snapshot_created"}:
            continue
        snapshot_name = event.get("snapshot_name")
        if not isinstance(snapshot_name, str):
            continue
        if event.get("event_type") == "snapshot_created" and snapshot_name in selections:
            continue
        selections[snapshot_name] = SnapshotSelection(
            snapshot_name=snapshot_name,
            cell_key=_optional_str(event.get("cell_key")),
            selector_mode=_optional_str(event.get("selector_mode")),
            selector_score=_optional_float(event.get("score")),
            selector_reasons=tuple(
                str(reason) for reason in event.get("selector_reasons") or ()
            ),
        )

    for snapshot_name, entry in archive_entries.items():
        if snapshot_name in selections:
            continue
        selections[snapshot_name] = SnapshotSelection(
            snapshot_name=snapshot_name,
            cell_key=_optional_str(entry.get("cell_key")),
            selector_mode=None,
            selector_score=_optional_float(entry.get("score")),
            selector_reasons=(),
        )
    return selections


def _warn_for_partial_rows(
    rows: Sequence[Mapping[str, Any]],
    warnings: list[AnalysisWarning],
) -> None:
    for row in rows:
        artifact = str(row.get("job_dir") or row.get("run_id") or "unknown")
        if row.get("method") == "unknown":
            warnings.append(
                AnalysisWarning(
                    artifact=artifact,
                    field="method",
                    message="method is unknown; pass a fixed-budget manifest to join planned metadata",
                )
            )
        if row.get("total_tokens_status") != "complete":
            warnings.append(
                AnalysisWarning(
                    artifact=artifact,
                    field="total_tokens",
                    message=f"token accounting is {row.get('total_tokens_status')}",
                )
            )
        if row.get("cost_usd_status") != "complete":
            warnings.append(
                AnalysisWarning(
                    artifact=artifact,
                    field="cost_usd",
                    message=f"cost accounting is {row.get('cost_usd_status')}",
                )
            )
        if row.get("parent_snapshot") and row.get("snapshot_cell_key") is None:
            warnings.append(
                AnalysisWarning(
                    artifact=artifact,
                    field="snapshot_cell_key",
                    message="parent snapshot has no archive/event cell metadata",
                )
            )
        if row.get("repeated_setup_score") is None:
            warnings.append(
                AnalysisWarning(
                    artifact=artifact,
                    field="repeated_setup_score",
                    message="repeated-work metric is unknown",
                    severity="info",
                )
            )


def _warn_for_planning_only_budgets(
    planned_jobs: Sequence[PlannedJobMetadata],
    warnings: list[AnalysisWarning],
    *,
    artifact: str,
) -> None:
    if not any(job.budget_enforcement == "planning_only" for job in planned_jobs):
        return

    warnings.append(
        AnalysisWarning(
            artifact=artifact,
            field="budget_enforcement",
            message=(
                "planned token budgets are planning_only labels, not enforced "
                "caps; compare actual total_tokens before making strict "
                "fixed-budget claims"
            ),
        )
    )


def _run_id_for_trial(
    job_dir: Path,
    trial: TrialSummary,
    planned: PlannedJobMetadata | None,
) -> str:
    if planned is not None:
        return planned.job_name
    return trial.trial_name or job_dir.name


def _outcome_for_trial(trial: TrialSummary) -> str:
    if trial.exception_type:
        return "agent_error"
    if trial.reward == 1.0:
        return "success"
    if trial.reward is None:
        return "missing_result"
    return "fail"


def _failure_mode_for_trial(trial: TrialSummary) -> str | None:
    if trial.exception_type:
        return trial.exception_type
    if trial.reward is None:
        return "missing_result"
    if trial.reward != 1.0:
        return "incorrect"
    return None


def _start_state_type(
    planned: PlannedJobMetadata | None,
    lineage: ContinuationLineage | None,
) -> str:
    if planned is not None:
        return planned.start_state_type
    if lineage is not None:
        return lineage.start_state_type
    return "unknown"


def _context_mode(
    planned: PlannedJobMetadata | None,
    lineage: ContinuationLineage | None,
) -> str:
    if planned is not None:
        return planned.context_mode
    if lineage is not None:
        return lineage.context_mode
    return "unknown"


def _parent_run_id(
    planned: PlannedJobMetadata | None,
    lineage: ContinuationLineage | None,
) -> str | None:
    if planned is not None and planned.parent_run_id is not None:
        return planned.parent_run_id
    if lineage is not None:
        return lineage.parent_run_id
    return None


def _selector_mode(
    planned: PlannedJobMetadata | None,
    selection: SnapshotSelection | None,
) -> str | None:
    if planned is not None and planned.selector_mode is not None:
        return planned.selector_mode
    if selection is not None:
        return selection.selector_mode
    return None


def _budget_columns(budget: BudgetSummary) -> dict[str, Any]:
    return {
        "n_input_tokens": budget.n_input_tokens,
        "n_output_tokens": budget.n_output_tokens,
        "n_cache_tokens": budget.n_cache_tokens,
        "total_tokens": budget.total_tokens,
        "total_tokens_status": budget.total_tokens_status,
        "cost_usd": budget.cost_usd,
        "cost_usd_status": budget.cost_usd_status,
        "duration_seconds": budget.duration_seconds,
        "duration_seconds_status": budget.duration_seconds_status,
        "agent_execution_seconds": budget.agent_execution_seconds,
        "environment_setup_seconds": budget.environment_setup_seconds,
        "snapshot_overhead_seconds": budget.snapshot_overhead_seconds,
        "snapshot_overhead_seconds_status": budget.snapshot_overhead_seconds_status,
        "restore_overhead_seconds": budget.restore_overhead_seconds,
        "restore_overhead_seconds_status": budget.restore_overhead_seconds_status,
    }


def _count_events(
    events: Sequence[Mapping[str, Any]],
    *,
    event_type: str,
    run_id: str,
    trial_name: str,
    job_dir: Path,
) -> int:
    return sum(
        1
        for event in events
        if event.get("event_type") == event_type
        and _event_matches_run(event, run_id, trial_name, job_dir)
    )


def _count_forks(
    events: Sequence[Mapping[str, Any]],
    *,
    run_id: str,
    trial_name: str,
    job_dir: Path,
) -> int:
    continuation_starts = [
        event
        for event in events
        if event.get("event_type") == "continuation_started"
        and _event_matches_run(event, run_id, trial_name, job_dir)
    ]
    if continuation_starts:
        return len(continuation_starts)
    return sum(
        1
        for event in events
        if event.get("event_type") == "snapshot_selected"
        and _event_matches_run(event, run_id, trial_name, job_dir)
    )


def _event_matches_run(
    event: Mapping[str, Any],
    run_id: str,
    trial_name: str,
    job_dir: Path,
) -> bool:
    event_run_id = event.get("run_id")
    event_trial_name = event.get("trial_name")
    event_job_dir = event.get("job_dir")
    return (
        event_run_id == run_id
        or event_run_id == trial_name
        or event_trial_name == trial_name
        or (
            isinstance(event_job_dir, str)
            and _normalize_path(Path(event_job_dir)) == _normalize_path(job_dir)
        )
    )


def _experiment_id_for_run(
    events: Sequence[Mapping[str, Any]],
    run_id: str,
    trial_name: str,
) -> str | None:
    for event in events:
        if event.get("run_id") in {run_id, trial_name} and isinstance(
            event.get("experiment_id"),
            str,
        ):
            return str(event["experiment_id"])
    return None


def _repeated_value(
    repeated_work: Mapping[str, Mapping[str, Any]],
    *run_ids: str,
    key: str,
) -> Any:
    for run_id in run_ids:
        metrics = repeated_work.get(run_id)
        if metrics is not None:
            return metrics.get(key)
    return None


def _sum_known(rows: Sequence[Mapping[str, Any]], key: str) -> int | float | None:
    values = [row.get(key) for row in rows if isinstance(row.get(key), int | float)]
    if not values:
        return None
    return sum(values)


def _first_str(values: Iterable[Any]) -> str | None:
    for value in values:
        if isinstance(value, str) and value:
            return value
    return None


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _optional_float(value: Any) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    return None


def _ordered_row(row: Mapping[str, Any], fields: Sequence[str]) -> dict[str, Any]:
    return {field: row.get(field) for field in fields}


def _write_csv(
    path: Path,
    fields: Sequence[str],
    rows: Sequence[Mapping[str, Any]],
) -> None:
    with path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(fields))
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in fields})


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    return value


def _dedupe_paths(paths: Sequence[Path]) -> tuple[Path, ...]:
    deduped: dict[str, Path] = {}
    for path in paths:
        deduped.setdefault(_normalize_path(path), path)
    return tuple(deduped.values())


def _normalize_path(path: Path) -> str:
    return str(path.expanduser())
