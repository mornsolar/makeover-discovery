"""Domain error to HTTP status mapping."""

from __future__ import annotations

from fastapi import status

from makeover_discovery.domain.errors import (
    MakeoverError,
    NotFoundError,
    PolicyViolationError,
    UpstreamError,
    ValidationError,
)
from makeover_discovery.interfaces.api.errors import DEFAULT_STATUS, status_for


def test_maps_a_missing_entity_to_not_found():
    assert status_for(NotFoundError("gone")) == status.HTTP_404_NOT_FOUND


def test_maps_bad_input_to_unprocessable_entity():
    assert status_for(ValidationError("bad")) == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_maps_a_provider_failure_to_bad_gateway():
    # 502 rather than 500: the fault is upstream, and the distinction is what
    # tells an operator whether to look at our logs or the provider's status page.
    assert status_for(UpstreamError("overpass down")) == status.HTTP_502_BAD_GATEWAY


def test_maps_a_refused_action_to_forbidden():
    assert status_for(PolicyViolationError("robots")) == status.HTTP_403_FORBIDDEN


def test_falls_back_to_server_error_for_an_unmapped_domain_error():
    assert status_for(MakeoverError("unclassified")) == DEFAULT_STATUS


def test_resolves_a_subclass_through_its_ancestors():
    class TileServerError(UpstreamError):
        pass

    assert status_for(TileServerError("boom")) == status.HTTP_502_BAD_GATEWAY
