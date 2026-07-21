import asyncio
from pathlib import Path

from go_explore.snapshots import AsyncSnapshotManager, EveryAgentStepPolicy, SnapshotHandle
from go_explore.snapshots.replay import (
    extract_signals_from_atif_step,
    extract_signals_from_atif_steps,
    process_atif_trajectory,
)


def test_process_atif_trajectory_calls_snapshotting_once_per_agent_action():
    class CountingBackend:
        def __init__(self):
            self.calls: list[tuple[str, int]] = []

        async def create_snapshot(self, candidate, context):
            self.calls.append((candidate.id, context.step_id))
            return SnapshotHandle(
                backend="noop",
                environment_id=f"env-{context.step_id}",
                restore_ref=f"restore-{candidate.id}",
            )

    async def run_test():
        backend = CountingBackend()
        manager = AsyncSnapshotManager(
            policy=EveryAgentStepPolicy(),
            backend=backend,
        )
        trajectory_path = Path("tests/fixtures/atif_trajectory.json")

        records = await process_atif_trajectory(
            trajectory_path,
            manager,
            trial_name="fix-git__abc123",
        )

        assert backend.calls == [
            ("fix-git__abc123:step-2", 2),
            ("fix-git__abc123:step-3", 3),
        ]
        assert [record.id for record in records] == [
            "fix-git__abc123:step-2",
            "fix-git__abc123:step-3",
        ]
        assert [record.backend for record in records] == ["noop", "noop"]
        assert [record.candidate.metadata["snapshot_backend"] for record in records] == [
            "noop",
            "noop",
        ]
        assert [record.candidate.trace_path for record in records] == [
            trajectory_path,
            trajectory_path,
        ]
        assert manager.list() == records

    asyncio.run(run_test())


def _agent_step(command: str, *, observation: str = "", duration: float = 0.5):
    return {
        "step_id": 2,
        "source": "agent",
        "tool_calls": [
            {
                "function_name": "bash_command",
                "arguments": {"keystrokes": command, "duration": duration},
            }
        ],
        "observation": {"results": [{"content": observation}]},
    }


def test_extract_signals_preserves_unknown_commands():
    signals = extract_signals_from_atif_step(_agent_step("echo hello\n"))

    assert len(signals) == 1
    assert signals[0].event_type == "command_executed"
    assert signals[0].command == "echo hello"
    assert signals[0].step_id == 2
    assert signals[0].duration_seconds == 0.5


def test_extract_signals_detects_changed_files():
    signals = extract_signals_from_atif_step(_agent_step("sed -i 's/a/b/' ./main.py\n"))

    command_events = [signal for signal in signals if signal.event_type == "command_executed"]
    file_events = [signal for signal in signals if signal.event_type == "file_changed"]

    assert command_events[0].changed_files == ("main.py",)
    assert len(file_events) == 1
    assert file_events[0].changed_files == ("main.py",)
    assert file_events[0].metadata["detected_by"] == "command_heuristic"


def test_extract_signals_detects_pytest_counts():
    signals = extract_signals_from_atif_step(
        _agent_step("pytest tests -q\n", observation="3 passed, 1 failed")
    )

    test_events = [signal for signal in signals if signal.event_type == "test_run"]

    assert len(test_events) == 1
    assert test_events[0].framework == "pytest"
    assert test_events[0].tests_passed == 3
    assert test_events[0].tests_failed == 1


def test_extract_signals_detects_common_test_commands():
    cases = {
        "npm test\n": "npm",
        "cargo test\n": "cargo",
        "go test ./...\n": "go",
        "python -m unittest\n": "unittest",
    }

    for command, framework in cases.items():
        signals = extract_signals_from_atif_step(
            _agent_step(command, observation="passed")
        )
        test_events = [signal for signal in signals if signal.event_type == "test_run"]
        assert len(test_events) == 1
        assert test_events[0].framework == framework
        assert test_events[0].tests_passed == 1


def test_extract_signals_detects_dependency_installs():
    cases = {
        "pip install pytest requests\n": ("pip", ("pytest", "requests")),
        "python -m pip install -r requirements.txt pandas\n": ("pip", ("pandas",)),
        "uv pip install pytest\n": ("uv-pip", ("pytest",)),
        "npm install lodash\n": ("npm", ("lodash",)),
        "cargo add serde\n": ("cargo", ("serde",)),
        "go get github.com/example/pkg\n": ("go", ("github.com/example/pkg",)),
    }

    for command, expected in cases.items():
        signals = extract_signals_from_atif_step(_agent_step(command))
        dependency_events = [
            signal for signal in signals if signal.event_type == "dependency_installed"
        ]
        assert len(dependency_events) == 1
        assert dependency_events[0].dependency_manager == expected[0]
        assert dependency_events[0].packages == expected[1]


def test_extract_signals_from_steps_skips_non_agent_steps():
    signals = extract_signals_from_atif_steps(
        [
            {"step_id": 1, "source": "user", "message": "task"},
            _agent_step("go test ./...\n", observation="ok"),
        ]
    )

    assert [signal.event_type for signal in signals] == [
        "command_executed",
        "test_run",
    ]
