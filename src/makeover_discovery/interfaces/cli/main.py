"""Command-line entry point.

Exists so each phase is demonstrable without a browser or an HTTP client, and
so the same object graph the API uses gets exercised by a second caller.
``argparse`` rather than a CLI framework: one command does not justify a
dependency.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence
from typing import Final

from makeover_contracts.business import BusinessCategory
from makeover_contracts.geo import Postcode
from pydantic import ValidationError

from makeover_discovery.application.use_cases.enrich_business_profile import EnrichmentResult
from makeover_discovery.composition import (
    build_discover_businesses,
    build_enrich_business_profile,
    build_generate_design_brief,
    build_run_makeover_pipeline,
    create_shared_resources,
)
from makeover_discovery.config.settings import get_settings
from makeover_discovery.domain.errors import ConfigurationError, NotFoundError, UpstreamError
from makeover_discovery.domain.model.brief import BriefResult
from makeover_discovery.domain.model.discovery import (
    DEFAULT_RESULT_LIMIT,
    DiscoveryQuery,
    DiscoveryResult,
    SearchFilters,
)
from makeover_discovery.domain.model.pipeline import PipelineOutcome, PipelineResult
from makeover_discovery.infrastructure.time.system_clock import SystemClock

EXIT_OK: Final = 0
EXIT_USAGE: Final = 2
EXIT_NOT_FOUND: Final = 3
EXIT_UPSTREAM: Final = 4
EXIT_CONFIG: Final = 5
EXIT_RENDER_FAILED: Final = 6


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="makeover", description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)

    discover = subcommands.add_parser("discover", help="Find businesses near a postcode")
    discover.add_argument("postcode")
    discover.add_argument("--country", default="MY", help="ISO 3166-1 alpha-2 code")
    discover.add_argument("--limit", type=int, default=DEFAULT_RESULT_LIMIT)
    discover.add_argument(
        "--category",
        action="append",
        default=[],
        choices=[member.value for member in BusinessCategory],
        help="Restrict to a category; repeatable.",
    )

    enrich = subcommands.add_parser("enrich", help="Discover then enrich the nearest businesses")
    enrich.add_argument("postcode")
    enrich.add_argument("--country", default="MY", help="ISO 3166-1 alpha-2 code")
    enrich.add_argument("--limit", type=int, default=3)

    brief = subcommands.add_parser("brief", help="Discover, enrich, then generate design briefs")
    brief.add_argument("postcode")
    brief.add_argument("--country", default="MY", help="ISO 3166-1 alpha-2 code")
    brief.add_argument("--limit", type=int, default=1, help="Briefs cost money; default one.")

    pipeline = subcommands.add_parser(
        "pipeline", help="Discover, enrich, brief, and render - the full pipeline"
    )
    pipeline.add_argument("postcode")
    pipeline.add_argument("--country", default="MY", help="ISO 3166-1 alpha-2 code")
    pipeline.add_argument(
        "--limit", type=int, default=1, help="Renders cost time and money; default one."
    )
    return parser


def _query(args: argparse.Namespace) -> DiscoveryQuery:
    return DiscoveryQuery(
        postcode=Postcode(value=args.postcode, country=args.country),
        filters=SearchFilters(
            categories=tuple(BusinessCategory(value) for value in getattr(args, "category", [])),
            limit=args.limit,
        ),
    )


async def run_discover(args: argparse.Namespace) -> DiscoveryResult:
    settings = get_settings()
    resources = create_shared_resources(settings)
    try:
        use_case = build_discover_businesses(settings, resources, SystemClock())
        return await use_case.execute(_query(args))
    finally:
        # The HTTP client owns a connection pool; leaking it makes the process
        # hang on exit rather than fail visibly.
        await resources.aclose()


async def run_enrich(args: argparse.Namespace) -> tuple[EnrichmentResult, ...]:
    settings = get_settings()
    resources = create_shared_resources(settings)
    try:
        clock = SystemClock()
        discovered = await build_discover_businesses(settings, resources, clock).execute(
            _query(args)
        )
        enricher = build_enrich_business_profile(settings, resources, clock)
        # Sequential on purpose: the per-host rate limiter is the point, and
        # firing these concurrently would defeat it for a shared host.
        return tuple([await enricher.execute(candidate) for candidate in discovered.candidates])
    finally:
        await resources.aclose()


async def run_brief(args: argparse.Namespace) -> tuple[BriefResult, ...]:
    settings = get_settings()
    resources = create_shared_resources(settings)
    try:
        clock = SystemClock()
        discovered = await build_discover_businesses(settings, resources, clock).execute(
            _query(args)
        )
        enricher = build_enrich_business_profile(settings, resources, clock)
        briefer = build_generate_design_brief(settings, resources, clock)
        # Sequential for the same reason enrichment is, plus one more: each
        # brief is a paid model call, so a fan-out mistake is expensive.
        return tuple(
            [
                await briefer.execute((await enricher.execute(candidate)).profile)
                for candidate in discovered.candidates
            ]
        )
    finally:
        await resources.aclose()


async def run_pipeline(args: argparse.Namespace) -> tuple[PipelineResult, ...]:
    settings = get_settings()
    resources = create_shared_resources(settings)
    try:
        use_case = build_run_makeover_pipeline(settings, resources, SystemClock())
        return await use_case.execute(_query(args))
    finally:
        await resources.aclose()


def render(result: DiscoveryResult) -> str:
    lines = [f"{len(result.candidates)} business(es) near {result.postcode}", ""]
    for index, candidate in enumerate(result.candidates, start=1):
        lines.append(f"{index:>3}. {candidate.name}  [{candidate.category.value}]")
        if candidate.address_line:
            lines.append(f"     {candidate.address_line}")
        lines.append(f"     {candidate.location.lat:.5f}, {candidate.location.lon:.5f}")
    if result.attributions:
        lines.extend(["", "Data: " + "; ".join(result.attributions)])
    return "\n".join(lines)


def render_profiles(results: tuple[EnrichmentResult, ...]) -> str:
    lines: list[str] = []
    for result in results:
        profile = result.profile
        lines.append(f"{profile.name.value}  [{profile.category.value}]")
        lines.append(f"  id       {profile.id}")
        lines.append(f"  website  {result.website_outcome.value}")
        if profile.descriptors:
            lines.append("  tags     " + ", ".join(d.value for d in profile.descriptors))
        if profile.photo_urls:
            lines.append(f"  photos   {len(profile.photo_urls)}")
        lines.append("  data     " + "; ".join(profile.attributions()))
        lines.append("")
    return "\n".join(lines)


def render_briefs(results: tuple[BriefResult, ...]) -> str:
    lines: list[str] = []
    for result in results:
        brief = result.brief
        lines.append(f"{brief.business_id}")
        lines.append(f"  style     {brief.style_direction}")
        lines.append(f"  palette   {' '.join(brief.palette)}")
        lines.append(f"  materials {', '.join(brief.material_families)}")
        lines.append(f'  signage   "{brief.signage.text}" ({brief.signage.tone})')
        lines.append(f"  lighting  {brief.lighting_mood.value}")
        lines.append(f"  camera    {brief.camera_move}")
        lines.append(f"  avoid     {'; '.join(brief.do_not_include)}")
        lines.append(
            f"  model     {brief.generation.model} / {brief.generation.prompt_version} "
            f"/ seed {brief.generation.seed}"
        )
        lines.append(
            f"  cost      ~${result.cost_usd:.4f} "
            f"({result.usage.total_tokens} tokens, {result.attempts} attempt(s))"
        )
        lines.append("")
    return "\n".join(lines)


def render_pipeline(results: tuple[PipelineResult, ...]) -> str:
    lines: list[str] = []
    for result in results:
        lines.append(f"{result.business.name.value}  [{result.outcome.value}]")
        artifacts = result.render_job.artifacts if result.render_job else None
        if artifacts is not None:
            lines.append(f"  video      {artifacts.video.uri}")
            lines.append(f"  gltf       {artifacts.gltf.uri}")
            lines.append(f"  thumbnail  {artifacts.thumbnail.uri}")
        if result.error:
            lines.append(f"  error      {result.error}")
        lines.append("")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "enrich":
            print(render_profiles(asyncio.run(run_enrich(args))))
            return EXIT_OK
        if args.command == "brief":
            print(render_briefs(asyncio.run(run_brief(args))))
            return EXIT_OK
        if args.command == "pipeline":
            results = asyncio.run(run_pipeline(args))
            print(render_pipeline(results))
            # A batch is only fully successful if every business rendered;
            # a script driving this command needs that signal to know
            # whether to look at the per-business errors printed above.
            if any(result.outcome is not PipelineOutcome.RENDERED for result in results):
                return EXIT_RENDER_FAILED
            return EXIT_OK
        result = asyncio.run(run_discover(args))
    except ValidationError as exc:
        print(f"invalid input: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except ConfigurationError as exc:
        print(f"not configured: {exc}", file=sys.stderr)
        return EXIT_CONFIG
    except NotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_NOT_FOUND
    except UpstreamError as exc:
        print(f"upstream failure: {exc}", file=sys.stderr)
        return EXIT_UPSTREAM
    print(render(result))
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
