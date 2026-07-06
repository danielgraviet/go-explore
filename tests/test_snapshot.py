from pathlib import Path

import pytest

from go_explore.snapshots import (
    EveryAgentStepPolicy,
    HeuristicSnapshotSelector,
    InMemorySnapshotStore,
    InterestingAgentStepPolicy,
    NoopSnapshotBackend,
    SnapshotBackend,
    SnapshotCandidate,
    SnapshotEvent,
    SnapshotHandle,
    SnapshotManager,
    SnapshotRecord,
    context_from_atif_step,
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


def test_context_from_atif_step_extracts_tool_calls_and_observations():
    step = {
        "step_id": 4,
        "source": "agent",
        "timestamp": "2026-07-06T16:02:10Z",
        "model_name": "anthropic/test-model",
        "message": "Plan and commands",
        "tool_calls": [
            {
                "function_name": "bash_command",
                "arguments": {"keystrokes": "git status\n", "duration": 0.5},
            }
        ],
        "observation": {"results": [{"content": "working tree clean"}]},
    }

    context = context_from_atif_step(
        step,
        trial_name="fix-git__abc123",
        trace_path=Path("trajectory.json"),
        environment_id="env-1",
        restore_ref="restore-1",
    )

    assert context.trial_name == "fix-git__abc123"
    assert context.step_id == 4
    assert context.tool_calls[0]["function_name"] == "bash_command"
    assert context.observation_text == "working tree clean"
    assert context.trace_path == Path("trajectory.json")
    assert context.environment_id == "env-1"
    assert context.restore_ref == "restore-1"
    assert context.metadata["model_name"] == "anthropic/test-model"


def test_every_agent_step_policy_snapshots_each_agent_step_only():
    policy = EveryAgentStepPolicy()
    user_context = context_from_atif_step(
        {"step_id": 1, "source": "user", "message": "task"},
        trial_name="trial",
    )
    agent_context = context_from_atif_step(
        {
            "step_id": 2,
            "source": "agent",
            "tool_calls": [
                {
                    "function_name": "bash_command",
                    "arguments": {"keystrokes": "git status\n"},
                }
            ],
        },
        trial_name="trial",
    )

    assert policy.candidates_for_step(user_context) == []

    candidates = policy.candidates_for_step(agent_context)

    assert len(candidates) == 1
    assert candidates[0].id == "trial:step-2"
    assert candidates[0].event == SnapshotEvent.AGENT_STEP
    assert candidates[0].command == "git status"
    assert candidates[0].metadata["policy"] == "every_agent_step"


def test_interesting_policy_snapshots_git_transitions_and_file_edits():
    policy = InterestingAgentStepPolicy()
    context = context_from_atif_step(
        {
            "step_id": 6,
            "source": "agent",
            "tool_calls": [
                {
                    "function_name": "bash_command",
                    "arguments": {
                        "keystrokes": "cat > _includes/about.md << 'EOF'\nnew text\nEOF\n"
                    },
                },
                {
                    "function_name": "bash_command",
                    "arguments": {"keystrokes": "git add _includes/about.md\n"},
                },
            ],
            "observation": {"results": [{"content": "file updated"}]},
        },
        trial_name="fix-git__abc123",
    )

    candidates = policy.candidates_for_step(context)

    assert len(candidates) == 1
    assert candidates[0].event == SnapshotEvent.FILE_EDIT
    assert candidates[0].changed_files == ("_includes/about.md",)
    assert candidates[0].metadata["policy"] == "interesting_agent_step"


def test_interesting_policy_ignores_low_signal_agent_step():
    policy = InterestingAgentStepPolicy()
    context = context_from_atif_step(
        {
            "step_id": 2,
            "source": "agent",
            "tool_calls": [
                {
                    "function_name": "bash_command",
                    "arguments": {"keystrokes": "ls -la\n"},
                }
            ],
            "observation": {"results": [{"content": "README.md"}]},
        },
        trial_name="trial",
    )

    assert policy.candidates_for_step(context) == []


def test_in_memory_snapshot_store_put_get_list_and_replace():
    first = SnapshotRecord(
        candidate=SnapshotCandidate(id="snapshot-1", event=SnapshotEvent.AGENT_STEP),
        description="first version",
    )
    replacement = SnapshotRecord(
        candidate=SnapshotCandidate(id="snapshot-1", event=SnapshotEvent.FILE_EDIT),
        description="replacement version",
    )
    second = SnapshotRecord(
        candidate=SnapshotCandidate(id="snapshot-2", event=SnapshotEvent.TEST_RUN),
        description="second snapshot",
    )

    store = InMemorySnapshotStore()
    store.put(first)
    store.put(second)
    store.put(replacement)

    assert store.get("snapshot-1") == replacement
    assert store.get("missing") is None
    assert store.list() == [replacement, second]
    assert store.as_dict() == {"snapshot-1": replacement, "snapshot-2": second}


def test_noop_snapshot_backend_preserves_existing_references():
    backend = NoopSnapshotBackend()
    candidate = SnapshotCandidate(
        id="snapshot-1",
        event=SnapshotEvent.AGENT_STEP,
        environment_id="candidate-env",
        restore_ref="candidate-restore",
    )
    context = context_from_atif_step(
        {"step_id": 1, "source": "agent"},
        trial_name="trial",
        environment_id="context-env",
    )

    handle = backend.create_snapshot(candidate, context)

    assert handle.backend == "noop"
    assert handle.environment_id == "candidate-env"
    assert handle.restore_ref == "candidate-restore"


def test_snapshot_manager_processes_policy_candidates_into_records():
    manager = SnapshotManager(policy=EveryAgentStepPolicy())
    context = context_from_atif_step(
        {
            "step_id": 2,
            "source": "agent",
            "tool_calls": [
                {
                    "function_name": "bash_command",
                    "arguments": {"keystrokes": "git status\n"},
                }
            ],
        },
        trial_name="fix-git__abc123",
    )

    records = manager.process_step(context)

    assert len(records) == 1
    assert records[0].id == "fix-git__abc123:step-2"
    assert records[0].backend == "noop"
    assert records[0].candidate.command == "git status"
    assert records[0].candidate.metadata["snapshot_backend"] == "noop"
    assert records[0].description == "agent_step | trial=fix-git__abc123 | step=2 | agent step"
    assert manager.get("fix-git__abc123:step-2") == records[0]
    assert manager.list() == records


def test_snapshot_manager_does_not_store_when_policy_returns_no_candidates():
    manager = SnapshotManager(policy=InterestingAgentStepPolicy())
    context = context_from_atif_step(
        {
            "step_id": 2,
            "source": "agent",
            "tool_calls": [
                {
                    "function_name": "bash_command",
                    "arguments": {"keystrokes": "ls\n"},
                }
            ],
            "observation": {"results": [{"content": "README.md"}]},
        },
        trial_name="trial",
    )

    assert manager.process_step(context) == []
    assert manager.list() == []


def test_snapshot_manager_accepts_replaceable_store():
    class RecordingStore:
        def __init__(self):
            self.records: dict[str, SnapshotRecord] = {}
            self.put_calls: list[str] = []

        def put(self, record: SnapshotRecord) -> None:
            self.put_calls.append(record.id)
            self.records[record.id] = record

        def get(self, snapshot_id: str) -> SnapshotRecord | None:
            return self.records.get(snapshot_id)

        def list(self) -> list[SnapshotRecord]:
            return list(self.records.values())

    store = RecordingStore()
    manager = SnapshotManager(policy=EveryAgentStepPolicy(), store=store)
    context = context_from_atif_step(
        {"step_id": 3, "source": "agent"},
        trial_name="trial",
    )

    records = manager.process_step(context)

    assert store.put_calls == ["trial:step-3"]
    assert store.get("trial:step-3") == records[0]


def test_snapshot_manager_accepts_replaceable_backend():
    class RecordingBackend:
        def __init__(self):
            self.calls: list[str] = []

        def create_snapshot(
            self,
            candidate: SnapshotCandidate,
            context,
        ) -> SnapshotHandle:
            self.calls.append(candidate.id)
            return SnapshotHandle(
                backend="recording",
                environment_id=f"env-{context.step_id}",
                restore_ref=f"restore-{candidate.id}",
                metadata={"backend_note": "captured"},
            )

    backend = RecordingBackend()
    manager = SnapshotManager(policy=EveryAgentStepPolicy(), backend=backend)
    context = context_from_atif_step(
        {"step_id": 4, "source": "agent"},
        trial_name="trial",
    )

    records = manager.process_step(context)

    assert backend.calls == ["trial:step-4"]
    assert records[0].backend == "recording"
    assert records[0].candidate.environment_id == "env-4"
    assert records[0].candidate.restore_ref == "restore-trial:step-4"
    assert records[0].candidate.metadata["snapshot_backend"] == "recording"
    assert records[0].candidate.metadata["backend_note"] == "captured"
