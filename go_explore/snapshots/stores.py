from __future__ import annotations

from typing import Protocol

from go_explore.snapshots.models import SnapshotRecord


class SnapshotStore(Protocol):
    """Storage boundary for snapshot metadata."""

    def put(self, record: SnapshotRecord) -> None:
        ...

    def get(self, snapshot_id: str) -> SnapshotRecord | None:
        ...

    def list(self) -> list[SnapshotRecord]:
        ...


class InMemorySnapshotStore:
    """Dictionary-backed store for early experiments and unit tests."""

    def __init__(self, records: dict[str, SnapshotRecord] | None = None):
        self._records: dict[str, SnapshotRecord] = dict(records or {})

    def put(self, record: SnapshotRecord) -> None:
        self._records[record.id] = record

    def get(self, snapshot_id: str) -> SnapshotRecord | None:
        return self._records.get(snapshot_id)

    def list(self) -> list[SnapshotRecord]:
        return list(self._records.values())

    def as_dict(self) -> dict[str, SnapshotRecord]:
        return dict(self._records)
