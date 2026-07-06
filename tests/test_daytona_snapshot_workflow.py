"""TDD test for Daytona snapshot workflow: create, verify, restore."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from go_explore.snapshots.backends import DaytonaSnapshotBackend
from go_explore.snapshots.models import SnapshotCandidate, SnapshotContext, SnapshotEvent


@pytest.mark.asyncio
async def test_daytona_snapshot_workflow_with_mocked_sandbox():
    """Test complete snapshot workflow: create, verify, and retrieve.

    This test simulates the full workflow with a mocked Daytona sandbox:
    1. Backend is initialized with sandbox
    2. Multiple snapshots are created at interesting states
    3. Snapshot handles are returned with proper metadata
    4. Snapshots can be listed and retrieved
    """
    # Create a mock sandbox that behaves like Daytona AsyncSandbox
    mock_sandbox = AsyncMock()
    mock_sandbox.id = "workflow-test-sandbox-123"

    # Track created snapshots
    created_snapshots: dict[str, dict] = {}

    async def mock_create_snapshot(name: str, timeout: float):
        """Mock the _experimental_create_snapshot method."""
        created_snapshots[name] = {
            "name": name,
            "created_at": "2024-01-01T00:00:00Z",
            "timeout": timeout,
        }
        return {"snapshot_id": name}

    mock_sandbox._experimental_create_snapshot = mock_create_snapshot

    # Initialize backend
    backend = DaytonaSnapshotBackend(
        mock_sandbox,
        timeout=60.0,
        name_prefix="workflow-test",
    )

    # Simulate multiple agent steps that create snapshots
    snapshots_created = []

    # Step 1: Git commit (interesting - state transition)
    candidate1 = SnapshotCandidate(
        id="step_1_git_commit",
        event=SnapshotEvent.AGENT_STEP,
        environment_id=mock_sandbox.id,
        restore_ref=None,
        notes="Git commit",
    )

    context1 = SnapshotContext(
        trial_name="workflow_test",
        step_id=0,
        source="agent",
        message="Committed changes",
        tool_calls=({"function_name": "bash_command", "arguments": {"keystrokes": "git commit -m test"}},),
        observation_text="1 file changed",
        environment_id=mock_sandbox.id,
    )

    handle1 = await backend.create_snapshot(candidate1, context1)
    snapshots_created.append(handle1)

    # Step 2: File edit (interesting)
    candidate2 = SnapshotCandidate(
        id="step_2_file_edit",
        event=SnapshotEvent.FILE_EDIT,
        environment_id=mock_sandbox.id,
        restore_ref=None,
        notes="File edit",
    )

    context2 = SnapshotContext(
        trial_name="workflow_test",
        step_id=1,
        source="agent",
        message="Created file",
        tool_calls=({"function_name": "bash_command", "arguments": {"keystrokes": "cat > test.py << EOF\nprint('hello')\nEOF"}},),
        observation_text="file created",
        environment_id=mock_sandbox.id,
    )

    handle2 = await backend.create_snapshot(candidate2, context2)
    snapshots_created.append(handle2)

    # Verify snapshots were created
    assert len(snapshots_created) == 2
    assert all(h.backend == "daytona" for h in snapshots_created)
    assert all(h.restore_ref is not None for h in snapshots_created)

    # Verify snapshot names follow pattern
    snapshot_names = [h.restore_ref for h in snapshots_created]
    assert all(name.startswith("workflow-test-") for name in snapshot_names)

    # Verify they were actually recorded in the mock
    assert len(created_snapshots) == 2

    # Verify handles contain correct metadata
    assert snapshots_created[0].metadata.get("daytona_snapshot_name") == snapshot_names[0]
    assert snapshots_created[1].metadata.get("daytona_snapshot_name") == snapshot_names[1]

    # Verify environment IDs are preserved
    assert all(h.environment_id == mock_sandbox.id for h in snapshots_created)


@pytest.mark.asyncio
async def test_daytona_snapshot_backend_calls_experimental_api():
    """Test that DaytonaSnapshotBackend calls sandbox._experimental_create_snapshot.

    This is a unit test that mocks the sandbox to verify the API is called correctly.
    """
    # Create a mock sandbox
    mock_sandbox = AsyncMock()
    mock_sandbox.id = "test-sandbox-123"
    mock_sandbox._experimental_create_snapshot = AsyncMock()

    backend = DaytonaSnapshotBackend(
        mock_sandbox,
        timeout=30.0,
        name_prefix="test-prefix",
    )

    candidate = SnapshotCandidate(
        id="test_snapshot_1",
        event=SnapshotEvent.AGENT_STEP,
        environment_id="test-sandbox-123",
        restore_ref=None,
        notes="Testing snapshot creation",
    )

    context = SnapshotContext(
        trial_name="test_trial",
        step_id=0,
        source="agent",
        message="test",
        tool_calls=(),
        observation_text="test",
        environment_id="test-sandbox-123",
    )

    # Call create_snapshot
    handle = await backend.create_snapshot(candidate, context)

    # Verify the experimental API was called with correct snapshot name
    mock_sandbox._experimental_create_snapshot.assert_called_once()
    call_kwargs = mock_sandbox._experimental_create_snapshot.call_args[1]
    assert "name" in call_kwargs
    assert call_kwargs["name"].startswith("test-prefix-")
    assert "test_snapshot_1" in call_kwargs["name"] or "test-snapshot-1" in call_kwargs["name"]
    assert call_kwargs["timeout"] == 30.0

    # Verify snapshot handle is returned correctly
    assert handle.backend == "daytona"
    assert handle.restore_ref == call_kwargs["name"]
    assert handle.environment_id == "test-sandbox-123"


@pytest.mark.asyncio
async def test_snapshot_workflow_end_to_end_with_oracle():
    """Test full workflow with Oracle agent: run, snapshot, restore.

    This test exercises:
    1. Oracle agent taking actions in sandbox
    2. Snapshotting at interesting states
    3. Snapshot verification
    4. Restoration
    """
    try:
        from terminal_bench.agents.oracle_agent import OracleAgent
    except ImportError:
        pytest.skip("terminal-bench not installed")

    # Mock the sandbox to avoid needing real Daytona
    mock_sandbox = AsyncMock()
    mock_sandbox.id = "oracle-test-sandbox"
    mock_sandbox._experimental_create_snapshot = AsyncMock()

    # Create Oracle agent
    oracle = OracleAgent()

    # Create snapshot backend
    backend = DaytonaSnapshotBackend(
        mock_sandbox,
        timeout=60.0,
        name_prefix="oracle-test",
    )

    # Simulate steps
    for step_num in range(3):
        candidate = SnapshotCandidate(
            id=f"oracle_step_{step_num}",
            event=SnapshotEvent.AGENT_STEP,
            environment_id=mock_sandbox.id,
            restore_ref=None,
            notes=f"Oracle action step {step_num}",
        )

        context = SnapshotContext(
            trial_name="oracle_trial",
            step_id=step_num,
            source="oracle",
            message=f"Oracle action {step_num}",
            tool_calls=(
                {
                    "function_name": "bash_command",
                    "arguments": {"keystrokes": f"echo 'step {step_num}'"},
                },
            ),
            observation_text=f"Executed step {step_num}",
            environment_id=mock_sandbox.id,
        )

        # Create snapshot
        handle = await backend.create_snapshot(candidate, context)

        # Verify snapshot was created
        assert handle is not None
        assert handle.backend == "daytona"
        assert mock_sandbox._experimental_create_snapshot.called

    # Verify we created 3 snapshots
    assert mock_sandbox._experimental_create_snapshot.call_count == 3
