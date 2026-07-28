"""Tests for the snapshot-aware agent wrapper."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock

import pytest

from go_explore.agents.factory import SnapshotAwareTerminus2
from go_explore.agents.snapshot_agent import SnapshotAwareAgent
from go_explore.snapshots.policies import (
    EveryAgentStepPolicy,
    InterestingAgentStepPolicy,
)


def test_snapshot_aware_terminus2_advertises_atif_support():
    assert SnapshotAwareTerminus2.SUPPORTS_ATIF is True


def test_snapshot_aware_terminus2_defaults_to_tmux_preflight_without_recording(
    tmp_path,
    monkeypatch,
):
    captured: dict[str, object] = {}

    class FakeTerminus2:
        def __init__(self, *, logs_dir, model_name, logger=None, **kwargs):
            captured["logs_dir"] = logs_dir
            captured["model_name"] = model_name
            captured["logger"] = logger
            captured["kwargs"] = kwargs

        def to_agent_info(self):
            return {"name": "terminus-2"}

    harbor_module = ModuleType("harbor")
    agents_module = ModuleType("harbor.agents")
    terminus_module = ModuleType("harbor.agents.terminus_2")
    terminus_module.Terminus2 = FakeTerminus2
    monkeypatch.setitem(sys.modules, "harbor", harbor_module)
    monkeypatch.setitem(sys.modules, "harbor.agents", agents_module)
    monkeypatch.setitem(sys.modules, "harbor.agents.terminus_2", terminus_module)

    agent = SnapshotAwareTerminus2(logs_dir=tmp_path, model_name="model-a")

    assert agent._preinstall_tmux is True
    assert captured["kwargs"]["record_terminal_session"] is False


def test_snapshot_aware_terminus2_accepts_context_mode_without_wrapped_leak(
    tmp_path,
    monkeypatch,
):
    captured: dict[str, object] = {}

    class FakeTerminus2:
        def __init__(self, *, logs_dir, model_name, logger=None, **kwargs):
            captured["kwargs"] = kwargs

        def to_agent_info(self):
            return {"name": "terminus-2"}

    harbor_module = ModuleType("harbor")
    agents_module = ModuleType("harbor.agents")
    terminus_module = ModuleType("harbor.agents.terminus_2")
    terminus_module.Terminus2 = FakeTerminus2
    monkeypatch.setitem(sys.modules, "harbor", harbor_module)
    monkeypatch.setitem(sys.modules, "harbor.agents", agents_module)
    monkeypatch.setitem(sys.modules, "harbor.agents.terminus_2", terminus_module)

    agent = SnapshotAwareTerminus2(
        logs_dir=tmp_path,
        model_name="model-a",
        context_mode="none",
        parent_context_path=tmp_path / "parent.md",
    )

    assert agent._context_mode == "none"
    assert agent._parent_context_path == tmp_path / "parent.md"
    assert "context_mode" not in captured["kwargs"]
    assert "parent_context_path" not in captured["kwargs"]


def test_snapshot_aware_terminus2_accepts_diff_path_without_wrapped_leak(
    tmp_path,
    monkeypatch,
):
    """Regression test: diff_path must reach SnapshotAwareAgent (which applies
    it in setup()), not leak through to the wrapped Terminus2 as an unknown
    kwarg - that bug meant `--ak diff_path=...` silently never applied any
    diff in a live run, with no error to signal it."""
    captured: dict[str, object] = {}

    class FakeTerminus2:
        def __init__(self, *, logs_dir, model_name, logger=None, **kwargs):
            captured["kwargs"] = kwargs

        def to_agent_info(self):
            return {"name": "terminus-2"}

    harbor_module = ModuleType("harbor")
    agents_module = ModuleType("harbor.agents")
    terminus_module = ModuleType("harbor.agents.terminus_2")
    terminus_module.Terminus2 = FakeTerminus2
    monkeypatch.setitem(sys.modules, "harbor", harbor_module)
    monkeypatch.setitem(sys.modules, "harbor.agents", agents_module)
    monkeypatch.setitem(sys.modules, "harbor.agents.terminus_2", terminus_module)

    agent = SnapshotAwareTerminus2(
        logs_dir=tmp_path,
        model_name="model-a",
        diff_path=str(tmp_path / "parent.diff"),
        diff_apply_timeout_sec=30.0,
    )

    assert agent._diff_path == tmp_path / "parent.diff"
    assert agent._diff_apply_timeout_sec == 30.0
    assert "diff_path" not in captured["kwargs"]
    assert "diff_apply_timeout_sec" not in captured["kwargs"]


def test_snapshot_aware_agent_instantiation_without_sandbox():
    """Test that SnapshotAwareAgent can be instantiated without a sandbox."""
    wrapped = MagicMock()
    wrapped.name.return_value = "mock-agent"

    agent = SnapshotAwareAgent(wrapped_agent=wrapped)

    assert agent._wrapped_agent is wrapped
    assert agent._sandbox is None
    assert agent._snapshot_session is None


def test_snapshot_aware_agent_instantiation_with_sandbox():
    """Test that SnapshotAwareAgent initializes snapshot session with sandbox."""
    wrapped = MagicMock()
    sandbox = MagicMock()

    agent = SnapshotAwareAgent(wrapped_agent=wrapped, sandbox=sandbox)

    assert agent._wrapped_agent is wrapped
    assert agent._sandbox is sandbox
    assert agent._snapshot_session is not None


def test_snapshot_aware_agent_defaults_to_interesting_policy():
    """Test that the wrapper defaults to InterestingAgentStepPolicy, not every-step."""
    wrapped = MagicMock()

    agent = SnapshotAwareAgent(wrapped_agent=wrapped)

    assert isinstance(agent._snapshot_policy, InterestingAgentStepPolicy)


def test_snapshot_aware_agent_accepts_custom_policy():
    """Test that an explicit snapshot_policy overrides the default."""
    wrapped = MagicMock()
    policy = EveryAgentStepPolicy()

    agent = SnapshotAwareAgent(wrapped_agent=wrapped, snapshot_policy=policy)

    assert agent._snapshot_policy is policy


def test_snapshot_aware_agent_rejects_unknown_context_mode():
    with pytest.raises(ValueError, match="Unknown context_mode"):
        SnapshotAwareAgent(wrapped_agent=MagicMock(), context_mode="trust_parent")


def test_snapshot_aware_agent_appends_parent_context_by_default():
    class FakeWrapped:
        def __init__(self):
            self.instruction = None

        def perform_task(
            self, *, instruction, session, logging_dir=None, time_limit_seconds=None
        ):
            self.instruction = instruction
            return MagicMock()

        def to_agent_info(self):
            return {}

    wrapped = FakeWrapped()
    agent = SnapshotAwareAgent(wrapped_agent=wrapped)
    agent._load_parent_context = AsyncMock(return_value="step 1: parent note")  # type: ignore[method-assign]

    agent.perform_task("solve task", MagicMock(session_name="trial-a"))

    assert wrapped.instruction is not None
    assert "solve task" in wrapped.instruction
    assert "step 1: parent note" in wrapped.instruction


def test_snapshot_aware_agent_none_context_mode_does_not_append_parent_context():
    class FakeWrapped:
        def __init__(self):
            self.instruction = None

        def perform_task(
            self, *, instruction, session, logging_dir=None, time_limit_seconds=None
        ):
            self.instruction = instruction
            return MagicMock()

        def to_agent_info(self):
            return {}

    wrapped = FakeWrapped()
    agent = SnapshotAwareAgent(wrapped_agent=wrapped, context_mode="none")
    agent._load_parent_context = AsyncMock(return_value="step 1: parent note")  # type: ignore[method-assign]

    agent.perform_task("solve task", MagicMock(session_name="trial-a"))

    assert wrapped.instruction == "solve task"


def test_snapshot_aware_agent_critical_context_uses_untrusted_audit_prompt():
    class FakeWrapped:
        def __init__(self):
            self.instruction = None

        def perform_task(
            self, *, instruction, session, logging_dir=None, time_limit_seconds=None
        ):
            self.instruction = instruction
            return MagicMock()

        def to_agent_info(self):
            return {}

    wrapped = FakeWrapped()
    agent = SnapshotAwareAgent(
        wrapped_agent=wrapped,
        context_mode="critical_parent_summary",
    )
    agent._load_parent_context = AsyncMock(return_value="step 1: parent note")  # type: ignore[method-assign]

    agent.perform_task("solve task", MagicMock(session_name="trial-a"))

    assert wrapped.instruction is not None
    assert "solve task" in wrapped.instruction
    assert "step 1: parent note" in wrapped.instruction
    assert "untrusted evidence" in wrapped.instruction
    assert "unknown or failed" in wrapped.instruction
    assert "Independently audit" in wrapped.instruction
    assert "do not declare success solely" in wrapped.instruction
    assert "so you don't repeat it" not in wrapped.instruction


@pytest.mark.asyncio
async def test_snapshot_aware_agent_tmux_preflight_skips_when_tmux_exists():
    wrapped = MagicMock()
    wrapped.setup = AsyncMock()
    environment = MagicMock()
    environment.exec = AsyncMock(return_value=MagicMock(return_code=0))
    agent = SnapshotAwareAgent(wrapped_agent=wrapped, preinstall_tmux=True)

    await agent.setup(environment)

    environment.exec.assert_awaited_once_with(
        command="tmux -V",
        user="root",
        timeout_sec=30,
    )
    wrapped.setup.assert_awaited_once_with(environment)


@pytest.mark.asyncio
async def test_snapshot_aware_agent_tmux_preflight_installs_when_missing():
    wrapped = MagicMock()
    wrapped.setup = AsyncMock()
    environment = MagicMock()
    environment.exec = AsyncMock(
        side_effect=[
            MagicMock(return_code=1),
            MagicMock(return_code=0),
        ]
    )
    agent = SnapshotAwareAgent(
        wrapped_agent=wrapped,
        preinstall_tmux=True,
        tmux_install_timeout_sec=123.0,
    )

    await agent.setup(environment)

    assert environment.exec.await_count == 2
    install_call = environment.exec.await_args_list[1].kwargs
    assert "apt-get install -y tmux" in install_call["command"]
    assert "asciinema" not in install_call["command"]
    assert install_call["user"] == "root"
    assert install_call["timeout_sec"] == 123.0
    wrapped.setup.assert_awaited_once_with(environment)


@pytest.mark.asyncio
async def test_snapshot_aware_agent_tmux_preflight_raises_clear_error_on_failure():
    wrapped = MagicMock()
    wrapped.setup = AsyncMock()
    environment = MagicMock()
    environment.exec = AsyncMock(
        side_effect=[
            MagicMock(return_code=1),
            MagicMock(return_code=1, stderr="apt failed"),
        ]
    )
    agent = SnapshotAwareAgent(wrapped_agent=wrapped, preinstall_tmux=True)

    with pytest.raises(RuntimeError, match="tmux preflight failed: apt failed"):
        await agent.setup(environment)

    wrapped.setup.assert_not_awaited()


@pytest.mark.asyncio
async def test_snapshot_aware_agent_applies_diff_before_wrapped_setup(tmp_path):
    diff_path = tmp_path / "parent.diff"
    diff_path.write_text("diff --git a/x b/x\n")
    wrapped = MagicMock()
    wrapped.setup = AsyncMock()
    environment = MagicMock()
    environment.upload_file = AsyncMock()
    environment.exec = AsyncMock(return_value=MagicMock(return_code=0))
    environment.task_env_config = MagicMock(workdir="/app")
    agent = SnapshotAwareAgent(wrapped_agent=wrapped, diff_path=diff_path)

    await agent.setup(environment)

    environment.upload_file.assert_awaited_once()
    wrapped.setup.assert_awaited_once_with(environment)


@pytest.mark.asyncio
async def test_snapshot_aware_agent_diff_apply_failure_raises_distinct_error(tmp_path):
    diff_path = tmp_path / "parent.diff"
    diff_path.write_text("diff --git a/x b/x\n")
    wrapped = MagicMock()
    wrapped.setup = AsyncMock()
    environment = MagicMock()
    environment.upload_file = AsyncMock()
    environment.exec = AsyncMock(
        return_value=MagicMock(return_code=1, stderr="patch does not apply")
    )
    environment.task_env_config = MagicMock(workdir="/app")
    agent = SnapshotAwareAgent(wrapped_agent=wrapped, diff_path=diff_path)

    from go_explore.snapshots.diff_only import DiffApplyFailed

    with pytest.raises(DiffApplyFailed, match="patch does not apply"):
        await agent.setup(environment)

    wrapped.setup.assert_not_awaited()


@pytest.mark.asyncio
async def test_snapshot_aware_agent_skips_diff_apply_when_no_diff_path():
    wrapped = MagicMock()
    wrapped.setup = AsyncMock()
    environment = MagicMock()
    environment.upload_file = AsyncMock()
    agent = SnapshotAwareAgent(wrapped_agent=wrapped)

    await agent.setup(environment)

    environment.upload_file.assert_not_awaited()
    wrapped.setup.assert_awaited_once_with(environment)


def test_snapshot_aware_agent_name_matches_wrapped():
    """Test that agent name delegates to wrapped agent."""
    wrapped = MagicMock()
    wrapped.name.return_value = "terminus-2"

    # We can't easily test this without terminal-bench, but we can verify
    # the method exists and is callable
    assert hasattr(SnapshotAwareAgent, "name")
    assert callable(SnapshotAwareAgent.name)


def test_snapshot_aware_agent_stores_trial_name():
    """Test that trial name is stored during perform_task."""
    wrapped = MagicMock()
    session = MagicMock()
    session.session_name = "test-trial-123"

    agent = SnapshotAwareAgent(wrapped_agent=wrapped)

    # perform_task would be called here, but we can't without terminal-bench
    # Instead, verify the attributes are set up correctly
    assert agent._trial_name is None
    assert agent._step_counter == 0


def test_snapshot_agent_handles_missing_execute_commands():
    """Test that the wrapper gracefully handles agents without _execute_commands."""
    wrapped = MagicMock(spec=[])  # Empty spec - no attributes
    wrapped.__class__.__name__ = "CustomAgent"

    agent = SnapshotAwareAgent(wrapped_agent=wrapped)

    # _hook_agent_loop should not crash even if _execute_commands doesn't exist
    try:
        agent._hook_agent_loop()
    except AttributeError:
        pytest.fail("_hook_agent_loop should not raise AttributeError")


@pytest.mark.asyncio
async def test_process_step_snapshot_with_empty_commands():
    """Test that process_step_snapshot handles empty command lists."""
    wrapped = MagicMock()
    agent = SnapshotAwareAgent(wrapped_agent=wrapped)

    # Should return early without processing
    await agent._process_step_snapshot([], "output")
    # No exception should be raised


@pytest.mark.asyncio
async def test_process_step_snapshot_without_session():
    """Test that process_step_snapshot handles missing snapshot session."""
    wrapped = MagicMock()
    agent = SnapshotAwareAgent(wrapped_agent=wrapped, sandbox=None)

    # No snapshot session, should handle gracefully
    await agent._process_step_snapshot(["git status"], "output")
    # No exception should be raised


@pytest.mark.asyncio
async def test_process_step_snapshot_creates_snapshot_for_every_command_batch():
    """Test that the wrapper snapshots a normal agent command batch under EveryAgentStepPolicy."""
    wrapped = MagicMock()
    sandbox = MagicMock()
    sandbox.id = "snapshot-test-sandbox"
    sandbox._experimental_create_snapshot = AsyncMock()

    agent = SnapshotAwareAgent(
        wrapped_agent=wrapped, sandbox=sandbox, snapshot_policy=EveryAgentStepPolicy()
    )

    await agent._process_step_snapshot(["pwd"], "working directory")

    sandbox._experimental_create_snapshot.assert_awaited_once()
    assert agent._snapshot_session is not None
    assert len(agent._snapshot_session.manager.list()) == 1


def test_tmux_session_send_keys_triggers_snapshot_processing():
    """Test that the tmux send_keys path captures snapshots under EveryAgentStepPolicy."""
    wrapped = MagicMock()
    sandbox = MagicMock()
    sandbox.id = "snapshot-test-sandbox"
    sandbox._experimental_create_snapshot = AsyncMock()

    agent = SnapshotAwareAgent(
        wrapped_agent=wrapped, sandbox=sandbox, snapshot_policy=EveryAgentStepPolicy()
    )

    session = MagicMock()
    session.send_keys = MagicMock(return_value=None)

    agent._hook_tmux_session(session)
    session.send_keys(["git status\n"])

    sandbox._experimental_create_snapshot.assert_awaited_once()
    assert agent._step_counter == 1


def test_summarize_step_reports_ok_for_clean_output():
    wrapped = MagicMock()
    agent = SnapshotAwareAgent(wrapped_agent=wrapped)

    line = agent._summarize_step(0, ["pytest tests/"], "5 passed in 0.1s")

    assert line == "step 0: pytest tests/ -> ok"


def test_summarize_step_reports_failed_signal():
    wrapped = MagicMock()
    agent = SnapshotAwareAgent(wrapped_agent=wrapped)

    line = agent._summarize_step(0, ["pytest tests/"], "3 failed, 12 passed")

    assert line.endswith("-> failed")


def test_summarize_step_reports_error_signal():
    wrapped = MagicMock()
    agent = SnapshotAwareAgent(wrapped_agent=wrapped)

    line = agent._summarize_step(
        0, ["python bad.py"], "Traceback (most recent call last):"
    )

    assert line.endswith("-> error")


def test_summarize_step_uses_explicit_label_not_step_counter():
    """The label must be caller-controlled, since it may need to follow ATIF's
    own step_id numbering rather than self._step_counter."""
    wrapped = MagicMock()
    agent = SnapshotAwareAgent(wrapped_agent=wrapped)
    agent._step_counter = 5

    line = agent._summarize_step(99, ["pytest tests/"], "5 passed")

    assert line == "step 99: pytest tests/ -> ok"


@pytest.mark.asyncio
async def test_process_step_snapshot_accumulates_trajectory_log():
    """Each processed step should append a summary line, in order, when no
    ATIF trajectory.json is available (e.g. no logs_dir)."""
    wrapped = MagicMock()
    sandbox = MagicMock()
    sandbox.id = "trajectory-test-sandbox"
    sandbox._experimental_create_snapshot = AsyncMock()
    sandbox.fs.upload_file = AsyncMock()

    agent = SnapshotAwareAgent(
        wrapped_agent=wrapped, sandbox=sandbox, snapshot_policy=EveryAgentStepPolicy()
    )

    await agent._process_step_snapshot(["pytest tests/"], "5 passed")
    agent._step_counter += 1
    await agent._process_step_snapshot(["pytest tests/"], "1 failed")

    assert agent._trajectory_log == [
        "step 0: pytest tests/ -> ok",
        "step 1: pytest tests/ -> failed",
    ]


@pytest.mark.asyncio
async def test_load_parent_context_returns_none_without_sandbox():
    wrapped = MagicMock()
    agent = SnapshotAwareAgent(wrapped_agent=wrapped, sandbox=None)

    assert await agent._load_parent_context() is None


@pytest.mark.asyncio
async def test_load_parent_context_returns_none_when_file_missing():
    wrapped = MagicMock()
    sandbox = MagicMock()
    sandbox.fs.download_file = AsyncMock(return_value=None)

    agent = SnapshotAwareAgent(wrapped_agent=wrapped, sandbox=sandbox)

    assert await agent._load_parent_context() is None


@pytest.mark.asyncio
async def test_load_parent_context_decodes_sandbox_file():
    wrapped = MagicMock()
    sandbox = MagicMock()
    sandbox.fs.download_file = AsyncMock(return_value=b"step 0: pip install -> ok")

    agent = SnapshotAwareAgent(wrapped_agent=wrapped, sandbox=sandbox)

    assert await agent._load_parent_context() == "step 0: pip install -> ok"


@pytest.mark.asyncio
async def test_load_parent_context_uses_explicit_context_before_sandbox():
    wrapped = MagicMock()
    sandbox = MagicMock()
    sandbox.fs.download_file = AsyncMock(return_value=b"step 0: sandbox note")
    agent = SnapshotAwareAgent(
        wrapped_agent=wrapped,
        sandbox=sandbox,
        parent_context="step 0: explicit note",
    )

    assert await agent._load_parent_context() == "step 0: explicit note"
    sandbox.fs.download_file.assert_not_called()


@pytest.mark.asyncio
async def test_load_parent_context_summarizes_host_trajectory_path(tmp_path):
    trajectory_path = tmp_path / "trajectory.json"
    _write_trajectory(
        trajectory_path,
        [
            {"step_id": 0, "source": "user", "message": "Fix it."},
            {"step_id": 1, "source": "agent", "message": "Ran pytest and saw failure."},
            {"step_id": 2, "source": "agent", "message": "Edited parser.py."},
        ],
    )
    wrapped = MagicMock()
    agent = SnapshotAwareAgent(
        wrapped_agent=wrapped,
        parent_context_path=trajectory_path,
    )

    assert await agent._load_parent_context() == (
        "step 1: Ran pytest and saw failure.\nstep 2: Edited parser.py."
    )


def test_augment_instruction_appends_parent_context():
    result = SnapshotAwareAgent._augment_instruction(
        "Fix the bug.", "step 0: pip install -> ok"
    )

    assert result.startswith("Fix the bug.\n\n")
    assert "step 0: pip install -> ok" in result


def test_snapshot_aware_agent_failure_symptom_uses_diverge_prompt():
    class FakeWrapped:
        def __init__(self):
            self.instruction = None

        def perform_task(
            self, *, instruction, session, logging_dir=None, time_limit_seconds=None
        ):
            self.instruction = instruction
            return MagicMock()

        def to_agent_info(self):
            return {}

    wrapped = FakeWrapped()
    agent = SnapshotAwareAgent(
        wrapped_agent=wrapped,
        context_mode="failure_symptom",
    )
    agent._load_parent_context = AsyncMock(  # type: ignore[method-assign]
        return_value=(
            "The prior attempt from this sandbox state did not solve the task "
            "(reward: 0.0).\n\nLast observed test/verifier output:\n"
            "2 passed, 1 failed\nFAILED test_parser.py::test_toml_config"
        )
    )

    agent.perform_task("solve task", MagicMock(session_name="trial-a"))

    assert wrapped.instruction is not None
    assert "solve task" in wrapped.instruction
    assert "did not solve the task" in wrapped.instruction
    assert "test_toml_config" in wrapped.instruction
    assert "commands are deliberately not shown to you" in wrapped.instruction
    assert "so you don't repeat it" not in wrapped.instruction
    assert "untrusted evidence" not in wrapped.instruction


def test_snapshot_aware_agent_resume_notice_appends_static_orientation():
    class FakeWrapped:
        def __init__(self):
            self.instruction = None

        def perform_task(
            self, *, instruction, session, logging_dir=None, time_limit_seconds=None
        ):
            self.instruction = instruction
            return MagicMock()

        def to_agent_info(self):
            return {}

    wrapped = FakeWrapped()
    agent = SnapshotAwareAgent(wrapped_agent=wrapped, context_mode="resume_notice")
    # resume_notice must not depend on parent context being loadable - it's a
    # static structural notice, not narrative content.
    agent._load_parent_context = AsyncMock(return_value=None)  # type: ignore[method-assign]

    agent.perform_task("solve task", MagicMock(session_name="trial-a"))

    assert wrapped.instruction is not None
    assert "solve task" in wrapped.instruction
    assert "already contains state from a prior attempt" in wrapped.instruction
    assert "Do not assume the sandbox is empty" in wrapped.instruction
    agent._load_parent_context.assert_not_awaited()


def test_augment_instruction_resume_notice_carries_no_parent_narrative():
    result = SnapshotAwareAgent._augment_instruction_resume_notice("Fix the bug.")

    assert result.startswith("Fix the bug.\n\n")
    assert "success criteria" in result
    # It's a fixed template, not a summary of what the parent did - there is
    # no parent-supplied content to leak here.
    assert "prior attempt" in result


def test_snapshot_aware_agent_full_transcript_summary_uses_disclaimer_prompt(tmp_path):
    """diff_only + transcript pairs a filesystem-applied diff with a
    deterministic, rule-based text summary. The prompt must carry an
    explicit "not a model-generated narrative / verify yourself" disclaimer,
    per T008's prompt-contract discipline."""
    transcript_path = tmp_path / "transcript-summary.md"
    transcript_path.write_text(
        "# Parent attempt summary: fix-git\n"
        "outcome: failed (reward: 0.0)\n\n"
        "## Test runs (observed, not inferred)\n"
        "- `pytest tests -q` -> 2 passed, 1 failed\n"
    )

    class FakeWrapped:
        def __init__(self):
            self.instruction = None

        def perform_task(
            self, *, instruction, session, logging_dir=None, time_limit_seconds=None
        ):
            self.instruction = instruction
            return MagicMock()

        def to_agent_info(self):
            return {}

    wrapped = FakeWrapped()
    agent = SnapshotAwareAgent(
        wrapped_agent=wrapped,
        context_mode="full_transcript_summary",
        parent_context_path=transcript_path,
    )

    agent.perform_task("solve task", MagicMock(session_name="trial-a"))

    assert wrapped.instruction is not None
    assert "solve task" in wrapped.instruction
    assert "2 passed, 1 failed" in wrapped.instruction
    assert "not a model-generated narrative" in wrapped.instruction
    assert "verify" in wrapped.instruction.lower()
    assert "already applied" in wrapped.instruction


