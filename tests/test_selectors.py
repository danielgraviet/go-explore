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
    tests_passed: int | None = None,
    tests_failed: int | None = None,
) -> SnapshotCandidate:
    return SnapshotCandidate(
        id=f"trial:{restore_ref}",
        event=event,
        restore_ref=restore_ref,
        changed_files=changed_files,
        tests_passed=tests_passed,
        tests_failed=tests_failed,
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
            tests_passed=1,
            tests_failed=0,
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
        "priority=4.25",
        "score=4.25",
        "times_selected=0",
    )


def test_validated_progress_selector_requires_passing_validation():
    archive = SnapshotArchive()
    archive.add(
        _candidate(
            changed_files=("bad.py",),
            event=SnapshotEvent.TEST_RUN,
            restore_ref="snap-bad",
            tests_passed=2,
            tests_failed=1,
        )
    )
    archive.add(
        _candidate(
            changed_files=("good.py",),
            event=SnapshotEvent.TEST_RUN,
            restore_ref="snap-good",
            tests_passed=2,
            tests_failed=0,
        )
    )
    archive.add(
        _candidate(
            changed_files=("edit.py",),
            event=SnapshotEvent.FILE_EDIT,
            restore_ref="snap-edit",
        )
    )

    selected = select_archive_entries(
        archive, mode="validated_progress", k=3
    )

    assert [item.entry.snapshot_name for item in selected] == ["snap-good"]
    assert selected[0].selector_reasons == (
        "2 tests passed",
        "0 tests failed",
        "validated progress",
    )


def test_validated_progress_selector_returns_empty_without_validation():
    assert select_archive_entries(
        SnapshotArchive(), mode="validated_progress", k=2
    ) == []


def test_partial_progress_selector_accepts_discovery_and_partial_tests():
    archive = SnapshotArchive()
    archive.add(
        _candidate(
            changed_files=(),
            event=SnapshotEvent.DISCOVERY,
            restore_ref="snap-discovery",
        )
    )
    archive.add(
        _candidate(
            changed_files=("test.py",),
            event=SnapshotEvent.TEST_RUN,
            restore_ref="snap-partial",
            tests_passed=2,
            tests_failed=1,
        )
    )
    archive.add(
        _candidate(
            changed_files=(),
            event=SnapshotEvent.FILE_EDIT,
            restore_ref="snap-edit",
        )
    )

    selected = select_archive_entries(
        archive, mode="partial_progress", k=3
    )

    assert [item.entry.snapshot_name for item in selected] == [
        "snap-partial",
        "snap-discovery",
    ]
    assert selected[0].selector_reasons == (
        "2 tests passed",
        "1 tests failed",
        "partial validation progress",
    )
    assert selected[1].selector_reasons == (
        "investigative discovery",
        "partial progress candidate",
    )


def test_partial_progress_selector_accepts_file_edits_without_validation_signal():
    archive = SnapshotArchive()
    archive.add(
        _candidate(
            changed_files=("kv-store.proto", "server.py"),
            event=SnapshotEvent.FILE_EDIT,
            restore_ref="snap-edit",
        )
    )
    archive.add(
        _candidate(
            changed_files=(),
            event=SnapshotEvent.FILE_EDIT,
            restore_ref="snap-edit-no-files",
        )
    )

    selected = select_archive_entries(archive, mode="partial_progress", k=3)

    assert [item.entry.snapshot_name for item in selected] == ["snap-edit"]
    assert selected[0].selector_reasons == (
        "2 changed files",
        "file edit without validation signal",
        "partial progress candidate",
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
