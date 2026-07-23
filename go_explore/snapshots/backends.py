from __future__ import annotations

import inspect
import re
from typing import Protocol

from go_explore.snapshots.models import (
    CONTEXT_FILE_PATH,
    SnapshotCandidate,
    SnapshotContext,
    SnapshotHandle,
)


class AsyncSnapshotBackend(Protocol):
    """Async environment-specific side effect for creating a restorable snapshot."""

    async def create_snapshot(
        self,
        candidate: SnapshotCandidate,
        context: SnapshotContext,
    ) -> SnapshotHandle:
        ...

    async def delete_snapshot(self, snapshot_name: str) -> None:
        ...


class AsyncNoopSnapshotBackend:
    """Async no-op backend for tests and dry runs."""

    async def create_snapshot(
        self,
        candidate: SnapshotCandidate,
        context: SnapshotContext,
    ) -> SnapshotHandle:
        return SnapshotHandle(
            backend="noop",
            restore_ref=candidate.restore_ref,
            environment_id=candidate.environment_id or context.environment_id,
        )

    async def delete_snapshot(self, snapshot_name: str) -> None:
        return None


class DaytonaSnapshotBackend:
    """Create real Daytona snapshots from a live AsyncSandbox."""

    def __init__(
        self,
        sandbox,
        *,
        timeout: float | None = 60,
        name_prefix: str = "go-explore",
    ):
        self._sandbox = sandbox
        self._timeout = timeout
        self._name_prefix = name_prefix

    async def create_snapshot(
        self,
        candidate: SnapshotCandidate,
        context: SnapshotContext,
    ) -> SnapshotHandle:
        snapshot_name = daytona_snapshot_name(candidate.id, prefix=self._name_prefix)

        if context.trajectory_summary:
            try:
                await self._sandbox.fs.upload_file(
                    context.trajectory_summary.encode(), CONTEXT_FILE_PATH
                )
            except Exception as e:
                print(f"Warning: Failed to write trajectory context to sandbox: {e}")

        await self._sandbox._experimental_create_snapshot(
            name=snapshot_name,
            timeout=self._timeout,
        )

        return SnapshotHandle(
            backend="daytona",
            restore_ref=snapshot_name,
            environment_id=self._sandbox.id or candidate.environment_id or context.environment_id,
            metadata={"daytona_snapshot_name": snapshot_name},
        )

    async def delete_snapshot(self, snapshot_name: str) -> None:
        from daytona import AsyncDaytona

        async with AsyncDaytona() as daytona:
            snapshot = daytona.snapshot.get(snapshot_name)
            snapshot = await _maybe_await(snapshot)
            result = daytona.snapshot.delete(snapshot)
            await _maybe_await(result)


def daytona_snapshot_name(snapshot_id: str, *, prefix: str = "go-explore") -> str:
    raw_name = f"{prefix}-{snapshot_id}"
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "-", raw_name).strip("-")
    return normalized[:120] or prefix


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value