@pytest.mark.asyncio
async def test_snapshot_aware_agent_original_task_only_ignores_transcript_file(tmp_path):
    """A plain diff_only run (original_task_only) must not pick up a
    transcript file even if one happens to be passed - only
    full_transcript_summary triggers injection."""
    transcript_path = tmp_path / "transcript-summary.md"
    transcript_path.write_text("# Parent attempt summary: fix-git\n")

    wrapped = MagicMock()
    wrapped.run = AsyncMock()
    environment = MagicMock()
    environment.trial_paths = None
    environment.session_id = "trial-1"

    agent = SnapshotAwareAgent(
        wrapped_agent=wrapped,
        context_mode="original_task_only",
        parent_context_path=transcript_path,
    )

    await agent.run("solve task", environment, context=None)

    received_instruction = wrapped.run.await_args.args[0]
    assert received_instruction == "solve task"


def _write_trajectory(path: Path, steps: list[dict]) -> None:
    path.write_text(json.dumps({"steps": steps}))


def test_read_atif_trajectory_steps_returns_empty_without_logs_dir():
    wrapped = MagicMock()
    agent = SnapshotAwareAgent(wrapped_agent=wrapped)

    assert agent._logs_dir is None
    assert agent._read_atif_trajectory_steps() == []


def test_read_atif_trajectory_steps_returns_empty_when_file_missing(tmp_path):
    wrapped = MagicMock()
    agent = SnapshotAwareAgent(wrapped_agent=wrapped, logs_dir=tmp_path)

    assert agent._read_atif_trajectory_steps() == []


