"""Factory functions for creating snapshot-aware agent wrappers."""

from __future__ import annotations

from typing import Any

from go_explore.agents.snapshot_agent import SnapshotAwareAgent
from go_explore.snapshots.command_replay import (
    DEFAULT_COMMAND_TIMEOUT_SEC,
    DEFAULT_TOTAL_BUDGET_SEC,
)
from go_explore.snapshots.policies import (
    EveryAgentStepPolicy,
    InterestingAgentStepPolicy,
    SnapshotPolicy,
)

_SNAPSHOT_POLICIES: dict[str, type[SnapshotPolicy]] = {
    "every_step": EveryAgentStepPolicy,
    "interesting": InterestingAgentStepPolicy,
}


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _resolve_snapshot_policy(value: Any) -> SnapshotPolicy | None:
    if value is None or not isinstance(value, str):
        return value

    name = value.strip().lower()
    try:
        policy_cls = _SNAPSHOT_POLICIES[name]
    except KeyError:
        raise ValueError(
            f"Unknown snapshot_policy: {value!r} (choices: {sorted(_SNAPSHOT_POLICIES)})"
        ) from None
    return policy_cls()


def create_snapshot_aware_terminus2(
    model_name: str,
    sandbox: Any = None,
    **kwargs: Any,
) -> SnapshotAwareAgent:
    """Create a snapshot-aware Terminus-2 agent.

    Args:
        model_name: The model to use (e.g., "anthropic/claude-haiku-4-5-20251001")
        sandbox: The Daytona AsyncSandbox instance (provided by Harbor)
        **kwargs: Additional kwargs to pass to Terminus-2

    Returns:
        SnapshotAwareAgent wrapping Terminus-2
    """
    return SnapshotAwareTerminus2(
        model_name=model_name,
        sandbox=sandbox,
        **kwargs,
    )


def create_snapshot_aware_oracle(
    model_name: str | None = None,
    sandbox: Any = None,
    **kwargs: Any,
) -> SnapshotAwareAgent:
    """Create a snapshot-aware Oracle agent.

    Args:
        model_name: The model to use (optional for oracle)
        sandbox: The Daytona AsyncSandbox instance (provided by Harbor)
        **kwargs: Additional kwargs to pass to Oracle

    Returns:
        SnapshotAwareAgent wrapping Oracle
    """
    return SnapshotAwareOracle(
        model_name=model_name,
        sandbox=sandbox,
        **kwargs,
    )


class SnapshotAwareTerminus2(SnapshotAwareAgent):
    """Harbor 0.19-compatible import path for snapshot-aware Terminus-2."""

    SUPPORTS_ATIF: bool = True

    def __init__(
        self,
        logs_dir: Any,
        model_name: str | None = None,
        logger: Any = None,
        sandbox: Any = None,
        **kwargs: Any,
    ) -> None:
        if model_name is None:
            raise ValueError("model_name is required for terminus-2")

        from harbor.agents.terminus_2 import Terminus2

        hooks_debug = _as_bool(kwargs.pop("hooks_debug", False))
        snapshot_policy = _resolve_snapshot_policy(kwargs.pop("snapshot_policy", None))
        context_mode = kwargs.pop("context_mode", "parent_summary")
        parent_context = kwargs.pop("parent_context", None)
        parent_context_path = kwargs.pop("parent_context_path", None)
        preinstall_tmux = _as_bool(kwargs.pop("preinstall_tmux", True))
        tmux_install_timeout_sec = float(kwargs.pop("tmux_install_timeout_sec", 360.0))
        preflight_verification_timeout_sec = float(
            kwargs.pop("preflight_verification_timeout_sec", 180.0)
        )
        diff_path = kwargs.pop("diff_path", None)
        diff_apply_timeout_sec = float(kwargs.pop("diff_apply_timeout_sec", 60.0))
        replay_manifest_path = kwargs.pop("replay_manifest_path", None)
        replay_command_timeout_sec = float(
            kwargs.pop("replay_command_timeout_sec", DEFAULT_COMMAND_TIMEOUT_SEC)
        )
        replay_total_budget_sec = float(
            kwargs.pop("replay_total_budget_sec", DEFAULT_TOTAL_BUDGET_SEC)
        )
        kwargs.setdefault("record_terminal_session", False)
        wrapped = Terminus2(
            logs_dir=logs_dir,
            model_name=model_name,
            logger=logger,
            **kwargs,
        )
        super().__init__(
            wrapped_agent=wrapped,
            sandbox=sandbox,
            hooks_debug=hooks_debug,
            snapshot_policy=snapshot_policy,
            context_mode=context_mode,
            parent_context=parent_context,
            parent_context_path=parent_context_path,
            preinstall_tmux=preinstall_tmux,
            tmux_install_timeout_sec=tmux_install_timeout_sec,
            preflight_verification_timeout_sec=preflight_verification_timeout_sec,
            diff_path=diff_path,
            diff_apply_timeout_sec=diff_apply_timeout_sec,
            replay_manifest_path=replay_manifest_path,
            replay_command_timeout_sec=replay_command_timeout_sec,
            replay_total_budget_sec=replay_total_budget_sec,
            logs_dir=logs_dir,
            model_name=model_name,
            logger=logger,
        )


