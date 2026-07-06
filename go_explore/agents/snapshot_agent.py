"""Snapshot-aware agent wrapper that captures interesting states during execution."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

try:
    from terminal_bench.agents.base_agent import AgentResult, BaseAgent
    from terminal_bench.terminal.tmux_session import TmuxSession
except ImportError:
    # Fallback for development/testing when terminal-bench is not installed
    class BaseAgent:  # type: ignore
        """Stub for type hints when terminal-bench is not available."""

        @staticmethod
        def name() -> str:
            raise NotImplementedError

    class TmuxSession:  # type: ignore
        """Stub for type hints when terminal-bench is not available."""

        pass

    class AgentResult:  # type: ignore
        """Stub for type hints when terminal-bench is not available."""

        pass

from go_explore.snapshots.backends import DaytonaSnapshotBackend
from go_explore.snapshots.live import AsyncLiveSnapshotSession
from go_explore.snapshots.manager import AsyncSnapshotManager
from go_explore.snapshots.models import SnapshotContext
from go_explore.snapshots.policies import InterestingAgentStepPolicy


class SnapshotAwareAgent(BaseAgent):
    """Wraps any Harbor agent and captures snapshots during execution.

    Attributes:
        wrapped_agent: The agent instance to wrap
        sandbox: The Daytona AsyncSandbox (passed by Harbor via agent kwargs)
    """

    def __init__(
        self,
        wrapped_agent: BaseAgent,
        sandbox: Any = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._wrapped_agent = wrapped_agent
        self._sandbox = sandbox

        # Initialize snapshot session if sandbox is available
        self._snapshot_session: AsyncLiveSnapshotSession | None = None
        if self._sandbox is not None:
            manager = AsyncSnapshotManager(
                policy=InterestingAgentStepPolicy(),
                backend=DaytonaSnapshotBackend(
                    sandbox=self._sandbox,
                    name_prefix="go-explore",
                    timeout=60.0,
                ),
            )
            self._snapshot_session = AsyncLiveSnapshotSession(manager)

        # Store state for step tracking
        self._step_counter = 0
        self._trial_name: str | None = None
        self._commands_in_step: list[str] = []

    @staticmethod
    def name() -> str:
        return "snapshot-aware"

    def _wrap_agent_method(self, method_name: str) -> Any:
        """Get a method from the wrapped agent."""
        return getattr(self._wrapped_agent, method_name)

    async def _process_step_snapshot(
        self,
        commands: list[str],
        terminal_output: str,
    ) -> None:
        """Process a step through the snapshot session.

        Args:
            commands: List of bash commands executed in this step
            terminal_output: The terminal output from executing those commands
        """
        if self._snapshot_session is None or not commands:
            return

        # Build the context for this step
        context = SnapshotContext(
            trial_name=self._trial_name or "unknown",
            step_id=self._step_counter,
            source="agent",
            message="Agent step",
            tool_calls=tuple(
                {
                    "function_name": "bash_command",
                    "arguments": {
                        "keystrokes": cmd,
                    },
                }
                for cmd in commands
            ),
            observation_text=terminal_output,
        )

        # Process through snapshot manager
        await self._snapshot_session.process_step(context)

    def _hook_agent_loop(self) -> None:
        """Hook into the wrapped agent's loop to capture snapshots.

        This wraps the agent's _execute_commands method to capture step data.
        """
        if not hasattr(self._wrapped_agent, "_execute_commands"):
            return

        original_execute = self._wrapped_agent._execute_commands
        commands_buffer: list[str] = []

        def wrapped_execute(commands: list[Any], session: TmuxSession) -> tuple[bool, str]:
            """Wrapper around _execute_commands that captures snapshots."""
            # Extract command strings from the Command objects
            nonlocal commands_buffer
            commands_buffer = [cmd.keystrokes for cmd in commands]

            # Call the original method
            timeout_occurred, terminal_output = original_execute(commands, session)

            # Process snapshot asynchronously if we have a session
            if self._snapshot_session and commands_buffer:
                try:
                    # Run async snapshot processing
                    asyncio.run(
                        self._process_step_snapshot(commands_buffer, terminal_output)
                    )
                except Exception as e:
                    # Log but don't fail the agent if snapshotting fails
                    print(f"Warning: Snapshot processing failed: {e}")

            self._step_counter += 1
            return timeout_occurred, terminal_output

        # Replace the method
        self._wrapped_agent._execute_commands = wrapped_execute

    def perform_task(
        self,
        instruction: str,
        session: TmuxSession,
        logging_dir: Path | None = None,
        time_limit_seconds: float | None = None,
    ) -> AgentResult:
        """Execute the task using the wrapped agent with snapshot hooks.

        Args:
            instruction: The task instruction
            session: The TmuxSession to execute in
            logging_dir: Optional logging directory
            time_limit_seconds: Optional time limit for execution

        Returns:
            AgentResult from the wrapped agent
        """
        # Extract trial name from instruction or use a default
        self._trial_name = getattr(session, "session_name", "trial")
        self._step_counter = 0

        # Hook the agent's execution loop
        self._hook_agent_loop()

        # Call the wrapped agent's perform_task
        return self._wrapped_agent.perform_task(
            instruction=instruction,
            session=session,
            logging_dir=logging_dir,
            time_limit_seconds=time_limit_seconds,
        )
