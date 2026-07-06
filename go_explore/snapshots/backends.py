from __future__ import annotations

from typing import Protocol

from go_explore.snapshots.models import SnapshotCandidate, SnapshotContext, SnapshotHandle


class SnapshotBackend(Protocol):
    """Environment-specific side effect for creating a restorable snapshot."""

    def create_snapshot(
        self,
        candidate: SnapshotCandidate,
        context: SnapshotContext,
    ) -> SnapshotHandle:
        ...

class NoopSnapshotBackend:
    """Backend for policy/store testing before a real environment integration exists."""

    def create_snapshot(
        self,
        candidate: SnapshotCandidate,
        context: SnapshotContext,
    ) -> SnapshotHandle:
        return SnapshotHandle(
            backend="noop",
            restore_ref=candidate.restore_ref,
            environment_id=candidate.environment_id or context.environment_id,
        )
