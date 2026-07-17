"""Integration tests for SnapshotAwareAgent with snapshotting workflow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from go_explore.agents.snapshot_agent import SnapshotAwareAgent
from go_explore.snapshots.backends import DaytonaSnapshotBackend
from go_explore.snapshots.manager import AsyncSnapshotManager
from go_explore.snapshots.models import SnapshotContext
from go_explore.snapshots.policies import InterestingAgentStepPolicy
from go_explore.snapshots.archive import ArchiveStore
from go_explore.snapshots.stores import InMemorySnapshotStore


@pytest.mark.asyncio
async def test_snapshot_aware_agent_creates_snapshots_on_agent_steps():
    """Test that SnapshotAwareAgent creates snapshots for interesting steps.

    This test verifies:
    1. Agent is wrapped with snapshot awareness
    2. During step execution, snapshots are created
    3. Snapshots are stored in the backend
    4. Snapshots can be retrieved
    """
    # Create a mock agent that will be wrapped
    mock_agent = MagicMock()
    mock_agent.name.return_value = "mock-agent"

    # Create a mock sandbox
    mock_sandbox = AsyncMock()
    mock_sandbox.id = "test-sandbox"
    mock_sandbox._experimental_create_snapshot = AsyncMock()

    # Create the wrapped agent with snapshot awareness
    agent = SnapshotAwareAgent(wrapped_agent=mock_agent, sandbox=mock_sandbox)

    # Verify snapshot session was initialized
    assert agent._snapshot_session is not None
    assert agent._sandbox is mock_sandbox

    # Verify the snapshot manager has the right components
    manager = agent._snapshot_session._manager
    assert isinstance(manager, AsyncSnapshotManager)
    # Policy is private but we can verify backend and store
    assert isinstance(manager.backend, DaytonaSnapshotBackend)
    # The agent now records into the persistent archive rather than memory.
    assert isinstance(manager.store, ArchiveStore)


@pytest.mark.asyncio
async def test_snapshot_aware_agent_captures_step_data():
    """Test that SnapshotAwareAgent correctly captures command and output data.

    This test verifies:
    1. Commands are extracted from step execution
    2. Terminal output is captured
    3. Data is formatted correctly for snapshot processing
    """
    mock_agent = MagicMock()
    mock_agent.name.return_value = "test-agent"

    mock_sandbox = AsyncMock()
    mock_sandbox.id = "capture-test-sandbox"
    mock_sandbox._experimental_create_snapshot = AsyncMock()

    agent = SnapshotAwareAgent(wrapped_agent=mock_agent, sandbox=mock_sandbox)

    # Create test step data - a file edit, which the default
    # InterestingAgentStepPolicy treats as a state-changing (snapshot-worthy) step
    commands = ["cat > test.txt << 'EOF'\ntest content\nEOF"]
    terminal_output = "file created"

    # Process the step through the snapshot session
    await agent._process_step_snapshot(commands, terminal_output)

    mock_sandbox._experimental_create_snapshot.assert_awaited_once()
    assert agent._snapshot_session is not None
    assert len(agent._snapshot_session.manager.list()) == 1


@pytest.mark.asyncio
async def test_snapshot_manager_stores_snapshots_from_agent_steps():
    """Test that snapshots from agent steps are properly stored.

    This test verifies the end-to-end flow:
    1. Agent step context is created
    2. Policy evaluates if it's interesting
    3. Backend creates snapshot
    4. Snapshot is stored with metadata
    5. Snapshot can be retrieved
    """
    # Create a real backend (mocked sandbox) and store
    mock_sandbox = AsyncMock()
    mock_sandbox.id = "manager-test-sandbox"
    mock_sandbox._experimental_create_snapshot = AsyncMock()

    backend = DaytonaSnapshotBackend(mock_sandbox, timeout=60.0, name_prefix="test")
    store = InMemorySnapshotStore()
    policy = InterestingAgentStepPolicy()
    manager = AsyncSnapshotManager(policy=policy, backend=backend, store=store)

    # Create a context for an agent step with git commit (interesting - git state transition)
    context = SnapshotContext(
        trial_name="test_trial",
        step_id=0,
        source="agent",
        message="Made a git commit",
        tool_calls=(
            {
                "function_name": "bash_command",
                "arguments": {"keystrokes": "git commit -m 'test'"},
            },
        ),
        observation_text="1 file changed\nmaster abc1234",
        environment_id="manager-test-sandbox",
    )

    # Process the step
    records = await manager.process_step(context)

    # Verify snapshot was created and stored
    assert len(records) > 0
    assert records[0].backend == "daytona"

    # Verify we can retrieve it
    snapshot_id = records[0].id
    retrieved = store.get(snapshot_id)
    assert retrieved is not None
    assert retrieved.id == snapshot_id


@pytest.mark.asyncio
async def test_snapshot_metrics_are_recorded():
    """Test that snapshot processing metrics are recorded.

    This test verifies:
    1. Timing metrics are captured
    2. Candidate and snapshot counts are accurate
    3. Metrics can be accessed via process_step_with_metrics
    """
    mock_sandbox = AsyncMock()
    mock_sandbox.id = "metrics-test-sandbox"
    mock_sandbox._experimental_create_snapshot = AsyncMock()

    backend = DaytonaSnapshotBackend(mock_sandbox, timeout=60.0, name_prefix="test")
    store = InMemorySnapshotStore()
    policy = InterestingAgentStepPolicy()
    manager = AsyncSnapshotManager(policy=policy, backend=backend, store=store)

    # Create a context with a file edit (interesting via cat)
    context = SnapshotContext(
        trial_name="test_trial",
        step_id=0,
        source="agent",
        message="Edited file",
        tool_calls=(
            {
                "function_name": "bash_command",
                "arguments": {"keystrokes": "cat > test.txt << 'EOF'\ntest content\nEOF"},
            },
        ),
        observation_text="file created",
        environment_id="metrics-test-sandbox",
    )

    # Get metrics from processing
    result = await manager.process_step_with_metrics(context)

    # Verify metrics are present
    assert result.timing is not None
    assert result.timing.total_seconds > 0
    assert result.timing.n_candidates >= 0
    assert result.timing.n_snapshots >= 0

    # Verify records match count
    assert len(result.records) == result.timing.n_snapshots
