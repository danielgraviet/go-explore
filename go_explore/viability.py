from __future__ import annotations

import json
import shlex
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from go_explore.analysis_tables import (
    AnalysisInputs,
    AnalysisTables,
    build_analysis_tables,
    write_analysis_tables,
)
from go_explore.experiment_runner import (
    CommandRunner,
    ContinuationRunner,
    RunExperimentReport,
    format_run_experiment_report,
    run_fixed_budget_manifest,
)
from go_explore.fixed_budget import (
    DEFAULT_BRANCH_CONTEXT_MODE,
    BUDGET_ENFORCEMENT_DESCRIPTION,
    BUDGET_ENFORCEMENT_PLANNING_ONLY,
    ExperimentMethod,
    FixedBudgetManifest,
    FixedBudgetPlanConfig,
    load_fixed_budget_manifest,
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
    n_branch_continuations: int = 3
    branch_root_fraction: float = 0.3
    promising_selector_mode: str = "archive_priority"
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


@dataclass(frozen=True)
class ViabilityPilotRunConfig:
    plan_path: Path
    jobs_dir: Path = Path("jobs")
    analysis_dir: Path | None = None
    memo_path: Path = Path("docs/experiments/viability-pilot.md")
    execute: bool = False
    rerun_existing: bool = False
    build_analysis: bool = True
    tmux_session: str = "phase6-viability-pilot"


@dataclass(frozen=True)
class ViabilityPilotRunReport:
    experiment_id: str
    plan_path: Path
    analysis_dir: Path
    combined_manifest_path: Path
    execution_report_path: Path
    memo_path: Path
    execute: bool
    reports: tuple[RunExperimentReport, ...]
    job_dirs: tuple[Path, ...]
    continuation_reports: tuple[Path, ...]
    event_logs: tuple[Path, ...]
    analysis_tables: AnalysisTables | None
    tmux_session: str

    @property
    def has_infrastructure_failures(self) -> bool:
        return any(report.has_infrastructure_failures for report in self.reports)


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


def load_viability_plan(path: Path) -> ViabilityPlan:
    with path.open() as file:
        data = json.load(file)

    output_dir = Path(data.get("output_dir") or path.parent)
    records: list[ViabilityManifestRecord] = []
    for raw in data.get("records") or ():
        manifest_path = Path(raw["manifest_path"])
        manifest = load_fixed_budget_manifest(manifest_path)
        records.append(
            ViabilityManifestRecord(
                task_id=str(raw["task_id"]),
                arm=str(raw["arm"]),
                context_mode=str(raw["context_mode"]),
                manifest_path=manifest_path,
                manifest=manifest,
            )
        )

    return ViabilityPlan(
        experiment_id=str(data.get("experiment_id") or path.stem),
        output_dir=output_dir,
        records=tuple(records),
        index_path=path,
    )


def run_viability_pilot(
    config: ViabilityPilotRunConfig,
    *,
    command_runner: CommandRunner = subprocess.run,
    continuation_runner: ContinuationRunner | None = None,
) -> ViabilityPilotRunReport:
    plan = load_viability_plan(config.plan_path)
    analysis_dir = config.analysis_dir or (plan.output_dir / "analysis")
    execution_report_path = analysis_dir / "execution-report.json"
    combined_manifest_path = analysis_dir / "pilot-combined-manifest.json"

    reports: list[RunExperimentReport] = []
    for record in plan.records:
        record_analysis_dir = analysis_dir / "arms" / _slug(
            f"{record.task_id}-{record.arm}"
        )
        kwargs: dict[str, Any] = {
            "manifest_path": record.manifest_path,
            "jobs_dir": config.jobs_dir,
            "analysis_dir": record_analysis_dir,
            "execute": config.execute,
            "rerun_existing": config.rerun_existing,
            "build_analysis": False,
            "command_runner": command_runner,
        }
        if continuation_runner is not None:
            kwargs["continuation_runner"] = continuation_runner
        reports.append(run_fixed_budget_manifest(record.manifest, **kwargs))

    job_dirs = _dedupe_paths(
        path for report in reports for path in report.job_dirs
    )
    continuation_reports = _dedupe_paths(
        path for report in reports for path in report.continuation_reports
    )
    event_logs = _dedupe_paths(path for report in reports for path in report.event_logs)
    _write_combined_manifest(plan, combined_manifest_path)

    analysis_tables = None
    if config.build_analysis:
        analysis_tables = build_analysis_tables(
            AnalysisInputs(
                manifest_path=combined_manifest_path,
                job_dirs=job_dirs,
                continuation_report_paths=continuation_reports,
                event_log_paths=event_logs,
                jobs_dir=config.jobs_dir,
            )
        )
        write_analysis_tables(analysis_tables, analysis_dir)

    report = ViabilityPilotRunReport(
        experiment_id=plan.experiment_id,
        plan_path=config.plan_path,
        analysis_dir=analysis_dir,
        combined_manifest_path=combined_manifest_path,
        execution_report_path=execution_report_path,
        memo_path=config.memo_path,
        execute=config.execute,
        reports=tuple(reports),
        job_dirs=job_dirs,
        continuation_reports=continuation_reports,
        event_logs=event_logs,
        analysis_tables=analysis_tables,
        tmux_session=config.tmux_session,
    )
    _write_viability_execution_report(report)
    write_viability_pilot_memo(report)
    return report


def format_viability_pilot_report(report: ViabilityPilotRunReport) -> str:
    lines = [
        f"plan: {report.plan_path}",
        f"execution_report: {report.execution_report_path}",
        f"combined_manifest: {report.combined_manifest_path}",
        f"memo: {report.memo_path}",
        f"budget_enforcement: {BUDGET_ENFORCEMENT_PLANNING_ONLY}",
        f"budget_note: {BUDGET_ENFORCEMENT_DESCRIPTION}",
        f"execute: {report.execute}",
        f"manifest_count: {len(report.reports)}",
        f"job_dirs: {len(report.job_dirs)}",
        f"continuation_reports: {len(report.continuation_reports)}",
        f"event_logs: {len(report.event_logs)}",
    ]
    if report.analysis_tables is not None:
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
    for arm_report in report.reports:
        lines.append("")
        lines.append(format_run_experiment_report(arm_report))
    return "\n".join(lines)


def write_viability_pilot_memo(report: ViabilityPilotRunReport) -> None:
    report.memo_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Phase 6 Viability Pilot",
        "",
        "## Status",
        "",
        (
            "Executed pilot run."
            if report.execute
            else "Dry-run/planning pass; no paid Harbor jobs were executed."
        ),
        "",
        "## Artifacts",
        "",
        f"- Plan: `{report.plan_path}`",
        f"- Combined analysis manifest: `{report.combined_manifest_path}`",
        f"- Execution report: `{report.execution_report_path}`",
        f"- Run summary: `{report.analysis_dir / 'run-summary.csv'}`",
        f"- Task summary: `{report.analysis_dir / 'task-summary.csv'}`",
        f"- Warnings: `{report.analysis_dir / 'warnings.json'}`",
        "",
        "## Tmux",
        "",
        "Launch command for this report:",
        "",
        "```bash",
        _tmux_launch_command(report),
        "```",
    ]
    if not report.execute:
        lines.extend(
            [
                "",
                "Paid execution command:",
                "",
                "```bash",
                _tmux_launch_command(report, execute=True),
                "```",
            ]
        )
    lines.extend(
        [
            "",
            "Attach command:",
            "",
            "```bash",
            f"tmux attach -t {shlex.quote(report.tmux_session)}",
            "```",
            "",
            "## Pilot Coverage",
            "",
            f"- Manifest arms: {len(report.reports)}",
            f"- Observed job directories: {len(report.job_dirs)}",
            f"- Continuation reports: {len(report.continuation_reports)}",
            f"- Event logs: {len(report.event_logs)}",
        ]
    )
    failure_details = _failure_details(report)
    if failure_details:
        lines.extend(
            [
                "",
                "## Infrastructure Failures",
                "",
                *[f"- {detail}" for detail in failure_details],
            ]
        )
    if report.analysis_tables is not None:
        lines.extend(
            [
                f"- Analysis run rows: {len(report.analysis_tables.run_rows)}",
                f"- Analysis task rows: {len(report.analysis_tables.task_rows)}",
                f"- Analysis warnings: {len(report.analysis_tables.warnings)}",
                "",
                "## Decision",
                "",
                _pilot_decision(report),
            ]
        )
    report.memo_path.write_text("\n".join(lines) + "\n")


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
                promising_selector_mode=config.promising_selector_mode,
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


