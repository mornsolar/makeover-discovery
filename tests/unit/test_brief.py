from __future__ import annotations

from datetime import UTC, datetime

import pytest
from makeover_contracts.brief import (
    BriefGeneration,
    DesignBrief,
    LightingMood,
    SignageBrief,
)
from pydantic import ValidationError

GENERATION = BriefGeneration(
    model="claude-opus-5",
    prompt_version="brief-v1",
    seed=42,
    generated_at=datetime(2026, 8, 13, 9, 0, tzinfo=UTC),
)


def make_brief(**overrides) -> DesignBrief:
    defaults = {
        "business_id": "kedai-kopi-50450",
        "style_direction": "Warm tropical modernism with rattan and aged brass accents.",
        "palette": ("#1B4D3E", "#E8D6B3"),
        "material_families": ("timber", "brass"),
        "signage": SignageBrief(text="KEDAI KOPI", tone="confident, hand-lettered"),
        "lighting_mood": LightingMood.WARM_EVENING,
        "camera_move": "orbit",
        "rationale": "Rattan and brass echo the shophouse vernacular of the district.",
        "generation": GENERATION,
    }
    return DesignBrief(**{**defaults, **overrides})


class TestSignageBrief:
    @pytest.mark.parametrize(
        "text", ["visit https://evil.example", "WWW.example.com", "http://a.b"]
    )
    def test_rejects_signage_containing_a_url(self, text):
        # Signage is set in 3D type; a URL is both wrong for the medium and a
        # route for injected content to reach a rendered surface.
        with pytest.raises(ValidationError, match="must not contain a URL"):
            SignageBrief(text=text, tone="neutral")

    def test_accepts_ordinary_signage(self):
        assert SignageBrief(text="KEDAI KOPI", tone="warm").text == "KEDAI KOPI"

    def test_rejects_signage_longer_than_the_sign(self):
        with pytest.raises(ValidationError):
            SignageBrief(text="X" * 41, tone="warm")


class TestBriefGeneration:
    def test_requires_timezone_aware_generation_time(self):
        with pytest.raises(ValidationError, match="timezone-aware"):
            BriefGeneration(
                model="claude-opus-5",
                prompt_version="brief-v1",
                seed=1,
                generated_at=datetime(2026, 8, 13, 9, 0),
            )


class TestDesignBrief:
    def test_records_the_contract_version_it_was_built_against(self):
        assert make_brief().contract_version == "0.1.0"

    def test_rejects_a_single_colour_palette(self):
        with pytest.raises(ValidationError):
            make_brief(palette=("#1B4D3E",))

    def test_rejects_a_malformed_hex_colour(self):
        with pytest.raises(ValidationError):
            make_brief(palette=("#1B4D3E", "not-a-colour"))

    def test_carries_prohibitions_forward_to_the_renderer(self):
        brief = make_brief(do_not_include=("real brand logos", "trademarked marks"))
        assert "real brand logos" in brief.do_not_include

    def test_is_immutable(self):
        with pytest.raises(ValidationError):
            make_brief().camera_move = "pan"
