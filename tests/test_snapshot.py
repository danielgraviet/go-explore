from pathlib import Path

import pytest

from go_explore.snapshots import (
    HeuristicSnapshotSelector,
    SnapshotCandidate,
    SnapshotEvent,
)


def test_scores_validation_snapshot_with_test_signal_and_changed_files():
    selector = HeuristicSnapshotSelector()
    candidate = SnapshotCandidate(
        id="after-tests",
        event=SnapshotEvent.TEST_RUN,
        tests_passed=4,
        tests_failed=2,
        changed_files=("app.py", "tests/test_app.py"),
    )

    scored = selector.score(candidate)

    assert scored.score == pytest.approx(6.5)
    assert scored.candidate is candidate
    assert scored.reasons == (
        "4 tests passed",
        "2 tests failed",
        "has validation signal",
        "2 changed files",
    )


def test_file_edit_snapshot_gets_edit_bonus_and_preserves_metadata():
    selector = HeuristicSnapshotSelector()
    candidate = SnapshotCandidate(
        id="custom-checkpoint",
        event=SnapshotEvent.FILE_EDIT,
        environment_id="env-123",
        restore_ref="snapshot-abc",
        trace_path=Path("jobs/run-1/trial/trace.jsonl"),
        changed_files=("go_explore/snapshots.py",),
        command="apply_patch",
        notes="after adding scoring",
        metadata={"trial": "trial-1", "agent": "codex"},
    )

    scored = selector.score(candidate)

    assert scored.score == pytest.approx(1.25)
    assert scored.candidate.id == "custom-checkpoint"
    assert scored.candidate.environment_id == "env-123"
    assert scored.candidate.restore_ref == "snapshot-abc"
    assert scored.candidate.trace_path == Path("jobs/run-1/trial/trace.jsonl")
    assert scored.candidate.metadata["agent"] == "codex"
    assert scored.reasons == ("captures a file edit", "1 changed files")


def test_terminal_failure_snapshot_is_penalized():
    selector = HeuristicSnapshotSelector()
    candidate = SnapshotCandidate(
        id="failed-final-state",
        event=SnapshotEvent.FAILURE,
        tests_passed=1,
        tests_failed=3,
    )

    scored = selector.score(candidate)

    assert scored.score == pytest.approx(-2.5)
    assert scored.reasons == (
        "1 tests passed",
        "3 tests failed",
        "terminal event: failure",
    )


def test_score_caps_large_failure_and_changed_file_counts():
    selector = HeuristicSnapshotSelector()
    candidate = SnapshotCandidate(
        id="large-noisy-state",
        event=SnapshotEvent.VERIFIER,
        tests_passed=2,
        tests_failed=100,
        changed_files=tuple(f"file_{index}.py" for index in range(20)),
    )

    scored = selector.score(candidate)

    assert scored.score == pytest.approx(-3.75)
    assert scored.reasons == (
        "2 tests passed",
        "100 tests failed",
        "has validation signal",
        "20 changed files",
    )


def test_select_returns_highest_scoring_snapshots_in_order():
    selector = HeuristicSnapshotSelector()
    candidates = [
        SnapshotCandidate(id="command", event=SnapshotEvent.COMMAND),
        SnapshotCandidate(
            id="tests-bad",
            event=SnapshotEvent.TEST_RUN,
            tests_passed=1,
            tests_failed=6,
        ),
        SnapshotCandidate(
            id="tests-good",
            event=SnapshotEvent.TEST_RUN,
            tests_passed=5,
            tests_failed=1,
        ),
        SnapshotCandidate(
            id="edit",
            event=SnapshotEvent.FILE_EDIT,
            changed_files=("app.py",),
        ),
    ]

    selected = selector.select(candidates, limit=2)

    assert [snapshot.candidate.id for snapshot in selected] == ["tests-good", "edit"]
    assert [snapshot.score for snapshot in selected] == pytest.approx([7.5, 1.25])


def test_select_handles_empty_candidates():
    assert HeuristicSnapshotSelector().select([], limit=3) == []
