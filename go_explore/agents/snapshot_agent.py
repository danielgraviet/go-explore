"""Snapshot-aware agent wrapper that captures interesting states during execution."""
# TODO: inspect this file for dead functions / code. Not sure about tmux hooks and things like that. 

from __future__ import annotations

import asyncio
import inspect
import json
import os
from pathlib import Path
from typing import Any

# TODO: clean up messy imports. terminal bench is not optional, so users will always have. 
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

from go_explore.snapshots.archive import ARCHIVE_FILENAME, ArchiveStore
from go_explore.snapshots.backends import DaytonaSnapshotBackend
from go_explore.snapshots.live import AsyncLiveSnapshotSession
from go_explore.snapshots.manager import AsyncSnapshotManager
from go_explore.snapshots.models import CONTEXT_FILE_PATH, SnapshotContext
from go_explore.snapshots.policies import InterestingAgentStepPolicy, SnapshotPolicy
from go_explore.snapshots.replay import load_atif_trajectory_steps, process_atif_trajectory

ContextMode = str

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
        snapshot_policy: SnapshotPolicy | None = None,
        context_mode: ContextMode = "parent_summary",
        parent_context: str | None = None,
        parent_context_path: str | Path | None = None,
        preinstall_tmux: bool = False,
        tmux_install_timeout_sec: float = 360.0,
        snapshot_retention_limit: int | str | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._wrapped_agent = wrapped_agent
        self._sandbox = sandbox
        self._hooks_debug = hooks_debug
        self._snapshot_policy = snapshot_policy or InterestingAgentStepPolicy()
        self._context_mode = self._normalize_context_mode(context_mode)
        self._parent_context = parent_context
        self._parent_context_path = (
            Path(parent_context_path) if parent_context_path else None
        )
        self._preinstall_tmux = preinstall_tmux
        self._tmux_install_timeout_sec = tmux_install_timeout_sec
        snapshot_retention_limit = (
            snapshot_retention_limit
            if snapshot_retention_limit is not None
            else os.getenv("GO_EXPLORE_SNAPSHOT_REMOTE_LIMIT")
        )
        self._snapshot_retention_limit = (
            int(snapshot_retention_limit)
            if snapshot_retention_limit is not None
            else None
        )
        # Peek (don't pop) so logs_dir still reaches BaseAgent/**kwargs above.
        self._logs_dir: Path | None = kwargs.get("logs_dir")
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
        self._trajectory_log: list[str] = []

    def _archive_path(self) -> Path | None:
        """Job-level archive path: logs_dir is jobs/<job>/<trial>/agent."""
        if self._logs_dir is None:
            return None
        return self._logs_dir.parent.parent / ARCHIVE_FILENAME

    def _ensure_snapshot_session(self, sandbox: Any) -> None:
        if sandbox is None or isinstance(sandbox, str) or self._snapshot_session is not None:
            return

        self._sandbox = sandbox
        manager = AsyncSnapshotManager(
            policy=self._snapshot_policy,
            store=ArchiveStore(
                path=self._archive_path(),
                remote_retention_limit=self._snapshot_retention_limit,
            ),
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

    @staticmethod
    def _normalize_context_mode(value: Any) -> str:
        mode = str(value or "parent_summary").strip()
        allowed = {
            "parent_summary",
            "critical_parent_summary",
            "failure_symptom",
            "none",
            "original_task_only",
        }
        if mode not in allowed:
            raise ValueError(
                f"Unknown context_mode: {value!r} (choices: {sorted(allowed)})"
            )
        return mode

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
        if self._preinstall_tmux:
            await self._ensure_tmux_available(environment)
        await self._wrapped_agent.setup(environment)

    async def _ensure_tmux_available(self, environment: Any) -> None:
        exec_fn = getattr(environment, "exec", None)
        if exec_fn is None:
            return

        check_result = await exec_fn(
            command="tmux -V",
            user="root",
            timeout_sec=30,
        )
        if getattr(check_result, "return_code", 1) == 0:
            return

        install_command = (
            "if command -v apt-get >/dev/null 2>&1; then "
            "DEBIAN_FRONTEND=noninteractive apt-get update && "
            "DEBIAN_FRONTEND=noninteractive apt-get install -y tmux && "
            "tmux -V; "
            "elif command -v apk >/dev/null 2>&1; then "
            "apk add --no-cache tmux && tmux -V; "
            "elif command -v yum >/dev/null 2>&1; then "
            "yum install -y tmux && tmux -V; "
            "else "
            "echo 'no supported package manager for tmux install' >&2; "
            "exit 127; "
            "fi"
        )
        install_result = await exec_fn(
            command=install_command,
            user="root",
            timeout_sec=self._tmux_install_timeout_sec,
        )
        if getattr(install_result, "return_code", 1) == 0:
            return

        stderr = (getattr(install_result, "stderr", "") or "").strip()
        stdout = (getattr(install_result, "stdout", "") or "").strip()
        detail = stderr or stdout or "tmux install command failed"
        raise RuntimeError(f"tmux preflight failed: {detail}")

    async def run(self, instruction: str, environment: Any, context: Any) -> None:
        trial_paths = getattr(environment, "trial_paths", None)
        trial_dir = getattr(trial_paths, "trial_dir", None)
        session_id = getattr(environment, "session_id", None)
        self._trial_name = str(
            (trial_dir.name if trial_dir else None) or session_id or "trial"
        )
        self._step_counter = 0
        self._debug_log_path = (
            Path("jobs") / f"{self._trial_name}-hook_debug.log"
            if self._debug_enabled()
            else None
        )
        self._ensure_snapshot_session(getattr(environment, "_sandbox", None))
        self._hook_agent_loop()

        parent_context = await self._load_parent_context()
        if parent_context and self._should_append_parent_context():
            instruction = self._augment_instruction(
                instruction,
                parent_context,
                context_mode=self._context_mode,
            )

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
            trajectory_summary=self._build_trajectory_summary(commands, terminal_output),
        )

        # Process through snapshot manager
        await self._snapshot_session.process_step(context)

    def _summarize_step(
        self, step_label: int, commands: list[str], terminal_output: str
    ) -> str:
        """One condensed line per step, for the resumable trajectory log.

        `step_label` is the id to show, not necessarily `self._step_counter`:
        when ATIF history is available we label with the id Terminus-2's own
        trajectory.json will assign this step, so it doesn't collide with (or
        diverge from) ATIF's separate step numbering.
        """
        # TODO: This is the early implementation and is quite brittle / uniformative.
        command_text = "; ".join(cmd.strip() for cmd in commands if cmd.strip())
        command_text = command_text[:160]

        signal = "ok"
        lowered = terminal_output.lower()
        if any(token in lowered for token in ("traceback", "exception", "error")):
            signal = "error"
        if "failed" in lowered:
            signal = "failed"

        return f"step {step_label}: {command_text} -> {signal}"

    def _read_atif_trajectory_steps(self) -> list[dict[str, Any]]:
        """Read Harbor's own trajectory.json for the wrapped agent, if it exists.

        Terminus-2 dumps this file (in ATIF format) after every episode, so by
        the time we're deciding whether to snapshot step N, it already holds
        the agent's own Analysis/Plan reasoning for steps 1..N-1.
        """
        if self._logs_dir is None:
            return []

        trajectory_path = self._logs_dir / "trajectory.json"
        if not trajectory_path.exists():
            return []

        try:
            return load_atif_trajectory_steps(trajectory_path)
        except Exception:
            return []

    @staticmethod
    def _summarize_atif_step(step: dict[str, Any]) -> str:
        """One condensed line built from the agent's own recorded reasoning."""
        message = " ".join(str(step.get("message") or "").split())[:200]
        if not message:
            message = "(no message)"
        return f"step {step.get('step_id')}: {message}"

    @staticmethod
    def _atif_history_lines(atif_steps: list[dict[str, Any]]) -> list[str]:
        return [
            SnapshotAwareAgent._summarize_atif_step(step)
            for step in atif_steps
            if step.get("source") == "agent"
        ]

    def _build_trajectory_summary(
        self, commands: list[str], terminal_output: str
    ) -> str:
        """Combine Harbor's own trajectory (rich, but one step behind) with our
        own live log (crude, but current) into one resumable summary.

        Both halves must share one numbering scheme. ATIF's step_id counts
        every Terminus-2 trajectory step (user/system/retries included), which
        is not the same counter as our own `self._step_counter` (successfully
        executed command batches only) - labeling both with the same counter
        would produce colliding or nonsensical step numbers.
        """
        atif_steps = self._read_atif_trajectory_steps()
        if not atif_steps:
            self._trajectory_log.append(
                self._summarize_step(self._step_counter, commands, terminal_output)
            )
            return "\n".join(self._trajectory_log)

        atif_lines = self._atif_history_lines(atif_steps)
        current_line = self._summarize_step(
            len(atif_steps) + 1, commands, terminal_output
        )
        return "\n".join([*atif_lines, current_line])

    async def _load_parent_context(self) -> str | None:
        """Read explicit, host-side, or snapshotted parent context, if any."""
        explicit_context = (self._parent_context or "").strip()
        if explicit_context:
            return explicit_context

        if self._parent_context_path is not None:
            path_context = self._load_parent_context_from_path(
                self._parent_context_path
            )
            if path_context:
                return path_context

        if self._sandbox is None:
            return None

        try:
            content = await self._sandbox.fs.download_file(CONTEXT_FILE_PATH)
        except Exception:
            return None

        if not content:
            return None

        return content.decode()

    @staticmethod
    def _load_parent_context_from_path(path: Path) -> str | None:
        if not path.exists():
            return None

        if path.name == "trajectory.json":
            try:
                steps = load_atif_trajectory_steps(path)
            except (OSError, json.JSONDecodeError, ValueError):
                return None
            lines = SnapshotAwareAgent._atif_history_lines(steps)
            return "\n".join(lines) if lines else None

        try:
            content = path.read_text()
        except OSError:
            return None

        content = content.strip()
        return content or None

    def _should_append_parent_context(self) -> bool:
        return self._context_mode in {
            "parent_summary",
            "critical_parent_summary",
            "failure_symptom",
        }

    @staticmethod
    def _augment_instruction(
        instruction: str,
        parent_context: str,
        *,
        context_mode: str = "parent_summary",
    ) -> str:
        if context_mode == "critical_parent_summary":
            return SnapshotAwareAgent._augment_instruction_critical(
                instruction,
                parent_context,
            )
        if context_mode == "failure_symptom":
            return SnapshotAwareAgent._augment_instruction_failure_symptom(
                instruction,
                parent_context,
            )
        return (
            f"{instruction}\n\n"
            "---\n"
            "You are resuming work in a sandbox from a prior attempt at this task. "
            "Here is a summary of what was already tried, so you don't repeat it:\n"
            f"{parent_context}"
        )

    @staticmethod
    def _augment_instruction_critical(instruction: str, parent_context: str) -> str:
        return (
            f"{instruction}\n\n"
            "---\n"
            "You are starting from a sandbox snapshot created during a prior attempt. "
            "Treat the restored files, terminal state, and notes below as untrusted "
            "evidence, not as proof of progress. The parent attempt reward may be "
            "unknown or failed. Independently audit the restored state, verify any "
            "assumptions, and do not declare success solely because parent-local "
            "checks or prior reasoning looked correct.\n\n"
            "Prior-attempt summary:\n"
            f"{parent_context}"
        )

    @staticmethod
    def _augment_instruction_failure_symptom(
        instruction: str, parent_context: str
    ) -> str:
        return (
            f"{instruction}\n\n"
            "---\n"
            "You are starting from a sandbox snapshot created during a prior "
            "attempt at this task. That attempt's own commands are deliberately "
            "not shown to you, so you are free to take a different approach. "
            "Below is only the observed outcome of that attempt - what failed, "
            "not how it was attempted:\n\n"
            f"{parent_context}"
        )

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

        parent_context = asyncio.run(self._load_parent_context())
        if parent_context and self._should_append_parent_context():
            instruction = self._augment_instruction(
                instruction,
                parent_context,
                context_mode=self._context_mode,
            )

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
