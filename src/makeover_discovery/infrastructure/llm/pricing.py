"""Published Anthropic list prices, for cost estimation only.

A table rather than a lookup call: the API does not report cost, and a stale rate
is a wrong estimate, not a wrong charge. Unknown models fall back to the most
expensive row here so a misconfiguration overstates spend rather than hiding it.
"""

from __future__ import annotations

from typing import Final

from makeover_discovery.domain.model.llm import ModelPricing

DEFAULT_MODEL: Final = "claude-opus-5"

_RATES: Final[dict[str, tuple[float, float]]] = {
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-4-8": (5.00, 25.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
}

_UNKNOWN_MODEL_RATE: Final = max(_RATES.values())


def pricing_for(model: str) -> ModelPricing:
    """Rates for ``model``, erring high when the model is not in the table."""
    input_rate, output_rate = _RATES.get(model, _UNKNOWN_MODEL_RATE)
    return ModelPricing(
        model=model,
        input_usd_per_mtok=input_rate,
        output_usd_per_mtok=output_rate,
    )