def test_read_atif_trajectory_steps_parses_existing_file(tmp_path):
    wrapped = MagicMock()
    agent = SnapshotAwareAgent(wrapped_agent=wrapped, logs_dir=tmp_path)
    _write_trajectory(
        tmp_path / "trajectory.json",
        [
            {"step_id": 1, "source": "user", "message": "Fix the failing test."},
            {
                "step_id": 2,
                "source": "agent",
                "message": "Analysis: ...\nPlan: install deps",
            },
        ],
    )

    steps = agent._read_atif_trajectory_steps()

    assert [step["step_id"] for step in steps] == [1, 2]


def test_summarize_atif_step_collapses_and_truncates_message():
    line = SnapshotAwareAgent._summarize_atif_step(
        {"step_id": 3, "message": "Analysis: found it\nPlan:  install pkg  "}
    )

    assert line == "step 3: Analysis: found it Plan: install pkg"


def test_summarize_atif_step_handles_missing_message():
    line = SnapshotAwareAgent._summarize_atif_step({"step_id": 4, "message": ""})

    assert line == "step 4: (no message)"


def test_atif_history_lines_filters_to_agent_steps_only():
    atif_steps = [
        {"step_id": 1, "source": "user", "message": "Fix the failing test."},
        {"step_id": 2, "source": "agent", "message": "Plan: install deps"},
    ]

    lines = SnapshotAwareAgent._atif_history_lines(atif_steps)

    assert lines == ["step 2: Plan: install deps"]


