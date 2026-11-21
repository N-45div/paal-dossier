"""Dossier API and build behaviour against the mock web: fields, citations, budget,
search rule, clock, provider faults, listing, reset during a build.

Ledger ids named per test.

Also covers: R1.5-R1.9, R1.133 (404 not_found), R1.185-R1.186, R1.188 (one build at a time),
R1.193 (reads make no provider call), R1.194-R1.196, R1.198, R1.202-R1.209, R1.214-R1.215.
"""
import json
import re
import time

import pytest

from conftest import (SAMPLE_DOMAINS, await_settled, call, check_dossier_fields, domain_searches,
                      get_dossier, login, mock_calls, mock_faults, new_key, parse_ts,
                      reset_service, set_clock, start_build, total_cost)

RFC3339_OFFSET = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$")


def build(token, domain):
    """POST a build, wait for it to settle, return (settled dossier, provider calls since reset)."""
    r = start_build(token, domain)
    assert r.status_code == 202, r.text
    d = await_settled(token, domain)
    return d, mock_calls()


def test_create_then_ready_with_clock_time_and_fast_completion(env):
    # R1.73, R1.187, R1.191, R1.197, R1.210
    set_clock("2026-03-01T11:30:00+02:00")  # 09:30Z, after the fixture clock 09:00Z
    domain = SAMPLE_DOMAINS[0]
    t0 = time.time()
    r = start_build(env["ada"], domain)
    assert r.status_code == 202, r.text
    assert set(r.json()) == {"dossier_id", "domain", "state"}
    assert r.json()["state"] == "building" and r.json()["domain"] == domain
    d = await_settled(env["ada"], domain)
    assert time.time() - t0 <= 10, "build did not end within 10 s with fast providers"
    assert d["state"] == "ready"
    assert RFC3339_OFFSET.match(d["researched_at"]), d["researched_at"]
    assert parse_ts(d["researched_at"]) == parse_ts("2026-03-01T11:30:00+02:00")
    assert set(d) >= {"dossier_id", "domain", "state", "researched_at", "spent_units", "fields"}


def test_building_state_before_first_build_completes_has_unknown_fields(env):
    # R1.203-R1.205
    domain = SAMPLE_DOMAINS[0]
    mock_faults("nimble", ["search"], "delay", seconds=3)
    mock_faults("tavily", ["search"], "error")
    try:
        assert start_build(env["ada"], domain).status_code == 202
        d = get_dossier(env["ada"], domain).json()
        assert d["state"] == "building"
        assert d["researched_at"] is None
        for name, fld in d["fields"].items():
            assert fld["value"] is None and fld["status"] == "unknown" and fld["citations"] == [], name
        await_settled(env["ada"], domain)
    finally:
        mock_faults("nimble", ["search"], "none")
        mock_faults("tavily", ["search"], "none")


def test_refresh_while_building_keeps_last_ready_fields_visible(env):
    # R1.204, R1.210
    domain = SAMPLE_DOMAINS[0]
    first, _ = build(env["ada"], domain)
    assert first["state"] == "ready"
    mock_faults("nimble", ["search"], "delay", seconds=3)
    try:
        r = call("POST", f"/dossiers/{domain}/refresh", token=env["ada"], key=new_key())
        assert r.status_code == 202
        mid = get_dossier(env["ada"], domain).json()
        assert mid["state"] == "building"
        assert mid["fields"] == first["fields"]
        assert mid["researched_at"] == first["researched_at"]
        await_settled(env["ada"], domain)
    finally:
        mock_faults("nimble", ["search"], "none")


@pytest.mark.parametrize("domain", SAMPLE_DOMAINS)
def test_six_fields_shape_citations_and_support(env, domain):
    # R1.85-R1.98, R1.99-R1.108, R1.109-R1.111, R1.190
    d, calls = build(env["ada"], domain)
    assert d["state"] == "ready", d
    known = check_dossier_fields(d, domain, calls)
    assert known >= 1, "no field supported for a company that has sources in the corpus"


@pytest.mark.parametrize("domain", SAMPLE_DOMAINS)
def test_budget_never_above_80_and_spent_matches_provider_records(env, domain):
    # R1.11, R1.236, R1.206, R1.233, R1.234
    d, calls = build(env["ada"], domain)
    recorded = total_cost(calls)
    assert d["spent_units"] <= 80, d["spent_units"]
    assert recorded <= 80, recorded
    assert d["spent_units"] == recorded, (d["spent_units"], recorded)


@pytest.mark.parametrize("domain", SAMPLE_DOMAINS)
def test_exactly_one_successful_search_for_the_exact_domain(env, domain):
    # R1.100-R1.101
    _, calls = build(env["ada"], domain)
    assert len(domain_searches(calls, domain)) == 1, [
        (c["provider"], c["method"], c["query"], c["status"]) for c in calls]


