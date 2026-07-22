from __future__ import annotations

import argparse
import shlex
from pathlib import Path

from go_explore.analysis_tables import (
    AnalysisInputs,
    build_analysis_tables,
    write_analysis_tables,
)
from go_explore.continuations import (
    SnapshotSelectionMetadata,
    harbor_config_from_job,
    list_daytona_snapshots_for_trial_sync,
    plan_start_state_baselines,
    plan_snapshot_continuations,
    run_continuation_plans,
    select_trial,
    write_plan_manifest,
)
from go_explore.events import EVENT_LOG_FILENAME
from go_explore.experiment_runner import (
    RunExperimentConfig,
    format_run_experiment_report,
    run_fixed_budget_experiment,
)
from go_explore.fixed_budget import (
    FixedBudgetPlanConfig,
    plan_fixed_budget_runs,
    write_fixed_budget_manifest,
)
from go_explore.figure_tables import (
    FigureTableInputs,
    build_figure_tables,
    write_figure_tables,
)
from go_explore.harbor import HarborRunConfig, run_harbor
from go_explore.results import format_job_summary, summarize_job
from go_explore.snapshots.archive import ARCHIVE_FILENAME, SnapshotArchive
from go_explore.snapshots.selectors import load_oracle_labels, select_archive_entries
from go_explore.task_inventory import load_cached_tasks


def _add_harbor_args(parser: argparse.ArgumentParser) -> None:
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--dataset", help="Registered Harbor dataset name, optionally with @version.")
    source.add_argument("--path", type=Path, help="Local Harbor task or dataset path.")
    parser.add_argument("--jobs-dir", type=Path, default=Path("jobs"))
    parser.add_argument("--task-name")
    parser.add_argument("--n-tasks", type=int)
    parser.add_argument("--n-attempts", type=int, default=1)
    parser.add_argument("--n-concurrent", type=int, default=1)
    parser.add_argument("--env", default="docker")
    parser.add_argument("--model")
    parser.add_argument("--job-name")
    parser.add_argument("--execute", action="store_true", help="Run Harbor instead of printing the command.")


def oracle_run(args: argparse.Namespace) -> int:
    config = HarborRunConfig(
        jobs_dir=args.jobs_dir,
        agent="oracle",
        env=args.env,
        dataset=args.dataset,
        path=args.path,
        model=args.model,
        task_name=args.task_name,
        n_tasks=args.n_tasks,
        n_attempts=args.n_attempts,
        n_concurrent=args.n_concurrent,
        job_name=args.job_name,
    )

    result = run_harbor(config, dry_run=not args.execute)
    if isinstance(result, list):
        print(shlex.join(result))
        return 0
    return result.returncode


def summarize(args: argparse.Namespace) -> int:
    print(format_job_summary(summarize_job(args.job_dir)))
    return 0


def list_cached_tasks(args: argparse.Namespace) -> int:
    tasks = load_cached_tasks(args.cache_dir)
    for task in tasks:
        print(
            f"{task.name}\t{task.difficulty or '-'}\t{task.category or '-'}"
            f"\tagent_timeout={task.agent_timeout_sec}"
            f"\tverifier_timeout={task.verifier_timeout_sec}"
        )
    return 0


