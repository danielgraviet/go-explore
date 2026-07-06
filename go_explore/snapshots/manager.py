from __future__ import annotations

from go_explore.snapshots.backends import NoopSnapshotBackend, SnapshotBackend
from go_explore.snapshots.models import (
    SnapshotCandidate,
    SnapshotContext,
    SnapshotHandle,
    SnapshotRecord,
)
from go_explore.snapshots.policies import SnapshotPolicy
from go_explore.snapshots.stores import InMemorySnapshotStore, SnapshotStore


class SnapshotManager:
    """Coordinates policy decisions, backend capture, and metadata storage."""

    def __init__(
        self,
        policy: SnapshotPolicy,
        store: SnapshotStore | None = None,
        backend: SnapshotBackend | None = None,
    ):
        self._policy = policy
        self._store = store or InMemorySnapshotStore()
        self._backend = backend or NoopSnapshotBackend()

    @property
    def store(self) -> SnapshotStore:
        return self._store

    @property
    def backend(self) -> SnapshotBackend:
        return self._backend

    def process_step(self, context: SnapshotContext) -> list[SnapshotRecord]:
        records: list[SnapshotRecord] = []
        for candidate in self._policy.candidates_for_step(context):
            handle = self._backend.create_snapshot(candidate, context)
            saved_candidate = _candidate_with_handle(candidate, handle)
            record = SnapshotRecord(
                candidate=saved_candidate,
                description=self._describe_candidate(context, saved_candidate),
                backend=handle.backend,
            )
            self._store.put(record)
            records.append(record)
        return records

    def get(self, snapshot_id: str) -> SnapshotRecord | None:
        return self._store.get(snapshot_id)

    def list(self) -> list[SnapshotRecord]:
        return self._store.list()

    def _describe_candidate(
        self,
        context: SnapshotContext,
        candidate: SnapshotCandidate,
    ) -> str:
        parts = [
            candidate.event.value,
            f"trial={context.trial_name}",
            f"step={context.step_id}",
        ]
        if candidate.notes:
            parts.append(candidate.notes)
        return " | ".join(parts)


def _candidate_with_handle(
    candidate: SnapshotCandidate,
    handle: SnapshotHandle,
) -> SnapshotCandidate:
    return SnapshotCandidate(
        id=candidate.id,
        event=candidate.event,
        environment_id=handle.environment_id or candidate.environment_id,
        restore_ref=handle.restore_ref or candidate.restore_ref,
        trace_path=candidate.trace_path,
        tests_passed=candidate.tests_passed,
        tests_failed=candidate.tests_failed,
        changed_files=candidate.changed_files,
        command=candidate.command,
        notes=candidate.notes,
        metadata={**candidate.metadata, **handle.metadata, "snapshot_backend": handle.backend},
    )
