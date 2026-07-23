"""Persistent snapshot archive: the cell -> best-snapshot map Go-Explore needs.

The archive is what turns snapshotting into search. Each accepted snapshot is
bucketed into a *cell* (a descriptor of "what kind of state is this"); the
archive keeps only the best-scoring snapshot per cell, records lineage, and
persists to `jobs/<job>/archive.json` so continuation can rank what to fork
instead of forking in list order.

See `docs/snapshot-archive-proposal.md`.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

from go_explore.events import EVENT_LOG_FILENAME, append_event, base_event
from go_explore.snapshots.models import ScoredSnapshot, SnapshotCandidate, SnapshotRecord
from go_explore.snapshots.policies import HeuristicSnapshotSelector

ARCHIVE_FILENAME = "archive.json"

# How much to penalize a cell for each time we've already forked from it, so
# select() spreads across the frontier instead of re-picking one winner.
RESELECT_PENALTY = 1.0


def cell_key_for(candidate: SnapshotCandidate) -> str:
    """Cell key, option A: the set of files this state has touched.

    Two snapshots that touched the same files are treated as the same kind of
    progress. States with no detected file change fall back to bucketing by
    event type, which is coarse but keeps them from each becoming a unique cell.
    Upgrade path is option B (files + tests passing) once a mid-run test signal
    exists.
    """
    if candidate.changed_files:
        return "{" + ", ".join(sorted(set(candidate.changed_files))) + "}"
    return f"<{candidate.event.value}>"


@dataclass(frozen=True)
class ArchiveEntry:
    """One cell's best-known snapshot."""

    cell_key: str
    snapshot_name: str
    score: float
    trial_name: str = ""
    step_id: int = -1
    event: str = ""
    changed_files: tuple[str, ...] = ()
    reward_signal: float | None = None
    parent_snapshot: str | None = None
    depth: int = 0
    times_selected: int = 0
    created_at: str = ""
    remote_retained: bool = True

    @property
    def priority(self) -> float:
        """Score, down-weighted each time we've already forked this cell."""
        return self.score - RESELECT_PENALTY * self.times_selected