def continue_from_snapshots(args: argparse.Namespace) -> int:
    root_summary = summarize_job(args.root_job_dir)
    root_trial = select_trial(root_summary, args.trial_name)
    root_config = harbor_config_from_job(
        args.root_job_dir,
        agent=args.agent,
        model=args.model,
        extra_args=tuple(args.extra_arg),
    )

    snapshots = tuple(args.snapshot)
    selector_mode = "explicit"
    selection_metadata: tuple[SnapshotSelectionMetadata, ...] = ()
    plan_max_snapshots = args.max_snapshots
    if not snapshots and args.from_archive:
        archive_path = args.archive_path or args.root_job_dir / ARCHIVE_FILENAME
        archive = SnapshotArchive.load(archive_path)
        if not len(archive):
            print(f"Archive {archive_path} is empty or missing.")
            return 1
        oracle_labels = (
            load_oracle_labels(args.oracle_labels) if args.oracle_labels else None
        )
        try:
            chosen = select_archive_entries(
                archive,
                mode=args.selector_mode,
                k=args.max_snapshots or 3,
                seed=args.selector_seed,
                oracle_labels=oracle_labels,
            )
        except ValueError as error:
            print(str(error))
            return 1
        snapshots = tuple(selection.entry.snapshot_name for selection in chosen)
        plan_max_snapshots = None
        selector_mode = args.selector_mode
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
        print(f"archive: {archive_path} ({len(archive)} cells)")
        for selection in chosen:
            entry = selection.entry
            print(
                f"  select {entry.snapshot_name}"
                f"  mode={selection.selector_mode}"
                f"  cell={entry.cell_key}"
                f"  priority={entry.priority:.2f}"
                f"  score={entry.score:.2f}"
            )
        # Record the fork so a later run rotates to the rest of the frontier
        # instead of picking these same cells again.
        for selection in chosen:
            archive.mark_selected(selection.entry.cell_key)
        archive.save()
    if not snapshots:
        snapshots = tuple(
            list_daytona_snapshots_for_trial_sync(
                root_trial.trial_name,
                name_prefix=args.snapshot_prefix,
            )
        )
        selector_mode = "daytona_list"

    event_log_path = args.root_job_dir / EVENT_LOG_FILENAME
    plans = plan_snapshot_continuations(
        root_config=root_config,
        root_summary=root_summary,
        snapshots=snapshots,
        continuation_job_prefix=args.job_prefix,
        agent=args.agent,
        model=args.model,
        max_snapshots=plan_max_snapshots,
        parent_trial_name=root_trial.trial_name,
        event_log_path=event_log_path,
        selector_mode=selector_mode,
        selection_metadata=selection_metadata,
        context_mode=getattr(args, "context_mode", "parent_summary"),
    )

    if not plans:
        print(f"No continuation plans for trial {root_trial.trial_name}.")
        return 1

    if not args.execute:
        for plan in plans:
            print(shlex.join(plan.command))
        return 0

    report_path = args.report_path or args.root_job_dir / "continuation-report.json"
    report = run_continuation_plans(
        plans,
        root_summary=root_summary,
        root_trial=root_trial,
        report_path=report_path,
        event_log_path=event_log_path,
    )
    print(f"continuation_report: {report_path}")
    print(f"attempts: {len(report.attempts)}")
    print(f"any_success: {report.any_success}")
    return 0 if report.any_success else 1


def plan_start_state_baselines_cmd(args: argparse.Namespace) -> int:
    root_summary = summarize_job(args.root_job_dir)
    root_trial = select_trial(root_summary, args.trial_name)
    root_config = harbor_config_from_job(
        args.root_job_dir,
        agent=args.agent,
        model=args.model,
        extra_args=tuple(args.extra_arg),
    )

    snapshots = tuple(args.snapshot)
    if not snapshots and args.from_archive:
        archive_path = args.archive_path or args.root_job_dir / ARCHIVE_FILENAME
        archive = SnapshotArchive.load(archive_path)
        if not len(archive):
            print(f"Archive {archive_path} is empty or missing.")
            return 1
        oracle_labels = (
            load_oracle_labels(args.oracle_labels) if args.oracle_labels else None
        )
        try:
            chosen = select_archive_entries(
                archive,
                mode=args.selector_mode,
                k=args.max_snapshots or 3,
                seed=args.selector_seed,
                oracle_labels=oracle_labels,
            )
        except ValueError as error:
            print(str(error))
            return 1
        snapshots = tuple(selection.entry.snapshot_name for selection in chosen)

    start_state_types = tuple(
        args.start_state_type or ("clean", "diff_only", "full_snapshot")
    )
    if "full_snapshot" in start_state_types and not snapshots:
        print("Full snapshot planning requires --snapshot or --from-archive.")
        return 1

    plans = plan_start_state_baselines(
        root_config=root_config,
        root_summary=root_summary,
        continuation_job_prefix=args.job_prefix,
        start_state_types=start_state_types,
        snapshots=snapshots,
        diff_path=args.diff_path,
        agent=args.agent,
        model=args.model,
        max_snapshots=args.max_snapshots,
        parent_trial_name=root_trial.trial_name,
    )

    if args.manifest_path:
        write_plan_manifest(plans, args.manifest_path)
        print(f"manifest: {args.manifest_path}")

    for plan in plans:
        print(
            f"{plan.start_state_type}\t{plan.context_mode}\t"
            f"{plan.executor_status}\t{plan.job_name}"
        )
        print(shlex.join(plan.command))
    return 0


