from __future__ import annotations

import json
import shlex
import subprocess
from collections import deque
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

from go_explore.analysis_tables import (
    AnalysisInputs,
    AnalysisTables,
    build_analysis_tables,
    write_analysis_tables,
)
from go_explore.continuations import (
    ContinuationReport,
    SnapshotSelectionMetadata,
    harbor_config_from_job,
    plan_snapshot_continuations,
    run_continuation_plans,
    select_trial,
)
from go_explore.events import EVENT_LOG_FILENAME
from go_explore.fixed_budget import (
    BUDGET_ENFORCEMENT_DESCRIPTION,
    BUDGET_ENFORCEMENT_PLANNING_ONLY,
    DEFAULT_BRANCH_CONTEXT_MODE,
    ExperimentMethod,
    FixedBudgetManifest,
    FixedBudgetPlanConfig,
    PlannedExperimentJob,
    plan_fixed_budget_runs,
    write_fixed_budget_manifest,
)
from go_explore.harbor import HarborRunConfig
from go_explore.harbor import environment_with_repo_path
from go_explore.results import summarize_job
from go_explore.snapshots.archive import ARCHIVE_FILENAME, SnapshotArchive
from go_explore.snapshots.selectors import select_archive_entries


CommandRunner = Callable[..., subprocess.CompletedProcess[str]]
ContinuationRunner = Callable[..., ContinuationReport]


@dataclass(frozen=True)
class RunExperimentConfig:
    experiment_id: str
    base_config: HarborRunConfig
    total_token_budget: int | None
    methods: tuple[ExperimentMethod, ...] = (
        "single",
        "retry",
        "random_branch",
        "promising_branch",
    )
    seeds: tuple[int, ...] = (0,)
    job_prefix: str | None = None
    manifest_path: Path | None = None
    analysis_dir: Path | None = None
    n_retries: int = 5
    n_branch_continuations: int = 3
    branch_root_fraction: float = 0.3
    branch_context_mode: str = DEFAULT_BRANCH_CONTEXT_MODE
    promising_selector_mode: str = "archive_priority"
    execute: bool = False
    rerun_existing: bool = False
    build_analysis: bool = True


@dataclass(frozen=True)
class ExperimentExecutionRecord:
    job_name: str
    method: str
    role: str
    status: str
    job_dir: str | None = None
    command: tuple[str, ...] = ()
    returncode: int | None = None
    details: str | None = None


@dataclass(frozen=True)
class RunExperimentReport:
    experiment_id: str
    manifest_path: Path
    analysis_dir: Path | None
    execution_report_path: Path
    budget_enforcement: str
    budget_enforcement_description: str
    records: tuple[ExperimentExecutionRecord, ...]
    job_dirs: tuple[Path, ...]
    continuation_reports: tuple[Path, ...]
    event_logs: tuple[Path, ...]
    analysis_tables: AnalysisTables | None = None

    @property
    def has_infrastructure_failures(self) -> bool:
        failed_statuses = {
            "failed",
            "skipped_missing_root_result",
            "skipped_empty_archive",
            "skipped_missing_archive",
        }
        return any(record.status in failed_statuses for record in self.records)


def run_fixed_budget_experiment(
    config: RunExperimentConfig,
    *,
    command_runner: CommandRunner = subprocess.run,
    continuation_runner: ContinuationRunner = run_continuation_plans,
) -> RunExperimentReport:
    job_prefix = config.job_prefix or config.experiment_id
    manifest_path = config.manifest_path or (
        Path("docs/experiments/main-benchmark/manifests") / f"{config.experiment_id}.json"
    )
    analysis_dir = config.analysis_dir or (
        Path("docs/experiments/main-benchmark/analysis") / config.experiment_id
    )

    manifest = plan_fixed_budget_runs(
        FixedBudgetPlanConfig(
            experiment_id=config.experiment_id,
            base_config=config.base_config,
            job_prefix=job_prefix,
            total_token_budget=config.total_token_budget,
            methods=config.methods,
            seeds=config.seeds,
            n_retries=config.n_retries,
            n_branch_continuations=config.n_branch_continuations,
            branch_root_fraction=config.branch_root_fraction,
            branch_context_mode=config.branch_context_mode,
            promising_selector_mode=config.promising_selector_mode,
        )
    )
    write_fixed_budget_manifest(manifest, manifest_path)

    return run_fixed_budget_manifest(
        manifest,
        manifest_path=manifest_path,
        jobs_dir=config.base_config.jobs_dir,
        analysis_dir=analysis_dir,
        execute=config.execute,
        rerun_existing=config.rerun_existing,
        build_analysis=config.build_analysis,
        command_runner=command_runner,
        continuation_runner=continuation_runner,
    )


