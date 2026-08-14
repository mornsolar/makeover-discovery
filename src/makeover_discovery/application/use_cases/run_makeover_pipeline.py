"""Runs the full pipeline for a batch of businesses.

Discover -> enrich -> brief -> compose a scene -> submit it to Repo B -> wait
for the render. One business's failure must not discard the batch's other
results, so this is the one use case in the repo that owns partial-failure
handling itself rather than raising past its own boundary.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Final, Protocol

from makeover_contracts.brief import DesignBrief
from makeover_contracts.business import BusinessCandidate, BusinessProfile
from makeover_contracts.capability import CapabilityManifest
from makeover_contracts.jobs import JobStatus, RenderJob
from makeover_contracts.scene import SceneSpec

from makeover_discovery.application.ports.capability_source import CapabilitySource
from makeover_discovery.application.ports.render_client import RenderClient
from makeover_discovery.application.use_cases.enrich_business_profile import EnrichmentResult
from makeover_discovery.domain.errors import UpstreamError
from makeover_discovery.domain.model.brief import BriefResult
from makeover_discovery.domain.model.discovery import DiscoveryQuery, DiscoveryResult
from makeover_discovery.domain.model.pipeline import PipelineOutcome, PipelineResult

DEFAULT_POLL_INTERVAL_S: Final = 3.0
DEFAULT_POLL_TIMEOUT_S: Final = 300.0


class DiscoveryStep(Protocol):
    """What ``RunMakeoverPipeline`` needs from ``DiscoverBusinesses``.

    A Protocol rather than the concrete use case so a test can inject a
    lightweight double instead of wiring a real geocoder and directory just to
    exercise this use case's own batching and failure-isolation logic.
    """

    async def execute(self, query: DiscoveryQuery) -> DiscoveryResult: ...


class EnrichmentStep(Protocol):
    async def execute(self, candidate: BusinessCandidate) -> EnrichmentResult: ...


class BriefStep(Protocol):
    async def execute(self, profile: BusinessProfile) -> BriefResult: ...


class ComposeStep(Protocol):
    def execute(
        self, business: BusinessProfile, brief: DesignBrief, manifest: CapabilityManifest
    ) -> SceneSpec: ...


class RunMakeoverPipeline:
    def __init__(
        self,
        discover: DiscoveryStep,
        enrich: EnrichmentStep,
        brief: BriefStep,
        compose: ComposeStep,
        capabilities: CapabilitySource,
        render: RenderClient,
        *,
        poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
        poll_timeout_s: float = DEFAULT_POLL_TIMEOUT_S,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._discover = discover
        self._enrich = enrich
        self._brief = brief
        self._compose = compose
        self._capabilities = capabilities
        self._render = render
        self._poll_interval_s = poll_interval_s
        self._poll_timeout_s = poll_timeout_s
        self._sleep = sleep

    async def execute(self, query: DiscoveryQuery) -> tuple[PipelineResult, ...]:
        discovery = await self._discover.execute(query)
        # Fetched once and reused for every business in the batch: the
        # renderer's vocabulary does not change mid-run, and re-fetching per
        # business would be a wasted round trip each time.
        manifest = await self._capabilities.manifest()
        results = [await self._run_one(candidate, manifest) for candidate in discovery.candidates]
        return tuple(results)

    async def _run_one(
        self,
        candidate: BusinessCandidate,
        manifest: CapabilityManifest,
    ) -> PipelineResult:
        enrichment = await self._enrich.execute(candidate)
        business = enrichment.profile

        try:
            brief_result = await self._brief.execute(business)
        except UpstreamError as exc:
            return PipelineResult(
                business=business, outcome=PipelineOutcome.BRIEF_FAILED, error=str(exc)
            )
        brief = brief_result.brief

        try:
            spec = self._compose.execute(business, brief, manifest)
            job = await self._render.submit(spec)
            job = await self._poll_until_terminal(job.id)
        except UpstreamError as exc:
            return PipelineResult(
                business=business,
                outcome=PipelineOutcome.RENDER_FAILED,
                brief=brief,
                error=str(exc),
            )

        if job.status is not JobStatus.SUCCEEDED:
            return PipelineResult(
                business=business,
                outcome=PipelineOutcome.RENDER_FAILED,
                brief=brief,
                scene_spec=job.spec,
                render_job=job,
                error=job.error,
            )

        return PipelineResult(
            business=business,
            outcome=PipelineOutcome.RENDERED,
            brief=brief,
            scene_spec=job.spec,
            render_job=job,
        )

    async def _poll_until_terminal(self, job_id: str) -> RenderJob:
        # Measured against the wall clock rather than accumulated interval
        # counts, so a zero or near-zero poll interval degrades to fast
        # polling instead of a timeout that can never trigger.
        deadline = time.monotonic() + self._poll_timeout_s
        job = await self._render.poll(job_id)
        while not job.status.is_terminal:
            if time.monotonic() >= deadline:
                raise UpstreamError(
                    f"render job {job_id} did not finish within {self._poll_timeout_s}s"
                )
            await self._sleep(self._poll_interval_s)
            job = await self._render.poll(job_id)
        return job
