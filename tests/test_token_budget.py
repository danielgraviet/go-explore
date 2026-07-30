from __future__ import annotations

from types import SimpleNamespace

from go_explore.agents.token_budget import (
    AgentBudgetExhaustedError,
    is_budget_exhausted,
    tokens_consumed,
)


def test_tokens_consumed_sums_input_output_cache():
    chat = SimpleNamespace(
        total_input_tokens=100,
        total_output_tokens=50,
        total_cache_tokens=25,
    )

    assert tokens_consumed(chat) == 175


def test_tokens_consumed_treats_missing_attributes_as_zero():
    chat = SimpleNamespace(total_input_tokens=10)

    assert tokens_consumed(chat) == 10


def test_is_budget_exhausted_true_at_or_over_budget():
    assert is_budget_exhausted(1000, 1000) is True
    assert is_budget_exhausted(1001, 1000) is True


def test_is_budget_exhausted_false_under_budget():
    assert is_budget_exhausted(999, 1000) is False


def test_agent_budget_exhausted_error_carries_fields():
    error = AgentBudgetExhaustedError(token_budget=1000, tokens_consumed=1200)

    assert error.token_budget == 1000
    assert error.tokens_consumed == 1200
    assert "1200" in str(error)
    assert "1000" in str(error)
