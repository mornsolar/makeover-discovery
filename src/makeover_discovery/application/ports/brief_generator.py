"""Design-brief generation port."""

from __future__ import annotations

from typing import Protocol

from makeover_discovery.domain.model.brief import BriefRequest, GeneratedBrief


class BriefGenerator(Protocol):
    """Turns a business profile into art direction, within a fixed vocabulary.

    The port says nothing about a language model: the deterministic fake used by
    the test suite satisfies it exactly as the Anthropic adapter does, which is
    what keeps the pipeline testable without a network or an API key.
    """

    async def generate(self, request: BriefRequest) -> GeneratedBrief: ...
