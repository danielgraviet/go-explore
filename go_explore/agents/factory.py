"""Factory functions for creating snapshot-aware agent wrappers."""

from __future__ import annotations

from typing import Any

from go_explore.agents.snapshot_agent import SnapshotAwareAgent


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
    try:
        from terminal_bench.agents.terminus_2 import Terminus2

        wrapped = Terminus2(model_name=model_name, **kwargs)
        return SnapshotAwareAgent(wrapped_agent=wrapped, sandbox=sandbox)
    except ImportError:
        raise ImportError("terminal-bench must be installed to use Terminus-2")


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
    try:
        from terminal_bench.agents.oracle_agent import OracleAgent

        wrapped = OracleAgent(**kwargs)
        return SnapshotAwareAgent(wrapped_agent=wrapped, sandbox=sandbox)
    except ImportError:
        raise ImportError("terminal-bench must be installed to use OracleAgent")


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
        # From Harbor CLI with agent-import-path
        # --agent-import-path go_explore.agents.factory:snapshot_aware_terminus2_factory
        # --ak model_name="anthropic/claude-haiku-4-5-20251001"
        # --ak sandbox="<daytona_sandbox>"
    """
    if agent_name == "terminus-2":
        if model_name is None:
            raise ValueError("model_name is required for terminus-2")
        return create_snapshot_aware_terminus2(model_name, sandbox=sandbox, **kwargs)
    elif agent_name == "oracle":
        return create_snapshot_aware_oracle(model_name, sandbox=sandbox, **kwargs)
    else:
        raise ValueError(f"Unknown agent: {agent_name}")


# Harbor-compatible factory functions (these are what --agent-import-path will call)
def snapshot_aware_terminus2_factory(**kwargs: Any) -> SnapshotAwareAgent:
    """Factory function for Harbor: creates snapshot-aware Terminus-2.

    Usage:
        harbor run \
          --agent-import-path go_explore.agents.factory:snapshot_aware_terminus2_factory \
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
          --agent-import-path go_explore.agents.factory:snapshot_aware_oracle_factory \
          ...
    """
    sandbox = kwargs.pop("sandbox", None)
    return create_snapshot_aware_oracle(sandbox=sandbox, **kwargs)
