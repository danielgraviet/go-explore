from __future__ import annotations

import argparse
import shlex
from pathlib import Path

from go_explore.harbor import HarborRunConfig, run_harbor
from go_explore.results import format_job_summary, summarize_job
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

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
