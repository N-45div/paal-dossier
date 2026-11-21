"""Export/import (section 10), concurrency and bursts (section 11), limits (section 2).

Ledger ids named per test.

Also covers: R1.256 (requirements hold at every read, under bursts).
"""
import concurrent.futures as cf
import json
import time

import requests

from conftest import (BASE_URL, PASSWORD, SAMPLE_DOMAINS, await_settled, call, domain_searches,
                      get_dossier, login, mock_calls, mock_faults, new_key, parse_ts,
                      reset_service, seed_fixture, set_clock, start_build, total_cost)


def _export():
    r = call("GET", "/_test/export", timeout=10)
    assert r.status_code == 200, r.text
    return r


def _import(payload):
    return call("POST", "/_test/import", body=payload, timeout=10)


def _export_payload():
    return _export().json()


def test_export_shape_and_no_plaintext_passwords(env):
    # R1.238, R1.239, R1.241, R1.160-R1.161
    start_build(env["ada"], SAMPLE_DOMAINS[0])
    await_settled(env["ada"], SAMPLE_DOMAINS[0])
    r = _export()
    body = r.json()
    assert body["track"] == "dossier" and body["format_version"] == 1
    assert isinstance(body["state"], dict)
    assert PASSWORD not in r.text, "export contains a plaintext password"


def test_export_import_round_trip_keeps_dossiers_tokens_and_replays(env):
    # R1.242-R1.249, R1.181-R1.182
    domain = SAMPLE_DOMAINS[0]
    key = new_key()
    r = start_build(env["ada"], domain, key)
    assert r.status_code == 202
    before_body = r.json()
    settled = await_settled(env["ada"], domain)
    carol = call("POST", "/auth/signup", body={"email": "carol@example.com",
                                               "password": "correct horse",
                                               "display_name": "Carol"}).json()
    payload = _export_payload()
    reset_service(seed_fixture(now="2026-06-01T00:00:00+00:00"))
    assert _import(payload).status_code == 204
    ada = login("ada@example.com")
    after = get_dossier(ada, domain).json()
    assert after == settled
    assert call("GET", "/dossiers", token=carol["token"]).status_code == 200  # old token survives
    calls_before = len(mock_calls())
    replay = start_build(ada, domain, key)
    assert replay.status_code == 200 and replay.json() == before_body
    assert len(mock_calls()) == calls_before  # imported dossiers are not researched again


def test_import_is_replacement_and_repeatable(env):
    # R1.243-R1.244, R1.250, R1.251
    domain = SAMPLE_DOMAINS[1]
    start_build(env["ada"], domain)
    await_settled(env["ada"], domain)
    payload = _export_payload()
    late = call("POST", "/auth/signup", body={"email": "late@example.com",
                                              "password": "correct horse", "display_name": "Late"}).json()
    for _ in range(2):
        assert _import(payload).status_code == 204
    assert call("GET", "/dossiers", token=late["token"]).status_code == 401  # previous credentials removed
    listed = call("GET", "/dossiers", token=login("ada@example.com")).json()["dossiers"]
    assert [d["domain"] for d in listed] == [domain]  # no duplication


def test_invalid_import_changes_nothing(env):
    # R1.243 (422 / 400 rules of section 10)
    domain = SAMPLE_DOMAINS[0]
    start_build(env["ada"], domain)
    settled = await_settled(env["ada"], domain)
    good = _export_payload()
    bad_payloads = [
        {"track": "other", "format_version": 1, "state": good["state"]},
        {"track": "dossier", "format_version": 2, "state": good["state"]},
        {"track": "dossier", "format_version": 1},
        {"track": "dossier", "format_version": 1, "state": "garbage"},
    ]
    for p in bad_payloads:
        r = _import(p)
        assert r.status_code == 422 and r.json()["error"]["code"] == "validation_failed", p
        assert get_dossier(env["ada"], domain).json() == settled
    r = call("POST", "/_test/import", raw="{not json", timeout=10)
    assert r.status_code == 400 and r.json()["error"]["code"] == "malformed_request"
    assert get_dossier(env["ada"], domain).json() == settled


def test_import_keeps_clock_and_makes_no_provider_call(env):
    # R1.252, R1.247
    domain = SAMPLE_DOMAINS[0]
    set_clock("2026-03-01T09:00:00+00:00")
    start_build(env["ada"], domain)
    await_settled(env["ada"], domain)
    payload = _export_payload()
    set_clock("2026-03-10T00:00:00+00:00")
    before = len(mock_calls())
    assert _import(payload).status_code == 204
    assert len(mock_calls()) == before
    assert parse_ts(get_dossier(env["ada"], domain).json()["researched_at"]) == parse_ts(
        "2026-03-01T09:00:00+00:00")
    # the clock is still 2026-03-10: a refresh now stamps that time
    token = login("ada@example.com")
    assert call("POST", f"/dossiers/{domain}/refresh", token=token, key=new_key()).status_code == 202
    d = await_settled(token, domain)
    assert parse_ts(d["researched_at"]) == parse_ts("2026-03-10T00:00:00+00:00")


