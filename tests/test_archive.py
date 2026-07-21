"""Tests for the persistent snapshot archive."""

from __future__ import annotations

from go_explore.snapshots.archive import (
    ArchiveStore,
    SnapshotArchive,
    cell_key_for,
)
from go_explore.snapshots.models import (
    SnapshotCandidate,
    SnapshotEvent,
    SnapshotRecord,
)


def _candidate(
    *,
    id: str = "trial:step-0",
    event: SnapshotEvent = SnapshotEvent.FILE_EDIT,
    changed_files: tuple[str, ...] = ("main.py",),
    restore_ref: str = "go-explore-trial-step-0",
    trial: str = "trial",
    step: int = 0,
) -> SnapshotCandidate:
    return SnapshotCandidate(
        id=id,
        event=event,
        restore_ref=restore_ref,
        changed_files=changed_files,
        metadata={"trial_name": trial, "step_id": str(step)},
    )


def test_cell_key_buckets_by_changed_file_set_regardless_of_order():
    a = _candidate(changed_files=("main.py", "utils.py"))
    b = _candidate(changed_files=("utils.py", "main.py"))
    assert cell_key_for(a) == cell_key_for(b)


def test_cell_key_falls_back_to_event_when_no_files_changed():
    candidate = _candidate(event=SnapshotEvent.TEST_RUN, changed_files=())
    assert cell_key_for(candidate) == "<test_run>"


def test_add_stores_one_entry_per_cell():
    archive = SnapshotArchive()
    archive.add(_candidate(restore_ref="snap-a"))
    archive.add(_candidate(restore_ref="snap-b"))
    assert len(archive) == 1


def test_add_keeps_the_higher_scoring_snapshot_for_a_cell():
    archive = SnapshotArchive()
    # A plain file edit scores lower than a file edit carrying a test signal.
    archive.add(_candidate(event=SnapshotEvent.FILE_EDIT, restore_ref="snap-low"))
    archive.add(_candidate(event=SnapshotEvent.TEST_RUN, restore_ref="snap-high"))

    entry = archive.get(cell_key_for(_candidate()))
    assert entry is not None
    assert entry.snapshot_name == "snap-high"


def test_add_rejects_a_lower_scoring_snapshot_for_an_existing_cell():
    archive = SnapshotArchive()
    archive.add(_candidate(event=SnapshotEvent.TEST_RUN, restore_ref="snap-high"))
    result = archive.add(_candidate(event=SnapshotEvent.FILE_EDIT, restore_ref="snap-low"))
    assert result is None
    assert archive.get(cell_key_for(_candidate())).snapshot_name == "snap-high"


def test_add_ignores_candidates_without_a_restore_ref():
    archive = SnapshotArchive()
    assert archive.add(_candidate(restore_ref="")) is None
    assert len(archive) == 0


def test_select_returns_best_cells_first():
    archive = SnapshotArchive()
    archive.add(_candidate(changed_files=("a.py",), event=SnapshotEvent.FILE_EDIT, restore_ref="s-a"))
    archive.add(_candidate(changed_files=("b.py",), event=SnapshotEvent.TEST_RUN, restore_ref="s-b"))

    top = archive.select(k=2)
    assert [e.snapshot_name for e in top] == ["s-b", "s-a"]


def test_select_respects_k():
    archive = SnapshotArchive()
    for i in range(4):
        archive.add(_candidate(changed_files=(f"f{i}.py",), restore_ref=f"s-{i}"))
    assert len(archive.select(k=2)) == 2


def test_mark_selected_down_weights_a_repeatedly_forked_cell():
    archive = SnapshotArchive()
    archive.add(_candidate(changed_files=("a.py",), event=SnapshotEvent.TEST_RUN, restore_ref="s-a"))
    archive.add(_candidate(changed_files=("b.py",), event=SnapshotEvent.FILE_EDIT, restore_ref="s-b"))

    best = archive.select(k=1)[0]
    assert best.snapshot_name == "s-a"

    # After forking it enough times, the frontier should rotate to the other cell.
    archive.mark_selected(best.cell_key)
    archive.mark_selected(best.cell_key)
    archive.mark_selected(best.cell_key)
    assert archive.select(k=1)[0].snapshot_name == "s-b"