def run_fixed_budget_manifest(
    manifest: FixedBudgetManifest,
    *,
    manifest_path: Path,
    jobs_dir: Path,
    analysis_dir: Path,
    execute: bool = False,
    rerun_existing: bool = False,
    build_analysis: bool = True,
    command_runner: CommandRunner = subprocess.run,
    continuation_runner: ContinuationRunner = run_continuation_plans,
) -> RunExperimentReport:
    execution_report_path = analysis_dir / "execution-report.json"
    records: list[ExperimentExecutionRecord] = []
    observed_job_dirs: list[Path] = []
    continuation_report_paths: list[Path] = []
    event_log_paths: list[Path] = []

    for seed in manifest.seeds:
        for method in manifest.methods:
            method_jobs = [
                job
                for job in manifest.jobs
                if job.seed == seed
                and job.method == method
                and job.role != "continuation"
            ]
            for job in method_jobs:
                record = _run_planned_job(
                    job,
                    jobs_dir=jobs_dir,
                    execute=execute,
                    rerun_existing=rerun_existing,
                    command_runner=command_runner,
                )
                records.append(record)
                job_dir = jobs_dir / job.job_name
                if (job_dir / "result.json").exists():
                    observed_job_dirs.append(job_dir)
                    event_log_paths.append(job_dir / EVENT_LOG_FILENAME)

                if method in {"random_branch", "promising_branch"} and job.role == "root":
                    branch_records, branch_job_dirs, branch_reports, branch_events = (
                        _run_branch_continuations(
                            job,
                            manifest=manifest,
                            jobs_dir=jobs_dir,
                            execute=execute,
                            rerun_existing=rerun_existing,
                            experiment_id=manifest.experiment_id,
                            continuation_runner=continuation_runner,
                        )
                    )
                    records.extend(branch_records)
                    observed_job_dirs.extend(branch_job_dirs)
                    continuation_report_paths.extend(branch_reports)
                    event_log_paths.extend(branch_events)

    analysis_tables = None
    if build_analysis and execute:
        analysis_tables = build_analysis_tables(
            AnalysisInputs(
                manifest_path=manifest_path,
                job_dirs=tuple(_dedupe_paths(observed_job_dirs)),
                continuation_report_paths=tuple(_dedupe_paths(continuation_report_paths)),
                event_log_paths=tuple(_dedupe_paths(event_log_paths)),
                jobs_dir=jobs_dir,
            )
        )
        write_analysis_tables(analysis_tables, analysis_dir)

    report = RunExperimentReport(
        experiment_id=manifest.experiment_id,
        manifest_path=manifest_path,
        analysis_dir=analysis_dir if build_analysis else None,
        execution_report_path=execution_report_path,
        budget_enforcement=BUDGET_ENFORCEMENT_PLANNING_ONLY,
        budget_enforcement_description=BUDGET_ENFORCEMENT_DESCRIPTION,
        records=tuple(records),
        job_dirs=tuple(_dedupe_paths(observed_job_dirs)),
        continuation_reports=tuple(_dedupe_paths(continuation_report_paths)),
        event_logs=tuple(_dedupe_paths(event_log_paths)),
        analysis_tables=analysis_tables,
    )
    _write_execution_report(report)
    return report


def format_run_experiment_report(report: RunExperimentReport) -> str:
    lines = [
        f"manifest: {report.manifest_path}",
        f"execution_report: {report.execution_report_path}",
        f"budget_enforcement: {report.budget_enforcement}",
        f"budget_note: {report.budget_enforcement_description}",
    ]
    if report.analysis_tables is not None and report.analysis_dir is not None:
        lines.extend(
            [
                f"run_summary: {report.analysis_dir / 'run-summary.csv'}",
                f"task_summary: {report.analysis_dir / 'task-summary.csv'}",
                f"warnings: {report.analysis_dir / 'warnings.json'}",
                f"run_rows: {len(report.analysis_tables.run_rows)}",
                f"task_rows: {len(report.analysis_tables.task_rows)}",
                f"warnings_count: {len(report.analysis_tables.warnings)}",
            ]
        )
    for record in report.records:
        command = f"\t{shlex.join(record.command)}" if record.command else ""
        lines.append(
            f"{record.method}\t{record.role}\t{record.status}\t{record.job_name}{command}"
        )
        if record.details:
            lines.append(f"  {record.details}")
    return "\n".join(lines)