def plan_fixed_budget(args: argparse.Namespace) -> int:
    agent = args.agent
    if agent is None and args.agent_import_path is None:
        agent = "terminus-2"

    base_config = HarborRunConfig(
        jobs_dir=args.jobs_dir,
        agent=agent,
        agent_import_path=args.agent_import_path,
        env=args.env,
        dataset=args.dataset,
        path=args.path,
        model=args.model,
        task_name=args.task_name,
        n_tasks=1,
        n_attempts=1,
        n_concurrent=1,
        export_traces=True,
        extra_args=tuple(args.extra_arg),
    )
    manifest = plan_fixed_budget_runs(
        FixedBudgetPlanConfig(
            experiment_id=args.experiment_id,
            base_config=base_config,
            job_prefix=args.job_prefix,
            total_token_budget=args.total_token_budget,
            methods=tuple(
                args.method or ("single", "retry", "random_branch", "promising_branch")
            ),
            seeds=tuple(args.seed or (0,)),
            n_retries=args.n_retries,
            n_branch_continuations=args.n_branch_continuations,
            branch_root_fraction=args.branch_root_fraction,
            snapshots=tuple(args.snapshot),
            branch_context_mode=args.branch_context_mode,
        )
    )

    write_fixed_budget_manifest(manifest, args.manifest_path)
    print(f"manifest: {args.manifest_path}")
    for job in manifest.jobs:
        print(
            f"{job.method}\t{job.role}\tseed={job.seed}\t"
            f"budget={job.budget.token_budget}\t{job.executor_status}\t"
            f"{job.job_name}"
        )
        if job.command:
            print(shlex.join(job.command))
    return 0


def build_analysis_tables_cmd(args: argparse.Namespace) -> int:
    tables = build_analysis_tables(
        AnalysisInputs(
            manifest_path=args.manifest,
            job_dirs=tuple(args.job_dir),
            continuation_report_paths=tuple(args.continuation_report),
            event_log_paths=tuple(args.event_log),
            repeated_work_report_paths=tuple(args.repeated_work_report),
            jobs_dir=args.jobs_dir,
            include_missing_planned=not args.only_observed_runs,
        )
    )
    write_analysis_tables(tables, args.output_dir)
    print(f"run_summary: {args.output_dir / 'run-summary.csv'}")
    print(f"task_summary: {args.output_dir / 'task-summary.csv'}")
    print(f"warnings: {args.output_dir / 'warnings.json'}")
    print(f"run_rows: {len(tables.run_rows)}")
    print(f"task_rows: {len(tables.task_rows)}")
    print(f"warnings_count: {len(tables.warnings)}")
    return 0


def build_figure_tables_cmd(args: argparse.Namespace) -> int:
    report = build_figure_tables(
        FigureTableInputs(
            task_summary_paths=tuple(args.task_summary),
            run_summary_paths=tuple(args.run_summary),
            execution_status_path=args.execution_status,
        )
    )
    write_figure_tables(report, args.output_dir)
    print(f"figure_dir: {args.output_dir}")
    print(f"figure_status: {args.output_dir / 'figure-status.csv'}")
    for status in report.statuses:
        print(
            f"{status['figure']}\t{status['status']}\t"
            f"rows={status['source_rows']}"
        )
    return 0


