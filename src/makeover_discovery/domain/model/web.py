"""Web page value objects.

The boundary between "we fetched some bytes" and "we understood them". Fetchers
produce ``FetchedPage``; extractors turn it into ``ExtractedContent``. Keeping
them apart is what lets a Playwright fetcher and an httpx fetcher feed the same
extraction code.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_DESCRIPTORS: Final = 12
MAX_PHOTOS: Final = 8
MAX_HTML_BYTES: Final = 2_000_000
"""Ceiling on a fetched document.

A business site that serves more than this is either broken or hostile, and
either way parsing it is not worth the memory.
"""


class FetchedPage(BaseModel):
    """One retrieved HTML document."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    requested_url: str = Field(min_length=1, max_length=2048)
    final_url: str = Field(min_length=1, max_length=2048)
    status_code: int = Field(ge=100, le=599)
    html: str
    fetched_at: datetime

    @field_validator("fetched_at")
    @classmethod
    def _require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("fetched_at must be timezone-aware")
        return value

    @property
    def was_redirected(self) -> bool:
        return self.requested_url != self.final_url


class ExtractedContent(BaseModel):
    """What a page told us about the business it belongs to.

    Every field is optional: a business website is under no obligation to be
    machine-readable, and an empty result is a normal outcome rather than a
    failure.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    phone: str | None = Field(default=None, max_length=64)
    descriptors: tuple[str, ...] = Field(default=(), max_length=MAX_DESCRIPTORS)
    photo_urls: tuple[str, ...] = Field(default=(), max_length=MAX_PHOTOS)

    @property
    def is_empty(self) -> bool:
        return not any((self.name, self.description, self.phone, self.descriptors, self.photo_urls))
