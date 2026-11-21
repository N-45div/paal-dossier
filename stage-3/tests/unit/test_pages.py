"""Unit tests for app/pages.py: page kind and publication time (Rul-S2-3)."""

import pytest

from app.pages import page_meta


@pytest.mark.parametrize("kind", ["own", "filing", "news", "aggregator"])
def test_declared_kind_is_taken_exactly(kind):
    assert page_meta({"Kind": kind}, "https://elsewhere.test/x", "acme.test").kind == kind


@pytest.mark.parametrize("declared", ["News", "OWN", " news", "blog", ""])
def test_other_declared_kinds_fall_back_to_the_host(declared):
    assert page_meta({"Kind": declared}, "https://acme.test/x", "acme.test").kind == "own"
    assert page_meta({"Kind": declared}, "https://other.test/x", "acme.test").kind == "aggregator"


def test_no_kind_line_uses_the_host_with_www_and_trailing_dot_normalised():
    assert page_meta({}, "https://www.acme.test./about", "acme.test").kind == "own"


def test_host_rule_for_an_invalid_host_is_aggregator():
    assert page_meta({}, "https://ACME_TEST/", "acme.test").kind == "aggregator"


@pytest.mark.parametrize(
    "stamp, expected",
    [
        ("2026-01-10T00:00:00Z", "2026-01-10T00:00:00+00:00"),
        ("2026-01-10T09:30:00+02:00", "2026-01-10T09:30:00+02:00"),
        ("2026-01-10T09:30:00.250-05:00", "2026-01-10T09:30:00.250000-05:00"),
        ("2026-01-10t00:00:00z", "2026-01-10T00:00:00+00:00"),
    ],
)
def test_rfc3339_with_offset_is_kept_as_its_instant(stamp, expected):
    assert page_meta({"Published": stamp}, "https://a.test/", "acme.test").published_at == expected


@pytest.mark.parametrize(
    "stamp",
    ["2026-01-10", "2026-01-10T00:00:00", "yesterday", "2026-13-01T00:00:00Z", "2026-01-10 09:00:00"],
)
def test_published_without_offset_or_invalid_has_no_time(stamp):
    assert page_meta({"Published": stamp}, "https://a.test/", "acme.test").published_at is None


def test_missing_published_has_no_time():
    assert page_meta({}, "https://a.test/", "acme.test").published_at is None
