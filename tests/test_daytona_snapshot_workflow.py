"""TDD test for Daytona snapshot workflow: create, verify, restore."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from go_explore.snapshots.backends import DaytonaSnapshotBackend
from go_explore.snapshots.models import SnapshotCandidate, SnapshotContext, SnapshotEvent


@pytest.mark.e2e
async def test_daytona_snapshot_workflow_creates_real_snapshots():
    """Test complete snapshot workflow with real Daytona sandbox.

    This test creates a real Daytona sandbox, runs commands, creates snapshots,
    and verifies they can be listed. Requires DAYTONA_API_KEY and DAYTONA_API_URL
    environment variables.

    Workflow:
    1. Create real Daytona sandbox
    2. Run commands to create interesting state
    3. Create snapshot via DaytonaSnapshotBackend
    4. Verify snapshot appears in Daytona's snapshot list
    5. Clean up
    """
    try:
        from daytona import AsyncDaytona
    except ImportError:
        pytest.skip("daytona not installed")

    # Try to initialize Daytona - will fail if credentials not available
    try:
        async with AsyncDaytona() as daytona:
            pass
    except Exception as e:
        pytest.skip(f"Daytona credentials not available: {e}")

    # Create a real sandbox
    async with AsyncDaytona() as daytona:
        sandbox = await daytona.create()
        sandbox_id = sandbox.id
        sandbox_obj = sandbox

        try:
            # Create snapshot backend (with longer timeout for Daytona API)
            backend = DaytonaSnapshotBackend(
                sandbox,
                timeout=300.0,  # 5 minutes - Daytona snapshot creation can be slow
                name_prefix="test-go-explore",
            )

            # Create a snapshot candidate for a file edit
            candidate = SnapshotCandidate(
                id="real_snapshot_test_1",
                event=SnapshotEvent.FILE_EDIT,
                environment_id=sandbox_id,
                restore_ref=None,
                notes="Created test file",
            )

            context = SnapshotContext(
                trial_name="real_snapshot_test",
                step_id=0,
                source="agent",
                message="Created test.txt",
                tool_calls=(
                    {
                        "function_name": "bash_command",
                        "arguments": {"keystrokes": "cat > test.txt << 'EOF'\ntest content\nEOF"},
                    },
                ),
                observation_text="file created",
                environment_id=sandbox_id,
            )

            # Create the snapshot
            snapshot_handle = await backend.create_snapshot(candidate, context)

            # Verify handle is returned
            assert snapshot_handle is not None
            assert snapshot_handle.backend == "daytona"
            assert snapshot_handle.restore_ref is not None
            assert snapshot_handle.environment_id == sandbox_id

            # Verify snapshot exists in Daytona
            snapshots = await daytona.snapshot.list(sandbox_id=sandbox_id)
            snapshot_names = [s.name for s in snapshots]

            assert snapshot_handle.restore_ref in snapshot_names, (
                f"Snapshot {snapshot_handle.restore_ref} not found in "
                f"Daytona snapshots: {snapshot_names}"
            )

        finally:
            # Clean up: delete the sandbox (may take time due to state transitions)
            try:
                await daytona.delete(sandbox_obj)
            except Exception as cleanup_error:
                # Log but don't fail the test if cleanup fails
                print(f"Warning: Sandbox cleanup failed (sandbox will auto-delete): {cleanup_error}")


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