class SnapshotAwareOracle(SnapshotAwareAgent):
    """Harbor 0.19-compatible import path for snapshot-aware Oracle."""

    def __init__(
        self,
        logs_dir: Any,
        model_name: str | None = None,
        logger: Any = None,
        sandbox: Any = None,
        **kwargs: Any,
    ) -> None:
        from harbor.agents.oracle import OracleAgent

        hooks_debug = _as_bool(kwargs.pop("hooks_debug", False))
        snapshot_policy = _resolve_snapshot_policy(kwargs.pop("snapshot_policy", None))
        context_mode = kwargs.pop("context_mode", "parent_summary")
        parent_context = kwargs.pop("parent_context", None)
        parent_context_path = kwargs.pop("parent_context_path", None)
        preflight_verification_timeout_sec = float(
            kwargs.pop("preflight_verification_timeout_sec", 180.0)
        )
        diff_path = kwargs.pop("diff_path", None)
        diff_apply_timeout_sec = float(kwargs.pop("diff_apply_timeout_sec", 60.0))
        replay_manifest_path = kwargs.pop("replay_manifest_path", None)
        replay_command_timeout_sec = float(
            kwargs.pop("replay_command_timeout_sec", DEFAULT_COMMAND_TIMEOUT_SEC)
        )
        replay_total_budget_sec = float(
            kwargs.pop("replay_total_budget_sec", DEFAULT_TOTAL_BUDGET_SEC)
        )
        wrapped = OracleAgent(
            logs_dir=logs_dir,
            model_name=model_name,
            logger=logger,
            **kwargs,
        )
        super().__init__(
            wrapped_agent=wrapped,
            sandbox=sandbox,
            hooks_debug=hooks_debug,
            snapshot_policy=snapshot_policy,
            context_mode=context_mode,
            parent_context=parent_context,
            parent_context_path=parent_context_path,
            preflight_verification_timeout_sec=preflight_verification_timeout_sec,
            diff_path=diff_path,
            diff_apply_timeout_sec=diff_apply_timeout_sec,
            replay_manifest_path=replay_manifest_path,
            replay_command_timeout_sec=replay_command_timeout_sec,
            replay_total_budget_sec=replay_total_budget_sec,
            logs_dir=logs_dir,
            model_name=model_name,
            logger=logger,
        )


def create_snapshot_aware_agent(
    agent_name: str,
    model_name: str | None = None,
    sandbox: Any = None,
    **kwargs: Any,
) -> SnapshotAwareAgent:
    """Create a snapshot-aware wrapper around any Harbor agent.

    Args:
        agent_name: Name of the agent to wrap (e.g., "terminus-2", "oracle")
        model_name: The model to use (optional depending on agent)
        sandbox: The Daytona AsyncSandbox instance (provided by Harbor)
        **kwargs: Additional kwargs to pass to the wrapped agent

    Returns:
        SnapshotAwareAgent wrapping the specified agent

    Example:
        # From Harbor CLI with an agent import path
        # --agent-import-path go_explore.agents.factory:SnapshotAwareTerminus2
        # --ak model_name="anthropic/claude-haiku-4-5-20251001"
        # --ak sandbox="<daytona_sandbox>"
    """
    # TODO: Consider using a registry of agent factories instead of hardcoding agent names here.
    if agent_name == "terminus-2":
        if model_name is None:
            raise ValueError("model_name is required for terminus-2")
        return create_snapshot_aware_terminus2(model_name, sandbox=sandbox, **kwargs)
    elif agent_name == "oracle":
        return create_snapshot_aware_oracle(model_name, sandbox=sandbox, **kwargs)
    else:
        raise ValueError(f"Unknown agent: {agent_name}")


# Factory functions kept for direct Python callers.
def snapshot_aware_terminus2_factory(**kwargs: Any) -> SnapshotAwareAgent:
    """Factory function for Harbor: creates snapshot-aware Terminus-2.

    Usage:
        harbor run \
          --agent-import-path go_explore.agents.factory:SnapshotAwareTerminus2 \
          --model anthropic/claude-haiku-4-5-20251001 \
          ...
    """
    model_name = kwargs.pop("model", None) or kwargs.pop("model_name", None)
    if not model_name:
        raise ValueError("model_name is required")
    sandbox = kwargs.pop("sandbox", None)
    return create_snapshot_aware_terminus2(model_name, sandbox=sandbox, **kwargs)


def snapshot_aware_oracle_factory(**kwargs: Any) -> SnapshotAwareAgent:
    """Factory function for Harbor: creates snapshot-aware Oracle.

    Usage:
        harbor run \
          --agent-import-path go_explore.agents.factory:SnapshotAwareOracle \
          ...
    """
    sandbox = kwargs.pop("sandbox", None)
    return create_snapshot_aware_oracle(sandbox=sandbox, **kwargs)
