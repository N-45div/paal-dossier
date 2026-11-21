"""Clauses the other files do not name directly: Appendix A tables (oracle level, no
service needed), the cost table and search/research rules (mock log), field shape,
clock rules, and the first-clock rule (run this file's fresh-start test first).

Ledger ids named per test.

Also covers: R1.115-R1.121 (headers, Facts, fixture shape).
"""
import datetime as dt

import pytest

from conftest import (SAMPLE_DOMAINS, await_settled, call, get_dossier, login, mock_calls,
                      mock_faults, new_key, parse_ts, reset_service, seed_fixture, set_clock,
                      start_build, total_cost)
from oracle import (FIELDS, HEADCOUNT_RANGES, LEGAL_SUFFIXES, NEGATING, STATEMENT,
                    prose_sentences, split_header, split_sentences, supported_values)

D = "acme-robotics.test"


# ---- Appendix A tables (no service) ---------------------------------------------

@pytest.mark.parametrize("field", FIELDS)
def test_every_statement_phrase_is_recognised(field):
    # R1.279-R1.284, R1.267, R1.271
    expected = {
        "legal_name": ("Acme Robotics, Inc.", "The {p} is Acme Robotics, Inc."),
        "hq_city": ("Lisbon", "Acme Robotics is {p} Lisbon."),
        "ceo": ("Dana Ruiz", "Acme Robotics {p} Dana Ruiz."),
        "founded_year": (2014, "Acme Robotics was {p} in 2014."),
        "headcount_range": ("51-200", "Acme Robotics has 120 {p}."),
        "funding_total": (12000000, "Acme Robotics {p} $12M."),
    }[field]
    value, template = expected
    for phrase in STATEMENT[field]:
        sent = template.format(p=phrase)
        got = supported_values(D, sent).get(field)
        assert got == value, (phrase, sent, got)


@pytest.mark.parametrize("neg", NEGATING)
def test_every_negating_phrase_blocks_support(neg):
    # R1.268, R1.285-R1.286
    assert supported_values(D, f"Acme Robotics {neg} be founded in 2014.") == {}, neg


@pytest.mark.parametrize("suffix", LEGAL_SUFFIXES)
def test_every_legal_suffix_forms_a_legal_name(suffix):
    # R1.295, R1.301-R1.302
    sent = f"The registered name is Acme Robotics, {suffix} today."
    assert supported_values(D, sent).get("legal_name") == f"Acme Robotics, {suffix}", suffix


def test_capitalised_uppercase_and_non_ascii_words():
    # R1.287-R1.291, R1.296-R1.297
    assert supported_values(D, "Acme Robotics is based in Zürich.") == {"hq_city": "Zürich"}
    assert supported_values(D, "Acme Robotics chief executive Hans Müller runs it.") == {"ceo": "Hans Müller"}
    assert supported_values(D, "The registered name is Acme Robotics AI Inc.") == {
        "legal_name": "Acme Robotics AI Inc."}


def test_number_forms_and_boundaries():
    # R1.292-R1.294, R1.298-R1.299
    assert supported_values(D, "Acme Robotics employs 1,200 people.") == {"headcount_range": "1001-5000"}
    assert supported_values(D, "Acme Robotics employs 12.5 people.") == {}
    assert supported_values(D, "Acme Robotics was founded in Q2014.") == {}
    assert supported_values(D, "Acme Robotics employs 10001 people.") == {"headcount_range": "10001+"}
    assert supported_values(D, "Acme Robotics employs 10 people.") == {"headcount_range": "1-10"}
    assert supported_values(D, "Acme Robotics employs 11 people.") == {"headcount_range": "11-50"}
    for lo, hi, label in HEADCOUNT_RANGES:
        if hi is not None:
            assert supported_values(D, f"Acme Robotics employs {hi} people.") == {"headcount_range": label}


def test_sentence_split_empty_and_space_rules():
    # R1.259, R1.262, R1.260
    assert prose_sentences("  \n \n") == []
    assert prose_sentences("A is based in Lisbon.\n\nB was founded in 2014.") == [
        "A is based in Lisbon.", "B was founded in 2014."]
    assert split_sentences("Ends with a period.Not a split.") == ["Ends with a period.Not a split."]
    assert split_sentences("Question? Yes!") == ["Question?", "Yes!"]


