from __future__ import annotations

import pytest
from makeover_contracts.version import CONTRACT_VERSION, is_compatible


class TestIsCompatible:
    def test_accepts_the_current_version(self):
        assert is_compatible(CONTRACT_VERSION) is True

    def test_accepts_an_additive_minor_bump(self):
        assert is_compatible("0.9.3") is True

    def test_rejects_a_major_bump(self):
        assert is_compatible("1.0.0") is False

    @pytest.mark.parametrize("value", ["", "not-a-version"])
    def test_rejects_unparseable_input(self, value):
        assert is_compatible(value) is False