class SnapshotArchive:
    """A cell-keyed archive of snapshots, persisted as JSON."""

    def __init__(
        self,
        path: Path | None = None,
        *,
        selector: HeuristicSnapshotSelector | None = None,
    ):
        self._entries: dict[str, ArchiveEntry] = {}
        self._path = Path(path) if path else None
        self._selector = selector or HeuristicSnapshotSelector()

    # ---- reads -----------------------------------------------------------

    @property
    def path(self) -> Path | None:
        return self._path

    def entries(self) -> list[ArchiveEntry]:
        return list(self._entries.values())

    def get(self, cell_key: str) -> ArchiveEntry | None:
        return self._entries.get(cell_key)

    def __len__(self) -> int:
        return len(self._entries)

    def score(self, candidate: SnapshotCandidate) -> ScoredSnapshot:
        return self._selector.score(candidate)

    # ---- writes ----------------------------------------------------------

    def add(
        self,
        candidate: SnapshotCandidate,
        snapshot_name: str | None = None,
        *,
        parent_snapshot: str | None = None,
        depth: int = 0,
    ) -> ArchiveEntry | None:
        """Insert this snapshot if its cell is new or it beats the incumbent.

        Returns the stored entry, or None when an existing entry scored higher
        (the archive keeps at most one snapshot per cell).
        """
        return self.add_with_result(
            candidate,
            snapshot_name,
            parent_snapshot=parent_snapshot,
            depth=depth,
        ).entry

    def add_with_result(
        self,
        candidate: SnapshotCandidate,
        snapshot_name: str | None = None,
        *,
        parent_snapshot: str | None = None,
        depth: int = 0,
    ) -> "ArchiveAddResult":
        restore_ref = snapshot_name or candidate.restore_ref
        if not restore_ref:
            return ArchiveAddResult(entry=None, accepted=False)

        key = cell_key_for(candidate)
        score = self.score(candidate).score
        incumbent = self._entries.get(key)
        if incumbent is not None and incumbent.score >= score:
            return ArchiveAddResult(
                entry=None,
                accepted=False,
                rejected_snapshot_name=restore_ref,
            )

        entry = ArchiveEntry(
            cell_key=key,
            snapshot_name=restore_ref,
            score=score,
            trial_name=str(candidate.metadata.get("trial_name", "")),
            step_id=int(candidate.metadata.get("step_id", -1) or -1),
            event=candidate.event.value,
            changed_files=tuple(candidate.changed_files),
            reward_signal=(
                float(candidate.tests_passed)
                if candidate.tests_passed is not None
                else None
            ),
            parent_snapshot=parent_snapshot,
            depth=depth,
            times_selected=incumbent.times_selected if incumbent else 0,
            created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        self._entries[key] = entry
        return ArchiveAddResult(
            entry=entry,
            accepted=True,
            replaced_snapshot_name=incumbent.snapshot_name if incumbent else None,
        )

    def select(self, k: int = 3) -> list[ArchiveEntry]:
        """Return the top-k cells to fork from, best first."""
        return sorted(
            (entry for entry in self._entries.values() if entry.remote_retained),
            key=lambda e: (e.priority, e.score),
            reverse=True,
        )[:k]

    def apply_remote_retention_limit(self, limit: int | None) -> tuple[str, ...]:
        if limit is None:
            return ()
        if limit < 1:
            raise ValueError("remote retention limit must be >= 1 when set.")

        ranked = sorted(
            self._entries.values(),
            key=lambda e: (e.priority, e.score),
            reverse=True,
        )
        keep_names = {entry.snapshot_name for entry in ranked[:limit]}
        pruned: list[str] = []
        for entry in ranked:
            should_retain = entry.snapshot_name in keep_names
            if entry.remote_retained and not should_retain:
                pruned.append(entry.snapshot_name)
            if entry.remote_retained != should_retain:
                self._entries[entry.cell_key] = replace(
                    entry,
                    remote_retained=should_retain,
                )
        return tuple(pruned)

    def mark_selected(self, cell_key: str) -> None:
        """Record that we forked this cell, so select() rotates onward."""
        entry = self._entries.get(cell_key)
        if entry is not None:
            self._entries[cell_key] = replace(
                entry, times_selected=entry.times_selected + 1
            )

    def promote(self, child: ArchiveEntry, parent_snapshot: str) -> ArchiveEntry:
        """Record that `child` came from forking `parent_snapshot`."""
        parent = next(
            (e for e in self._entries.values() if e.snapshot_name == parent_snapshot),
            None,
        )
        promoted = replace(
            child,
            parent_snapshot=parent_snapshot,
            depth=(parent.depth + 1) if parent else child.depth + 1,
        )
        self._entries[promoted.cell_key] = promoted
        return promoted

    # ---- persistence -----------------------------------------------------

    def to_json_dict(self) -> dict:
        entries = sorted(
            self._entries.values(),
            key=lambda e: (e.remote_retained, e.priority, e.score),
            reverse=True,
        )
        return {
            "version": 1,
            "n_cells": len(self._entries),
            "entries": [asdict(e) for e in entries],
        }

    def save(self, path: Path | None = None) -> Path | None:
        target = Path(path) if path else self._path
        if target is None:
            return None
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_json_dict(), indent=2) + "\n")
        return target

    @classmethod
    def load(cls, path: Path) -> "SnapshotArchive":
        archive = cls(path=path)
        p = Path(path)
        if not p.exists():
            return archive
        data = json.loads(p.read_text())
        for raw in data.get("entries", []):
            raw = dict(raw)
            raw["changed_files"] = tuple(raw.get("changed_files") or ())
            raw.setdefault("remote_retained", True)
            entry = ArchiveEntry(**raw)
            archive._entries[entry.cell_key] = entry
        return archive