def test_phrase_with_collapsed_whitespace_matches_one_space():
    # R1.271
    assert supported_values(D, "Acme Robotics is based in  Lisbon.") == {"hq_city": "Lisbon"}


def test_facts_header_is_informative_and_other_headers_ignored():
    # R1.114-R1.120
    import json
    text = ('Kind: news\nFacts: {"founded_year": 2014, "ceo": "Dana Ruiz"}\nZeta: x\n\n'
            "Acme Robotics was founded in 2015.")
    headers, prose = split_header(text)
    assert json.loads(headers["Facts"]) == {"founded_year": 2014, "ceo": "Dana Ruiz"}
    assert prose == "Acme Robotics was founded in 2015."
    # the Facts value is not evidence: the prose decides
    assert supported_values(D, prose) == {"founded_year": 2015}


# ---- clock rules ---------------------------------------------------------------

def test_clock_stands_still_between_calls_and_reset_sets_it():
    # R1.68, R1.69, R1.66, R1.187
    reset_service(seed_fixture(now="2026-03-01T09:00:00+00:00"))
    ada = login("ada@example.com")
    first = start_build(ada, SAMPLE_DOMAINS[0])
    d1 = await_settled(ada, SAMPLE_DOMAINS[0])
    second = start_build(ada, SAMPLE_DOMAINS[1])
    d2 = await_settled(ada, SAMPLE_DOMAINS[1])
    assert first.status_code == 202 and second.status_code == 202
    assert parse_ts(d1["researched_at"]) == parse_ts("2026-03-01T09:00:00+00:00")
    assert parse_ts(d2["researched_at"]) == parse_ts("2026-03-01T09:00:00+00:00")


def test_timestamps_are_rfc3339_with_offset_everywhere():
    # R1.73, R1.66
    reset_service(seed_fixture(now="2026-03-01T09:00:00-05:00"))
    ada = login("ada@example.com")
    start_build(ada, SAMPLE_DOMAINS[0])
    d = await_settled(ada, SAMPLE_DOMAINS[0])
    assert parse_ts(d["researched_at"]) == parse_ts("2026-03-01T14:00:00+00:00")


# ---- identifiers, field shape, dossier fields ----------------------------------

def test_ids_are_opaque_and_at_most_64_characters(env):
    # R1.76, R1.84
    r = start_build(env["ada"], SAMPLE_DOMAINS[0])
    assert r.status_code == 202
    dossier_id = r.json()["dossier_id"]
    assert isinstance(dossier_id, str) and 1 <= len(dossier_id) <= 64
    await_settled(env["ada"], SAMPLE_DOMAINS[0])


def test_field_shape_has_exact_keys_and_six_fields(env):
    # R1.85, R1.94, R1.96, R1.97, R1.98
    domain = SAMPLE_DOMAINS[0]
    start_build(env["ada"], domain)
    d = await_settled(env["ada"], domain)
    assert set(d["fields"]) == set(FIELDS)
    for name, fld in d["fields"].items():
        assert set(fld) == {"value", "status", "citations"}, name
        if fld["value"] is not None:
            assert fld["status"] == "known"
            for c in fld["citations"]:
                assert set(c) == {"url", "excerpt", "provider"}, (name, c)
        else:
            assert fld["status"] == "unknown"


def test_list_fields_only_six_and_ignored_for_other_fields(env):
    # R1.12, R1.216
    domain = SAMPLE_DOMAINS[0]
    start_build(env["ada"], domain)
    d = await_settled(env["ada"], domain)
    assert "email" not in d["fields"] and "phone" not in d["fields"]
    listed = call("GET", "/dossiers", token=env["ada"]).json()["dossiers"][0]
    assert listed["legal_name"] == d["fields"]["legal_name"]["value"]


# ---- cost table and provider-call rules (checked against the mock's log) ------

