import asyncio
import sys
import types
from pathlib import Path

import pytest

from go_explore.snapshots import (
    AsyncNoopSnapshotBackend,
    DaytonaSnapshotBackend,
    EveryAgentStepPolicy,
    HeuristicSnapshotSelector,
    InMemorySnapshotStore,
    InterestingAgentStepPolicy,
    SnapshotCandidate,
    SnapshotEvent,
    SnapshotRecord,
    context_from_atif_step,
    daytona_snapshot_name,
)
from go_explore.snapshots.backends import _delete_daytona_snapshot_sync


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

    assert scored.score == pytest.approx(2.5)
    assert scored.candidate is candidate
    assert scored.reasons == (
        "4 tests passed",
        "2 tests failed",
        "mixed validation signal",
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


def test_daytona_delete_snapshot_uses_sync_get_then_delete(monkeypatch):
    calls = []

    class FakeSnapshotService:
        def get(self, name):
            calls.append(("get", name))
            return {"name": name}

        def delete(self, snapshot):
            calls.append(("delete", snapshot))
            return None

    class FakeDaytona:
        def __init__(self):
            self.snapshot = FakeSnapshotService()

    monkeypatch.setitem(
        sys.modules,
        "daytona",
        types.SimpleNamespace(Daytona=FakeDaytona),
    )

    _delete_daytona_snapshot_sync("snapshot-a")

    assert calls == [
        ("get", "snapshot-a"),
        ("delete", {"name": "snapshot-a"}),
    ]


def test_discovery_snapshot_gets_investigation_bonus():
    selector = HeuristicSnapshotSelector()
    candidate = SnapshotCandidate(
        id="found-password-fragment",
        event=SnapshotEvent.DISCOVERY,
        command="strings ae3f4c.dat | grep PASSWORD",
        notes="investigative command",
    )

    scored = selector.score(candidate)

    assert scored.score == pytest.approx(1.0)
    assert scored.reasons == ("captures an investigative discovery",)


def test_terminal_failure_snapshot_is_penalized():
    selector = HeuristicSnapshotSelector()
    candidate = SnapshotCandidate(
        id="failed-final-state",
        event=SnapshotEvent.FAILURE,
        tests_passed=1,
        tests_failed=3,
    )

    scored = selector.score(candidate)

    assert scored.score == pytest.approx(-5.5)
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

    assert scored.score == pytest.approx(-25.75)
    assert scored.reasons == (
        "2 tests passed",
        "100 tests failed",
        "mixed validation signal",
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
    assert [snapshot.score for snapshot in selected] == pytest.approx([4.5, 1.25])


def test_selector_prefers_positive_probe_over_plain_file_edit():
    selector = HeuristicSnapshotSelector()
    passing_probe = SnapshotCandidate(
        id="tests-good",
        event=SnapshotEvent.TEST_RUN,
        tests_passed=1,
        tests_failed=0,
    )
    plain_edit = SnapshotCandidate(
        id="edit",
        event=SnapshotEvent.FILE_EDIT,
        changed_files=("app.py",),
    )

    selected = selector.select([plain_edit, passing_probe], limit=2)

    assert [snapshot.candidate.id for snapshot in selected] == ["tests-good", "edit"]
    assert selector.score(passing_probe).reasons == (
        "1 tests passed",
        "0 tests failed",
        "all observed tests passed",
    )


def test_selector_downranks_negative_probe_below_plain_file_edit():
    selector = HeuristicSnapshotSelector()
    failing_probe = SnapshotCandidate(
        id="tests-bad",
        event=SnapshotEvent.TEST_RUN,
        tests_passed=None,
        tests_failed=1,
    )
    plain_edit = SnapshotCandidate(
        id="edit",
        event=SnapshotEvent.FILE_EDIT,
        changed_files=("app.py",),
    )

    selected = selector.select([failing_probe, plain_edit], limit=2)

    assert [snapshot.candidate.id for snapshot in selected] == ["edit", "tests-bad"]
    assert selector.score(failing_probe).score < selector.score(plain_edit).score
    assert selector.score(failing_probe).reasons == (
        "1 tests failed",
        "failed validation signal",
    )


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


def test_interesting_policy_snapshots_investigative_commands():
    policy = InterestingAgentStepPolicy()
    context = context_from_atif_step(
        {
            "step_id": 15,
            "source": "agent",
            "tool_calls": [
                {
                    "function_name": "bash_command",
                    "arguments": {
                        "keystrokes": "strings ae3f4c.dat | grep PASSWORD\n",
                    },
                },
            ],
            "observation": {"results": [{"content": "PASSWORD=8XDP5Q2RT9Z"}]},
        },
        trial_name="password-recovery__abc123",
    )

    candidates = policy.candidates_for_step(context)

    assert len(candidates) == 1
    assert candidates[0].event == SnapshotEvent.DISCOVERY
    assert "investigative command" in candidates[0].notes


def test_interesting_policy_extracts_positive_probe_metadata():
    policy = InterestingAgentStepPolicy()
    context = context_from_atif_step(
        {
            "step_id": 9,
            "source": "agent",
            "tool_calls": [
                {
                    "function_name": "bash_command",
                    "arguments": {"keystrokes": "pytest tests/test_regex.py -q\n"},
                },
            ],
            "observation": {"results": [{"content": "3 passed in 0.12s"}]},
        },
        trial_name="regex-log-r3__abc123",
    )

    candidate = policy.candidates_for_step(context)[0]

    assert candidate.event == SnapshotEvent.TEST_RUN
    assert candidate.tests_passed == 3
    assert candidate.tests_failed is None
    assert candidate.metadata["probe_signal"] == "validation"
    assert candidate.metadata["probe_status"] == "positive"
    assert candidate.metadata["probe_framework"] == "pytest"
    assert candidate.metadata["tests_passed"] == "3"
    assert candidate.notes == "positive validation signal"


def test_interesting_policy_does_not_treat_successful_install_as_test_pass():
    policy = InterestingAgentStepPolicy()
    context = context_from_atif_step(
        {
            "step_id": 0,
            "source": "agent",
            "tool_calls": [
                {
                    "function_name": "bash_command",
                    "arguments": {
                        "keystrokes": "pip install grpcio==1.73.0\n"
                    },
                }
            ],
            "observation": {
                "results": [{"content": "Successfully installed grpcio-1.73.0"}]
            },
        },
        trial_name="kv-store-grpc__abc123",
    )

    assert policy.candidates_for_step(context) == []


def test_interesting_policy_extracts_negative_assertion_probe_metadata():
    policy = InterestingAgentStepPolicy()
    context = context_from_atif_step(
        {
            "step_id": 10,
            "source": "agent",
            "tool_calls": [
                {
                    "function_name": "bash_command",
                    "arguments": {
                        "keystrokes": (
                            "python - <<'PY'\nassert parse('x') == 1\nPY\n"
                        ),
                    },
                },
            ],
            "observation": {"results": [{"content": "AssertionError"}]},
        },
        trial_name="regex-log-r3__abc123",
    )

    candidate = policy.candidates_for_step(context)[0]

    assert candidate.event == SnapshotEvent.TEST_RUN
    assert candidate.tests_passed is None
    assert candidate.tests_failed == 1
    assert candidate.metadata["probe_status"] == "negative"
    assert candidate.metadata["probe_framework"] == "assertion"
    assert candidate.metadata["probe_error_signal"] == "true"


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
    async def run_test():
        backend = AsyncNoopSnapshotBackend()
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

        handle = await backend.create_snapshot(candidate, context)

        assert handle.backend == "noop"
        assert handle.environment_id == "candidate-env"
        assert handle.restore_ref == "candidate-restore"

    asyncio.run(run_test())


def test_daytona_snapshot_name_normalizes_candidate_ids():
    name = daytona_snapshot_name("fix-git__trial:step-4/file edit", prefix="go-explore")

    assert name == "go-explore-fix-git__trial-step-4-file-edit"
