"""Checks a generated brief before it is allowed out of the use case.

Two separate concerns, deliberately in one place because both must pass before a
brief is usable: it has to be *renderable* (inside the manifest's vocabulary) and
it has to be *publishable* (no brand marks, no invented claims). Problems are
returned rather than raised so every one of them can be fed back to the model in
a single repair round instead of one per attempt.
"""

from __future__ import annotations

import re
from typing import Final

from makeover_contracts.brief import DesignBrief

from makeover_discovery.domain.model.brief import MANDATORY_EXCLUSIONS, BriefVocabulary

BANNED_SIGNAGE_TERMS: Final = ("™", "®", "©")
"""Trademark marks in 3D signage are the clearest form of the risk the roadmap
flags; they are also the easiest to detect, so they are rejected outright."""

_CLAIM_PATTERNS: Final = (
    re.compile(r"\b(?:since|est\.?|established)\s+\d{4}\b", re.IGNORECASE),
    re.compile(r"\b(?:award[- ]winning|michelin|no\.?\s*1|#1|best in)\b", re.IGNORECASE),
    re.compile(r"\b\d+(?:\.\d+)?\s*(?:stars?|/\s*5)\b", re.IGNORECASE),
)
"""Factual-sounding claims we have no source for.

Every other field in this system is ``Provenanced``; a brief is generated, so it
has no source at all and must therefore assert nothing checkable.
"""


def validate_brief(brief: DesignBrief, vocabulary: BriefVocabulary) -> tuple[str, ...]:
    """Return human-readable reasons ``brief`` is unusable; empty means valid."""
    return _vocabulary_problems(brief, vocabulary) + _content_problems(brief)


def _vocabulary_problems(brief: DesignBrief, vocabulary: BriefVocabulary) -> tuple[str, ...]:
    problems: list[str] = []

    unknown = [f for f in brief.material_families if f not in vocabulary.material_families]
    if unknown:
        offered = ", ".join(vocabulary.material_families)
        problems.append(
            f"unknown material families: {', '.join(sorted(unknown))}; renderer offers: {offered}"
        )

    if brief.camera_move not in vocabulary.camera_moves:
        offered = ", ".join(vocabulary.camera_moves)
        problems.append(f"unknown camera move {brief.camera_move!r}; renderer offers: {offered}")

    if brief.lighting_mood not in vocabulary.lighting_moods:
        offered = ", ".join(mood.value for mood in vocabulary.lighting_moods)
        problems.append(
            f"unsupported lighting mood {brief.lighting_mood.value!r}; renderer offers: {offered}"
        )

    return tuple(problems)


def _content_problems(brief: DesignBrief) -> tuple[str, ...]:
    problems: list[str] = []

    marks = [mark for mark in BANNED_SIGNAGE_TERMS if mark in brief.signage.text]
    if marks:
        problems.append(f"signage text contains trademark marks: {' '.join(marks)}")

    for field_name, text in (("signage text", brief.signage.text), ("rationale", brief.rationale)):
        claim = _first_claim(text)
        if claim is not None:
            problems.append(
                f"{field_name} makes an unsourced factual claim: {claim!r}; "
                "a brief may describe style, never assert facts about the business"
            )

    missing = [item for item in MANDATORY_EXCLUSIONS if item not in brief.do_not_include]
    if missing:
        problems.append(f"do_not_include is missing mandatory entries: {'; '.join(missing)}")

    return tuple(problems)


def _first_claim(text: str) -> str | None:
    for pattern in _CLAIM_PATTERNS:
        match = pattern.search(text)
        if match is not None:
            return match.group(0)
    return None