def _expected_cost(c):
    p, m, depth = c["provider"], c["method"], c.get("depth")
    if m == "search":
        table = {("nimble", "lite"): 1, ("nimble", "fast"): 5, ("nimble", "deep"): 15,
                 ("tavily", "lite"): 8, ("tavily", "fast"): 16, ("tavily", "deep"): 16}
        return table.get((p, depth))
    if m == "extract":
        per = {"nimble": 1, "tavily": 2}[p]
        return per * len(c.get("urls") or [])
    if m == "research":
        return 25
    return None


def test_cost_table_and_search_rules_match_provider_records(env):
    # R1.220-R1.231, R1.235, R1.237
    domain = SAMPLE_DOMAINS[0]
    start_build(env["ada"], domain)
    await_settled(env["ada"], domain)
    calls = mock_calls()
    checked = 0
    for c in calls:
        if c["status"] != 200:
            assert c["cost"] == 0, c  # refused calls cost nothing (R1.232)
            continue
        exp = _expected_cost(c)
        if exp is None:
            continue
        assert c["cost"] == exp, (c["provider"], c["method"], c.get("depth"), c["cost"], exp)
        checked += 1
        if c["method"] == "search":
            assert len(c["served"]) <= 10  # R1.231
        if c["method"] == "research":
            name = domain.split(".")[0].replace("-", " ")
            assert domain in c["query"] or name in c["query"].lower()  # R1.237
            assert c["fields"] and set(c["fields"]) <= set(FIELDS)
    assert checked >= 2


def test_search_depths_are_webrouter_names(env):
    # R1.230
    domain = SAMPLE_DOMAINS[0]
    start_build(env["ada"], domain)
    await_settled(env["ada"], domain)
    for c in mock_calls():
        if c["method"] == "search":
            assert c.get("depth") in ("lite", "fast", "deep"), c


def test_tavily_extract_outage_costs_nothing_extra(env):
    # R1.232, R1.236
    mock_faults("tavily", ["extract", "search"], "error")
    domain = SAMPLE_DOMAINS[1]
    start_build(env["ada"], domain)
    d = await_settled(env["ada"], domain)
    calls = mock_calls()
    assert d["spent_units"] == total_cost(calls) <= 80
    assert all(c["cost"] == 0 for c in calls if c["provider"] == "tavily" and c["status"] != 200)


def test_budget_counts_provider_records_not_service_claims(env):
    # R1.233-R1.234: costs are counted from the provider's records, not from the service
    domain = SAMPLE_DOMAINS[0]
    start_build(env["ada"], domain)
    d = await_settled(env["ada"], domain)
    assert d["spent_units"] == total_cost(mock_calls())


# ---- search, rate and ordering --------------------------------------------------

# ---- export/import rules not covered elsewhere ---------------------------------

def test_failed_request_key_reusable_after_import(env):
    # R1.248, R1.174
    import json
    from conftest import call as _call
    key = new_key()
    r = _call("POST", "/dossiers", token=env["ada"], key=key, raw=json.dumps({"domain": "bad domain"}))
    assert r.status_code == 422
    exp = _call("GET", "/_test/export", timeout=10)
    assert exp.status_code == 200
    reset_service()
    assert _call("POST", "/_test/import", body=exp.json(), timeout=10).status_code == 204
    token = login("ada@example.com")
    r2 = _call("POST", "/dossiers", token=token, key=key, body={"domain": SAMPLE_DOMAINS[0]})
    assert r2.status_code == 202, r2.text
    await_settled(token, SAMPLE_DOMAINS[0])


def test_reads_make_no_provider_call(env):
    # R1.193, R1.192-R1.194 (reads and lists make no provider call)
    domain = SAMPLE_DOMAINS[0]
    start_build(env["ada"], domain)
    await_settled(env["ada"], domain)
    before = len(mock_calls())
    assert get_dossier(env["ada"], domain).status_code == 200
    assert call("GET", "/dossiers", token=env["ada"]).status_code == 200
    assert get_dossier(env["ada"], "nothing-here.test").status_code == 404
    assert len(mock_calls()) == before
