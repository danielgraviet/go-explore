"""Small, pure primitives for enforcing a per-job token budget.

Kept separate from `snapshot_agent.py` so the accounting logic can be unit
tested without a real Harbor `Chat`/`Terminus2` instance.
"""

from __future__ import annotations

from typing import Any


class AgentBudgetExhaustedError(RuntimeError):
    """Raised to stop the agent loop once its token budget is spent.

    Blocks the *next* model request; it does not bound the size of the
    request that pushed consumption over the limit, since token totals are
    only known after a request completes.
    """

    def __init__(self, *, token_budget: int, tokens_consumed: int) -> None:
        self.token_budget = token_budget
        self.tokens_consumed = tokens_consumed
        super().__init__(
            f"Token budget exhausted: consumed {tokens_consumed} tokens "
            f"against a budget of {token_budget}."
        )


def tokens_consumed(chat: Any) -> int:
    """Total tokens spent so far on `chat` (input + output + cache)."""

    return (
        int(getattr(chat, "total_input_tokens", 0) or 0)
        + int(getattr(chat, "total_output_tokens", 0) or 0)
        + int(getattr(chat, "total_cache_tokens", 0) or 0)
    )


def is_budget_exhausted(consumed: int, token_budget: int) -> bool:
    return consumed >= token_budget