def test_atif_history_lines_returns_empty_when_no_agent_steps():
    atif_steps = [{"step_id": 1, "source": "user", "message": "Fix the failing test."}]

    assert SnapshotAwareAgent._atif_history_lines(atif_steps) == []


def test_build_trajectory_summary_falls_back_without_atif():
    wrapped = MagicMock()
    agent = SnapshotAwareAgent(wrapped_agent=wrapped)

    summary = agent._build_trajectory_summary(["pytest tests/"], "5 passed")

    assert summary == "step 0: pytest tests/ -> ok"


def test_build_trajectory_summary_combines_atif_history_with_correctly_numbered_current_line(
    tmp_path,
):
    """The current step's label must continue ATIF's own step_id numbering
    (len(atif_steps) + 1), not self._step_counter - otherwise the two
    numbering schemes can collide or diverge, as seen in a real run where
    ATIF had already reached step 29 while self._step_counter was still 27."""
    wrapped = MagicMock()
    agent = SnapshotAwareAgent(wrapped_agent=wrapped, logs_dir=tmp_path)
    agent._step_counter = 27
    _write_trajectory(
        tmp_path / "trajectory.json",
        [
            {"step_id": 1, "source": "agent", "message": "Plan: install deps"},
            {"step_id": 2, "source": "agent", "message": "Plan: run tests"},
        ],
    )

    summary = agent._build_trajectory_summary(["pytest tests/"], "1 failed")

    assert summary == (
        "step 1: Plan: install deps\n"
        "step 2: Plan: run tests\n"
        "step 3: pytest tests/ -> failed"
    )


