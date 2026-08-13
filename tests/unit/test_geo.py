from __future__ import annotations

import pytest
from makeover_contracts.geo import CircleArea, GeoPoint, PolygonArea, Postcode
from pydantic import ValidationError


class TestPostcode:
    def test_normalises_whitespace_and_case(self):
        # Arrange / Act
        postcode = Postcode(value="  sw1a  1aa ", country="gb")

        # Assert
        assert postcode.value == "SW1A 1AA"
        assert postcode.country == "GB"

    def test_accepts_valid_malaysian_postcode(self):
        assert Postcode(value="50450", country="MY").value == "50450"

    def test_rejects_malaysian_postcode_of_wrong_length(self):
        with pytest.raises(ValidationError, match="not a valid MY postcode"):
            Postcode(value="5045", country="MY")

    def test_accepts_unknown_country_without_a_pattern(self):
        # We would rather admit an unfamiliar country than reject a real address.
        assert Postcode(value="ABC12", country="ZZ").country == "ZZ"

    def test_rejects_non_alphabetic_country(self):
        with pytest.raises(ValidationError):
            Postcode(value="50450", country="1Y")

    def test_is_immutable(self):
        postcode = Postcode(value="50450", country="MY")
        with pytest.raises(ValidationError):
            postcode.value = "50460"

    def test_string_form_includes_country(self):
        assert str(Postcode(value="50450", country="MY")) == "50450 MY"


class TestGeoPoint:
    @pytest.mark.parametrize(("lat", "lon"), [(91.0, 0.0), (-91.0, 0.0), (0.0, 181.0)])
    def test_rejects_out_of_range_coordinates(self, lat, lon):
        with pytest.raises(ValidationError):
            GeoPoint(lat=lat, lon=lon)

    def test_accepts_kuala_lumpur(self):
        point = GeoPoint(lat=3.1578, lon=101.7117)
        assert point.lat == pytest.approx(3.1578)


class TestSearchAreas:
    def test_circle_query_center_is_its_center(self):
        center = GeoPoint(lat=3.1578, lon=101.7117)
        area = CircleArea(center=center, radius_m=800)
        assert area.query_center == center

    def test_circle_rejects_radius_beyond_the_cap(self):
        with pytest.raises(ValidationError):
            CircleArea(center=GeoPoint(lat=0.0, lon=0.0), radius_m=50_001)

    def test_polygon_query_center_is_the_vertex_mean(self):
        area = PolygonArea(
            vertices=(
                GeoPoint(lat=0.0, lon=0.0),
                GeoPoint(lat=2.0, lon=0.0),
                GeoPoint(lat=1.0, lon=3.0),
            )
        )
        assert area.query_center.lat == pytest.approx(1.0)
        assert area.query_center.lon == pytest.approx(1.0)

    def test_polygon_requires_at_least_three_vertices(self):
        with pytest.raises(ValidationError):
            PolygonArea(vertices=(GeoPoint(lat=0.0, lon=0.0), GeoPoint(lat=1.0, lon=1.0)))
