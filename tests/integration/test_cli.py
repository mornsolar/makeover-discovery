"""The ``makeover discover`` command."""

from __future__ import annotations

import pytest

from makeover_discovery.application.use_cases.discover_businesses import DiscoverBusinesses
from makeover_discovery.domain.errors import UpstreamError
from makeover_discovery.domain.model.discovery import DiscoveryQuery
from makeover_discovery.domain.model.pipeline import PipelineOutcome, PipelineResult
from makeover_discovery.interfaces.cli import main as cli
from tests.fakes.candidates import make_candidate
from tests.fakes.directory import FakeBusinessDirectory
from tests.fakes.geocoder import FailingGeocoder, FakeGeocoder
from tests.fakes.render_client import make_render_job
from tests.fakes.specs import make_scene_spec


@pytest.fixture
def stub_use_case(monkeypatch):
    """Swap the composed use case, leaving argument parsing and output real."""

    def install(use_case: DiscoverBusinesses) -> None:
        monkeypatch.setattr(cli, "create_shared_resources", lambda settings: _NoResources())
        monkeypatch.setattr(
            cli, "build_discover_businesses", lambda settings, resources, clock: use_case
        )

    return install


class _NoResources:
    async def aclose(self) -> None:
        return None


def test_prints_each_business_found(stub_use_case, capsys):
    directory = FakeBusinessDirectory((make_candidate(address_line="Jalan Ampang"),))
    stub_use_case(DiscoverBusinesses(FakeGeocoder(), directory))

    exit_code = cli.main(["discover", "50450", "--country", "MY"])

    output = capsys.readouterr().out
    assert exit_code == cli.EXIT_OK
    assert "Kedai Kopi Ali" in output
    assert "Jalan Ampang" in output


def test_prints_the_attribution_the_licence_requires(stub_use_case, capsys):
    stub_use_case(DiscoverBusinesses(FakeGeocoder(), FakeBusinessDirectory((make_candidate(),))))

    cli.main(["discover", "50450"])

    assert "© OpenStreetMap contributors" in capsys.readouterr().out


def test_defaults_to_malaysia(stub_use_case):
    geocoder = FakeGeocoder()
    stub_use_case(DiscoverBusinesses(geocoder, FakeBusinessDirectory()))

    cli.main(["discover", "50450"])

    assert geocoder.calls[0].country == "MY"


def test_exits_with_a_usage_code_for_a_malformed_postcode(stub_use_case, capsys):
    stub_use_case(DiscoverBusinesses(FakeGeocoder(), FakeBusinessDirectory()))

    exit_code = cli.main(["discover", "5045"])

    assert exit_code == cli.EXIT_USAGE
    assert "invalid input" in capsys.readouterr().err


def test_exits_with_a_not_found_code_for_an_unlocatable_postcode(stub_use_case):
    stub_use_case(DiscoverBusinesses(FakeGeocoder(), FakeBusinessDirectory()))

    assert cli.main(["discover", "99999"]) == cli.EXIT_NOT_FOUND


def test_exits_with_an_upstream_code_when_a_provider_fails(stub_use_case, capsys):
    stub_use_case(DiscoverBusinesses(FailingGeocoder(), FakeBusinessDirectory()))

    exit_code = cli.main(["discover", "50450"])

    assert exit_code == cli.EXIT_UPSTREAM
    assert "upstream failure" in capsys.readouterr().err


def test_rejects_an_unknown_category():
    with pytest.raises(SystemExit):
        cli.main(["discover", "50450", "--category", "nightclub"])


def test_closes_the_connection_pool_even_when_discovery_fails(stub_use_case, monkeypatch):
    # A leaked httpx pool makes the process hang on exit instead of failing
    # visibly, which is a miserable thing to debug from a cron log.
    closed: list[bool] = []

    class _Recording(_NoResources):
        async def aclose(self) -> None:
            closed.append(True)

    monkeypatch.setattr(cli, "create_shared_resources", lambda settings: _Recording())
    monkeypatch.setattr(
        cli,
        "build_discover_businesses",
        lambda settings, resources, clock: _Exploding(),
    )

    exit_code = cli.main(["discover", "50450"])

    assert exit_code == cli.EXIT_UPSTREAM
    assert closed == [True]