@pytest.mark.asyncio
async def test_diff_only_applies_to_filesystem_not_agent_context(tmp_path):
    """diff_only must be a filesystem operation, not a context-injection one:
    the diff is `git apply`-ed to the sandbox during setup(), and the agent's
    instruction must stay byte-for-byte unmodified (original_task_only) -
    the diff's content should never appear in the prompt or cost a token."""
    diff_path = tmp_path / "parent.diff"
    diff_text = "diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1 +1 @@\n-old\n+new\n"
    diff_path.write_text(diff_text)

    wrapped = MagicMock()
    wrapped.setup = AsyncMock()
    wrapped.run = AsyncMock()

    environment = MagicMock()
    environment.upload_file = AsyncMock()
    environment.exec = AsyncMock(return_value=MagicMock(return_code=0))
    environment.task_env_config = MagicMock(workdir="/app")
    environment.trial_paths = None
    environment.session_id = "trial-1"

    agent = SnapshotAwareAgent(
        wrapped_agent=wrapped,
        context_mode="original_task_only",
        diff_path=diff_path,
    )

    await agent.setup(environment)
    await agent.run("Fix the failing test.", environment, context=None)

    # Applied to the sandbox filesystem via exec/upload, before the agent ran.
    environment.upload_file.assert_awaited_once()
    environment.exec.assert_awaited_once()
    assert "git apply" in environment.exec.await_args.kwargs["command"]
    wrapped.setup.assert_awaited_once_with(environment)

    # Never surfaced to the agent: instruction is untouched, no diff bytes in it.
    wrapped.run.assert_awaited_once()
    received_instruction = wrapped.run.await_args.args[0]
    assert received_instruction == "Fix the failing test."
    assert "diff --git" not in received_instruction
    assert "-old" not in received_instruction
    assert "+new" not in received_instruction


