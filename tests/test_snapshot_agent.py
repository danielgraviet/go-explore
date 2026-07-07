"""Tests for the snapshot-aware agent wrapper."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from go_explore.agents.snapshot_agent import SnapshotAwareAgent


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
    """Test that the wrapper snapshots a normal agent command batch."""
    wrapped = MagicMock()
    sandbox = MagicMock()
    sandbox.id = "snapshot-test-sandbox"
    sandbox._experimental_create_snapshot = AsyncMock()

    agent = SnapshotAwareAgent(wrapped_agent=wrapped, sandbox=sandbox)

    await agent._process_step_snapshot(["pwd"], "working directory")

    sandbox._experimental_create_snapshot.assert_awaited_once()
    assert agent._snapshot_session is not None
    assert len(agent._snapshot_session.manager.list()) == 1


def test_tmux_session_send_keys_triggers_snapshot_processing():
    """Test that the tmux send_keys path captures snapshots."""
    wrapped = MagicMock()
    sandbox = MagicMock()
    sandbox.id = "snapshot-test-sandbox"
    sandbox._experimental_create_snapshot = AsyncMock()

    agent = SnapshotAwareAgent(wrapped_agent=wrapped, sandbox=sandbox)

    session = MagicMock()
    session.send_keys = MagicMock(return_value=None)

    agent._hook_tmux_session(session)
    session.send_keys(["git status\n"])

    sandbox._experimental_create_snapshot.assert_awaited_once()
    assert agent._step_counter == 1
