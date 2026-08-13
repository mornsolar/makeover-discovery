"""Token accounting and cost estimation."""

from __future__ import annotations

import pytest

from makeover_discovery.domain.model.llm import ModelPricing, TokenUsage
from makeover_discovery.infrastructure.llm.pricing import DEFAULT_MODEL, pricing_for

OPUS = pricing_for(DEFAULT_MODEL)


def test_adds_two_calls_field_by_field():
    first = TokenUsage(input_tokens=100, output_tokens=10, cache_read_input_tokens=5)
    second = TokenUsage(input_tokens=200, output_tokens=20, cache_write_input_tokens=7)

    total = first + second

    assert total == TokenUsage(
        input_tokens=300,
        output_tokens=30,
        cache_read_input_tokens=5,
        cache_write_input_tokens=7,
    )


def test_rejects_negative_counts():
    with pytest.raises(ValueError, match="negative"):
        TokenUsage(input_tokens=-1)


def test_prices_input_and_output_at_their_own_rates():
    usage = TokenUsage(input_tokens=1_000_000, output_tokens=1_000_000)

    assert OPUS.cost_usd(usage) == pytest.approx(30.00)


def test_bills_cached_input_below_the_base_rate():
    # A cache read must be an order of magnitude cheaper, or the whole reason to
    # cache a long system prompt disappears from the estimate.
    cached = TokenUsage(cache_read_input_tokens=1_000_000)
    fresh = TokenUsage(input_tokens=1_000_000)

    assert OPUS.cost_usd(cached) == pytest.approx(OPUS.cost_usd(fresh) * 0.1)


def test_bills_a_cache_write_above_the_base_rate():
    written = TokenUsage(cache_write_input_tokens=1_000_000)

    assert OPUS.cost_usd(written) == pytest.approx(6.25)


def test_costs_nothing_when_nothing_was_used():
    assert OPUS.cost_usd(TokenUsage()) == 0.0


def test_an_unknown_model_is_priced_at_the_most_expensive_known_rate():
    # A misconfigured model name should overstate spend, never hide it.
    unknown = pricing_for("claude-something-unreleased")

    assert unknown.input_usd_per_mtok >= OPUS.input_usd_per_mtok
    assert unknown.output_usd_per_mtok >= OPUS.output_usd_per_mtok


def test_rejects_negative_rates():
    with pytest.raises(ValueError, match="negative"):
        ModelPricing(model="x", input_usd_per_mtok=-1.0, output_usd_per_mtok=1.0)
