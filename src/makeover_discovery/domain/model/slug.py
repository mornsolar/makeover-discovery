"""Stable identifiers for businesses.

A profile's id has to survive being put in a URL, a filename, and a Blender
object name, so it is derived once here rather than improvised per interface.
"""

from __future__ import annotations

import hashlib
import re
from typing import Final

MAX_SLUG_CHARS: Final = 64
FINGERPRINT_CHARS: Final = 8

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def to_slug(name: str, unique_key: str) -> str:
    """Build a readable, collision-resistant slug.

    The name makes it legible; a short digest of ``unique_key`` makes it unique.
    Two branches of the same chain in one postcode would otherwise collide, and
    the second would silently overwrite the first's artifacts.
    """
    fingerprint = hashlib.sha256(unique_key.encode()).hexdigest()[:FINGERPRINT_CHARS]
    stem = _NON_ALNUM.sub("-", name.casefold()).strip("-")
    if not stem:
        return f"business-{fingerprint}"
    available = MAX_SLUG_CHARS - len(fingerprint) - 1
    return f"{stem[:available].strip('-')}-{fingerprint}"
