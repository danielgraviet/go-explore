from __future__ import annotations

from dataclasses import dataclass

from go_explore.snapshots.models import SnapshotRecord


@dataclass(frozen=True)
class SnapshotTiming:
    started_at: float
    finished_at: float
    policy_seconds: float
    backend_seconds: float
    store_seconds: float
    total_seconds: float
    n_candidates: int
    n_snapshots: int


@dataclass(frozen=True)
class SnapshotProcessingResult:
    records: tuple[SnapshotRecord, ...]
    timing: SnapshotTiming
