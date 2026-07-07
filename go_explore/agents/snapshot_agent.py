"""Snapshot-aware agent wrapper that captures interesting states during execution."""

from __future__ import annotations

import asyncio
import inspect
import os
from pathlib import Path
from typing import Any

try:
    from harbor.agents.base import BaseAgent
except ImportError:
    class BaseAgent:  # type: ignore
        """Stub for type hints when terminal-bench is not available."""

        def __init__(self, *args: Any, **kwargs: Any):
            pass

try:
    from terminal_bench.agents.base_agent import AgentResult
    from terminal_bench.terminal.tmux_session import TmuxSession
except ImportError:
    class TmuxSession:  # type: ignore
        """Stub for type hints when terminal-bench is not available locally."""

        pass

    class AgentResult:  # type: ignore
        """Stub for type hints when terminal-bench is not available locally."""

        pass

from go_explore.snapshots.backends import DaytonaSnapshotBackend
from go_explore.snapshots.live import AsyncLiveSnapshotSession
from go_explore.snapshots.manager import AsyncSnapshotManager
from go_explore.snapshots.models import SnapshotContext
from go_explore.snapshots.policies import EveryAgentStepPolicy
from go_explore.snapshots.replay import process_atif_trajectory


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
        hooks_debug: bool = False,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._wrapped_agent = wrapped_agent
        self._sandbox = sandbox
        self._hooks_debug = hooks_debug
        self._agent_execute_hooked = False
        self._session_snapshot_hooked = False
        self._agent_step_active = False
        self._debug_log_path: Path | None = None

        self._snapshot_session: AsyncLiveSnapshotSession | None = None
        self._ensure_snapshot_session(self._sandbox)

        # Store state for step tracking
        self._step_counter = 0
        self._trial_name: str | None = None
        self._commands_in_step: list[str] = []

    def _ensure_snapshot_session(self, sandbox: Any) -> None:
        if sandbox is None or isinstance(sandbox, str) or self._snapshot_session is not None:
            return

        self._sandbox = sandbox
        manager = AsyncSnapshotManager(
            policy=EveryAgentStepPolicy(),
            backend=DaytonaSnapshotBackend(
                sandbox=sandbox,
                name_prefix="go-explore",
                timeout=60.0,
            ),
        )
        self._snapshot_session = AsyncLiveSnapshotSession(manager)

    @staticmethod
    def name() -> str:
        return "snapshot-aware"

    def _wrap_agent_method(self, method_name: str) -> Any:
        """Get a method from the wrapped agent."""
        return getattr(self._wrapped_agent, method_name)

    def _debug_enabled(self) -> bool:
        return self._hooks_debug or os.environ.get("DEBUG", "").strip() not in {
            "",
            "0",
            "false",
            "False",
        }

    def _debug_log(self, message: str) -> None:
        if not self._debug_enabled():
            return

        print(message)
        if self._debug_log_path is None:
            return

        try:
            self._debug_log_path.parent.mkdir(parents=True, exist_ok=True)
            with self._debug_log_path.open("a") as file:
                file.write(message + "\n")
        except Exception:
            pass

    def _should_snapshot_commands(self, commands: list[str]) -> bool:
        normalized = [command.strip() for command in commands if command.strip()]
        if not normalized:
            return False

        control_tokens = {"q", "c-c", "enter"}
        if all(command.lower() in control_tokens for command in normalized):
            return False

        return True

    def version(self) -> str | None:
        version = getattr(self._wrapped_agent, "version", None)
        if callable(version):
            return version()
        return None

    def to_agent_info(self) -> Any:
        return self._wrapped_agent.to_agent_info()

    async def setup(self, environment: Any) -> None:
        await self._wrapped_agent.setup(environment)

    async def run(self, instruction: str, environment: Any, context: Any) -> None:
        trial_paths = getattr(environment, "trial_paths", None)
        trial_dir = getattr(trial_paths, "trial_dir", None)
        session_id = getattr(environment, "session_id", None)
        self._trial_name = str(session_id or (trial_dir.name if trial_dir else "trial"))
        self._step_counter = 0
        self._debug_log_path = (
            Path("jobs") / f"{self._trial_name}-hook_debug.log"
            if self._debug_enabled()
            else None
        )
        self._ensure_snapshot_session(getattr(environment, "_sandbox", None))
        self._hook_agent_loop()
        await self._wrapped_agent.run(instruction, environment, context)

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
        if (
            self._snapshot_session is None
            or not commands
            or not self._should_snapshot_commands(commands)
        ):
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
            environment_id=getattr(self._sandbox, "id", None),
        )

        # Process through snapshot manager
        await self._snapshot_session.process_step(context)

    def _hook_tmux_session(self, session: Any) -> None:
        """Hook the tmux session command path when available."""
        if self._snapshot_session is None:
            return

        if self._debug_enabled():
            candidates = [
                name
                for name in ("send_keys", "send", "write", "execute", "run_command", "run")
                if hasattr(session, name)
            ]
            self._debug_log(
                f"DEBUG tmux session type={type(session).__name__} "
                f"candidates={candidates}"
            )

        for method_name in ("send_keys", "send", "write", "execute", "run_command", "run"):
            if not hasattr(session, method_name):
                continue

            original_method = getattr(session, method_name)
            self._session_snapshot_hooked = True

            def wrapped_method(*args: Any, **kwargs: Any) -> Any:
                if self._debug_enabled():
                    arg_types = [type(arg).__name__ for arg in args]
                    self._debug_log(
                        f"DEBUG tmux hook method={method_name} "
                        f"arg_types={arg_types} "
                        f"kwargs_keys={list(kwargs)}"
                    )

                result = original_method(*args, **kwargs)

                commands: list[str] = []
                if args:
                    first_arg = args[0]
                    if isinstance(first_arg, (list, tuple)):
                        commands = [str(command) for command in first_arg]
                    elif isinstance(first_arg, str):
                        commands = [first_arg]

                for key in ("keys", "commands", "keystrokes"):
                    if commands or key not in kwargs:
                        continue
                    value = kwargs[key]
                    if isinstance(value, (list, tuple)):
                        commands = [str(command) for command in value]
                    elif isinstance(value, str):
                        commands = [value]

                if self._debug_enabled():
                    self._debug_log(
                        f"DEBUG tmux hook method={method_name} "
                        f"commands={commands!r} "
                        f"should_snapshot={self._should_snapshot_commands(commands)}"
                    )

                if self._snapshot_session and self._should_snapshot_commands(commands):
                    try:
                        asyncio.run(self._process_step_snapshot(commands, ""))
                    except Exception as e:
                        print(f"Warning: Snapshot processing failed: {e}")

                if not self._agent_step_active:
                    self._step_counter += 1

                return result

            setattr(session, method_name, wrapped_method)
            return

    def _hook_agent_loop(self) -> None:
        """Hook into the wrapped agent's loop to capture snapshots.

        This wraps the agent's _execute_commands method to capture step data.
        """
        if self._debug_enabled():
            self._debug_log(
                f"DEBUG wrapped agent type={type(self._wrapped_agent).__name__} "
                f"has_execute_commands={hasattr(self._wrapped_agent, '_execute_commands')}"
            )

        if not hasattr(self._wrapped_agent, "_execute_commands"):
            return

        self._agent_execute_hooked = True
        original_execute = self._wrapped_agent._execute_commands
        if getattr(original_execute, "_go_explore_snapshot_wrapped", False):
            return

        def _extract_commands(commands: list[Any]) -> list[str]:
            return [str(getattr(cmd, "keystrokes", cmd)) for cmd in commands]

        async def async_wrapped_execute(
            commands: list[Any],
            session: Any,
        ) -> tuple[bool, str]:
            """Wrapper around Harbor Terminus2._execute_commands."""
            self._agent_step_active = True
            try:
                commands_buffer = _extract_commands(commands)
                timeout_occurred, terminal_output = await original_execute(commands, session)
                if self._debug_enabled():
                    self._debug_log(
                        f"DEBUG execute hook commands={commands_buffer!r} "
                        f"should_snapshot={self._should_snapshot_commands(commands_buffer)}"
                    )
                if self._snapshot_session and commands_buffer:
                    try:
                        await self._process_step_snapshot(commands_buffer, terminal_output)
                    except Exception as e:
                        print(f"Warning: Snapshot processing failed: {e}")
                self._step_counter += 1
                return timeout_occurred, terminal_output
            finally:
                self._agent_step_active = False

        def sync_wrapped_execute(
            commands: list[Any],
            session: TmuxSession,
        ) -> tuple[bool, str]:
            """Wrapper around legacy sync _execute_commands."""
            self._agent_step_active = True
            try:
                commands_buffer = _extract_commands(commands)
                timeout_occurred, terminal_output = original_execute(commands, session)
                if self._snapshot_session and commands_buffer:
                    try:
                        asyncio.run(
                            self._process_step_snapshot(commands_buffer, terminal_output)
                        )
                    except Exception as e:
                        print(f"Warning: Snapshot processing failed: {e}")
                self._step_counter += 1
                return timeout_occurred, terminal_output
            finally:
                self._agent_step_active = False

        if inspect.iscoroutinefunction(original_execute):
            async_wrapped_execute._go_explore_snapshot_wrapped = True  # type: ignore[attr-defined]
            self._wrapped_agent._execute_commands = async_wrapped_execute
        else:
            sync_wrapped_execute._go_explore_snapshot_wrapped = True  # type: ignore[attr-defined]
            self._wrapped_agent._execute_commands = sync_wrapped_execute

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
        self._debug_log_path = (
            Path("jobs") / f"{self._trial_name}-hook_debug.log"
            if self._debug_enabled()
            else None
        )

        # Hook the agent's execution loop
        self._hook_agent_loop()
        self._hook_tmux_session(session)

        # Call the wrapped agent's perform_task
        result = self._wrapped_agent.perform_task(
            instruction=instruction,
            session=session,
            logging_dir=logging_dir,
            time_limit_seconds=time_limit_seconds,
        )

        if self._snapshot_session is not None and logging_dir is not None:
            trajectory_path = logging_dir / "agent" / "trajectory.json"
            if trajectory_path.exists() and not self._snapshot_session.manager.list():
                try:
                    asyncio.run(
                        process_atif_trajectory(
                            trajectory_path,
                            self._snapshot_session.manager,
                            trial_name=self._trial_name or logging_dir.name,
                            trace_path=trajectory_path,
                            environment_id=getattr(self._sandbox, "id", None),
                        )
                    )
                except Exception as e:
                    print(f"Warning: Snapshot replay failed: {e}")

        return result