def run_experiment_cmd(args: argparse.Namespace) -> int:
    agent = args.agent
    agent_import_path = args.agent_import_path
    if agent is None and agent_import_path is None:
        agent_import_path = "go_explore.agents.factory:SnapshotAwareTerminus2"

    base_config = HarborRunConfig(
        jobs_dir=args.jobs_dir,
        agent=agent,
        agent_import_path=agent_import_path,
        env=args.env,
        dataset=args.dataset,
        path=args.path,
        model=args.model,
        task_name=args.task_name,
        n_tasks=1,
        n_attempts=1,
        n_concurrent=1,
        export_traces=True,
        extra_args=tuple(args.extra_arg),
    )
    report = run_fixed_budget_experiment(
        RunExperimentConfig(
            experiment_id=args.experiment_id,
            base_config=base_config,
            total_token_budget=args.total_token_budget,
            methods=tuple(
                args.method or ("single", "retry", "random_branch", "promising_branch")
            ),
            seeds=tuple(args.seed or (0,)),
            job_prefix=args.job_prefix,
            manifest_path=args.manifest_path,
            analysis_dir=args.analysis_dir,
            n_retries=args.n_retries,
            n_branch_continuations=args.n_branch_continuations,
            branch_root_fraction=args.branch_root_fraction,
            branch_context_mode=args.branch_context_mode,
            execute=args.execute,
            rerun_existing=args.rerun_existing,
            build_analysis=not args.no_analysis,
        )
    )
    print(format_run_experiment_report(report))
    return 1 if args.execute and report.has_infrastructure_failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="go-explore")
    subparsers = parser.add_subparsers(dest="command", required=True)

    oracle = subparsers.add_parser("oracle-run", help="Run or print a Harbor oracle baseline command.")
    _add_harbor_args(oracle)
    oracle.set_defaults(func=oracle_run)

    summarize_parser = subparsers.add_parser("summarize-job", help="Summarize a Harbor job result directory.")
    summarize_parser.add_argument("job_dir", type=Path)
    summarize_parser.set_defaults(func=summarize)

    task_parser = subparsers.add_parser("list-cached-tasks", help="List Harbor tasks already present in the local cache.")
    task_parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path.home() / ".cache" / "harbor" / "tasks",
    )
    task_parser.set_defaults(func=list_cached_tasks)

    continue_parser = subparsers.add_parser(
        "continue-from-snapshots",
        help="Run continuation jobs from Daytona snapshots for one Harbor trial.",
    )
    continue_parser.add_argument("root_job_dir", type=Path)
    continue_parser.add_argument("--trial-name")
    continue_parser.add_argument("--snapshot", action="append", default=[])
    continue_parser.add_argument("--snapshot-prefix", default="go-explore")
    continue_parser.add_argument(
        "--from-archive",
        action="store_true",
        help="Pick snapshots from archive.json instead of listing Daytona.",
    )
    continue_parser.add_argument(
        "--selector-mode",
        choices=("archive_priority", "list_order", "random", "oracle"),
        default="archive_priority",
        help="Archive selector policy used with --from-archive.",
    )
    continue_parser.add_argument(
        "--selector-seed",
        type=int,
        help="Seed for --selector-mode random.",
    )
    continue_parser.add_argument(
        "--oracle-labels",
        type=Path,
        help=(
            "JSON object mapping snapshot names or archive cell keys to oracle "
            "scores for --selector-mode oracle."
        ),
    )
    continue_parser.add_argument(
        "--archive-path",
        type=Path,
        help="Archive JSON path (default: <root_job_dir>/archive.json).",
    )
    continue_parser.add_argument("--job-prefix", required=True)
    continue_parser.add_argument("--max-snapshots", type=int)
    continue_parser.add_argument("--agent")
    continue_parser.add_argument("--model")
    continue_parser.add_argument("--extra-arg", action="append", default=[])
    continue_parser.add_argument(
        "--context-mode",
        choices=("parent_summary", "none"),
        default="parent_summary",
        help="Parent context mode for full-snapshot continuation jobs.",
    )
    continue_parser.add_argument("--report-path", type=Path)
    continue_parser.add_argument(
        "--execute",
        action="store_true",
        help="Run Harbor continuation jobs instead of printing commands.",
    )
    continue_parser.set_defaults(func=continue_from_snapshots)

    start_state_parser = subparsers.add_parser(
        "plan-start-state-baselines",
        help="Plan clean, diff-only, and full-snapshot baseline child jobs.",
    )
    start_state_parser.add_argument("root_job_dir", type=Path)
    start_state_parser.add_argument("--trial-name")
    start_state_parser.add_argument(
        "--start-state-type",
        action="append",
        choices=("clean", "diff_only", "full_snapshot"),
        help="Start-state mode to include. Repeat to plan multiple modes.",
    )
    start_state_parser.add_argument("--snapshot", action="append", default=[])
    start_state_parser.add_argument(
        "--from-archive",
        action="store_true",
        help="Use archive.json to choose snapshots for full-snapshot plans.",
    )
    start_state_parser.add_argument(
        "--selector-mode",
        choices=("archive_priority", "list_order", "random", "oracle"),
        default="archive_priority",
        help="Archive selector policy used with --from-archive.",
    )
    start_state_parser.add_argument("--selector-seed", type=int)
    start_state_parser.add_argument("--oracle-labels", type=Path)
    start_state_parser.add_argument("--archive-path", type=Path)
    start_state_parser.add_argument("--diff-path", type=Path)
    start_state_parser.add_argument("--manifest-path", type=Path)
    start_state_parser.add_argument("--job-prefix", required=True)
    start_state_parser.add_argument("--max-snapshots", type=int)
    start_state_parser.add_argument("--agent")
    start_state_parser.add_argument("--model")
    start_state_parser.add_argument("--extra-arg", action="append", default=[])
    start_state_parser.set_defaults(func=plan_start_state_baselines_cmd)

    fixed_budget_parser = subparsers.add_parser(
        "plan-fixed-budget",
        help="Expand fixed-budget method settings into a dry-run manifest.",
    )
    fixed_source = fixed_budget_parser.add_mutually_exclusive_group(required=True)
    fixed_source.add_argument(
        "--dataset",
        help="Registered Harbor dataset name, optionally with @version.",
    )
    fixed_source.add_argument(
        "--path",
        type=Path,
        help="Local Harbor task or dataset path.",
    )
    fixed_budget_parser.add_argument("--jobs-dir", type=Path, default=Path("jobs"))
    fixed_budget_parser.add_argument("--task-name")
    fixed_budget_parser.add_argument("--env", default="daytona")
    fixed_budget_parser.add_argument("--model")
    fixed_agent = fixed_budget_parser.add_mutually_exclusive_group()
    fixed_agent.add_argument("--agent")
    fixed_agent.add_argument("--agent-import-path")
    fixed_budget_parser.add_argument("--extra-arg", action="append", default=[])
    fixed_budget_parser.add_argument("--experiment-id", required=True)
    fixed_budget_parser.add_argument("--job-prefix", required=True)
    fixed_budget_parser.add_argument("--manifest-path", type=Path, required=True)
    fixed_budget_parser.add_argument("--total-token-budget", type=int)
    fixed_budget_parser.add_argument(
        "--method",
        action="append",
        choices=("single", "retry", "random_branch", "promising_branch"),
        default=[],
        help="Method to include. Repeat to include multiple methods.",
    )
    fixed_budget_parser.add_argument(
        "--seed",
        action="append",
        type=int,
        default=[],
        help="Experiment seed. Repeat to plan multiple seeds.",
    )
    fixed_budget_parser.add_argument("--n-retries", type=int, default=5)
    fixed_budget_parser.add_argument("--n-branch-continuations", type=int, default=2)
    fixed_budget_parser.add_argument("--branch-root-fraction", type=float, default=0.3)
    fixed_budget_parser.add_argument(
        "--branch-context-mode",
        choices=("parent_summary", "none"),
        default="parent_summary",
        help="Parent context mode for planned branch continuation jobs.",
    )
    fixed_budget_parser.add_argument(
        "--snapshot",
        action="append",
        default=[],
        help=(
            "Optional known snapshot name for branch continuation commands. "
            "If omitted, branch continuations are marked pending_root_archive."
        ),
    )
    fixed_budget_parser.set_defaults(func=plan_fixed_budget)

    analysis_parser = subparsers.add_parser(
        "build-analysis-tables",
        help="Generate normalized run and task summary tables from experiment artifacts.",
    )
    analysis_parser.add_argument("--manifest", type=Path)
    analysis_parser.add_argument(
        "--job-dir",
        type=Path,
        action="append",
        default=[],
        help="Harbor job directory to include. Repeat for multiple jobs.",
    )
    analysis_parser.add_argument(
        "--continuation-report",
        type=Path,
        action="append",
        default=[],
        help="continuation-report.json path to join lineage metadata.",
    )
    analysis_parser.add_argument(
        "--event-log",
        type=Path,
        action="append",
        default=[],
        help="events.jsonl path to join snapshot counts and selector metadata.",
    )
    analysis_parser.add_argument(
        "--repeated-work-report",
        type=Path,
        action="append",
        default=[],
        help="Repeated-work JSON report to join run-level repeated setup scores.",
    )
    analysis_parser.add_argument("--jobs-dir", type=Path, default=Path("jobs"))
    analysis_parser.add_argument("--output-dir", type=Path, required=True)
    analysis_parser.add_argument(
        "--only-observed-runs",
        action="store_true",
        help="Do not emit missing_result rows for planned jobs absent from disk.",
    )
    analysis_parser.set_defaults(func=build_analysis_tables_cmd)

    figure_parser = subparsers.add_parser(
        "build-figure-tables",
        help="Generate paper figure source tables from normalized analysis CSVs.",
    )
    figure_parser.add_argument(
        "--task-summary",
        type=Path,
        action="append",
        default=[],
        help="task-summary.csv path. Repeat to include multiple result shards.",
    )
    figure_parser.add_argument(
        "--run-summary",
        type=Path,
        action="append",
        default=[],
        help="run-summary.csv path. Repeat to include multiple result shards.",
    )
    figure_parser.add_argument(
        "--execution-status",
        type=Path,
        help="Optional execution-status.csv ledger for planned job coverage.",
    )
    figure_parser.add_argument("--output-dir", type=Path, required=True)
    figure_parser.set_defaults(func=build_figure_tables_cmd)

    run_parser = subparsers.add_parser(
        "run-experiment",
        help="Plan and optionally execute a fixed-budget experiment end to end.",
    )
    run_source = run_parser.add_mutually_exclusive_group(required=True)
    run_source.add_argument(
        "--dataset",
        help="Registered Harbor dataset name, optionally with @version.",
    )
    run_source.add_argument(
        "--path",
        type=Path,
        help="Local Harbor task or dataset path.",
    )
    run_parser.add_argument("--jobs-dir", type=Path, default=Path("jobs"))
    run_parser.add_argument("--task-name")
    run_parser.add_argument("--env", default="daytona")
    run_parser.add_argument("--model")
    run_agent = run_parser.add_mutually_exclusive_group()
    run_agent.add_argument("--agent")
    run_agent.add_argument("--agent-import-path")
    run_parser.add_argument("--extra-arg", action="append", default=[])
    run_parser.add_argument("--experiment-id", required=True)
    run_parser.add_argument(
        "--job-prefix",
        help="Job name prefix. Defaults to --experiment-id.",
    )
    run_parser.add_argument("--manifest-path", type=Path)
    run_parser.add_argument("--analysis-dir", type=Path)
    run_parser.add_argument("--total-token-budget", type=int)
    run_parser.add_argument(
        "--method",
        action="append",
        choices=("single", "retry", "random_branch", "promising_branch"),
        default=[],
        help="Method to include. Repeat to include multiple methods.",
    )
    run_parser.add_argument(
        "--seed",
        action="append",
        type=int,
        default=[],
        help="Experiment seed. Repeat to run multiple seeds.",
    )
    run_parser.add_argument("--n-retries", type=int, default=5)
    run_parser.add_argument("--n-branch-continuations", type=int, default=2)
    run_parser.add_argument("--branch-root-fraction", type=float, default=0.3)
    run_parser.add_argument(
        "--branch-context-mode",
        choices=("parent_summary", "none"),
        default="parent_summary",
        help="Parent context mode for branch continuation jobs.",
    )
    run_parser.add_argument(
        "--execute",
        action="store_true",
        help="Run Harbor jobs and continuations. Without this, only plan.",
    )
    run_parser.add_argument(
        "--rerun-existing",
        action="store_true",
        help="Run jobs even when <jobs-dir>/<job-name>/result.json already exists.",
    )
    run_parser.add_argument(
        "--no-analysis",
        action="store_true",
        help="Skip analysis table generation after execution.",
    )
    run_parser.set_defaults(func=run_experiment_cmd)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
