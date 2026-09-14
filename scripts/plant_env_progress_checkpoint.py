"""Plant a mid-task Daytona snapshot for Experiment E.

Creates warehouse sqlite *outside* /app (secret lot code) plus a git commit
of an unapplied quantity migration, then freezes the sandbox.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from daytona import AsyncDaytona, CreateSandboxFromImageParams, Image

from go_explore.env_progress import (
    CHECKPOINT_JOB_NAME,
    PLANT_TRIAL_NAME,
    TASK_DIR,
    plant_shell_script,
)
from go_explore.snapshots.archive import SnapshotArchive
from go_explore.snapshots.backends import daytona_snapshot_name
from go_explore.snapshots.capture_diff import (
    assert_parent_diff_artifact,
    capture_parent_diff,
)
from go_explore.snapshots.models import SnapshotCandidate, SnapshotEvent


async def plant_checkpoint(
    *,
    jobs_dir: Path,
    model: str,
    agent_import_path: str,
) -> Path:
    """Return a synthetic root job dir with archive.json and parent.diff."""

    trial_name = PLANT_TRIAL_NAME
    snapshot_name = daytona_snapshot_name(f"{trial_name}-step-0")
    root_job_dir = jobs_dir / CHECKPOINT_JOB_NAME
    root_job_dir.mkdir(parents=True, exist_ok=True)
    trial_dir = root_job_dir / trial_name
    trial_dir.mkdir(parents=True, exist_ok=True)
    dockerfile = TASK_DIR / "environment" / "Dockerfile"

    async with AsyncDaytona() as daytona:
        await _delete_snapshot_if_present(daytona, snapshot_name)
        sandbox = await daytona.create(
            CreateSandboxFromImageParams(
                image=Image.from_dockerfile(dockerfile),
                auto_delete_interval=1,
            ),
            timeout=600,
            on_snapshot_create_logs=lambda line: print(line, end=""),
        )
        try:
            await sandbox.fs.upload_file(
                plant_shell_script().encode(),
                "/tmp/plant_env_progress.sh",
            )
            planted = await sandbox.process.exec(
                "bash /tmp/plant_env_progress.sh",
                timeout=300,
            )
            if getattr(planted, "exit_code", 0) not in (0, None):
                raise SystemExit(
                    f"plant failed: {(planted.result or '')[:2000]}"
                )
            await sandbox._experimental_create_snapshot(
                name=snapshot_name,
                timeout=300,
            )
        finally:
            await sandbox.delete()

    _write_synthetic_root(
        root_job_dir,
        trial_dir,
        trial_name=trial_name,
        snapshot_name=snapshot_name,
        model=model,
        agent_import_path=agent_import_path,
        jobs_dir=jobs_dir,
    )
    diff_path = root_job_dir / "parent.diff"
    await capture_parent_diff(snapshot_name, diff_path)
    assert_parent_diff_artifact(diff_path)
    return root_job_dir


async def _delete_snapshot_if_present(daytona: AsyncDaytona, name: str) -> None:
    try:
        snapshot = await daytona.snapshot.get(name)
    except Exception:
        return
    try:
        await daytona.snapshot.delete(snapshot)
    except Exception:
        return


def _write_synthetic_root(
    root_job_dir: Path,
    trial_dir: Path,
    *,
    trial_name: str,
    snapshot_name: str,
    model: str,
    agent_import_path: str,
    jobs_dir: Path,
) -> None:
    (root_job_dir / "config.json").write_text(
        json.dumps(
            {
                "jobs_dir": str(jobs_dir),
                "environment": {"type": "daytona"},
                "agents": [
                    {
                        "name": None,
                        "import_path": agent_import_path,
                        "model_name": model,
                        "kwargs": {},
                    }
                ],
                "datasets": [],
                "tasks": [{"path": str(TASK_DIR)}],
            },
            indent=2,
        )
        + "\n"
    )
    (root_job_dir / "result.json").write_text(
        json.dumps({"n_total_trials": 1, "stats": {"n_errors": 0}}) + "\n"
    )
    (trial_dir / "result.json").write_text(
        json.dumps(
            {
                "trial_name": trial_name,
                "task_name": "staged-service-repair",
                "verifier_result": {"reward": 0.0},
            }
        )
        + "\n"
    )
    archive = SnapshotArchive(path=root_job_dir / "archive.json")
    archive.add(
        SnapshotCandidate(
            id=f"{trial_name}-step-0",
            event=SnapshotEvent.TEST_RUN,
            restore_ref=snapshot_name,
            changed_files=("migrations/002_add_quantity.sql",),
            metadata={"trial_name": trial_name, "step_id": "0"},
        )
    )
    archive.save()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs-dir", type=Path, default=Path("jobs"))
    parser.add_argument("--model", required=True)
    parser.add_argument(
        "--agent-import-path",
        default="go_explore.agents.factory:SnapshotAwareTerminus2",
    )
    args = parser.parse_args()
    root = asyncio.run(
        plant_checkpoint(
            jobs_dir=args.jobs_dir,
            model=args.model,
            agent_import_path=args.agent_import_path,
        )
    )
    print(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
