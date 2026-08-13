"""Single source of truth for the contract version.

Both repositories pin this value. Repo B (``makeover-render``) reports it in its
``CapabilityManifest`` so Repo A can refuse to talk to a renderer built against
an incompatible contract.
"""

from __future__ import annotations

from typing import Final

CONTRACT_VERSION: Final[str] = "0.1.0"
"""Semantic version of the wire contract. Bump the minor for additive changes,
the major for anything that would break an existing consumer."""


def is_compatible(other: str) -> bool:
    """Return whether ``other`` can be safely exchanged with this contract.

    Compatibility is major-version equality: additive minor and patch changes
    are backward compatible by the evolution rules this package commits to, so
    only a major bump is treated as breaking.
    """
    if not isinstance(other, str) or not other:
        return False
    return CONTRACT_VERSION.split(".", 1)[0] == other.split(".", 1)[0]
