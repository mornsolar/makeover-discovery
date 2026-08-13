from __future__ import annotations

import pytest

from makeover_discovery.domain.errors import (
    MakeoverError,
    NotFoundError,
    PolicyViolationError,
    UpstreamError,
    ValidationError,
)


@pytest.mark.parametrize(
    "error", [ValidationError, NotFoundError, UpstreamError, PolicyViolationError]
)
def test_every_domain_error_shares_one_base(error):
    assert issubclass(error, MakeoverError)


def test_policy_violation_is_not_a_validation_error():
    # The remedy differs: a caller cannot fix a policy refusal by sending
    # different input, so handlers must be able to tell them apart.
    assert not issubclass(PolicyViolationError, ValidationError)