def _write_combined_manifest(plan: ViabilityPlan, path: Path) -> None:
    jobs: list[dict[str, Any]] = []
    methods: list[str] = []
    seeds: list[int] = []
    models: set[str] = set()
    total_token_budget = 0
    has_token_budget = False
    for record in plan.records:
        raw_manifest = record.manifest.to_json_dict()
        if record.manifest.model:
            models.add(record.manifest.model)
        if record.manifest.total_token_budget is not None:
            total_token_budget += record.manifest.total_token_budget
            has_token_budget = True
        for method in raw_manifest.get("methods") or ():
            if method not in methods:
                methods.append(method)
        for seed in raw_manifest.get("seeds") or ():
            if seed not in seeds:
                seeds.append(seed)
        for job in raw_manifest.get("jobs") or ():
            job = dict(job)
            job["experiment_id"] = record.manifest.experiment_id
            job["task_id"] = record.task_id
            job["model"] = record.manifest.model
            job["viability_arm"] = record.arm
            jobs.append(job)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "go-explore-fixed-budget-plan-v1",
                "experiment_id": plan.experiment_id,
                "task_id": None,
                "model": next(iter(models)) if len(models) == 1 else None,
                "budget": {
                    "total_token_budget": (
                        total_token_budget if has_token_budget else None
                    ),
                    "enforcement": BUDGET_ENFORCEMENT_PLANNING_ONLY,
                    "enforcement_description": BUDGET_ENFORCEMENT_DESCRIPTION,
                },
                "methods": methods,
                "seeds": sorted(seeds),
                "jobs": jobs,
            },
            indent=2,
        )
        + "\n"
    )


