"""Prompt version ``brief-v1``.

Versioned and stored beside the adapter because every generated brief records
which prompt produced it: without that, a change in output months from now is
indistinguishable from a change in the model.

The tool schema is built per request rather than declared as a constant - the
allowed materials, camera moves, and moods come from the renderer's live
manifest, so the vocabulary is enforced by the schema, not by the wording.
"""

from __future__ import annotations

from typing import Any, Final

from makeover_contracts.brief import (
    MAX_PALETTE_COLORS,
    MAX_SIGNAGE_CHARS,
    MIN_PALETTE_COLORS,
)
from makeover_contracts.business import BusinessProfile

from makeover_discovery.domain.model.brief import MANDATORY_EXCLUSIONS, BriefRequest

PROMPT_VERSION: Final = "brief-v1"
TOOL_NAME: Final = "submit_design_brief"

SYSTEM_PROMPT: Final = f"""\
You are an architectural set designer producing art direction for a speculative \
3D visualisation of a real shopfront. The result is an AI-generated concept, not \
an architectural proposal, and it will be published with that disclosure.

Hard rules:
- Never reproduce or describe a real logo, wordmark, or brand mark.
- Never assert a fact about the business - no founding year, no awards, no \
ratings, no claims about its food, service, or history. You know only what is \
in the profile, and even that is third-party data.
- Signage is set in 3D type: at most {MAX_SIGNAGE_CHARS} characters, no URLs, \
no phone numbers, no personal names.
- Choose only from the material families, camera moves, and lighting moods the \
tool schema offers. They are what the renderer can actually build.
- Work from the business category and its public descriptors. Where the profile \
is thin, design for the category rather than inventing detail.

Call the {TOOL_NAME} tool exactly once. Do not reply with prose.\
"""


def build_user_message(request: BriefRequest) -> str:
    """The per-business half of the prompt, including any repair feedback."""
    sections = [
        "Design a storefront makeover for this business.",
        "",
        _profile_block(request.profile),
    ]
    if request.problems:
        # Feeding back every problem at once is why validation returns a list:
        # one repair round should be able to fix all of them.
        sections.extend(
            [
                "",
                "Your previous brief was rejected. Fix all of the following:",
                *(f"- {problem}" for problem in request.problems),
            ]
        )
    return "\n".join(sections)


def _profile_block(profile: BusinessProfile) -> str:
    lines = [
        f"name: {profile.name.value}",
        f"category: {profile.category.value}",
    ]
    if profile.address_line is not None:
        lines.append(f"address: {profile.address_line.value}")
    if profile.descriptors:
        lines.append("descriptors: " + ", ".join(d.value for d in profile.descriptors))
    return "\n".join(lines)


def build_tool(request: BriefRequest) -> dict[str, Any]:
    """The forced-output tool, with the renderer's vocabulary baked into it.

    ``strict`` makes the API guarantee the arguments validate against this
    schema, which removes a whole class of parsing failure. The schema keeps to
    types and enums only - string length and hex-colour patterns are not
    enforceable here, so the contract models re-check them on the way in.
    """
    vocabulary = request.vocabulary
    return {
        "name": TOOL_NAME,
        "description": "Submit the finished design brief for this storefront.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "style_direction": {
                    "type": "string",
                    "description": (
                        "One or two sentences of art direction: the look, era, and mood "
                        "of the makeover. 10-400 characters."
                    ),
                },
                "palette": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        f"{MIN_PALETTE_COLORS}-{MAX_PALETTE_COLORS} sRGB colours as "
                        "uppercase hex strings such as '#1B4D3E'."
                    ),
                },
                "material_families": {
                    "type": "array",
                    "items": {"type": "string", "enum": list(vocabulary.material_families)},
                    "description": "1-6 material families the renderer ships.",
                },
                "signage_text": {
                    "type": "string",
                    "description": (
                        f"What the sign reads. At most {MAX_SIGNAGE_CHARS} characters. "
                        "Usually the business name; never a URL or a person's name."
                    ),
                },
                "signage_tone": {
                    "type": "string",
                    "description": "How the signage should feel, e.g. 'hand-painted, warm'.",
                },
                "lighting_mood": {
                    "type": "string",
                    "enum": [mood.value for mood in vocabulary.lighting_moods],
                },
                "camera_move": {
                    "type": "string",
                    "enum": list(vocabulary.camera_moves),
                },
                "rationale": {
                    "type": "string",
                    "description": (
                        "Why this direction suits the category and descriptors. "
                        "10-1000 characters. Describe design intent only - assert no facts."
                    ),
                },
                "do_not_include": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Things the render must avoid. These are always added and need "
                        f"not be repeated: {'; '.join(MANDATORY_EXCLUSIONS)}."
                    ),
                },
            },
            "required": [
                "style_direction",
                "palette",
                "material_families",
                "signage_text",
                "signage_tone",
                "lighting_mood",
                "camera_move",
                "rationale",
                "do_not_include",
            ],
        },
    }
