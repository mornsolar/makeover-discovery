"""Geographic value objects.

These are deliberately immutable (``frozen=True``): a postcode or a coordinate
that can be mutated after validation is only nominally validated.
"""

from __future__ import annotations

import re
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

VALUE_OBJECT_CONFIG: Final = ConfigDict(frozen=True, extra="forbid")

MAX_SEARCH_RADIUS_M: Final = 50_000
MIN_SEARCH_RADIUS_M: Final = 50
MIN_POLYGON_VERTICES: Final = 3

# Country-specific postcode shapes. Absence of an entry means "accept anything
# passing the generic length check" — better to admit an unfamiliar country than
# to reject a valid address.
_POSTCODE_PATTERNS: Final[dict[str, re.Pattern[str]]] = {
    "MY": re.compile(r"^\d{5}$"),
    "SG": re.compile(r"^\d{6}$"),
    "US": re.compile(r"^\d{5}(-\d{4})?$"),
    "GB": re.compile(r"^[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}$"),
}


class Postcode(BaseModel):
    """A postal code scoped to the country that issued it.

    A bare postcode string is ambiguous across countries, so the country is part
    of the value rather than an optional hint.
    """

    model_config = VALUE_OBJECT_CONFIG

    value: str = Field(min_length=2, max_length=12)
    country: str = Field(min_length=2, max_length=2, description="ISO 3166-1 alpha-2")

    @field_validator("value")
    @classmethod
    def _normalise_value(cls, value: str) -> str:
        collapsed = " ".join(value.split())
        if not collapsed:
            raise ValueError("postcode must not be blank")
        return collapsed.upper()

    @field_validator("country")
    @classmethod
    def _normalise_country(cls, value: str) -> str:
        upper = value.upper()
        if not upper.isalpha():
            raise ValueError("country must be two ASCII letters")
        return upper

    @model_validator(mode="after")
    def _check_country_specific_shape(self) -> Postcode:
        pattern = _POSTCODE_PATTERNS.get(self.country)
        if pattern is not None and pattern.match(self.value) is None:
            raise ValueError(f"{self.value!r} is not a valid {self.country} postcode")
        return self

    def __str__(self) -> str:
        return f"{self.value} {self.country}"


class GeoPoint(BaseModel):
    """A WGS-84 coordinate."""

    model_config = VALUE_OBJECT_CONFIG

    lat: float = Field(ge=-90.0, le=90.0)
    lon: float = Field(ge=-180.0, le=180.0)


class CircleArea(BaseModel):
    """A search area expressed as a centre point and a radius.

    This is the fallback shape when a postcode has no polygon in OpenStreetMap,
    which is common for Malaysian postcodes.
    """

    model_config = VALUE_OBJECT_CONFIG

    kind: Literal["circle"] = "circle"
    center: GeoPoint
    radius_m: float = Field(ge=MIN_SEARCH_RADIUS_M, le=MAX_SEARCH_RADIUS_M)

    @property
    def query_center(self) -> GeoPoint:
        return self.center


class PolygonArea(BaseModel):
    """A search area expressed as an explicit boundary."""

    model_config = VALUE_OBJECT_CONFIG

    kind: Literal["polygon"] = "polygon"
    vertices: tuple[GeoPoint, ...] = Field(min_length=MIN_POLYGON_VERTICES)

    @property
    def query_center(self) -> GeoPoint:
        """Arithmetic mean of the vertices.

        Not a true area centroid — it only needs to be good enough to seed a
        radial provider query; the polygon itself is used for filtering.
        """
        count = len(self.vertices)
        return GeoPoint(
            lat=sum(vertex.lat for vertex in self.vertices) / count,
            lon=sum(vertex.lon for vertex in self.vertices) / count,
        )


GeoArea = Annotated[CircleArea | PolygonArea, Field(discriminator="kind")]
"""Either shape of search area, discriminated on ``kind`` for stable JSON."""