@pytest.mark.asyncio
async def test_diff_only_apply_failure_blocks_agent_run(tmp_path):
    """If the diff doesn't apply cleanly, the agent must never run - the
    wrapper raises before delegating to wrapped.run(), so a broken diff can't
    silently masquerade as a normal (if unlucky) task attempt."""
    diff_path = tmp_path / "parent.diff"
    diff_path.write_text(
        "diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1 +1 @@\n-old\n+new\n"
    )

    wrapped = MagicMock()
    wrapped.setup = AsyncMock()
    wrapped.run = AsyncMock()

    environment = MagicMock()
    environment.upload_file = AsyncMock()
    environment.exec = AsyncMock(
        return_value=MagicMock(return_code=1, stderr="patch does not apply")
    )
    environment.task_env_config = MagicMock(workdir="/app")

    from go_explore.snapshots.diff_only import DiffApplyFailed

    agent = SnapshotAwareAgent(
        wrapped_agent=wrapped,
        context_mode="original_task_only",
        diff_path=diff_path,
    )

    with pytest.raises(DiffApplyFailed):
        await agent.setup(environment)

    wrapped.setup.assert_not_awaited()
    wrapped.run.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_passes_augmented_instruction_to_wrapped_agent():
    """The wrapped agent's run() must actually receive the parent's context,
    not just have it available somewhere on the wrapper."""
    wrapped = MagicMock()
    wrapped.run = AsyncMock()

    sandbox = MagicMock()
    sandbox.fs.download_file = AsyncMock(return_value=b"step 0: pip install -> ok")

    environment = MagicMock()
    environment._sandbox = sandbox
    environment.trial_paths = None
    environment.session_id = "trial-1"

    agent = SnapshotAwareAgent(wrapped_agent=wrapped, sandbox=sandbox)

    await agent.run("Fix the failing test.", environment, context=None)

    wrapped.run.assert_awaited_once()
    received_instruction = wrapped.run.await_args.args[0]
    assert received_instruction.startswith("Fix the failing test.")
    assert "step 0: pip install -> ok" in received_instruction