def test_promote_records_parent_and_increments_depth():
    archive = SnapshotArchive()
    parent = archive.add(_candidate(changed_files=("a.py",), restore_ref="s-parent"))
    child = archive.add(_candidate(changed_files=("a.py", "b.py"), restore_ref="s-child"))

    promoted = archive.promote(child, parent.snapshot_name)
    assert promoted.parent_snapshot == "s-parent"
    assert promoted.depth == parent.depth + 1


def test_save_and_load_round_trip_preserves_entries(tmp_path):
    path = tmp_path / "archive.json"
    archive = SnapshotArchive(path=path)
    archive.add(_candidate(changed_files=("a.py",), restore_ref="s-a"))
    archive.add(_candidate(changed_files=("b.py",), event=SnapshotEvent.TEST_RUN, restore_ref="s-b"))
    archive.save()

    loaded = SnapshotArchive.load(path)
    assert len(loaded) == 2
    assert {e.snapshot_name for e in loaded.entries()} == {"s-a", "s-b"}
    assert loaded.select(k=1)[0].snapshot_name == "s-b"


def test_load_of_missing_file_returns_empty_archive(tmp_path):
    archive = SnapshotArchive.load(tmp_path / "nope.json")
    assert len(archive) == 0


def test_archive_store_satisfies_store_protocol_and_persists(tmp_path):
    path = tmp_path / "archive.json"
    store = ArchiveStore(path=path)
    candidate = _candidate(restore_ref="s-a")
    record = SnapshotRecord(candidate=candidate, description="file edit", backend="daytona")

    store.put(record)

    # Store protocol behaviour.
    assert store.get(record.id) is record
    assert store.list() == [record]
    # Archive behaviour: bucketed and written to disk.
    assert len(store.archive) == 1
    assert path.exists()
    assert SnapshotArchive.load(path).select(k=1)[0].snapshot_name == "s-a"


def test_archive_store_with_missing_path_starts_empty_and_persists(tmp_path):
    path = tmp_path / "missing" / "archive.json"
    store = ArchiveStore(path=path)

    assert len(store.archive) == 0

    store.put(
        SnapshotRecord(
            candidate=_candidate(restore_ref="s-a"),
            description="file edit",
            backend="daytona",
        )
    )

    loaded = SnapshotArchive.load(path)
    assert len(loaded) == 1
    assert loaded.select(k=1)[0].snapshot_name == "s-a"


def test_archive_store_loads_existing_archive_before_put(tmp_path):
    path = tmp_path / "archive.json"
    existing = SnapshotArchive(path=path)
    existing.add(_candidate(changed_files=("a.py",), restore_ref="s-a"))
    existing.save()

    store = ArchiveStore(path=path)
    store.put(
        SnapshotRecord(
            candidate=_candidate(changed_files=("b.py",), restore_ref="s-b"),
            description="file edit",
            backend="daytona",
        )
    )

    loaded = SnapshotArchive.load(path)
    assert len(loaded) == 2
    assert {entry.snapshot_name for entry in loaded.entries()} == {"s-a", "s-b"}


def test_archive_store_replaces_same_cell_by_score_after_load(tmp_path):
    path = tmp_path / "archive.json"
    existing = SnapshotArchive(path=path)
    existing.add(
        _candidate(
            event=SnapshotEvent.FILE_EDIT,
            changed_files=("main.py",),
            restore_ref="s-low",
        )
    )
    existing.save()

    store = ArchiveStore(path=path)
    store.put(
        SnapshotRecord(
            candidate=_candidate(
                event=SnapshotEvent.TEST_RUN,
                changed_files=("main.py",),
                restore_ref="s-high",
            ),
            description="test run",
            backend="daytona",
        )
    )

    entry = SnapshotArchive.load(path).get(cell_key_for(_candidate()))
    assert entry is not None
    assert entry.snapshot_name == "s-high"


def test_archive_store_preserves_higher_score_after_load(tmp_path):
    path = tmp_path / "archive.json"
    existing = SnapshotArchive(path=path)
    existing.add(
        _candidate(
            event=SnapshotEvent.TEST_RUN,
            changed_files=("main.py",),
            restore_ref="s-high",
        )
    )
    existing.save()

    store = ArchiveStore(path=path)
    store.put(
        SnapshotRecord(
            candidate=_candidate(
                event=SnapshotEvent.FILE_EDIT,
                changed_files=("main.py",),
                restore_ref="s-low",
            ),
            description="file edit",
            backend="daytona",
        )
    )

    entry = SnapshotArchive.load(path).get(cell_key_for(_candidate()))
    assert entry is not None
    assert entry.snapshot_name == "s-high"
