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

from makeover_discovery.composition import build_discover_businesses, create_shared_resources
from makeover_discovery.config.settings import get_settings
from makeover_discovery.domain.errors import NotFoundError, UpstreamError
from makeover_discovery.domain.model.discovery import (
    DEFAULT_RESULT_LIMIT,
    DiscoveryQuery,
    DiscoveryResult,
    SearchFilters,
)
from makeover_discovery.infrastructure.time.system_clock import SystemClock

EXIT_OK: Final = 0
EXIT_USAGE: Final = 2
EXIT_NOT_FOUND: Final = 3
EXIT_UPSTREAM: Final = 4


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
    return parser


async def run_discover(args: argparse.Namespace) -> DiscoveryResult:
    settings = get_settings()
    resources = create_shared_resources(settings)
    try:
        use_case = build_discover_businesses(settings, resources, SystemClock())
        query = DiscoveryQuery(
            postcode=Postcode(value=args.postcode, country=args.country),
            filters=SearchFilters(
                categories=tuple(BusinessCategory(value) for value in args.category),
                limit=args.limit,
            ),
        )
        return await use_case.execute(query)
    finally:
        # The HTTP client owns a connection pool; leaking it makes the process
        # hang on exit rather than fail visibly.
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


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = asyncio.run(run_discover(args))
    except ValidationError as exc:
        print(f"invalid input: {exc}", file=sys.stderr)
        return EXIT_USAGE
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
