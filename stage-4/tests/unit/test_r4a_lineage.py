"""R4A lineage (stage 4, R4.5-R4.18): header lines, kinds, lookalikes and origins. Pure and async
on fake pages; no HTTP and no provider."""

from __future__ import annotations

import asyncio
import unittest

from app.gateway import ServedPage
from app.lineage import host_of, lineage_of
from app.origins import OriginResolver
from app.pages import page_meta

COMPANY = "acme-robotics.test"


def page(url: str, **headers: str) -> ServedPage:
    return ServedPage(url=url, prose="", headers=headers)


class LineageHeadersTest(unittest.TestCase):

    def test_registrant_defaults_to_the_host_of_the_own_url(self):
        # R4.9: a page with no valid Registrant line has the host of its own URL as registrant.
        assert lineage_of({}, "https://Acme-Robotics.test/about").registrant == COMPANY

    def test_invalid_registrant_falls_back_to_the_host(self):
        # R4.9: an invalid Registrant line falls back to the host of the page's own URL.
        assert lineage_of({"Registrant": "not a domain"}, "https://news.test/x").registrant == "news.test"

    def test_registrant_and_first_published_by_are_normalised(self):
        # R4.6 (Registrant line) and R4.8 (First-Published-By line), both normalised as in section 4 (R4.9).
        lineage = lineage_of({"Registrant": "WWW.Acme-Robotics.test.",
                              "First-Published-By": "Wire.Test"}, "https://mirror.test/x")
        assert (lineage.registrant, lineage.first_published_by) == (COMPANY, "wire.test")

    def test_canonical_must_be_an_http_url_with_a_host(self):
        # R4.7: the Canonical line names the original URL; only an http(s) URL with a host counts.
        assert lineage_of({"Canonical": "https://acme-robotics.test/a"}, "https://x.test/").canonical \
            == "https://acme-robotics.test/a"
        assert lineage_of({"Canonical": "ftp://acme-robotics.test/a"}, "https://x.test/").canonical is None
        assert lineage_of({"Canonical": "https:///nohost"}, "https://x.test/").canonical is None

    def test_host_of_normalises(self):
        assert host_of("https://WWW.Acme-Robotics.test:443/x") == COMPANY


class KindsTest(unittest.TestCase):

    def test_registrant_decides_own(self):
        assert page_meta({"Kind": "own", "Registrant": COMPANY}, "https://news.test/x", COMPANY).kind == "own"

    def test_declared_own_for_another_registrant_is_an_aggregator(self):
        meta = page_meta({"Kind": "own", "Registrant": "other.test"}, "https://other.test/x", COMPANY)
        assert meta.kind == "aggregator"

    def test_lookalike_is_own_stated_with_registrant_not_the_host(self):
        # R4.11: Kind own, registrant other.test, the page served from acme-robotics-news.test.
        headers = {"Kind": "own", "Registrant": "other.test"}
        meta = page_meta(headers, "https://acme-robotics-news.test/x", COMPANY)
        assert meta.lookalike is True
        assert meta.kind == "aggregator"

    def test_no_registrant_line_means_the_host_is_the_registrant_so_no_lookalike(self):
        meta = page_meta({"Kind": "own"}, "https://acme-robotics-news.test/x", COMPANY)
        assert meta.lookalike is False

    def test_own_page_on_its_registrant_is_not_a_lookalike(self):
        meta = page_meta({"Kind": "own", "Registrant": COMPANY}, "https://acme-robotics.test/x", COMPANY)
        assert meta.lookalike is False and meta.kind == "own"


