from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from go_explore.snapshots.manager import AsyncSnapshotManager
from go_explore.snapshots.models import SnapshotRecord, context_from_atif_step


async def process_atif_steps(
    steps: Sequence[Mapping[str, Any]],
    manager: AsyncSnapshotManager,
    *,
    trial_name: str,
    trace_path: Path | None = None,
    environment_id: str | None = None,
    restore_ref: str | None = None,
) -> list[SnapshotRecord]:
    """Replay a step stream through the snapshot manager one step at a time."""

    records: list[SnapshotRecord] = []
    for step in steps:
        context = context_from_atif_step(
            dict(step),
            trial_name=trial_name,
            trace_path=trace_path,
            environment_id=environment_id,
            restore_ref=restore_ref,
        )
        records.extend(await manager.process_step(context))
    return records


def load_atif_trajectory_steps(trajectory_path: Path) -> list[dict[str, Any]]:
    with trajectory_path.open() as file:
        payload = json.load(file)

    steps = payload.get("steps")
    if not isinstance(steps, list):
        raise ValueError(f"Trajectory file {trajectory_path} does not contain a steps list.")

    return [dict(step) for step in steps if isinstance(step, Mapping)]


async def process_atif_trajectory(
    trajectory_path: Path,
    manager: AsyncSnapshotManager,
    *,
    trial_name: str,
    trace_path: Path | None = None,
    environment_id: str | None = None,
    restore_ref: str | None = None,
) -> list[SnapshotRecord]:
    """Replay a saved ATIF trajectory file through the snapshot manager."""

    return await process_atif_steps(
        load_atif_trajectory_steps(trajectory_path),
        manager,
        trial_name=trial_name,
        trace_path=trace_path or trajectory_path,
        environment_id=environment_id,
        restore_ref=restore_ref,
    )