@dataclass(frozen=True)
class ArchiveAddResult:
    entry: ArchiveEntry | None
    accepted: bool
    rejected_snapshot_name: str | None = None
    replaced_snapshot_name: str | None = None


class ArchiveStore:
    """A `SnapshotStore` that also maintains a persistent `SnapshotArchive`.

    Implements the store protocol (`put`/`get`/`list`) so `AsyncSnapshotManager`
    can use it unchanged, while additionally bucketing each record into a cell
    and writing `archive.json` after every accepted snapshot.
    """

    def __init__(
        self,
        archive: SnapshotArchive | None = None,
        path: Path | None = None,
        *,
        remote_retention_limit: int | None = None,
    ):
        if archive is not None:
            self._archive = archive
        elif path is not None:
            # Load before writing so later process-local stores do not clobber
            # entries already persisted by earlier roots or continuations.
            self._archive = SnapshotArchive.load(Path(path))
        else:
            self._archive = SnapshotArchive()
        self._records: dict[str, SnapshotRecord] = {}
        self._remote_retention_limit = remote_retention_limit
        self._pending_remote_prunes: list[str] = []

    @property
    def archive(self) -> SnapshotArchive:
        return self._archive

    def put(self, record: SnapshotRecord) -> None:
        self._records[record.id] = record
        scored = self._archive.score(record.candidate)
        result = self._archive.add_with_result(record.candidate)
        self._record_remote_prunes(result)
        self._write_snapshot_created_event(record, scored, result.accepted)
        self._archive.save()

    def consume_remote_prunes(self) -> tuple[str, ...]:
        prunes = tuple(dict.fromkeys(self._pending_remote_prunes))
        self._pending_remote_prunes.clear()
        return prunes

    def get(self, snapshot_id: str) -> SnapshotRecord | None:
        return self._records.get(snapshot_id)

    def list(self) -> list[SnapshotRecord]:
        return list(self._records.values())

    def _record_remote_prunes(self, result: ArchiveAddResult) -> None:
        if result.rejected_snapshot_name:
            self._pending_remote_prunes.append(result.rejected_snapshot_name)
        if result.replaced_snapshot_name:
            self._pending_remote_prunes.append(result.replaced_snapshot_name)
        self._pending_remote_prunes.extend(
            self._archive.apply_remote_retention_limit(self._remote_retention_limit)
        )

    def _write_snapshot_created_event(
        self,
        record: SnapshotRecord,
        scored: ScoredSnapshot,
        archive_accepted: bool,
    ) -> None:
        if self._archive.path is None:
            return

        candidate = record.candidate
        snapshot_name = candidate.restore_ref
        if not snapshot_name:
            return

        event_log_path = self._archive.path.parent / EVENT_LOG_FILENAME
        trial_name = candidate.metadata.get("trial_name") or None
        run_id = trial_name or candidate.id
        raw_step_id = candidate.metadata.get("step_id")
        try:
            step_id = int(raw_step_id) if raw_step_id is not None else None
        except ValueError:
            step_id = None
        snapshot_backend_seconds = _optional_float(
            candidate.metadata.get("snapshot_backend_seconds")
        )

        event = base_event(
            event_type="snapshot_created",
            event_id=f"{run_id}:snapshot_created:{snapshot_name}",
            experiment_id=candidate.metadata.get("experiment_id"),
            run_id=run_id,
            job_dir=self._archive.path.parent,
            trial_name=trial_name,
            task_id=candidate.metadata.get("task_id"),
            step_id=step_id,
        )
        event.update(
            {
                "snapshot_name": snapshot_name,
                "cell_key": cell_key_for(candidate),
                "score": scored.score,
                "selector_reasons": list(scored.reasons),
                "backend": record.backend,
                "overhead_seconds": snapshot_backend_seconds,
                "snapshot_backend_seconds": snapshot_backend_seconds,
                "archive_accepted": archive_accepted,
            }
        )
        append_event(event_log_path, event)


def _optional_float(value: object) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None
