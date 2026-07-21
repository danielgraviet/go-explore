from __future__ import annotations

import json

import pytest

from go_explore.snapshots.archive import SnapshotArchive
from go_explore.snapshots.models import SnapshotCandidate, SnapshotEvent
from go_explore.snapshots.selectors import (
    load_oracle_labels,
    select_archive_entries,
)


def _candidate(
    *,
    changed_files: tuple[str, ...],
    event: SnapshotEvent = SnapshotEvent.FILE_EDIT,
    restore_ref: str,
) -> SnapshotCandidate:
    return SnapshotCandidate(
        id=f"trial:{restore_ref}",
        event=event,
        restore_ref=restore_ref,
        changed_files=changed_files,
        metadata={"trial_name": "trial", "step_id": "0"},
    )


def _archive() -> SnapshotArchive:
    archive = SnapshotArchive()
    archive.add(
        _candidate(
            changed_files=("a.py",),
            event=SnapshotEvent.FILE_EDIT,
            restore_ref="snap-a",
        )
    )
    archive.add(
        _candidate(
            changed_files=("b.py",),
            event=SnapshotEvent.TEST_RUN,
            restore_ref="snap-b",
        )
    )
    archive.add(
        _candidate(
            changed_files=("c.py",),
            event=SnapshotEvent.DISCOVERY,
            restore_ref="snap-c",
        )
    )
    return archive


def test_list_order_selector_uses_archive_insertion_order():
    selected = select_archive_entries(_archive(), mode="list_order", k=3)

    assert [item.entry.snapshot_name for item in selected] == [
        "snap-a",
        "snap-b",
        "snap-c",
    ]
    assert selected[0].selector_mode == "list_order"
    assert selected[0].selector_reasons == ("archive insertion order",)


def test_seeded_random_selector_is_reproducible():
    first = select_archive_entries(_archive(), mode="random", k=3, seed=42)
    second = select_archive_entries(_archive(), mode="random", k=3, seed=42)
    different_seed = select_archive_entries(_archive(), mode="random", k=3, seed=7)

    assert [item.entry.snapshot_name for item in first] == [
        item.entry.snapshot_name for item in second
    ]
    assert [item.entry.snapshot_name for item in first] != [
        item.entry.snapshot_name for item in different_seed
    ]
    assert first[0].selector_reasons == ("seed=42",)


def test_archive_priority_selector_uses_current_heuristic_ordering():
    selected = select_archive_entries(_archive(), mode="archive_priority", k=2)

    assert [item.entry.snapshot_name for item in selected] == ["snap-b", "snap-a"]
    assert selected[0].selector_mode == "archive_priority"
    assert selected[0].selector_reasons == (
        "priority=3.25",
        "score=3.25",
        "times_selected=0",
    )


def test_oracle_selector_uses_precomputed_labels():
    selected = select_archive_entries(
        _archive(),
        mode="oracle",
        k=2,
        oracle_labels={"snap-a": 0.1, "snap-b": 0.9, "snap-c": 0.4},
    )

    assert [item.entry.snapshot_name for item in selected] == ["snap-b", "snap-c"]
    assert selected[0].selector_reasons == ("oracle_label=0.9",)


def test_oracle_selector_can_use_cell_key_labels():
    selected = select_archive_entries(
        _archive(),
        mode="oracle",
        k=1,
        oracle_labels={"{c.py}": 1.0},
    )

    assert [item.entry.snapshot_name for item in selected] == ["snap-c"]


def test_oracle_selector_fails_when_labels_are_absent():
    with pytest.raises(ValueError, match="requires precomputed labels"):
        select_archive_entries(_archive(), mode="oracle", k=1)


def test_oracle_selector_fails_when_no_archive_entry_has_a_label():
    with pytest.raises(ValueError, match="found no labels"):
        select_archive_entries(
            _archive(),
            mode="oracle",
            k=1,
            oracle_labels={"missing-snapshot": 1.0},
        )


def test_load_oracle_labels_accepts_numeric_and_boolean_values(tmp_path):
    path = tmp_path / "oracle-labels.json"
    path.write_text(json.dumps({"snap-a": True, "{b.py}": 0.5}))

    assert load_oracle_labels(path) == {"snap-a": 1.0, "{b.py}": 0.5}


def test_load_oracle_labels_rejects_non_numeric_values(tmp_path):
    path = tmp_path / "oracle-labels.json"
    path.write_text(json.dumps({"snap-a": "yes"}))

    with pytest.raises(ValueError, match="must be a number or boolean"):
        load_oracle_labels(path)