class OriginRulesTest(unittest.TestCase):
    """R4.12: each page's origin is taken from the first rule that applies, in this order:
    R4.13 First-Published-By, R4.14 the original of Canonical, R4.15 the company for a lookalike,
    R4.16 the registrant. R4.17: each original is fetched once."""

    def _origin(self, pages: dict[str, ServedPage], start: str, fetches: list[str] | None = None) -> str:
        calls = [] if fetches is None else fetches

        async def fetch(url: str):
            calls.append(url)
            return pages.get(url)

        resolver = OriginResolver(COMPANY, fetch)
        return asyncio.run(resolver.origin(pages[start]))

    def test_rule_one_first_published_by(self):
        # R4.13: rule 1, the First-Published-By domain.
        pages = {"https://news.test/a": page("https://news.test/a", **{"First-Published-By": "wire.test"})}
        assert self._origin(pages, "https://news.test/a") == "wire.test"

    def test_rule_two_follows_canonical_to_the_original(self):
        # R4.14: rule 2, the origin of the page at the Canonical URL (its original).
        original = page("https://acme-robotics.test/a")
        pages = {"https://mirror.test/a": page("https://mirror.test/a", Canonical="https://acme-robotics.test/a"),
                 "https://acme-robotics.test/a": original}
        fetches: list[str] = []
        assert self._origin(pages, "https://mirror.test/a", fetches) == COMPANY
        assert fetches == ["https://acme-robotics.test/a"]

    def test_three_canonical_hops_are_followed(self):
        # R4.14: rule 2 applied through three Canonical hops.
        pages = {
            "https://a.test/1": page("https://a.test/1", Canonical="https://b.test/2"),
            "https://b.test/2": page("https://b.test/2", Canonical="https://c.test/3"),
            "https://c.test/3": page("https://c.test/3", Canonical="https://d.test/4"),
            "https://d.test/4": page("https://d.test/4", **{"First-Published-By": "wire.test"}),
        }
        assert self._origin(pages, "https://a.test/1") == "wire.test"

    def test_a_fourth_canonical_hop_gives_the_host_of_that_url(self):
        # R4.14: rule 2 stops after three hops; the URL it reaches then gives its host.
        pages = {
            "https://a.test/1": page("https://a.test/1", Canonical="https://b.test/2"),
            "https://b.test/2": page("https://b.test/2", Canonical="https://c.test/3"),
            "https://c.test/3": page("https://c.test/3", Canonical="https://d.test/4"),
            "https://d.test/4": page("https://d.test/4", Canonical="https://e.test/5"),
            "https://e.test/5": page("https://e.test/5", **{"First-Published-By": "wire.test"}),
        }
        # Links followed: b, c, d. The fourth link (to e) is not followed: e's host stands in.
        assert self._origin(pages, "https://a.test/1") == "e.test"

    def test_no_provider_serving_the_original_gives_its_host(self):
        # R4.14: when no provider serves the original, the host of the Canonical URL stands in.
        pages = {"https://mirror.test/a": page("https://mirror.test/a", Canonical="https://gone.test/a")}
        assert self._origin(pages, "https://mirror.test/a") == "gone.test"

    def test_a_lookalike_takes_the_company_domain(self):
        # R4.15: rule 3, the company's domain for a lookalike page.
        pages = {"https://acme-robotics-news.test/x": page(
            "https://acme-robotics-news.test/x", Kind="own", Registrant="other.test")}
        assert self._origin(pages, "https://acme-robotics-news.test/x") == COMPANY

    def test_rule_four_is_the_registrant(self):
        # R4.16: rule 4, the registrant.
        pages = {"https://news.test/x": page("https://news.test/x")}
        assert self._origin(pages, "https://news.test/x") == "news.test"

    def test_each_original_is_fetched_once(self):
        # R4.17: a build obtains each original that rule 2 needs once, however many pages point to it.
        pages = {
            "https://m1.test/a": page("https://m1.test/a", Canonical="https://acme-robotics.test/a"),
            "https://m2.test/a": page("https://m2.test/a", Canonical="https://acme-robotics.test/a"),
            "https://acme-robotics.test/a": page("https://acme-robotics.test/a"),
        }
        fetches: list[str] = []

        async def fetch(url: str):
            fetches.append(url)
            return pages.get(url)

        resolved = asyncio.run(OriginResolver(COMPANY, fetch).resolve(
            [pages["https://m1.test/a"], pages["https://m2.test/a"]]))
        assert resolved == {"https://m1.test/a": COMPANY, "https://m2.test/a": COMPANY}
        assert fetches == ["https://acme-robotics.test/a"]
