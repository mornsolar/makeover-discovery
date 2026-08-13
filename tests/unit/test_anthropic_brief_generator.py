"""The Anthropic adapter, driven entirely by a fake Messages API."""

from __future__ import annotations

import pytest

from makeover_discovery.domain.errors import UpstreamError
from makeover_discovery.domain.model.brief import BriefRequest
from makeover_discovery.infrastructure.llm.anthropic_brief_generator import (
    AnthropicBriefGenerator,
)
from makeover_discovery.infrastructure.llm.prompts.brief_v1 import PROMPT_VERSION, TOOL_NAME
from tests.fakes.anthropic import (
    FakeMessage,
    FakeText,
    FakeToolUse,
    FakeUsage,
    RecordingCreate,
    tool_response,
)
from tests.fakes.brief import VOCABULARY, make_profile
from tests.fakes.clock import FixedClock

MODEL = "claude-opus-5"
REQUEST = BriefRequest(profile=make_profile(), vocabulary=VOCABULARY, seed=42)


def build(create: RecordingCreate) -> AnthropicBriefGenerator:
    return AnthropicBriefGenerator(
        create,
        FixedClock(),
        model=MODEL,
        max_tokens=4_096,
        effort="high",
    )


async def generate(create: RecordingCreate):
    return await build(create).generate(REQUEST)


async def test_forces_the_brief_tool():
    # Without a forced tool the model may answer in prose, which is unusable.
    create = RecordingCreate()

    await generate(create)

    assert create.calls[0]["tool_choice"] == {"type": "tool", "name": TOOL_NAME}


async def test_declares_the_tool_as_strict():
    create = RecordingCreate()

    await generate(create)

    assert create.calls[0]["tools"][0]["strict"] is True


async def test_offers_only_the_renderer_vocabulary_in_the_schema():
    create = RecordingCreate()

    await generate(create)

    schema = create.calls[0]["tools"][0]["input_schema"]["properties"]
    assert schema["camera_move"]["enum"] == list(VOCABULARY.camera_moves)
    assert schema["material_families"]["items"]["enum"] == list(VOCABULARY.material_families)


async def test_asks_for_the_configured_model_and_effort():
    create = RecordingCreate()

    await generate(create)

    assert create.calls[0]["model"] == MODEL
    assert create.calls[0]["output_config"] == {"effort": "high"}


async def test_puts_the_business_in_the_user_message():
    create = RecordingCreate()

    await generate(create)

    assert "Kedai Kopi Ali" in create.calls[0]["messages"][0]["content"]


async def test_feeds_previous_problems_back_for_repair():
    create = RecordingCreate()
    request = BriefRequest(
        profile=make_profile(),
        vocabulary=VOCABULARY,
        seed=1,
        problems=("unknown camera move 'barrel_roll'",),
    )

    await build(create).generate(request)

    assert "barrel_roll" in create.calls[0]["messages"][0]["content"]


async def test_builds_the_brief_from_the_tool_arguments():
    generated = await generate(RecordingCreate())

    assert generated.brief.signage.text == "Kedai Kopi Ali"
    assert generated.brief.camera_move == "orbit"


async def test_records_the_model_prompt_version_and_seed():
    # A brief whose output shifts months from now has to be attributable to a
    # model change or a prompt change; without this it is neither.
    generated = await generate(RecordingCreate())

    assert generated.brief.generation.model == MODEL
    assert generated.brief.generation.prompt_version == PROMPT_VERSION
    assert generated.brief.generation.seed == REQUEST.seed


async def test_normalises_palette_casing():
    generated = await generate(RecordingCreate())

    assert generated.brief.palette[0] == "#1B4D3E"


async def test_reports_token_usage():
    create = RecordingCreate(
        FakeMessage(
            content=[FakeToolUse(input=tool_response().content[0].input)],
            usage=FakeUsage(
                input_tokens=1_200,
                output_tokens=300,
                cache_read_input_tokens=800,
                cache_creation_input_tokens=None,
            ),
        )
    )

    generated = await generate(create)

    assert generated.usage.input_tokens == 1_200
    assert generated.usage.cache_read_input_tokens == 800
    # Absent rather than zero is normal when nothing was cached.
    assert generated.usage.cache_write_input_tokens == 0


async def test_finds_the_tool_call_among_other_blocks():
    create = RecordingCreate(FakeMessage(content=[FakeText(), *tool_response().content]))

    assert (await generate(create)).brief.camera_move == "orbit"


async def test_rejects_a_response_with_no_tool_call():
    create = RecordingCreate(FakeMessage(content=[FakeText()]))

    with pytest.raises(UpstreamError, match=TOOL_NAME):
        await generate(create)


async def test_reports_a_refusal_rather_than_an_empty_brief():
    create = RecordingCreate(FakeMessage(content=[], stop_reason="refusal"))

    with pytest.raises(UpstreamError, match="declined"):
        await generate(create)


async def test_reports_a_truncated_response():
    create = RecordingCreate(FakeMessage(content=[], stop_reason="max_tokens"))

    with pytest.raises(UpstreamError, match="token output limit"):
        await generate(create)


async def test_reports_a_brief_that_fails_the_contract():
    # The tool schema cannot express hex-colour patterns, so this is the only
    # place a malformed palette can be caught.
    create = RecordingCreate(tool_response(palette=["chartreuse", "#FFFFFF"]))

    with pytest.raises(UpstreamError, match="fails the contract"):
        await generate(create)


async def test_reports_a_missing_field():
    create = RecordingCreate(FakeMessage(content=[FakeToolUse(input={"palette": []})]))

    with pytest.raises(UpstreamError, match="style_direction"):
        await generate(create)


async def test_reports_a_field_of_the_wrong_shape():
    create = RecordingCreate(tool_response(material_families="timber"))

    with pytest.raises(UpstreamError, match="material_families"):
        await generate(create)
