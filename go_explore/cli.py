from __future__ import annotations

import argparse
import shlex
from pathlib import Path

from go_explore.continuations import (
    harbor_config_from_job,
    list_daytona_snapshots_for_trial_sync,
    plan_snapshot_continuations,
    run_continuation_plans,
    select_trial,
)
from go_explore.events import EVENT_LOG_FILENAME
from go_explore.harbor import HarborRunConfig, run_harbor
from go_explore.results import format_job_summary, summarize_job
from go_explore.snapshots.archive import ARCHIVE_FILENAME, SnapshotArchive
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
    if not snapshots and args.from_archive:
        archive_path = args.archive_path or args.root_job_dir / ARCHIVE_FILENAME
        archive = SnapshotArchive.load(archive_path)
        if not len(archive):
            print(f"Archive {archive_path} is empty or missing.")
            return 1
        chosen = archive.select(args.max_snapshots or 3)
        snapshots = tuple(entry.snapshot_name for entry in chosen)
        selector_mode = "archive_priority"
        print(f"archive: {archive_path} ({len(archive)} cells)")
        for entry in chosen:
            print(
                f"  select {entry.snapshot_name}"
                f"  cell={entry.cell_key}  score={entry.score:.2f}"
            )
        # Record the fork so a later run rotates to the rest of the frontier
        # instead of picking these same cells again.
        for entry in chosen:
            archive.mark_selected(entry.cell_key)
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
        max_snapshots=args.max_snapshots,
        parent_trial_name=root_trial.trial_name,
        event_log_path=event_log_path,
        selector_mode=selector_mode,
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
        help="Pick snapshots by archive score (select_k) instead of listing Daytona.",
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
    continue_parser.add_argument("--report-path", type=Path)
    continue_parser.add_argument(
        "--execute",
        action="store_true",
        help="Run Harbor continuation jobs instead of printing commands.",
    )
    continue_parser.set_defaults(func=continue_from_snapshots)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
