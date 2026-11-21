"""Stage 4 origins, own pages and member rule (stage-4 spec, Own pages, Origins, Investors; ledger
R4.10-R4.18, R4.32, R4.38), black-box over HTTP against the real mock.

The mock corpus pages carry the lineage that the origin rules read: First-Published-By, Canonical,
registrant and page kind. The expectations below are the spec rules applied to those pages, not
values copied from the service. Each test names its ledger ids.
"""
import pytest

from conftest import await_settled, login, new_key, reset_service, start_build

import requests
from conftest import MOCK_URL, mock_reset, mock_weather

TIDEMARK = "tidemark-energy.test"
QUILLMATE = "quillmate.test"
LARKSPUR = "larkspur-health.test"
FERNCLIFF = "ferncliff-foods.test"
OSTRAVA = "ostrava-mobility.test"
BRIGHTWATER = "brightwater-labs.test"
DOMAINS = [TIDEMARK, QUILLMATE, LARKSPUR, FERNCLIFF, OSTRAVA, BRIGHTWATER]


@pytest.fixture(scope="module")
def built():
    """Build every corpus company once; tests read the candidates from these dossiers."""
    r = requests.get(MOCK_URL + "/_mock/health", timeout=5)
    assert r.status_code == 200, "mock web not reachable at MOCK_URL"
    mock_reset(0)
    mock_weather(False)
    reset_service()
    token = login("ada@example.com")
    out = {}
    for domain in DOMAINS:
        r = start_build(token, domain, key=new_key())
        assert r.status_code == 202, r.text
        out[domain] = await_settled(token, domain, timeout=120)
    return out


def _candidates(dossier, url_part):
    """Every candidate of every field whose page URL contains url_part."""
    return [c for fld in dossier["fields"].values() for c in fld["candidates"] if url_part in c["url"]]


def test_first_published_by_is_the_origin(built):
    # R4.12, R4.13: the origin is the First-Published-By domain when the page has one
    cs = _candidates(built[TIDEMARK], "/2025/06/inside-the-rise-of-tidemark-energy")
    assert cs, "no candidate from the First-Published-By pages"
    assert {c["origin"] for c in cs} == {"pressline.test"}, [(c["url"], c["origin"]) for c in cs]


def test_canonical_original_origin_and_same_origin_is_one_source(built):
    # R4.14 (canonical URL that is not the page's own: the original's origin), R4.18 (pages with the
    # same origin are one source, however many URLs they have)
    cs = _candidates(built[QUILLMATE], "/2025/06/quillmate-eyes-new-markets")
    by_host = {c["url"].split("/")[2]: c["origin"] for c in cs}
    assert by_host.get("harbourdaily.test") == "pressline.test", by_host
    assert by_host.get("businessbeat.test") == "pressline.test", by_host
    for fld in built[QUILLMATE]["fields"].values():
        if fld["origins"]:
            assert len(fld["origins"]) == len(set(fld["origins"])), fld["origins"]


def test_canonical_chain_follows_at_most_three_urls(built):
    # R4.17: rule 2 follows Canonical URLs; the chain larkspur -> metroherald -> pressline ends at
    # the host of the last URL when no provider serves a page there, and origin is pressline.test
    cs = _candidates(built[LARKSPUR], "/2025/04/larkspur-health-bets-on-remote-physiotherapy-apps")
    assert cs, "no candidate from the canonical-chain pages"
    assert {c["origin"] for c in cs} == {"pressline.test"}, [(c["url"], c["origin"]) for c in cs]


def test_registrant_is_the_origin_when_no_other_rule_applies(built):
    # R4.16: the origin is the registrant when First-Published-By and Canonical do not apply
    cs = _candidates(built[BRIGHTWATER], "companyfile.test/companies/brightwater-labs")
    assert cs, "no candidate from the aggregator profile page"
    assert {c["origin"] for c in cs} == {"companyfile.test"}, [(c["url"], c["origin"]) for c in cs]


def test_lookalike_own_page_has_company_domain_as_origin_and_aggregator_kind(built):
    # R4.10 (own only when the registrant is the company's domain; else kind aggregator),
    # R4.11 (lookalike: states Kind: own, registrant is not the host of its URL),
    # R4.15 (rule 3: origin is the company's domain for a lookalike)
    for domain, part in ((FERNCLIFF, "getferncliff-foods.test/about-us"),
                         (OSTRAVA, "ostrava-mobility-group.test/about-us"),
                         (BRIGHTWATER, "getbrightwater-labs.test/about-us")):
        cs = _candidates(built[domain], part)
        assert cs, f"no candidate from the lookalike page {part}"
        for c in cs:
            assert c["origin"] == domain, (domain, c)
            assert c["kind"] == "aggregator", (domain, c)


def test_investor_member_needs_own_filing_or_two_origins(built):
    # R4.32: a name is a member when a candidate with that name is own or filing, or its candidates
    # have two or more distinct origins. A name whose candidates are all one non-filing origin is not
    # a member, so it is not in the investors value.
    for domain, d in built.items():
        fld = d["fields"]["investors"]
        value = set(fld["value"] or [])
        by_name = {}
        for c in fld["candidates"]:
            by_name.setdefault(c["value"], []).append(c)
        for name, cs in by_name.items():
            if any(c.get("kind") in ("own", "filing") for c in cs):
                continue
            if len({c["origin"] for c in cs}) < 2:
                assert name not in value, (domain, name, [(c["url"], c["origin"]) for c in cs])


def test_member_true_from_and_field_true_from(built):
    # R4.38: a member's true_from is the earliest non-null true_from among its candidates (null when
    # all are null); the field's true_from is the latest of its members', or null when the value is
    # null or any member's is null.
    for domain, d in built.items():
        fld = d["fields"]["investors"]
        if fld["value"] is None:
            assert fld.get("true_from") is None, (domain, fld.get("true_from"))
            continue
        member_from = {}
        for name in fld["value"]:
            froms = [c.get("true_from") for c in fld["candidates"] if c["value"] == name and c.get("true_from")]
            member_from[name] = min(froms) if froms else None
        if any(v is None for v in member_from.values()):
            expected = None
        else:
            expected = max(member_from.values())
        assert fld.get("true_from") == expected, (domain, fld.get("true_from"), member_from)