@pytest.mark.asyncio
async def test_run_passes_original_instruction_when_no_parent_context():
    """A fresh sandbox (no prior snapshot) must not get a fabricated context block."""
    wrapped = MagicMock()
    wrapped.run = AsyncMock()

    sandbox = MagicMock()
    sandbox.fs.download_file = AsyncMock(return_value=None)

    environment = MagicMock()
    environment._sandbox = sandbox
    environment.trial_paths = None
    environment.session_id = "trial-1"

    agent = SnapshotAwareAgent(wrapped_agent=wrapped, sandbox=sandbox)

    await agent.run("Fix the failing test.", environment, context=None)

    wrapped.run.assert_awaited_once()
    received_instruction = wrapped.run.await_args.args[0]
    assert received_instruction == "Fix the failing test."


def test_perform_task_passes_augmented_instruction_to_wrapped_agent():
    """Same wiring guarantee for the sync/legacy perform_task path."""
    wrapped = MagicMock()

    sandbox = MagicMock()
    sandbox.fs.download_file = AsyncMock(return_value=b"step 0: pip install -> ok")

    session = MagicMock()
    session.session_name = "test-trial"

    agent = SnapshotAwareAgent(wrapped_agent=wrapped, sandbox=sandbox)

    agent.perform_task(instruction="Fix the failing test.", session=session)

    wrapped.perform_task.assert_called_once()
    received_instruction = wrapped.perform_task.call_args.kwargs["instruction"]
    assert received_instruction.startswith("Fix the failing test.")
    assert "step 0: pip install -> ok" in received_instruction


