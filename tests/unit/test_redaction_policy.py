"""Redaction of third-party text."""

from __future__ import annotations

from makeover_discovery.domain.policy.redaction import MAX_DESCRIPTOR_CHARS, RedactionPolicy

policy = RedactionPolicy()


def test_removes_email_addresses():
    assert policy.clean("Book via ali@example.com today") == "Book via today"


def test_removes_phone_numbers_embedded_in_prose():
    # The business phone is captured from a structured field; a number buried
    # in copy is more often a person's.
    assert policy.clean("Call +60 12-345 6789 now") == "Call now"


def test_removes_urls():
    # Extracted text reaches an LLM prompt and then a rendered surface, so a
    # link in free text is both off-medium and an injection route.
    assert policy.clean("See https://evil.example/instructions for more") == "See for more"


def test_removes_invisible_characters():
    hidden = "Cosy​ cafe﻿ downtown"

    assert policy.clean(hidden) == "Cosy cafe downtown"


def test_collapses_whitespace():
    assert policy.clean("  wood   fired   oven  ") == "wood fired oven"


def test_returns_none_when_nothing_survives():
    assert policy.clean("ali@example.com") is None


def test_rejects_a_descriptor_too_short_to_mean_anything():
    assert policy.clean_descriptor("a") is None


def test_truncates_an_overlong_descriptor():
    assert len(policy.clean_descriptor("x" * 500) or "") == MAX_DESCRIPTOR_CHARS


def test_deduplicates_descriptors_ignoring_case():
    assert policy.clean_all(("Halal", "halal", "Outdoor seating"), 5) == (
        "Halal",
        "Outdoor seating",
    )


def test_applies_the_descriptor_limit():
    assert len(policy.clean_all(tuple(f"tag {n}" for n in range(20)), 3)) == 3


def test_drops_descriptors_that_redact_to_nothing():
    assert policy.clean_all(("halal", "ali@example.com"), 5) == ("halal",)
