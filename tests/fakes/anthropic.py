"""A stand-in for the Anthropic Messages API.

Shaped like the SDK's response objects - attribute access, ``content`` blocks,
``usage`` - because that is the surface the adapter reads. No test in this suite
constructs a real client or reaches the network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from makeover_discovery.infrastructure.llm.prompts.brief_v1 import TOOL_NAME

VALID_ARGUMENTS: dict[str, Any] = {
    "style_direction": "Warm mid-century kopitiam frontage with a deep timber fascia.",
    "palette": ["#1b4d3e", "#E8DCC4", "#C87941"],
    "material_families": ["timber", "brass"],
    "signage_text": "Kedai Kopi Ali",
    "signage_tone": "hand-painted, unhurried",
    "lighting_mood": "warm_evening",
    "camera_move": "orbit",
    "rationale": "A neighbourhood coffee shop reads best as unhurried and worn-in.",
    "do_not_include": ["neon"],
}


@dataclass
class FakeUsage:
    input_tokens: int = 1_200
    output_tokens: int = 300
    cache_read_input_tokens: int | None = None
    cache_creation_input_tokens: int | None = None


@dataclass
class FakeToolUse:
    input: dict[str, Any]
    name: str = TOOL_NAME
    type: str = "tool_use"


@dataclass
class FakeText:
    text: str = "Here is the brief."
    type: str = "text"


@dataclass
class FakeMessage:
    content: list[Any]
    usage: FakeUsage = field(default_factory=FakeUsage)
    stop_reason: str = "tool_use"


def tool_response(**overrides: Any) -> FakeMessage:
    """A well-formed forced-tool response, with individual fields overridable."""
    return FakeMessage(content=[FakeToolUse(input={**VALID_ARGUMENTS, **overrides})])


class RecordingCreate:
    """Captures the request kwargs and replays a scripted response."""

    def __init__(self, *responses: FakeMessage) -> None:
        self._responses = list(responses) or [tool_response()]
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, **kwargs: Any) -> FakeMessage:
        self.calls.append(kwargs)
        index = min(len(self.calls) - 1, len(self._responses) - 1)
        return self._responses[index]
