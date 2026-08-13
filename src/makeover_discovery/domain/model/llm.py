"""Token usage and cost accounting for language-model calls.

Cost is recorded per generated brief rather than aggregated later: a brief is the
one artifact in this system that costs real money to produce, and attributing
that spend after the fact - from provider invoices - cannot tell you which
postcode or business caused it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

TOKENS_PER_MILLION: Final = 1_000_000

CACHE_READ_MULTIPLIER: Final = 0.1
"""Cached input is billed at a tenth of the base input rate."""

CACHE_WRITE_MULTIPLIER: Final = 1.25
"""Writing a 5-minute cache entry costs a quarter more than plain input."""


@dataclass(frozen=True)
class TokenUsage:
    """What one model call consumed, split by how each part is billed."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_write_input_tokens: int = 0

    def __post_init__(self) -> None:
        if min(self.as_tuple()) < 0:
            raise ValueError("token counts cannot be negative")

    def as_tuple(self) -> tuple[int, int, int, int]:
        return (
            self.input_tokens,
            self.output_tokens,
            self.cache_read_input_tokens,
            self.cache_write_input_tokens,
        )

    @property
    def total_tokens(self) -> int:
        return sum(self.as_tuple())

    def __add__(self, other: TokenUsage) -> TokenUsage:
        """Combine two calls - a first attempt and its repair round, typically."""
        left, right = self.as_tuple(), other.as_tuple()
        return TokenUsage(*(a + b for a, b in zip(left, right, strict=True)))


@dataclass(frozen=True)
class ModelPricing:
    """Published per-million-token rates for one model."""

    model: str
    input_usd_per_mtok: float
    output_usd_per_mtok: float

    def __post_init__(self) -> None:
        if self.input_usd_per_mtok < 0.0 or self.output_usd_per_mtok < 0.0:
            raise ValueError("model rates cannot be negative")

    def cost_usd(self, usage: TokenUsage) -> float:
        """Estimated spend for ``usage`` at these rates.

        Estimated, not authoritative: the provider's invoice is the source of
        truth, and published rates change. This exists to enforce a per-run
        budget and to make an unexpectedly expensive prompt visible immediately.
        """
        input_units = (
            usage.input_tokens
            + usage.cache_read_input_tokens * CACHE_READ_MULTIPLIER
            + usage.cache_write_input_tokens * CACHE_WRITE_MULTIPLIER
        )
        dollars = (
            input_units * self.input_usd_per_mtok + usage.output_tokens * self.output_usd_per_mtok
        )
        return dollars / TOKENS_PER_MILLION
