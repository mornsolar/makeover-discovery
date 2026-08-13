"""The ``makeover brief`` command."""

from __future__ import annotations

import pytest

from makeover_discovery.application.use_cases.discover_businesses import DiscoverBusinesses
from makeover_discovery.application.use_cases.enrich_business_profile import (
    EnrichBusinessProfile,
)
from makeover_discovery.application.use_cases.generate_design_brief import GenerateDesignBrief
from makeover_discovery.domain.errors import ConfigurationError
from makeover_discovery.domain.policy.redaction import RedactionPolicy
from makeover_discovery.domain.policy.retention import RetentionPolicy
from makeover_discovery.infrastructure.llm.pricing import DEFAULT_MODEL, pricing_for
from makeover_discovery.interfaces.cli import main as cli
from tests.fakes.brief import FakeBriefGenerator, FakeCapabilitySource
from tests.fakes.candidates import make_candidate
from tests.fakes.clock import FixedClock
from tests.fakes.directory import FakeBusinessDirectory
from tests.fakes.geocoder import FakeGeocoder
from tests.fakes.web import FakeExtractor, FakeWebFetcher, make_page


class _NoResources:
    async def aclose(self) -> None:
        return None


def enricher() -> EnrichBusinessProfile:
    return EnrichBusinessProfile(
        fetcher=FakeWebFetcher(make_page()),
        extractor=FakeExtractor(None),
        clock=FixedClock(),
        retention=RetentionPolicy(),
        redaction=RedactionPolicy(),
    )


@pytest.fixture
def stub_pipeline(monkeypatch):
    """Swap the composed use cases, leaving parsing and rendering real."""

    def install(build_brief=None) -> None:
        monkeypatch.setattr(cli, "create_shared_resources", lambda settings: _NoResources())
        monkeypatch.setattr(
            cli,
            "build_discover_businesses",
            lambda settings, resources, clock: DiscoverBusinesses(
                FakeGeocoder(), FakeBusinessDirectory((make_candidate(),))
            ),
        )
        monkeypatch.setattr(
            cli, "build_enrich_business_profile", lambda settings, resources, clock: enricher()
        )
        monkeypatch.setattr(
            cli,
            "build_generate_design_brief",
            build_brief
            or (
                lambda settings, resources, clock: GenerateDesignBrief(
                    generator=FakeBriefGenerator(),
                    capabilities=FakeCapabilitySource(),
                    pricing=pricing_for(DEFAULT_MODEL),
                )
            ),
        )

    return install


def test_prints_the_art_direction(stub_pipeline, capsys):
    stub_pipeline()

    exit_code = cli.main(["brief", "50450", "--country", "MY"])

    output = capsys.readouterr().out
    assert exit_code == cli.EXIT_OK
    assert "palette" in output
    assert "#1B4D3E" in output


def test_prints_what_the_brief_cost(stub_pipeline, capsys):
    stub_pipeline()

    cli.main(["brief", "50450"])

    assert "cost" in capsys.readouterr().out


def test_prints_the_prompt_version_behind_the_output(stub_pipeline, capsys):
    stub_pipeline()

    cli.main(["brief", "50450"])

    assert "brief-v1" in capsys.readouterr().out


def test_explains_a_missing_api_key_rather_than_crashing(stub_pipeline, capsys):
    def refuse(settings, resources, clock) -> GenerateDesignBrief:
        raise ConfigurationError("MAKEOVER_ANTHROPIC_API_KEY must be set")

    stub_pipeline(refuse)

    exit_code = cli.main(["brief", "50450"])

    assert exit_code == cli.EXIT_CONFIG
    assert "MAKEOVER_ANTHROPIC_API_KEY" in capsys.readouterr().err
