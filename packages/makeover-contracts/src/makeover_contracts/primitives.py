"""Small constrained scalar types shared across the contract."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field, StringConstraints

HexColor = Annotated[str, StringConstraints(pattern=r"^#[0-9A-Fa-f]{6}$")]
"""An opaque sRGB colour, e.g. ``#1B4D3E``. Alpha is never part of a palette."""

Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
"""Lowercase hex digest, making artifacts verifiable across the repo boundary."""

UnitInterval = Annotated[float, Field(ge=0.0, le=1.0)]
"""A normalised 0..1 factor, used for roughness, metallic, and similar."""

Slug = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$", max_length=64)]
"""Stable machine identifier for templates, material families, and projects."""
