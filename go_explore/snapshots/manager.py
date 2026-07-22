from __future__ import annotations

from collections.abc import Callable
from time import monotonic

from go_explore.snapshots.backends import (
    AsyncNoopSnapshotBackend,
    AsyncSnapshotBackend,
)
from go_explore.snapshots.metrics import SnapshotProcessingResult, SnapshotTiming
from go_explore.snapshots.models import (
    SnapshotCandidate,
    SnapshotContext,
    SnapshotHandle,
    SnapshotRecord,
)
from go_explore.snapshots.policies import SnapshotPolicy
from go_explore.snapshots.stores import InMemorySnapshotStore, SnapshotStore


class AsyncSnapshotManager:
    """Async variant for live environment backends such as Daytona."""

    def __init__(
        self,
        policy: SnapshotPolicy,
        store: SnapshotStore | None = None,
        backend: AsyncSnapshotBackend | None = None,
    ):
        self._policy = policy
        self._store = store or InMemorySnapshotStore()
        self._backend = backend or AsyncNoopSnapshotBackend()

    @property
    def store(self) -> SnapshotStore:
        return self._store

    @property
    def backend(self) -> AsyncSnapshotBackend:
        return self._backend

    async def process_step(self, context: SnapshotContext) -> list[SnapshotRecord]:
        return list((await self.process_step_with_metrics(context)).records)

    async def process_step_with_metrics(
        self,
        context: SnapshotContext,
        *,
        clock: Callable[[], float] = monotonic,
    ) -> SnapshotProcessingResult:
        started_at = clock()
        policy_started_at = clock()
        candidates = self._policy.candidates_for_step(context)
        policy_finished_at = clock()

        records: list[SnapshotRecord] = []
        backend_seconds = 0.0
        store_seconds = 0.0

        for candidate in candidates:
            backend_started_at = clock()
            handle = await self._backend.create_snapshot(candidate, context)
            backend_finished_at = clock()
            backend_elapsed = backend_finished_at - backend_started_at
            saved_candidate = _candidate_with_handle(
                candidate,
                handle,
                backend_seconds=backend_elapsed,
            )
            record = SnapshotRecord(
                candidate=saved_candidate,
                description=_describe_candidate(context, saved_candidate),
                backend=handle.backend,
            )
            store_started_at = clock()
            self._store.put(record)
            store_finished_at = clock()
            backend_seconds += backend_elapsed
            store_seconds += store_finished_at - store_started_at
            records.append(record)

        finished_at = clock()
        timing = SnapshotTiming(
            started_at=started_at,
            finished_at=finished_at,
            policy_seconds=policy_finished_at - policy_started_at,
            backend_seconds=backend_seconds,
            store_seconds=store_seconds,
            total_seconds=finished_at - started_at,
            n_candidates=len(candidates),
            n_snapshots=len(records),
        )
        return SnapshotProcessingResult(records=tuple(records), timing=timing)

    def get(self, snapshot_id: str) -> SnapshotRecord | None:
        return self._store.get(snapshot_id)

    def list(self) -> list[SnapshotRecord]:
        return self._store.list()


def _candidate_with_handle(
    candidate: SnapshotCandidate,
    handle: SnapshotHandle,
    *,
    backend_seconds: float,
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
        metadata={
            **candidate.metadata,
            **handle.metadata,
            "snapshot_backend": handle.backend,
            "snapshot_backend_seconds": backend_seconds,
        },
    )


def _describe_candidate(
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
