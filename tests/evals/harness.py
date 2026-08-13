"""Golden-brief eval harness.

Scores a design brief against objective criteria. It runs in the normal suite
against the deterministic generator, which is what makes it a regression guard
rather than a one-off experiment - but the criteria are model-agnostic, so the
same harness scores briefs from the real Anthropic adapter when someone runs it
with a key.

Criteria are all mechanically checkable on purpose. "Is this good art direction"
is not something a test can answer; "does this brief ask for a material the
renderer does not have" is.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from makeover_contracts.brief import DesignBrief
from makeover_contracts.business import BusinessProfile

from makeover_discovery.domain.model.brief import BriefVocabulary
from makeover_discovery.domain.policy.brief_guardrails import validate_brief

MIN_RATIONALE_CHARS = 40


@dataclass(frozen=True)
class EvalCase:
    """One golden business, plus what its brief must never mention."""

    name: str
    profile: BusinessProfile
    banned_terms: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvalScore:
    """Per-criterion outcome for one brief."""

    case: str
    failures: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.failures


Criterion = Callable[[DesignBrief, EvalCase, BriefVocabulary], bool]


def _is_renderable(brief: DesignBrief, _: EvalCase, vocabulary: BriefVocabulary) -> bool:
    return validate_brief(brief, vocabulary) == ()


def _palette_is_distinct(brief: DesignBrief, *_: object) -> bool:
    return len(set(brief.palette)) == len(brief.palette)


def _materials_are_distinct(brief: DesignBrief, *_: object) -> bool:
    return len(set(brief.material_families)) == len(brief.material_families)


def _rationale_is_substantive(brief: DesignBrief, *_: object) -> bool:
    return len(brief.rationale.strip()) >= MIN_RATIONALE_CHARS


def _signage_relates_to_the_business(brief: DesignBrief, case: EvalCase, *_: object) -> bool:
    # Signage that has nothing to do with the business is the clearest sign the
    # model invented a shop rather than reimagining this one.
    name_words = {word.lower() for word in case.profile.name.value.split() if len(word) > 2}
    signage_words = {word.lower().strip(".,'\"") for word in brief.signage.text.split()}
    return bool(name_words & signage_words)


def _avoids_banned_terms(brief: DesignBrief, case: EvalCase, *_: object) -> bool:
    haystack = " ".join(
        (brief.style_direction, brief.rationale, brief.signage.text, brief.signage.tone)
    ).lower()
    return not any(term.lower() in haystack for term in case.banned_terms)


CRITERIA: dict[str, Criterion] = {
    "renderable": _is_renderable,
    "palette_is_distinct": _palette_is_distinct,
    "materials_are_distinct": _materials_are_distinct,
    "rationale_is_substantive": _rationale_is_substantive,
    "signage_relates_to_the_business": _signage_relates_to_the_business,
    "avoids_banned_terms": _avoids_banned_terms,
}


def score(brief: DesignBrief, case: EvalCase, vocabulary: BriefVocabulary) -> EvalScore:
    failures = tuple(
        name for name, criterion in CRITERIA.items() if not criterion(brief, case, vocabulary)
    )
    return EvalScore(case=case.name, failures=failures)


def report(scores: list[EvalScore]) -> str:
    """A one-line-per-case summary, for running the harness by hand."""
    lines = [
        f"{'PASS' if s.passed else 'FAIL'}  {s.case}"
        + ("" if s.passed else f"  ({', '.join(s.failures)})")
        for s in scores
    ]
    passed = sum(1 for s in scores if s.passed)
    lines.append(f"{passed}/{len(scores)} briefs passed all {len(CRITERIA)} criteria")
    return "\n".join(lines)