def _run_planned_job(
    job: PlannedExperimentJob,
    *,
    jobs_dir: Path,
    execute: bool,
    rerun_existing: bool,
    command_runner: CommandRunner,
) -> ExperimentExecutionRecord:
    job_dir = jobs_dir / job.job_name
    if job.executor_status != "ready":
        return _record(job, "skipped_not_ready", job_dir=job_dir)
    if (job_dir / "result.json").exists() and not rerun_existing:
        return _record(job, "skipped_existing", job_dir=job_dir)
    if not job.command:
        return _record(job, "skipped_missing_command", job_dir=job_dir)
    if not execute:
        return _record(job, "planned", job_dir=job_dir)

    if command_runner is subprocess.run:
        result = _run_command_streaming(list(job.command))
    else:
        result = command_runner(
            list(job.command),
            check=False,
            text=True,
            capture_output=True,
        )
    status = "succeeded" if result.returncode == 0 else "failed"
    return _record(
        job,
        status,
        job_dir=job_dir,
        returncode=result.returncode,
        details=_completed_process_details(result) if status == "failed" else None,
    )


def _run_branch_continuations(
    root_job: PlannedExperimentJob,
    *,
    manifest: FixedBudgetManifest,
    jobs_dir: Path,
    execute: bool,
    rerun_existing: bool,
    experiment_id: str,
    continuation_runner: ContinuationRunner,
) -> tuple[
    tuple[ExperimentExecutionRecord, ...],
    tuple[Path, ...],
    tuple[Path, ...],
    tuple[Path, ...],
]:
    root_job_dir = jobs_dir / root_job.job_name
    selector_mode = root_job.selector_mode or (
        "random" if root_job.method == "random_branch" else "archive_priority"
    )
    planned_children = [
        job
        for job in manifest.jobs
        if job.method == root_job.method
        and job.seed == root_job.seed
        and job.role == "continuation"
        and job.parent_run_id == root_job.job_name
    ]
    continuation_count = len(planned_children)
    method_slug = root_job.method.replace("_", "-")
    root_suffix = f"-{method_slug}-seed-{root_job.seed}-root"
    prefix_base = (
        root_job.job_name[: -len(root_suffix)]
        if root_job.job_name.endswith(root_suffix)
        else root_job.job_name.removesuffix("-root")
    )
    continuation_prefix = f"{prefix_base}-{method_slug}-seed-{root_job.seed}"

    if not execute:
        return (
            tuple(
                _record(
                    job,
                    "planned_after_root_archive",
                    job_dir=jobs_dir / job.job_name,
                )
                for job in planned_children
            ),
            (),
            (),
            (),
        )

    if not (root_job_dir / "result.json").exists():
        return (
            (
                _record(
                    root_job,
                    "skipped_missing_root_result",
                    job_dir=root_job_dir,
                    details="branch continuations need a completed root job",
                ),
            ),
            (),
            (),
            (),
        )
    archive_path = root_job_dir / ARCHIVE_FILENAME
    archive = SnapshotArchive.load(archive_path)
    if not archive_path.exists():
        return (
            (
                _record(
                    root_job,
                    "skipped_missing_archive",
                    job_dir=root_job_dir,
                    details=f"{archive_path} does not exist",
                ),
            ),
            (),
            (),
            (),
        )
    if not len(archive):
        return (
            (
                _record(
                    root_job,
                    "skipped_empty_archive",
                    job_dir=root_job_dir,
                    details=f"{archive_path} has no snapshots",
                ),
            ),
            (),
            (),
            (),
        )

    chosen = select_archive_entries(
        archive,
        mode=selector_mode,
        k=continuation_count,
        seed=root_job.seed if selector_mode == "random" else None,
    )
    for selection in chosen:
        archive.mark_selected(selection.entry.cell_key)
    archive.save()

    selection_metadata = tuple(
        SnapshotSelectionMetadata(
            snapshot_name=selection.entry.snapshot_name,
            selector_mode=selection.selector_mode,
            cell_key=selection.entry.cell_key,
            priority=selection.entry.priority,
            score=selection.entry.score,
            times_selected=selection.entry.times_selected,
            selector_reasons=selection.selector_reasons,
        )
        for selection in chosen
    )
    snapshots = tuple(selection.entry.snapshot_name for selection in chosen)
    root_summary = summarize_job(root_job_dir)
    root_trial = select_trial(root_summary)
    root_config = harbor_config_from_job(root_job_dir)
    event_log_path = root_job_dir / EVENT_LOG_FILENAME
    branch_context_mode = (
        planned_children[0].context_mode if planned_children else "parent_summary"
    )
    plans = plan_snapshot_continuations(
        root_config=root_config,
        root_summary=root_summary,
        snapshots=snapshots,
        continuation_job_prefix=continuation_prefix,
        max_snapshots=None,
        parent_trial_name=root_trial.trial_name,
        event_log_path=event_log_path,
        experiment_id=experiment_id,
        selector_mode=selector_mode,
        selection_metadata=selection_metadata,
        context_mode=branch_context_mode,
    )

    records = [
        ExperimentExecutionRecord(
            job_name=plan.job_name,
            method=root_job.method,
            role="continuation",
            status="skipped_existing"
            if (root_job_dir.parent / plan.job_name / "result.json").exists()
            and not rerun_existing
            else "planned",
            job_dir=str(root_job_dir.parent / plan.job_name),
            command=plan.command,
        )
        for plan in plans
    ]
    if not execute:
        return (tuple(records), (), (), (event_log_path,))

    plan_job_dirs = tuple(root_job_dir.parent / plan.job_name for plan in plans)
    runnable_plans = [
        plan
        for plan in plans
        if rerun_existing or not (root_job_dir.parent / plan.job_name / "result.json").exists()
    ]
    report_path = root_job_dir / "continuation-report.json"
    report = None
    if runnable_plans:
        report = continuation_runner(
            runnable_plans,
            root_summary=root_summary,
            root_trial=root_trial,
            report_path=report_path,
            event_log_path=event_log_path,
            experiment_id=experiment_id,
        )
    executed_by_job = {
        Path(attempt.continuation_job_dir).name: attempt for attempt in report.attempts
    } if report is not None else {}
    final_records = []
    for record in records:
        attempt = executed_by_job.get(record.job_name)
        if attempt is None and record.status == "skipped_existing":
            final_records.append(record)
            continue
        status = "succeeded"
        details = None
        if attempt is None:
            status = "skipped_existing"
        elif attempt.exception_type:
            status = "failed"
            details = attempt.exception_type
        final_records.append(
            ExperimentExecutionRecord(
                job_name=record.job_name,
                method=record.method,
                role=record.role,
                status=status,
                job_dir=record.job_dir,
                command=record.command,
                details=details,
            )
        )

    continuation_job_dirs = _dedupe_paths(
        tuple(Path(attempt.continuation_job_dir) for attempt in executed_by_job.values())
        + tuple(path for path in plan_job_dirs if (path / "result.json").exists())
    )
    report_paths = (report_path,) if report_path.exists() else ()
    return (
        tuple(final_records),
        continuation_job_dirs,
        report_paths,
        (event_log_path,),
    )