def test_snapshot_aware_agent_accepts_preflight_verification_context_mode():
    SnapshotAwareAgent(wrapped_agent=MagicMock(), context_mode="preflight_verification")


def _preflight_environment(tmp_path, *, exit_code, ctrf_summary=None):
    """Build a MagicMock environment good enough for run_preflight_verification:
    a real tests dir on disk, and exec/upload_dir/download_file async mocks."""
    tests_dir = tmp_path / "task" / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test.sh").write_text("#!/bin/bash\nexit 0\n")

    environment = MagicMock()
    environment.environment_dir = tmp_path / "task" / "environment"
    environment.os = "linux"
    environment.upload_dir = AsyncMock()
    environment.exec = AsyncMock(return_value=MagicMock(return_code=exit_code))

    async def fake_download_file(remote_path, local_path):
        if ctrf_summary is None:
            raise FileNotFoundError(remote_path)
        Path(local_path).write_text(json.dumps(ctrf_summary))

    environment.download_file = AsyncMock(side_effect=fake_download_file)
    return environment


@pytest.mark.asyncio
async def test_run_preflight_verification_reports_passing_snapshot(tmp_path):
    wrapped = MagicMock()
    wrapped.run = AsyncMock()

    sandbox = MagicMock()
    environment = _preflight_environment(
        tmp_path,
        exit_code=0,
        ctrf_summary={
            "results": {
                "summary": {"passed": 9, "failed": 0, "tests": 9},
                "tests": [{"name": f"test_{i}", "status": "passed"} for i in range(9)],
            }
        },
    )
    environment._sandbox = sandbox
    environment.trial_paths = None
    environment.session_id = "trial-1"

    agent = SnapshotAwareAgent(
        wrapped_agent=wrapped, sandbox=sandbox, context_mode="preflight_verification"
    )

    await agent.run("Fix the failing test.", environment, context=None)

    received_instruction = wrapped.run.await_args.args[0]
    assert "9 of 9 tests passed" in received_instruction
    assert "All checks currently pass" in received_instruction
    assert "don't break anything" in received_instruction


@pytest.mark.asyncio
async def test_run_preflight_verification_reports_failing_tests(tmp_path):
    wrapped = MagicMock()
    wrapped.run = AsyncMock()

    sandbox = MagicMock()
    environment = _preflight_environment(
        tmp_path,
        exit_code=1,
        ctrf_summary={
            "results": {
                "summary": {"passed": 9, "failed": 2, "tests": 11},
                "tests": [
                    {"name": "test_numpy_version", "status": "failed"},
                    {"name": "test_pyknotid_repository_tests", "status": "failed"},
                    {"name": "test_other", "status": "passed"},
                ],
            }
        },
    )
    environment._sandbox = sandbox
    environment.trial_paths = None
    environment.session_id = "trial-1"

    agent = SnapshotAwareAgent(
        wrapped_agent=wrapped, sandbox=sandbox, context_mode="preflight_verification"
    )

    await agent.run("Fix the failing test.", environment, context=None)

    received_instruction = wrapped.run.await_args.args[0]
    assert "9 of 11 tests passed" in received_instruction
    assert "test_numpy_version" in received_instruction
    assert "test_pyknotid_repository_tests" in received_instruction
    assert "without breaking the ones that already pass" in received_instruction


@pytest.mark.asyncio
async def test_run_preflight_verification_falls_back_when_unavailable():
    wrapped = MagicMock()
    wrapped.run = AsyncMock()

    sandbox = MagicMock()
    environment = MagicMock(spec=["_sandbox", "trial_paths", "session_id"])
    environment._sandbox = sandbox
    environment.trial_paths = None
    environment.session_id = "trial-1"
    # No environment_dir attribute at all (spec restricts it) -> unavailable.

    agent = SnapshotAwareAgent(
        wrapped_agent=wrapped, sandbox=sandbox, context_mode="preflight_verification"
    )

    await agent.run("Fix the failing test.", environment, context=None)

    wrapped.run.assert_awaited_once()
    received_instruction = wrapped.run.await_args.args[0]
    assert "could not produce a result" in received_instruction
    assert "inspect it and run the tests yourself" in received_instruction


def test_perform_task_preflight_verification_degrades_gracefully_without_environment():
    """perform_task has no async BaseEnvironment to verify against - must not
    raise, and must fall back to the unavailable framing."""
    wrapped = MagicMock()

    sandbox = MagicMock()
    session = MagicMock()
    session.session_name = "test-trial"

    agent = SnapshotAwareAgent(
        wrapped_agent=wrapped, sandbox=sandbox, context_mode="preflight_verification"
    )

    agent.perform_task(instruction="Fix the failing test.", session=session)

    wrapped.perform_task.assert_called_once()
    received_instruction = wrapped.perform_task.call_args.kwargs["instruction"]
    assert "could not produce a result" in received_instruction