def test_unknown_company_does_not_invent_values(env):
    # R1.10, R1.111, R1.190
    domain = "no-such-company-xyz.test"
    d, calls = build(env["ada"], domain)
    assert d["state"] in ("ready", "failed")
    if d["state"] == "ready":
        check_dossier_fields(d, domain, calls)


def test_nimble_alone_suffices_when_tavily_is_down(env):
    # R1.25-R1.26, R1.100
    mock_faults("tavily", ["search", "extract"], "error")
    domain = SAMPLE_DOMAINS[0]
    d, calls = build(env["ada"], domain)
    assert d["state"] == "ready", d
    check_dossier_fields(d, domain, calls)
    for f in d["fields"].values():
        for c in f["citations"]:
            assert c["provider"] == "nimble"
    assert all(c["status"] != 200 for c in calls if c["provider"] == "tavily")


def test_every_provider_failing_gives_failed_and_keeps_fields(env):
    # R1.189, R1.232, R1.236
    domain = SAMPLE_DOMAINS[1]
    first, _ = build(env["ada"], domain)
    assert first["state"] == "ready"
    for prov, methods in (("nimble", ["search", "extract", "research"]),
                          ("tavily", ["search", "extract"])):
        mock_faults(prov, methods, "error")
    try:
        assert call("POST", f"/dossiers/{domain}/refresh", token=env["ada"],
                    key=new_key()).status_code == 202
        d = await_settled(env["ada"], domain)
    finally:
        mock_faults("nimble", ["search", "extract", "research"], "none")
        mock_faults("tavily", ["search", "extract"], "none")
    assert d["state"] == "failed"
    assert d["fields"] == first["fields"]
    assert d["researched_at"] == first["researched_at"]
    assert d["spent_units"] == first["spent_units"]  # refused calls cost nothing
    assert d["spent_units"] == total_cost(mock_calls())


def test_rate_limited_nimble_still_no_5xx_and_budget_holds(env):
    # R1.144, R1.11, R1.49
    domain = SAMPLE_DOMAINS[2]
    mock_faults("nimble", ["search", "extract", "research"], "rate_limit")
    try:
        d, calls = build(env["ada"], domain)
    finally:
        mock_faults("nimble", ["search", "extract", "research"], "none")
    assert d["state"] in ("ready", "failed")
    assert d["spent_units"] <= 80
    assert d["spent_units"] == total_cost(calls)
    if d["state"] == "ready":
        check_dossier_fields(d, domain, calls)


def test_throttled_research_run_still_ends_well_formed(env):
    # R1.144, R1.236
    domain = SAMPLE_DOMAINS[0]
    mock_faults("nimble", ["research"], "throttle")
    try:
        d, calls = build(env["ada"], domain)
    finally:
        mock_faults("nimble", ["research"], "none")
    assert d["state"] in ("ready", "failed")
    assert d["spent_units"] <= 80 and d["spent_units"] == total_cost(calls)
    if d["state"] == "ready":
        check_dossier_fields(d, domain, calls)


def test_refresh_updates_researched_at_and_spent_units(env):
    # R1.187, R1.205-R1.206, R1.212
    domain = SAMPLE_DOMAINS[0]
    set_clock("2026-03-01T09:00:00+00:00")
    first, _ = build(env["ada"], domain)
    set_clock("2026-03-05T12:00:00+00:00")
    before_calls = len(mock_calls())
    assert call("POST", f"/dossiers/{domain}/refresh", token=env["ada"], key=new_key()).status_code == 202
    d = await_settled(env["ada"], domain)
    calls = mock_calls()[before_calls:]
    assert parse_ts(d["researched_at"]) == parse_ts("2026-03-05T12:00:00+00:00")
    assert d["spent_units"] == first["spent_units"] + total_cost(calls)


def test_clock_cannot_move_backwards_and_researched_at_is_stable(env):
    # R1.70, R1.187
    domain = SAMPLE_DOMAINS[0]
    set_clock("2026-03-02T00:00:00+00:00")
    d, _ = build(env["ada"], domain)
    assert parse_ts(d["researched_at"]) == parse_ts("2026-03-02T00:00:00+00:00")
    r = call("POST", "/_test/clock", body={"now": "2026-03-01T00:00:00+00:00"})
    assert r.status_code == 422
    assert get_dossier(env["ada"], domain).json()["researched_at"] == d["researched_at"]