def _record(
    job: PlannedExperimentJob,
    status: str,
    *,
    job_dir: Path,
    returncode: int | None = None,
    details: str | None = None,
) -> ExperimentExecutionRecord:
    return ExperimentExecutionRecord(
        job_name=job.job_name,
        method=job.method,
        role=job.role,
        status=status,
        job_dir=str(job_dir),
        command=job.command,
        returncode=returncode,
        details=details,
    )


def _run_command_streaming(command: list[str]) -> subprocess.CompletedProcess[str]:
    output_tail: deque[str] = deque(maxlen=400)
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=environment_with_repo_path(),
    )
    assert process.stdout is not None
    for line in process.stdout:
        print(line, end="", flush=True)
        output_tail.append(line)
    returncode = process.wait()
    return subprocess.CompletedProcess(
        command,
        returncode,
        stdout="".join(output_tail),
        stderr=None,
    )


def _completed_process_details(result: subprocess.CompletedProcess[str]) -> str | None:
    output = "\n".join(
        part.strip()
        for part in (result.stdout, result.stderr)
        if isinstance(part, str) and part.strip()
    )
    return output or None


def _write_execution_report(report: RunExperimentReport) -> None:
    report.execution_report_path.parent.mkdir(parents=True, exist_ok=True)
    report.execution_report_path.write_text(
        json.dumps(
            {
                "schema_version": "go-explore-experiment-execution-v1",
                "experiment_id": report.experiment_id,
                "manifest_path": str(report.manifest_path),
                "analysis_dir": str(report.analysis_dir) if report.analysis_dir else None,
                "budget_enforcement": report.budget_enforcement,
                "budget_enforcement_description": (
                    report.budget_enforcement_description
                ),
                "job_dirs": [str(path) for path in report.job_dirs],
                "continuation_reports": [
                    str(path) for path in report.continuation_reports
                ],
                "event_logs": [str(path) for path in report.event_logs],
                "records": [asdict(record) for record in report.records],
            },
            indent=2,
        )
        + "\n"
    )


def _dedupe_paths(paths: Sequence[Path]) -> tuple[Path, ...]:
    deduped: dict[str, Path] = {}
    for path in paths:
        deduped.setdefault(str(path), path)
    return tuple(deduped.values())
