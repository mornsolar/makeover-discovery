"""Mapping between Google Places types and our business categories.

Mirrors ``osm_taxonomy``'s shape but is a separate table: the two providers
invented unrelated vocabularies (Places' ``primaryType`` is a flat enum of
~200 strings, OSM's tags are key/value pairs), and merging them into one table
would make neither easy to check against its provider's own documentation.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Final

from makeover_contracts.business import BusinessCategory

# Ordered so a specific type is matched before a broader one that would
# otherwise swallow it - "cafe" before "store", not after.
PLACES_RULES: Final[tuple[tuple[str, BusinessCategory], ...]] = (
    ("restaurant", BusinessCategory.RESTAURANT),
    ("fast_food_restaurant", BusinessCategory.RESTAURANT),
    ("food_court", BusinessCategory.RESTAURANT),
    ("cafe", BusinessCategory.CAFE),
    ("coffee_shop", BusinessCategory.CAFE),
    ("bakery", BusinessCategory.BAKERY),
    ("bar", BusinessCategory.BAR),
    ("pub", BusinessCategory.BAR),
    ("hair_salon", BusinessCategory.SALON),
    ("beauty_salon", BusinessCategory.SALON),
    ("spa", BusinessCategory.SALON),
    ("nail_salon", BusinessCategory.SALON),
    ("doctor", BusinessCategory.CLINIC),
    ("dentist", BusinessCategory.CLINIC),
    ("medical_lab", BusinessCategory.CLINIC),
    ("hotel", BusinessCategory.HOTEL),
    ("lodging", BusinessCategory.HOTEL),
    ("guest_house", BusinessCategory.HOTEL),
    ("car_repair", BusinessCategory.WORKSHOP),
    ("electrician", BusinessCategory.WORKSHOP),
    ("locksmith", BusinessCategory.WORKSHOP),
    ("store", BusinessCategory.RETAIL),
    ("clothing_store", BusinessCategory.RETAIL),
    ("convenience_store", BusinessCategory.RETAIL),
    ("supermarket", BusinessCategory.RETAIL),
)

_CATEGORY_BY_TYPE: Final[dict[str, BusinessCategory]] = dict(PLACES_RULES)


def classify(types: Sequence[str]) -> BusinessCategory | None:
    """Return the category implied by a place's ``types`` list, in provider order.

    Places lists ``primaryType`` first when present and otherwise several
    types with no guaranteed ordering, so every entry is checked and the rule
    table's own order breaks the tie, not the response's.
    """
    matches = (_CATEGORY_BY_TYPE.get(place_type) for place_type in types)
    found = {category for category in matches if category is not None}
    if not found:
        return None
    return next(category for _, category in PLACES_RULES if category in found)


def included_types_for(categories: Iterable[BusinessCategory]) -> tuple[str, ...]:
    """Places types to request via ``includedTypes``; empty means every type we handle.

    Places cannot search "give me everything"; the request must name types.
    """
    wanted = set(categories)
    rules = PLACES_RULES if not wanted else (r for r in PLACES_RULES if r[1] in wanted)
    return tuple(dict.fromkeys(place_type for place_type, _ in rules))
