"""``RunMakeoverPipeline``'s own orchestration: batching, failure isolation,
and the poll-until-terminal loop - against scripted steps, not real adapters."""

from __future__ import annotations

from dataclasses import dataclass

from makeover_contracts.business import BusinessCandidate, BusinessProfile
from makeover_contracts.capability import CapabilityManifest
from makeover_contracts.geo import CircleArea, GeoPoint, Postcode
from makeover_contracts.jobs import JobStatus, RenderJob

from makeover_discovery.application.use_cases.compose_scene_spec import ComposeSceneSpec
from makeover_discovery.application.use_cases.enrich_business_profile import (
    EnrichmentResult,
    WebsiteOutcome,
)
from makeover_discovery.application.use_cases.run_makeover_pipeline import RunMakeoverPipeline
from makeover_discovery.domain.errors import UpstreamError
from makeover_discovery.domain.model.brief import BriefResult
from makeover_discovery.domain.model.discovery import DiscoveryQuery, DiscoveryResult
from makeover_discovery.domain.model.llm import TokenUsage
from makeover_discovery.domain.model.pipeline import PipelineOutcome
from makeover_discovery.infrastructure.capabilities.static_manifest import BUILTIN_MANIFEST
from tests.fakes.brief import make_brief, make_profile
from tests.fakes.candidates import make_candidate
from tests.fakes.render_client import FakeRenderClient, make_render_job

POSTCODE = Postcode(value="50450", country="MY")
DUMMY_AREA = CircleArea(center=GeoPoint(lat=3.16, lon=101.71), radius_m=1_000.0)
COMPOSE = ComposeSceneSpec()


class ScriptedDiscovery:
    def __init__(self, candidates: tuple[BusinessCandidate, ...]) -> None:
        self._candidates = candidates

    async def execute(self, query: DiscoveryQuery) -> DiscoveryResult:
        return DiscoveryResult(
            postcode=query.postcode, area=DUMMY_AREA, candidates=self._candidates
        )


class ScriptedEnrichment:
    """Turns a candidate straight into a profile - id derivation is
    ``EnrichBusinessProfile``'s own concern, already covered by its tests."""

    async def execute(self, candidate: BusinessCandidate) -> EnrichmentResult:
        profile = make_profile(business_id=candidate.external_id, name=candidate.name)
        return EnrichmentResult(profile=profile, website_outcome=WebsiteOutcome.NOT_LISTED)


class ScriptedBrief:
    def __init__(self, by_business_id: dict[str, BriefResult]) -> None:
        self._by_business_id = by_business_id

    async def execute(self, profile: BusinessProfile) -> BriefResult:
        result = self._by_business_id.get(profile.id)
        if result is None:
            raise UpstreamError(f"no brief scripted for {profile.id}")
        return result


@dataclass
class CountingCapabilitySource:
    manifest_value: CapabilityManifest
    calls: int = 0

    async def manifest(self) -> CapabilityManifest:
        self.calls += 1
        return self.manifest_value


async def _no_sleep(_seconds: float) -> None:
    """A ``sleep`` that consumes no real time, so timeout tests stay instant."""


def _business(business_id: str, name: str) -> tuple[BusinessCandidate, BriefResult, RenderJob]:
    """One consistent business: the same profile ``ScriptedEnrichment`` would
    derive, a matching brief, and the exact ``RenderJob`` a successful poll
    would return for the spec ``ComposeSceneSpec`` would actually produce."""
    candidate = make_candidate(external_id=business_id, name=name)
    profile = make_profile(business_id=business_id, name=name)
    brief = make_brief(profile)
    brief_result = BriefResult(brief=brief, usage=TokenUsage(), cost_usd=0.0, attempts=1)
    spec = COMPOSE.execute(profile, brief, BUILTIN_MANIFEST)
    return candidate, brief_result, make_render_job(spec, job_id=f"job-{business_id}")


def build(
    candidates: tuple[BusinessCandidate, ...],
    briefs: dict[str, BriefResult],
    *,
    render_client: FakeRenderClient,
    capabilities: CountingCapabilitySource | None = None,
) -> RunMakeoverPipeline:
    return RunMakeoverPipeline(
        discover=ScriptedDiscovery(candidates),
        enrich=ScriptedEnrichment(),
        brief=ScriptedBrief(briefs),
        compose=COMPOSE,
        capabilities=capabilities or CountingCapabilitySource(BUILTIN_MANIFEST),
        render=render_client,
        poll_interval_s=0.0,
        poll_timeout_s=0.05,
        sleep=_no_sleep,
    )


async def test_a_batch_of_candidates_all_render_successfully():
    candidate_a, brief_a, job_a = _business("biz-a", "Shop A")
    candidate_b, brief_b, job_b = _business("biz-b", "Shop B")
    render_client = FakeRenderClient(poll_sequence=[job_a, job_b])

    pipeline = build(
        (candidate_a, candidate_b),
        {"biz-a": brief_a, "biz-b": brief_b},
        render_client=render_client,
    )

    results = await pipeline.execute(DiscoveryQuery(postcode=POSTCODE))

    assert [r.outcome for r in results] == [PipelineOutcome.RENDERED, PipelineOutcome.RENDERED]
    assert len(render_client.submitted) == 2


async def test_one_businesss_missing_brief_does_not_stop_the_batch():
    candidate_a, brief_a, job_a = _business("biz-a", "Shop A")
    candidate_b, _brief_b, _job_b = _business("biz-b", "Shop B")
    render_client = FakeRenderClient(poll_sequence=[job_a])

    # Only biz-a has a scripted brief; biz-b's brief step raises.
    pipeline = build((candidate_a, candidate_b), {"biz-a": brief_a}, render_client=render_client)

    results = await pipeline.execute(DiscoveryQuery(postcode=POSTCODE))

    outcomes = {result.business.id: result.outcome for result in results}
    assert outcomes["biz-a"] == PipelineOutcome.RENDERED
    assert outcomes["biz-b"] == PipelineOutcome.BRIEF_FAILED
    # Only the successful business ever reached the render client.
    assert len(render_client.submitted) == 1


async def test_a_render_that_never_terminates_times_out_as_render_failed():
    candidate, brief, job = _business("biz-a", "Shop A")
    running_job = job.model_copy(update={"status": JobStatus.RUNNING, "finished_at": None})
    render_client = FakeRenderClient(poll_sequence=[running_job])

    pipeline = build((candidate,), {"biz-a": brief}, render_client=render_client)

    results = await pipeline.execute(DiscoveryQuery(postcode=POSTCODE))

    assert results[0].outcome == PipelineOutcome.RENDER_FAILED
    assert results[0].error is not None and "did not finish" in results[0].error


async def test_the_manifest_is_fetched_once_for_the_whole_batch():
    candidate_a, brief_a, job_a = _business("biz-a", "Shop A")
    candidate_b, brief_b, job_b = _business("biz-b", "Shop B")
    render_client = FakeRenderClient(poll_sequence=[job_a, job_b])
    capabilities = CountingCapabilitySource(BUILTIN_MANIFEST)

    pipeline = build(
        (candidate_a, candidate_b),
        {"biz-a": brief_a, "biz-b": brief_b},
        render_client=render_client,
        capabilities=capabilities,
    )

    await pipeline.execute(DiscoveryQuery(postcode=POSTCODE))

    assert capabilities.calls == 1
