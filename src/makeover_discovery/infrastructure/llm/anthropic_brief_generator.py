"""Anthropic-backed design-brief generator.

Structured output is obtained by forcing a single tool call rather than by asking
for JSON in prose: the arguments are schema-validated by the API before they
reach us, so the failure mode "the model wrote an explanation instead of a
brief" cannot happen. The contract models still re-validate, because the schema
cannot express string lengths or hex-colour patterns.

No call is made anywhere in the test suite - the adapter takes the create
function as a dependency, and the suite passes a fake.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Final, Protocol

from makeover_contracts.brief import (
    BriefGeneration,
    DesignBrief,
    LightingMood,
    SignageBrief,
)
from pydantic import ValidationError

from makeover_discovery.application.ports.clock import Clock
from makeover_discovery.domain.errors import UpstreamError
from makeover_discovery.domain.model.brief import BriefRequest, GeneratedBrief
from makeover_discovery.domain.model.llm import TokenUsage
from makeover_discovery.infrastructure.llm.prompts.brief_v1 import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    TOOL_NAME,
    build_tool,
    build_user_message,
)

REFUSAL_STOP_REASON: Final = "refusal"
TRUNCATED_STOP_REASON: Final = "max_tokens"


class MessageCreator(Protocol):
    """The one Anthropic API call this adapter makes.

    Narrower than the SDK client on purpose: it is the entire seam the tests
    need, and it keeps the SDK's surface from leaking into the object graph.
    """

    async def __call__(self, **kwargs: Any) -> Any: ...


class AnthropicBriefGenerator:
    """Generates a ``DesignBrief`` with tool-forced structured output."""

    def __init__(
        self,
        create: MessageCreator,
        clock: Clock,
        *,
        model: str,
        max_tokens: int,
        effort: str,
    ) -> None:
        self._create = create
        self._clock = clock
        self._model = model
        self._max_tokens = max_tokens
        self._effort = effort

    async def generate(self, request: BriefRequest) -> GeneratedBrief:
        tool = build_tool(request)
        response = await self._create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_user_message(request)}],
            tools=[tool],
            # Forcing the tool is what makes the output structured; without it a
            # model that decides prose is more helpful produces nothing usable.
            tool_choice={"type": "tool", "name": TOOL_NAME},
            output_config={"effort": self._effort},
        )
        self._check_stop_reason(response)
        arguments = _tool_arguments(response)
        return GeneratedBrief(
            brief=self._to_brief(arguments, request),
            usage=_usage_of(response),
        )

    def _check_stop_reason(self, response: Any) -> None:
        stop_reason = getattr(response, "stop_reason", None)
        if stop_reason == REFUSAL_STOP_REASON:
            raise UpstreamError("the model declined to produce a brief for this business")
        if stop_reason == TRUNCATED_STOP_REASON:
            raise UpstreamError(
                f"the model hit the {self._max_tokens}-token output limit before "
                "completing the brief"
            )

    def _to_brief(self, arguments: dict[str, Any], request: BriefRequest) -> DesignBrief:
        try:
            return DesignBrief(
                business_id=request.profile.id,
                style_direction=_text(arguments, "style_direction"),
                palette=_palette(arguments),
                material_families=tuple(_strings(arguments, "material_families")),
                signage=SignageBrief(
                    text=_text(arguments, "signage_text"),
                    tone=_text(arguments, "signage_tone"),
                ),
                lighting_mood=LightingMood(_text(arguments, "lighting_mood")),
                camera_move=_text(arguments, "camera_move"),
                rationale=_text(arguments, "rationale"),
                do_not_include=tuple(_strings(arguments, "do_not_include")),
                generation=BriefGeneration(
                    model=self._model,
                    prompt_version=PROMPT_VERSION,
                    seed=request.seed,
                    generated_at=self._clock.now(),
                ),
            )
        except (ValidationError, ValueError) as exc:
            # The tool schema cannot express lengths or colour patterns, so this
            # is where those violations land. Reported, never silently patched.
            raise UpstreamError(
                f"the model returned a brief that fails the contract: {exc}"
            ) from exc


def _tool_arguments(response: Any) -> dict[str, Any]:
    content = getattr(response, "content", None)
    blocks: Sequence[Any] = content if isinstance(content, Sequence) else ()
    for block in blocks:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == TOOL_NAME:
            arguments = getattr(block, "input", None)
            if isinstance(arguments, dict):
                return arguments
    raise UpstreamError(f"the model returned no {TOOL_NAME} call")


def _usage_of(response: Any) -> TokenUsage:
    usage = getattr(response, "usage", None)
    return TokenUsage(
        input_tokens=_count(usage, "input_tokens"),
        output_tokens=_count(usage, "output_tokens"),
        cache_read_input_tokens=_count(usage, "cache_read_input_tokens"),
        cache_write_input_tokens=_count(usage, "cache_creation_input_tokens"),
    )


def _count(usage: Any, name: str) -> int:
    value = getattr(usage, name, None)
    # Absent rather than zero is normal: the cache fields are omitted entirely
    # when nothing was cached, and an unusable value must not corrupt the total.
    return value if isinstance(value, int) and value >= 0 else 0


def _text(arguments: dict[str, Any], key: str) -> str:
    value = arguments.get(key)
    if not isinstance(value, str):
        raise UpstreamError(f"the model omitted the {key!r} field")
    return value.strip()


def _strings(arguments: dict[str, Any], key: str) -> tuple[str, ...]:
    value = arguments.get(key)
    if not isinstance(value, list):
        raise UpstreamError(f"the model omitted the {key!r} field")
    return tuple(item.strip() for item in value if isinstance(item, str) and item.strip())


def _palette(arguments: dict[str, Any]) -> tuple[str, ...]:
    # Casing is cosmetic and the model is inconsistent about it; normalising here
    # keeps the same brief from rendering as two different cache entries later.
    return tuple(colour.upper() for colour in _strings(arguments, "palette"))
