"""E2e proof that a resumed sandbox's trajectory context reaches the child agent.

This exercises the real Daytona filesystem, not mocks: a parent "leaves" a
context file on a live sandbox (the same file DaytonaSnapshotBackend writes
right before taking a snapshot), and we confirm SnapshotAwareAgent reads it
back and hands the augmented instruction to the wrapped agent's run().
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from daytona import AsyncDaytona

from go_explore.agents.snapshot_agent import SnapshotAwareAgent
from go_explore.snapshots.models import CONTEXT_FILE_PATH


class _RecordingAgent:
    """Minimal wrapped-agent stub that just records what it was asked to do."""

    def __init__(self) -> None:
        self.received_instruction: str | None = None

    async def run(self, instruction: str, environment: object, context: object) -> None:
        self.received_instruction = instruction

    async def setup(self, environment: object) -> None:
        pass


@pytest.mark.e2e
async def test_child_agent_receives_parent_trajectory_context_from_real_sandbox():
    """Full round trip: write context to a real sandbox, restore it via
    SnapshotAwareAgent.run(), and confirm the wrapped agent's instruction
    contains both the original task and the parent's trajectory summary."""
    async with AsyncDaytona() as daytona:
        sandbox = await daytona.create()

        try:
            parent_summary = (
                "step 0: pip install -r requirements.txt -> ok\n"
                "step 7: pytest tests/ -> failed"
            )
            await sandbox.fs.upload_file(parent_summary.encode(), CONTEXT_FILE_PATH)

            recording_agent = _RecordingAgent()
            agent = SnapshotAwareAgent(wrapped_agent=recording_agent, sandbox=sandbox)

            environment = SimpleNamespace(
                trial_paths=None,
                session_id="context-resume-e2e",
                _sandbox=sandbox,
            )

            await agent.run("Fix the failing test.", environment, context=None)

            assert recording_agent.received_instruction is not None
            assert recording_agent.received_instruction.startswith(
                "Fix the failing test."
            )
            assert "pip install -r requirements.txt -> ok" in recording_agent.received_instruction
            assert "pytest tests/ -> failed" in recording_agent.received_instruction

        finally:
            try:
                await daytona.delete(sandbox)
            except Exception as cleanup_error:
                print(f"Warning: Sandbox cleanup failed (sandbox will auto-delete): {cleanup_error}")


@pytest.mark.e2e
async def test_child_agent_gets_unmodified_instruction_on_fresh_sandbox():
    """A sandbox with no prior context file must not fabricate one."""
    async with AsyncDaytona() as daytona:
        sandbox = await daytona.create()

        try:
            recording_agent = _RecordingAgent()
            agent = SnapshotAwareAgent(wrapped_agent=recording_agent, sandbox=sandbox)

            environment = SimpleNamespace(
                trial_paths=None,
                session_id="fresh-sandbox-e2e",
                _sandbox=sandbox,
            )

            await agent.run("Fix the failing test.", environment, context=None)

            assert recording_agent.received_instruction == "Fix the failing test."

        finally:
            try:
                await daytona.delete(sandbox)
            except Exception as cleanup_error:
                print(f"Warning: Sandbox cleanup failed (sandbox will auto-delete): {cleanup_error}")