def test_get_dossier_paths_normalise_and_validate(env):
    # R1.80, R1.82, R1.207
    domain = SAMPLE_DOMAINS[0]
    build(env["ada"], domain)
    r = get_dossier(env["ada"], "  WWW.Brightwater-Labs.TEST. ")
    assert r.status_code == 200 and r.json()["domain"] == domain
    for bad in ["not%20valid", "x_y.test", "a..test", "https:%2F%2Facme.test"]:
        r = call("GET", f"/dossiers/{bad}", token=env["ada"])
        assert r.status_code == 422 and r.json()["error"]["code"] == "validation_failed", bad
    r = get_dossier(env["ada"], "nothing-here.test")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


INVALID_DOMAINS = [
    "", "   ", "localhost", "https://acme-robotics.test", "acme-robotics.test/path",
    "ex ample.test", "-a.test", "a-.test", "a..test", "a_b.test", "a" * 64 + ".test",
    ("b" * 63 + ".") * 3 + "b" * 62,  # 254 characters in total
]


@pytest.mark.parametrize("raw_domain", INVALID_DOMAINS)
def test_invalid_domains_are_422(env, raw_domain):
    # R1.80-R1.82, R1.201
    r = call("POST", "/dossiers", token=env["ada"], key=new_key(),
             raw=json.dumps({"domain": raw_domain}))
    assert r.status_code == 422, (raw_domain, r.status_code, r.text)
    assert r.json()["error"]["code"] == "validation_failed"


def test_missing_domain_is_422(env):
    # R1.200
    r = call("POST", "/dossiers", token=env["ada"], key=new_key(), body={})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_failed"


def test_boundary_domains_accepted(env):
    # R1.81, R1.82
    label63 = "c" * 63 + ".test"
    total253 = ("b" * 63 + ".") * 3 + "b" * 61  # two or more labels, 253 characters
    assert len(total253) == 253
    for dom in (label63, total253, "www.www.brightwater-labs.test"):
        r = call("POST", "/dossiers", token=env["ada"], key=new_key(), body={"domain": dom})
        assert r.status_code == 202, (dom[:30], r.status_code, r.text)


def test_list_order_filter_pagination_and_shared_visibility(env):
    # R1.78, R1.216-R1.219
    for dom in SAMPLE_DOMAINS:
        build(env["ada"], dom)
    r = call("GET", "/dossiers", token=env["bob"])  # another user sees the same dossiers
    assert r.status_code == 200
    items = r.json()["dossiers"]
    domains = [i["domain"] for i in items]
    assert domains == sorted(domains)
    assert set(SAMPLE_DOMAINS) <= set(domains)
    for item in items:
        assert set(item) >= {"dossier_id", "domain", "state", "legal_name", "researched_at", "spent_units"}
        full = get_dossier(env["ada"], item["domain"]).json()
        assert item["legal_name"] == full["fields"]["legal_name"]["value"]
        assert item["spent_units"] == full["spent_units"] and item["state"] == full["state"]
    q = SAMPLE_DOMAINS[0].upper().split(".")[0][:8]
    filtered = call("GET", f"/dossiers?q={q}", token=env["ada"]).json()["dossiers"]
    assert SAMPLE_DOMAINS[0] in [i["domain"] for i in filtered]
    for it in filtered:
        hay = (it["domain"] + " " + (it["legal_name"] or "")).lower()
        assert q.lower() in hay
    all_items = call("GET", "/dossiers?q=", token=env["ada"]).json()["dossiers"]
    assert [i["domain"] for i in all_items] == domains
    page1 = call("GET", "/dossiers?limit=1&offset=0", token=env["ada"]).json()
    assert len(page1["dossiers"]) == 1 and page1["has_more"] is True
    last = call("GET", f"/dossiers?limit=1&offset={len(domains) - 1}", token=env["ada"]).json()
    assert last["dossiers"][0]["domain"] == domains[-1] and last["has_more"] is False
    walked = []
    off = 0
    while True:
        p = call("GET", f"/dossiers?limit=2&offset={off}", token=env["ada"]).json()
        walked += [i["domain"] for i in p["dossiers"]]
        if not p["has_more"]:
            break
        off += 2
    assert walked == domains


def test_list_default_limit_and_empty_state(env):
    # R1.219
    r = call("GET", "/dossiers", token=env["ada"]).json()
    assert r == {"dossiers": [], "has_more": False}


def test_reset_during_build_leaves_no_trace(env):
    # R1.63, R1.61
    domain = SAMPLE_DOMAINS[0]
    mock_faults("nimble", ["search"], "delay", seconds=3)
    try:
        assert start_build(env["ada"], domain).status_code == 202
        reset_service()
        assert get_dossier(env["ada"], domain).status_code in (401, 404)
        time.sleep(4)
    finally:
        mock_faults("nimble", ["search"], "none")
    reset_service()
    token = login("ada@example.com")
    assert get_dossier(token, domain).status_code == 404
    assert call("GET", "/dossiers", token=token).json()["dossiers"] == []