class _Exploding:
    async def execute(self, query) -> None:
        raise UpstreamError("boom")


def test_enrich_prints_a_profile_per_business(stub_use_case, monkeypatch, capsys):
    from makeover_discovery.application.use_cases.enrich_business_profile import (
        EnrichBusinessProfile,
    )
    from makeover_discovery.domain.model.web import ExtractedContent
    from makeover_discovery.domain.policy.redaction import RedactionPolicy
    from makeover_discovery.domain.policy.retention import RetentionPolicy
    from tests.fakes.clock import FixedClock
    from tests.fakes.web import FakeExtractor, FakeWebFetcher, make_page

    stub_use_case(DiscoverBusinesses(FakeGeocoder(), FakeBusinessDirectory((make_candidate(),))))
    monkeypatch.setattr(
        cli,
        "build_enrich_business_profile",
        lambda settings, resources, clock: EnrichBusinessProfile(
            fetcher=FakeWebFetcher(make_page()),
            extractor=FakeExtractor(ExtractedContent(descriptors=("halal",))),
            clock=FixedClock(),
            retention=RetentionPolicy(),
            redaction=RedactionPolicy(),
        ),
    )

    exit_code = cli.main(["enrich", "50450", "--limit", "1"])

    output = capsys.readouterr().out
    assert exit_code == cli.EXIT_OK
    assert "Kedai Kopi Ali" in output
    assert "not_listed" in output
    assert "© OpenStreetMap contributors" in output


class _ScriptedPipeline:
    def __init__(self, results: tuple[PipelineResult, ...]) -> None:
        self._results = results

    async def execute(self, query: DiscoveryQuery) -> tuple[PipelineResult, ...]:
        return self._results


def test_pipeline_prints_a_rendered_businesss_artifacts(monkeypatch, capsys):
    from tests.fakes.brief import make_profile

    profile = make_profile()
    spec = make_scene_spec()
    job = make_render_job(spec, job_id="job-1")
    monkeypatch.setattr(cli, "create_shared_resources", lambda settings: _NoResources())
    monkeypatch.setattr(
        cli,
        "build_run_makeover_pipeline",
        lambda settings, resources, clock: _ScriptedPipeline(
            (
                PipelineResult(
                    business=profile,
                    outcome=PipelineOutcome.RENDERED,
                    scene_spec=spec,
                    render_job=job,
                ),
            )
        ),
    )

    exit_code = cli.main(["pipeline", "50450", "--limit", "1"])

    output = capsys.readouterr().out
    assert exit_code == cli.EXIT_OK
    assert "Kedai Kopi Ali" in output
    assert job.artifacts is not None
    assert job.artifacts.video.uri in output


def test_pipeline_exits_with_render_failed_when_any_business_did_not_render(monkeypatch, capsys):
    from tests.fakes.brief import make_profile

    profile = make_profile()
    monkeypatch.setattr(cli, "create_shared_resources", lambda settings: _NoResources())
    monkeypatch.setattr(
        cli,
        "build_run_makeover_pipeline",
        lambda settings, resources, clock: _ScriptedPipeline(
            (
                PipelineResult(
                    business=profile,
                    outcome=PipelineOutcome.BRIEF_FAILED,
                    error="the model could not produce a usable brief",
                ),
            )
        ),
    )

    exit_code = cli.main(["pipeline", "50450", "--limit", "1"])

    output = capsys.readouterr().out
    assert exit_code == cli.EXIT_RENDER_FAILED
    assert "brief_failed" in output
    assert "the model could not produce a usable brief" in output
