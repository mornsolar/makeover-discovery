"""The golden businesses every brief-generator change is scored against.

Chosen to cover the shapes the pipeline actually meets in Kuala Lumpur: a
descriptor-rich profile, a bare one with nothing but a name and a category, a
long name that has to be truncated to fit a sign, and a category whose default
palette differs.
"""

from __future__ import annotations

from makeover_contracts.business import BusinessCategory

from tests.evals.harness import EvalCase
from tests.fakes.brief import make_profile

GOLDEN_CASES: tuple[EvalCase, ...] = (
    EvalCase(
        name="cafe-with-descriptors",
        profile=make_profile(),
        banned_terms=("logo", "trademark", "starbucks"),
    ),
    EvalCase(
        name="bare-retail-profile",
        profile=make_profile(
            business_id="kedai-runcit-siva-node-2",
            name="Kedai Runcit Siva",
            category=BusinessCategory.RETAIL,
            descriptors=(),
        ),
        banned_terms=("logo", "award-winning"),
    ),
    EvalCase(
        name="long-name-bakery",
        profile=make_profile(
            business_id="roti-canai-warisan-node-3",
            name="Roti Canai Warisan Keluarga Abdullah Sdn Bhd",
            category=BusinessCategory.BAKERY,
            descriptors=("halal",),
        ),
        banned_terms=("logo", "since"),
    ),
    EvalCase(
        name="salon",
        profile=make_profile(
            business_id="gunting-rambut-mei-node-4",
            name="Gunting Rambut Mei",
            category=BusinessCategory.SALON,
            descriptors=("walk-ins welcome",),
        ),
        banned_terms=("logo", "michelin"),
    ),
)