def test_export_taken_during_build_holds_pre_build_state(env):
    # R1.254, Rul-7
    domain = SAMPLE_DOMAINS[0]
    start_build(env["ada"], domain)
    first = await_settled(env["ada"], domain)
    mock_faults("nimble", ["search"], "delay", seconds=4)
    try:
        assert call("POST", f"/dossiers/{domain}/refresh", token=env["ada"], key=new_key()).status_code == 202
        payload = _export_payload()
        time.sleep(5)  # let the in-flight build finish against the live service
    finally:
        mock_faults("nimble", ["search"], "none")
    reset_service(seed_fixture())
    assert _import(payload).status_code == 204
    restored = get_dossier(login("ada@example.com"), domain).json()
    assert restored["state"] == "ready"
    assert restored["fields"] == first["fields"]
    assert restored["researched_at"] == first["researched_at"]


def test_export_and_import_need_no_auth(env):
    # R1.239
    r = requests.get(BASE_URL + "/_test/export", timeout=10)
    assert r.status_code == 200
    r = requests.post(BASE_URL + "/_test/import", json=r.json(), timeout=10)
    assert r.status_code == 204


def test_burst_identical_refresh_takes_effect_once(env):
    # R1.180, R1.144, R1.255
    domain = SAMPLE_DOMAINS[0]
    start_build(env["ada"], domain)
    await_settled(env["ada"], domain)
    before_searches = len(domain_searches(mock_calls(), domain))
    key = new_key()

    def go(_):
        t0 = time.time()
        r = call("POST", f"/dossiers/{domain}/refresh", token=env["ada"], key=key)
        return r.status_code, r.json() if r.status_code < 500 else None, time.time() - t0

    with cf.ThreadPoolExecutor(max_workers=50) as ex:
        results = list(ex.map(go, range(50)))
    codes = [c for c, _, _ in results]
    assert codes.count(202) == 1 and codes.count(200) == 49, codes
    assert all(t < 5 for _, _, t in results)
    bodies = {json.dumps(b, sort_keys=True) for _, b, _ in results}
    assert len(bodies) == 1
    await_settled(env["ada"], domain)
    assert len(domain_searches(mock_calls(), domain)) == before_searches + 1


def test_burst_conflicting_bodies_same_key_one_winner(env):
    # R1.173, R1.255
    key = new_key()
    domains = [f"burst-{i}.test" for i in range(30)]

    def go(dom):
        r = call("POST", "/dossiers", token=env["ada"], key=key, body={"domain": dom})
        return r.status_code, r.json() if r.status_code < 500 else None

    with cf.ThreadPoolExecutor(max_workers=30) as ex:
        results = list(ex.map(go, domains))
    codes = [c for c, _ in results]
    assert all(c < 500 for c in codes), codes
    assert codes.count(202) == 1 and codes.count(409) == 29, codes
    winner = next(b["domain"] for c, b in results if c == 202)
    listed = call("GET", "/dossiers?limit=200", token=env["ada"]).json()["dossiers"]
    assert [d["domain"] for d in listed] == [winner]
    await_settled(env["ada"], winner)


def test_mixed_burst_no_5xx_and_request_time_limit(env):
    # R1.144, R1.48, R1.49
    domains = SAMPLE_DOMAINS + [f"mixed-{i}.test" for i in range(7)]

    def op(i):
        k = i % 6
        t0 = time.time()
        if k == 0:
            r = start_build(env["ada"], domains[i % len(domains)])
        elif k == 1:
            r = call("GET", "/dossiers?limit=5", token=env["ada"])
        elif k == 2:
            r = call("GET", "/dossiers/nothing-here.test", token=env["ada"])
        elif k == 3:
            r = call("POST", "/auth/login", body={"email": "ada@example.com", "password": "wrong"})
        elif k == 4:
            r = call("POST", "/dossiers", token=env["bob"], key=new_key(), body={"domain": "bad domain"})
        else:
            r = call("POST", "/dossiers", token=env["ada"], key=new_key(), body={"domain": domains[i % len(domains)]})
        return r.status_code, time.time() - t0

    with cf.ThreadPoolExecutor(max_workers=50) as ex:
        results = list(ex.map(op, range(50)))
    assert all(code < 500 for code, _ in results), [c for c, _ in results]
    assert all(t <= 5 for _, t in results), max(t for _, t in results)
    for dom in domains:
        await_settled(env["ada"], dom, timeout=120)


def test_concurrent_builds_each_respect_budget(env):
    # R1.11, R1.236, R1.144
    domains = [f"parallel-{i}.test" for i in range(8)] + SAMPLE_DOMAINS
    with cf.ThreadPoolExecutor(max_workers=11) as ex:
        list(ex.map(lambda d: start_build(env["ada"], d), domains))
    for dom in domains:
        d = await_settled(env["ada"], dom, timeout=120)
        assert d["spent_units"] <= 80, (dom, d["spent_units"])
    assert total_cost(mock_calls()) <= 80 * len(domains)
