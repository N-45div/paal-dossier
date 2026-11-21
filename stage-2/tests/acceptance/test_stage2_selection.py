"""Stage 2: candidates, the selection rule, status, and citations, checked against the
Prover's independent selection oracle (selection_oracle.py).

Corpus companies used: rank-co.test (own 2010 vs news 2012 vs aggregator 2013; the own page
wins and the field is contested), recency-co.test (two news pages; the later one wins).
Ledger ids are named per test: R2.52-R2.74 (candidates, selection, status), Rul-S2-8.
"""
import json

import pytest

from conftest import call, await_settled, check_dossier_fields, login, mock_calls, start_build, reset_service
from selection_oracle import expected_citations, expected_status, rank_key

RANK = "rank-co.test"
RECENCY = "recency-co.test"
CAND_KEYS = {"value", "url", "excerpt", "provider", "kind", "published_at", "retrieved_at", "selected"}


def _build(env, domain):
    assert start_build(env["ada"], domain).status_code == 202
    return await_settled(env["ada"], domain, timeout=120)


def _check_field_selection(name, fld, dossier, domain):
    cands = fld["candidates"]
    assert isinstance(cands, list), name
    for c in cands:
        assert set(c) >= CAND_KEYS, (name, set(c))
    # candidates are listed in the rank order of the oracle, selected first
    assert [rank_key(c) for c in cands] == sorted(rank_key(c) for c in cands), name
    selected = [c for c in cands if c["selected"]]
    if cands:
        assert len(selected) == 1 and cands[0]["selected"] is True, name
        assert fld["value"] == cands[0]["value"], name
    else:
        assert selected == [] and fld["value"] is None and fld["status"] == "unknown", name
    assert fld["status"] == expected_status(cands), (name, fld["status"])
    assert fld["citations"] == expected_citations(cands), name
    # retrieved_at is the time of the build that gathered the candidate
    for c in cands:
        assert c["retrieved_at"] == dossier["researched_at"], name
    # one candidate per (value, page) (Rul-S2-8): no two share field, value and url
    keys = [(c["value"], c["url"]) for c in cands]
    assert len(keys) == len(set(keys)), (name, keys)


def test_every_field_has_candidates_list_and_consistent_selection(env):
    # R2.52, R2.55, R2.57, R2.58, R2.60-R2.68, R2.69-R2.74
    for domain in ("brightwater-labs.test", "ferncliff-foods.test", "tidemark-energy.test"):
        d = _build(env, domain)
        assert d["state"] == "ready", d["state"]
        for name, fld in d["fields"].items():
            _check_field_selection(name, fld, d, domain)
        check_dossier_fields(d, domain, mock_calls())


def test_own_page_beats_newer_news_and_aggregator_and_field_is_contested(env):
    # R2.60-R2.68 (authority first), R2.74 (contested)
    d = _build(env, RANK)
    fld = d["fields"]["founded_year"]
    assert fld["status"] == "contested"
    assert fld["value"] == 2010
    assert [c["kind"] for c in fld["candidates"]] == ["own", "news", "aggregator"]
    assert [c["value"] for c in fld["candidates"]] == [2010, 2012, 2013]
    assert [c["selected"] for c in fld["candidates"]] == [True, False, False]
    # the citations are only the candidates with the selected value
    assert [c["url"] for c in fld["citations"]] == [f"https://{RANK}/about"]
    _check_field_selection("founded_year", fld, d, RANK)


def test_later_news_page_wins_within_the_same_authority(env):
    # R2.60-R2.68 (recency within authority)
    d = _build(env, RECENCY)
    fld = d["fields"]["headcount_range"]
    assert fld["value"] == "1001-5000"
    assert fld["status"] == "contested"
    assert fld["candidates"][0]["url"] == f"https://news-b.test/recency"
    assert fld["candidates"][0]["selected"] is True
    _check_field_selection("headcount_range", fld, d, RECENCY)


def test_status_known_when_all_candidates_agree_and_unknown_without_any(env):
    # R2.69-R2.74
    d = _build(env, "brightwater-labs.test")
    for name, fld in d["fields"].items():
        if fld["candidates"]:
            values = {json.dumps(c["value"]) for c in fld["candidates"]}
            assert fld["status"] == ("known" if len(values) == 1 else "contested"), name
        else:
            assert fld["status"] == "unknown", name


def test_legal_name_in_list_is_the_selected_value(env):
    # R2.69-R2.74 (GET /dossiers legal_name = selected)
    _build(env, "brightwater-labs.test")
    listed = {i["domain"]: i for i in call("GET", "/dossiers", token=env["ada"]).json()["dossiers"]}
    item = listed["brightwater-labs.test"]
    full = call("GET", "/dossiers/brightwater-labs.test", token=env["ada"]).json()
    assert item["legal_name"] == full["fields"]["legal_name"]["value"]


def test_retrieved_at_is_the_build_time_of_the_last_ready_build(env):
    # R2.52, Rul-S2-1
    d1 = _build(env, RANK)
    assert all(c["retrieved_at"] == d1["researched_at"]
               for f in d1["fields"].values() for c in f["candidates"])


DUP = "dup-co.test"


def test_one_candidate_per_value_per_page_even_with_two_excerpts(env):
    # Rul-S2-8: one candidate per (field, value, url); two supporting sentences on one page
    # give one candidate, whose excerpt is the first supporting sentence in reading order.
    d = _build(env, DUP)
    fld = d["fields"]["founded_year"]
    keys = [(c["value"], c["url"]) for c in fld["candidates"]]
    assert keys == [(2010, f"https://{DUP}/about")], keys
    assert fld["candidates"][0]["excerpt"] == "Dup Co was founded in 2010.", fld["candidates"][0]["excerpt"]
    assert fld["status"] == "known"
    _check_field_selection("founded_year", fld, d, DUP)


TIE = "tie-co.test"


def test_equal_authority_and_date_selects_smaller_url(env):
    # R2.60-R2.68 (url order after authority and recency): two own pages with the same
    # published_at give different values; the smaller URL ranks first and is selected.
    d = _build(env, TIE)
    fld = d["fields"]["founded_year"]
    assert fld["status"] == "contested"
    assert fld["candidates"][0]["url"] == f"https://{TIE}/a-page", fld["candidates"][0]["url"]
    assert fld["value"] == 2012, fld["value"]
    assert [c["selected"] for c in fld["candidates"]] == [True, False]
    _check_field_selection("founded_year", fld, d, TIE)


TIE2 = "tie2-co.test"


def test_equal_authority_date_and_url_selects_smaller_value(env):
    # R2.60-R2.68 (value order after authority, recency, url, provider): one page gives two
    # different founding years; the smaller value ranks first and is selected.
    d = _build(env, TIE2)
    fld = d["fields"]["founded_year"]
    assert fld["status"] == "contested"
    assert [c["value"] for c in fld["candidates"]] == [2010, 2012], fld["candidates"]
    assert fld["value"] == 2010, fld["value"]
    assert [c["selected"] for c in fld["candidates"]] == [True, False]
    _check_field_selection("founded_year", fld, d, TIE2)
