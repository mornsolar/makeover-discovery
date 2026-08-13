"""The versioned brief prompt."""

from __future__ import annotations

from makeover_discovery.domain.model.brief import BriefRequest
from makeover_discovery.infrastructure.llm.prompts.brief_v1 import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_tool,
    build_user_message,
)
from tests.fakes.brief import VOCABULARY, make_profile


def request_for(profile=None, problems=()) -> BriefRequest:
    return BriefRequest(
        profile=profile or make_profile(),
        vocabulary=VOCABULARY,
        seed=1,
        problems=problems,
    )


def test_the_version_is_recorded_on_every_brief():
    # Output that drifts must be attributable to a prompt change or a model
    # change; an unversioned prompt makes those indistinguishable.
    assert PROMPT_VERSION == "brief-v1"


def test_the_system_prompt_forbids_brand_marks_and_invented_facts():
    assert "logo" in SYSTEM_PROMPT
    assert "Never assert a fact" in SYSTEM_PROMPT


def test_includes_the_business_descriptors():
    assert "halal" in build_user_message(request_for())


def test_includes_the_address_when_the_profile_has_one():
    profile = make_profile()
    with_address = profile.model_copy(update={"address_line": profile.name})

    assert "Kedai Kopi Ali" in build_user_message(request_for(with_address))


def test_omits_descriptors_when_the_profile_has_none():
    bare = make_profile(descriptors=())

    assert "descriptors" not in build_user_message(request_for(bare))


def test_carries_repair_feedback_into_the_next_attempt():
    message = build_user_message(request_for(problems=("unknown camera move 'barrel_roll'",)))

    assert "was rejected" in message
    assert "barrel_roll" in message


def test_the_tool_requires_every_brief_field():
    schema = build_tool(request_for())["input_schema"]

    assert set(schema["required"]) == set(schema["properties"])
    assert schema["additionalProperties"] is False