def _write_viability_execution_report(report: ViabilityPilotRunReport) -> None:
    report.execution_report_path.parent.mkdir(parents=True, exist_ok=True)
    report.execution_report_path.write_text(
        json.dumps(
            {
                "schema_version": "go-explore-viability-pilot-execution-v1",
                "experiment_id": report.experiment_id,
                "plan_path": str(report.plan_path),
                "analysis_dir": str(report.analysis_dir),
                "combined_manifest_path": str(report.combined_manifest_path),
                "memo_path": str(report.memo_path),
                "execute": report.execute,
                "budget_enforcement": BUDGET_ENFORCEMENT_PLANNING_ONLY,
                "budget_enforcement_description": BUDGET_ENFORCEMENT_DESCRIPTION,
                "job_dirs": [str(path) for path in report.job_dirs],
                "continuation_reports": [
                    str(path) for path in report.continuation_reports
                ],
                "event_logs": [str(path) for path in report.event_logs],
                "records": [
                    {
                        "experiment_id": arm_report.experiment_id,
                        "manifest_path": str(arm_report.manifest_path),
                        "execution_report_path": str(arm_report.execution_report_path),
                        "records": [
                            asdict(record) for record in arm_report.records
                        ],
                    }
                    for arm_report in report.reports
                ],
            },
            indent=2,
        )
        + "\n"
    )


def _tmux_launch_command(
    report: ViabilityPilotRunReport,
    *,
    execute: bool | None = None,
) -> str:
    should_execute = report.execute if execute is None else execute
    command = [
        ".venv/bin/python",
        "-m",
        "go_explore.cli",
        "run-viability-pilot",
        "--plan",
        str(report.plan_path),
        "--analysis-dir",
        str(report.analysis_dir),
        "--memo-path",
        str(report.memo_path),
        "--tmux-session",
        report.tmux_session,
    ]
    if should_execute:
        command.append("--execute")
    inner_command = (
        "set -a; source .env; set +a; "
        'export PATH="$HOME/.local/bin:$PATH"; '
        'export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"; '
        f"{shlex.join(command)}"
    )
    return (
        f"tmux new-session -d -s {shlex.quote(report.tmux_session)} "
        f"{shlex.quote(inner_command)}"
    )


def _pilot_decision(report: ViabilityPilotRunReport) -> str:
    if report.analysis_tables is None:
        return "Analysis tables were not built; no full-batch decision recorded."
    missing = sum(
        1
        for row in report.analysis_tables.run_rows
        if row.get("outcome") == "missing_result"
    )
    if not report.execute:
        return "Do not launch the full batch from this dry run; execute the pilot first."
    if report.has_infrastructure_failures or missing:
        return (
            "Do not launch the full batch unchanged; resolve infrastructure failures "
            "or missing planned rows first."
        )
    return (
        "Pilot artifacts are complete enough to inspect solve rate, cost, tokens, "
        "snapshot overhead, and restore overhead before choosing full-batch arms."
    )


def _failure_details(report: ViabilityPilotRunReport) -> tuple[str, ...]:
    details: list[str] = []
    for arm_report in report.reports:
        for record in arm_report.records:
            if record.status in {"failed", "skipped_missing_root_result"}:
                detail = " ".join((record.details or record.status).split())
                if detail not in details:
                    details.append(detail)
            if len(details) >= 3:
                return tuple(details)
    return tuple(details)


def _dedupe_paths(paths: Iterable[Path]) -> tuple[Path, ...]:
    deduped: dict[str, Path] = {}
    for path in paths:
        deduped.setdefault(str(path), path)
    return tuple(deduped.values())
