"""What must be stripped from third-party text before we keep it.

Two separate reasons, deliberately handled by one pass:

* **Privacy.** A business website often names staff and publishes personal
  email addresses. None of it helps infer a design brief, and all of it raises
  the obligations attached to what we store.
* **Injection.** Extracted text ends up in an LLM prompt and, downstream, on a
  rendered 3D surface. Text arriving from a page we do not control is the most
  likely route for an instruction to reach either.
"""

from __future__ import annotations

import re
from typing import Final

MAX_DESCRIPTOR_CHARS: Final = 80
MIN_DESCRIPTOR_CHARS: Final = 3

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_URL = re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)
_LONG_DIGITS = re.compile(r"\+?\d[\d\s().-]{7,}\d")
"""Anything phone-number-shaped. The business phone is captured deliberately
from a structured field; a number embedded in prose is more often a person's."""

_CONTROL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\u00ad\u200b-\u200f\u202a-\u202e\u2060\ufeff]")
"""Control and zero-width characters.

Invisible text is a standard way to hide instructions inside otherwise
innocuous copy, so it is removed rather than trusted.
"""


class RedactionPolicy:
    """Removes personal and unsafe content from extracted free text."""

    def clean(self, text: str) -> str | None:
        """Strip contact details and invisible characters; ``None`` if nothing left."""
        without_invisible = _CONTROL.sub("", text)
        redacted = _EMAIL.sub(" ", without_invisible)
        redacted = _URL.sub(" ", redacted)
        redacted = _LONG_DIGITS.sub(" ", redacted)
        collapsed = " ".join(redacted.split())
        return collapsed or None

    def clean_descriptor(self, text: str) -> str | None:
        """Clean a short descriptor, rejecting one that is too short to mean anything."""
        cleaned = self.clean(text)
        if cleaned is None or len(cleaned) < MIN_DESCRIPTOR_CHARS:
            return None
        return cleaned[:MAX_DESCRIPTOR_CHARS]

    def clean_all(self, texts: tuple[str, ...], limit: int) -> tuple[str, ...]:
        """Clean and de-duplicate descriptors, preserving order and first casing.

        Case-insensitive: "Halal" and "halal" are one descriptor, and letting
        both through would put a visible duplicate in the design brief.
        """
        kept: dict[str, str] = {}
        for text in texts:
            cleaned = self.clean_descriptor(text)
            if cleaned is not None:
                kept.setdefault(cleaned.casefold(), cleaned)
        return tuple(kept.values())[:limit]
