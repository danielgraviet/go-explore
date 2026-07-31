"""Prune Daytona snapshots that are no longer needed by any pending job.

Deletes a `go-explore-<trial>-step-N` remote snapshot only when it is safe:

- the trial's own job has finished (result.json exists) — never touches a
  snapshot belonging to a still-running job, since that job's own archive
  bookkeeping may still be live; and
- if the job is a branch root, all of its continuation children already
  have a job directory on disk (meaning they already restored from the
  snapshot at sandbox-creation time and no longer need it); non-root jobs
  (retries, continuations) never have downstream dependents in this
  experiment design, so their snapshots are safe once the job is done.

Local job data (trajectories, archive.json, rewards) is never touched or
required to still exist remotely afterward — this only prunes the remote
Daytona snapshot artifacts.

Usage:
    uv run python3 prune_snapshots.py            # deletes
    uv run python3 prune_snapshots.py --dry-run   # preview only
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
from pathlib import Path

from daytona import AsyncDaytona

JOBS_DIR = Path(__file__).resolve().parent / "jobs"
SNAPSHOT_NAME_RE = re.compile(r"^go-explore-(.+)-step-\d+$")


def _job_dir_for_trial(trial_name: str) -> Path | None:
    """Find the job directory that owns this trial, if any exists locally."""
    if not JOBS_DIR.is_dir():
        return None
    for job_dir in JOBS_DIR.iterdir():
        if not job_dir.is_dir():
            continue
        if (job_dir / trial_name).is_dir():
            return job_dir
    return None


def _n_children_launched(root_job_dir: Path) -> int:
    """How many of a branch root's continuation children already have job dirs."""
    prefix = root_job_dir.name.removesuffix("-root")
    parent = root_job_dir.parent
    return sum(
        1
        for entry in parent.iterdir()
        if entry.is_dir() and entry.name.startswith(f"{prefix}-snapshot-")
    )


def is_safe_to_delete(
    trial_name: str, *, n_branch_continuations: int
) -> tuple[bool, str]:
    # A root is only safe once ALL expected children have launched - checking
    # for just one (the old behavior) deleted snapshots a not-yet-launched
    # second child still needed, failing it with DaytonaValidationError.
    job_dir = _job_dir_for_trial(trial_name)
    if job_dir is None:
        return True, "no local job directory references this trial"

    if not (job_dir / "result.json").exists():
        return False, f"owning job {job_dir.name} has not finished yet"

    if job_dir.name.endswith("-root"):
        launched = _n_children_launched(job_dir)
        if launched >= n_branch_continuations:
            return True, (
                f"root {job_dir.name} finished and all "
                f"{n_branch_continuations} children already launched"
            )
        return False, (
            f"root {job_dir.name} finished but only {launched}/"
            f"{n_branch_continuations} children launched"
        )

    return True, f"non-root job {job_dir.name} finished"


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be deleted without deleting anything.",
    )
    parser.add_argument(
        "--n-branch-continuations",
        type=int,
        default=2,
        help=(
            "Expected children per branch root (must match the "
            "--n-branch-continuations value used to launch the run). A root "
            "is only safe to prune once this many children have local job "
            "dirs, not just one."
        ),
    )
    args = parser.parse_args()

    async with AsyncDaytona() as daytona:
        page = await daytona.snapshot.list(limit=200)
        go_explore = [s for s in page.items if s.name.startswith("go-explore-")]
        print(f"{len(go_explore)} go-explore-prefixed snapshots found.")

        to_delete = []
        kept = []
        for snapshot in go_explore:
            match = SNAPSHOT_NAME_RE.match(snapshot.name)
            trial_name = match.group(1) if match else None
            if trial_name is None:
                kept.append((snapshot.name, "name did not match expected pattern"))
                continue
            safe, reason = is_safe_to_delete(
                trial_name, n_branch_continuations=args.n_branch_continuations
            )
            if safe:
                to_delete.append((snapshot, reason))
            else:
                kept.append((snapshot.name, reason))

        print(f"\nSafe to delete: {len(to_delete)}")
        for snapshot, reason in to_delete:
            print(f"  DELETE {snapshot.name}  ({reason})")

        print(f"\nKeeping: {len(kept)}")
        for name, reason in kept:
            print(f"  KEEP   {name}  ({reason})")

        if args.dry_run:
            print("\n--dry-run: nothing deleted.")
            return

        deleted, failed = 0, 0
        for snapshot, _ in to_delete:
            try:
                await daytona.snapshot.delete(snapshot)
                deleted += 1
            except Exception as error:  # noqa: BLE001
                failed += 1
                print(f"failed to delete {snapshot.name}: {error}")

        print(f"\ndeleted={deleted} failed={failed} kept={len(kept)}")

        page2 = await daytona.snapshot.list(limit=200)
        remaining = len(page2.items)
        remaining_go_explore = len(
            [s for s in page2.items if s.name.startswith("go-explore-")]
        )
        print(f"remaining total snapshots: {remaining} (go-explore: {remaining_go_explore})")


if __name__ == "__main__":
    asyncio.run(main())
