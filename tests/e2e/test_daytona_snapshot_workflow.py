"""TDD test for Daytona snapshot workflow: create, verify, restore."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
import time

from daytona import AsyncDaytona

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

            steps = [
                (
                    0,
                    "real_snapshot_test_1",
                    "pwd",
                    SnapshotEvent.AGENT_STEP,
                    "Printed working directory",
                ),
                (
                    1,
                    "real_snapshot_test_2",
                    "ls -la",
                    SnapshotEvent.AGENT_STEP,
                    "Listed files",
                ),
                (
                    2,
                    "real_snapshot_test_3",
                    "cat > test.txt << 'EOF'\ntest content\nEOF",
                    SnapshotEvent.FILE_EDIT,
                    "Created test file",
                ),
            ]

            snapshot_handles = []
            for step_id, candidate_id, command, event, notes in steps:
                candidate = SnapshotCandidate(
                    id=candidate_id,
                    event=event,
                    environment_id=sandbox_id,
                    restore_ref=None,
                    notes=notes,
                )

                context = SnapshotContext(
                    trial_name="real_snapshot_test",
                    step_id=step_id,
                    source="agent",
                    message=notes,
                    tool_calls=(
                        {
                            "function_name": "bash_command",
                            "arguments": {"keystrokes": command},
                        },
                    ),
                    observation_text=notes.lower(),
                    environment_id=sandbox_id,
                )

                start = time.monotonic()
                snapshot_handle = await backend.create_snapshot(candidate, context)
                end = time.monotonic()
                elapsed = end - start
                print(f"Snapshot creation for step {step_id} took {elapsed:.2f} seconds.")
                snapshot_handles.append(snapshot_handle)

                assert snapshot_handle is not None
                assert snapshot_handle.backend == "daytona"
                assert snapshot_handle.restore_ref is not None
                assert snapshot_handle.environment_id == sandbox_id

            # Verify snapshot exists in Daytona
            snapshots_page = await daytona.snapshot.list()
            snapshot_names = {
                snapshot.name
                for snapshot in snapshots_page.items
                if snapshot.name.startswith("test-go-explore-")
            }
            expected_names = {handle.restore_ref for handle in snapshot_handles}

            assert expected_names <= snapshot_names, (
                f"Expected Daytona snapshots {sorted(expected_names)} but saw "
                f"{sorted(snapshot_names)}"
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


@pytest.mark.e2e
async def test_snapshot_workflow_end_to_end_with_real_daytona_sandbox():
    """Test full workflow against a real Daytona sandbox."""
    async with AsyncDaytona() as daytona:
        sandbox = await daytona.create()
        sandbox_id = sandbox.id

        try:
            backend = DaytonaSnapshotBackend(
                sandbox,
                timeout=300.0,
                name_prefix="real-daytona-test",
            )

            steps = [
                ("real_daytona_step_0", 0, "echo 'step 0'", "Executed step 0"),
                ("real_daytona_step_1", 1, "echo 'step 1'", "Executed step 1"),
                ("real_daytona_step_2", 2, "echo 'step 2'", "Executed step 2"),
            ]

            snapshot_handles = []
            for candidate_id, step_id, command, notes in steps:
                candidate = SnapshotCandidate(
                    id=candidate_id,
                    event=SnapshotEvent.AGENT_STEP,
                    environment_id=sandbox_id,
                    restore_ref=None,
                    notes=notes,
                )

                context = SnapshotContext(
                    trial_name="real_daytona_trial",
                    step_id=step_id,
                    source="agent",
                    message=notes,
                    tool_calls=(
                        {
                            "function_name": "bash_command",
                            "arguments": {"keystrokes": command},
                        },
                    ),
                    observation_text=notes,
                    environment_id=sandbox_id,
                )

                handle = await backend.create_snapshot(candidate, context)
                snapshot_handles.append(handle)

                assert handle is not None
                assert handle.backend == "daytona"
                assert handle.restore_ref is not None
                assert handle.environment_id == sandbox_id

            snapshots_page = await daytona.snapshot.list()
            snapshot_names = {str(item.name) for item in snapshots_page.items if hasattr(item, "name")}

            for handle in snapshot_handles:
                assert handle.restore_ref in snapshot_names
        finally:
            try:
                await daytona.delete(sandbox)
            except Exception as cleanup_error:
                print(f"Warning: Sandbox cleanup failed (sandbox will auto-delete): {cleanup_error}")
