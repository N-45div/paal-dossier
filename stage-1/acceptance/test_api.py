"""Stage 1 HTTP contract, exercised only through the running image."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import time

import pytest

from conftest import NOW, SEED

DOMAIN = "halvorsen-robotics.test"


def error(response, status, code):
    assert response.status_code == status, response.text
    body = response.json()
    assert body["error"]["code"] == code
    assert isinstance(body["error"]["message"], str)


def create(c, token, domain=DOMAIN, key="create"):
    return c.request("POST", "/dossiers", headers=c.auth(token, key), json={"domain": domain})


def test_health_and_seed(client):
    """R1.22 R1.23 R1.24 R1.27 R1.60 R1.61 R1.78 R1.84."""
    c = client
    before = c.calls()
    response = c.request("GET", "/health")
    assert response.status_code == 200 and response.json() == {"status": "ok"}
    assert c.calls() == before
    response = c.request("POST", "/auth/login", json={"email": "ADA@example.com", "password": "correct horse"})
    assert response.status_code == 200
    assert response.json()["user_id"] == "u_ada"
    assert response.json()["display_name"] == "Ada"


def test_auth_validation(client):
    """R1.63 R1.64 R1.66 R1.69 R1.70 R1.72 R1.77 R1.79 R1.80 R1.81 R1.82 R1.83 R1.85 R1.86 RL1.9 RL1.11."""
    c = client
    for auth in (None, "Bearer nonsense", "Basic x", "Bearer"):
        error(c.request("POST", "/dossiers", headers={} if auth is None else {"Authorization": auth}, json={}), 401, "unauthenticated")
    for body in ([], 1, None, "abc"):
        error(c.request("POST", "/auth/signup", json=body), 400, "malformed_request")
    good = {"email": "new@example.com", "password": "12345678", "display_name": "A"}
    for field, val, status in (("email", 3, 400), ("password", 3, 400), ("display_name", [], 400),
                               ("email", "a@@b", 422), ("email", "a @b", 422), ("email", "@b", 422),
                               ("password", "1234567", 422), ("display_name", " ", 422), ("display_name", "x" * 101, 422)):
        error(c.request("POST", "/auth/signup", json={**good, field: val}), status,
              "malformed_request" if status == 400 else "validation_failed")
    for field in good:
        error(c.request("POST", "/auth/signup", json={k: v for k, v in good.items() if k != field}), 422, "validation_failed")
    signup = c.request("POST", "/auth/signup", json={**good, "unused": {"a": 1}})
    assert signup.status_code == 201
    assert len(signup.json()["user_id"]) <= 64 and signup.json()["display_name"] == "A"
    error(c.request("POST", "/auth/signup", json={**good, "email": "NEW@example.com"}), 409, "email_taken")
    error(c.request("POST", "/auth/signup", json={**good, "password": "short"}), 422, "validation_failed")
    for data in ({"email": good["email"], "password": "incorrect"}, {"email": "absent@example.com", "password": "12345678"}):
        error(c.request("POST", "/auth/login", json=data), 401, "unauthenticated")
    other = c.request("POST", "/auth/login", json={"email": "NEW@EXAMPLE.COM", "password": "12345678"})
    assert other.status_code == 200
    for token in (signup.json()["token"], other.json()["token"]):
        assert c.request("GET", "/dossiers", headers=c.auth(token)).status_code == 200


def test_reset_atomicity_and_clock_validation(client):
    """R1.25 R1.28 R1.29 R1.30 R1.32 R1.33 R1.35 R1.62 RL1.6 RL1.9."""
    c = client
    token = c.login()
    duplicate = {"now": NOW, "users": [SEED["users"][0], {**SEED["users"][1], "email": "ADA@example.com"}]}
    error(c.request("POST", "/_test/reset", json=duplicate), 422, "validation_failed")
    assert c.request("GET", "/dossiers", headers=c.auth(token)).status_code == 200
    duplicate["users"][1] = {**SEED["users"][1], "id": "u_ada"}
    error(c.request("POST", "/_test/reset", json=duplicate), 422, "validation_failed")
    error(c.request("POST", "/_test/clock", json={"now": "2026-03-01T08:59:59Z"}), 422, "validation_failed")
    error(c.request("POST", "/_test/clock", json={"now": "2026-03-01T09:30:00"}), 422, "validation_failed")
    error(c.request("POST", "/_test/clock", json={"now": 4}), 400, "malformed_request")
    assert c.request("POST", "/_test/clock", json={"now": "2026-03-01T11:30:00+02:00"}).status_code == 204
    assert create(c, token).status_code == 202
    dossier = c.finish(DOMAIN, token)
    assert dossier["researched_at"] == "2026-03-01T11:30:00+02:00"
    assert datetime.fromisoformat(dossier["researched_at"]).utcoffset() is not None


@pytest.mark.parametrize("domain", ["x", "https://a.test", "a.test/path", ".a.test", "a..test", "-a.test", "a-.test", "a.test..", "www.www.", "x" * 64 + ".test", ("a" * 63 + ".") * 4 + "z"])
def test_invalid_domain(client, domain):
    """R1.41 R1.112."""
    error(create(client, client.login(), domain), 422, "validation_failed")


def test_domain_and_validation_order(client):
    """R1.34 R1.36 R1.38 R1.40 R1.42 R1.65 R1.67 R1.68 R1.73 R1.89 R1.92 R1.100 R1.108 R1.109 R1.111 R1.118 RL1.4."""
    c = client
    t = c.login()
    error(c.request("POST", "/dossiers", headers=c.auth(t), data="{"), 400, "missing_idempotency_key")
    error(c.request("POST", "/dossiers", headers=c.auth(t, "x" * 256), data="{"), 400, "malformed_request")
    error(create(c, t, "x.test", "x" * 256), 422, "validation_failed")
    error(c.request("POST", "/dossiers", headers=c.auth(t, "missing"), json={}), 422, "validation_failed")
    original = create(c, t, "  WWW.Halvorsen-Robotics.TEST.  ", "key")
    assert original.status_code == 202
    assert original.json()["domain"] == DOMAIN and original.json()["state"] == "building"
    assert len(original.json()["dossier_id"]) <= 64
    assert original.headers["content-type"].lower().startswith("application/json")
    error(c.request("POST", "/dossiers", headers=c.auth(t, "key"), json={"domain": 4}), 409, "idempotency_key_reuse")
    again = create(c, t, DOMAIN, "other")
    assert again.status_code == 200 and again.json()["dossier_id"] == original.json()["dossier_id"]
    path = c.request("GET", "/dossiers/WWW.Halvorsen-Robotics.TEST.", headers=c.auth(t))
    assert path.status_code == 200 and path.json()["domain"] == DOMAIN
    error(c.request("GET", "/dossiers/missing.test", headers=c.auth(t)), 404, "not_found")


def test_idempotency(client):
    """R1.3 R1.39 R1.90 R1.91 R1.93 R1.94 R1.95 R1.96 R1.97 R1.99 R1.107 R1.119 R1.121 RL1.5."""
    c = client
    a, b = c.login(), c.login("bob@example.com")
    error(create(c, a, "bad", "reuse"), 422, "validation_failed")
    first = create(c, a, DOMAIN, "reuse")
    assert first.status_code == 202
    c.finish(DOMAIN, a)
    calls = c.calls()
    replay = c.request("POST", "/dossiers", headers=c.auth(a, "reuse"), json={"ignored": 2, "domain": DOMAIN})
    assert replay.status_code == 200 and replay.json() == first.json()
    assert c.calls() == calls
    error(create(c, a, "else.test", "reuse"), 409, "idempotency_key_reuse")
    assert create(c, b, "else.test", "reuse").status_code == 202
    assert c.request("GET", "/dossiers/" + DOMAIN, headers=c.auth(b)).status_code == 200
    refresh = c.request("POST", "/dossiers/" + DOMAIN + "/refresh", headers=c.auth(a, "reuse"), data="junk")
    assert refresh.status_code == 202
    replay = c.request("POST", "/dossiers/" + DOMAIN + "/refresh", headers=c.auth(a, "reuse"), json={"whatever": 5})
    assert replay.status_code == 200 and replay.json() == refresh.json()
    error(c.request("POST", "/dossiers/nobody.test/refresh", headers=c.auth(a, "missing")), 404, "not_found")


@pytest.mark.parametrize("same_key", [True, False])
def test_burst(client, same_key):
    """R1.16 R1.17 R1.76 R1.98 R1.102 R1.110 R1.143 R1.164."""
    c = client
    token = c.login()
    def send(i):
        start = time.monotonic()
        r = create(c, token, DOMAIN, "shared" if same_key else f"key-{i}")
        return r, time.monotonic() - start
    with ThreadPoolExecutor(max_workers=50) as pool:
        replies = list(pool.map(send, range(50)))
    assert sum(r.status_code == 202 for r, _ in replies) == 1
    assert all(r.status_code in (200, 202) and elapsed < 5 for r, elapsed in replies)
    assert len({r.json()["dossier_id"] for r, _ in replies}) == 1
    if same_key:
        assert all(r.json() == replies[0][0].json() for r, _ in replies)
    c.finish(DOMAIN, token)
    assert len([x for x in c.calls() if x["method"] == "search" and x["query"] == DOMAIN and x["status"] < 400]) == 1


def test_listing(client):
    """R1.37 R1.71 R1.74 R1.75 R1.122 R1.123 R1.124 R1.125 R1.126 RL1.10."""
    c = client
    t = c.login()
    for name in ("zzz.test", "aaa.test", "mmm.test"):
        assert create(c, t, name, name).status_code == 202
    for query in ("limit=0", "limit=201", "limit=", "limit=1e9", "limit=4.0", "limit=%2B4", "offset=-1", "offset=1.0"):
        error(c.request("GET", "/dossiers?" + query, headers=c.auth(t)), 422, "validation_failed")
    page = c.request("GET", "/dossiers?limit=2&offset=0&unused=1", headers=c.auth(t)).json()
    assert [d["domain"] for d in page["dossiers"]] == ["aaa.test", "mmm.test"] and page["has_more"] is True
    page = c.request("GET", "/dossiers?limit=2&offset=2", headers=c.auth(t)).json()
    assert [d["domain"] for d in page["dossiers"]] == ["zzz.test"] and page["has_more"] is False
    page = c.request("GET", "/dossiers?q=MM", headers=c.auth(t)).json()
    assert [d["domain"] for d in page["dossiers"]] == ["mmm.test"]


def test_export_import_roundtrip(client):
    """R1.4 R1.87 R1.113 R1.116 R1.117 R1.133 R1.134 R1.135 R1.136 R1.137 R1.138 R1.139 R1.140 R1.141."""
    c = client
    t = c.login()
    first = create(c, t)
    assert first.status_code == 202
    dossier = c.finish(DOMAIN, t)
    assert dossier["state"] == "ready"
    snapshot_response = c.request("GET", "/_test/export", timeout=10)
    assert snapshot_response.status_code == 200
    snapshot = snapshot_response.json()
    assert snapshot["track"] == "dossier" and snapshot["format_version"] == 1 and isinstance(snapshot["state"], dict)
    assert "correct horse" not in snapshot_response.text
    assert c.request("POST", "/_test/reset", json={"now": NOW}, timeout=10).status_code == 204
    error(c.request("GET", "/dossiers", headers=c.auth(t)), 401, "unauthenticated")
    calls = c.calls()
    for _ in range(2):
        assert c.request("POST", "/_test/import", json=snapshot, timeout=10).status_code == 204
        assert c.request("GET", "/dossiers/" + DOMAIN, headers=c.auth(t)).json() == dossier
        replay = create(c, t)
        assert replay.status_code == 200 and replay.json() == first.json()
        assert c.login()
    assert c.calls() == calls
    for bad in ({}, {**snapshot, "track": "other"}, {**snapshot, "format_version": 2}, {**snapshot, "state": None}):
        error(c.request("POST", "/_test/import", json=bad, timeout=10), 422, "validation_failed")
        assert c.request("GET", "/dossiers/" + DOMAIN, headers=c.auth(t)).json() == dossier


def test_running_build_snapshot_and_reset(client):
    """R1.26 R1.31 R1.101 R1.114 R1.115 R1.142 RL1.8."""
    c = client
    token = c.login()
    c.control("faults", {"provider": "nimble", "methods": ["search", "extract", "research"], "mode": "delay", "seconds": 2})
    assert create(c, token).status_code == 202
    running = c.request("GET", "/dossiers/" + DOMAIN, headers=c.auth(token)).json()
    assert running["state"] == "building" and running["researched_at"] is None
    assert all(f == {"value": None, "status": "unknown", "citations": []} for f in running["fields"].values())
    snapshot = c.request("GET", "/_test/export", timeout=10).json()
    assert c.request("POST", "/_test/import", json=snapshot, timeout=10).status_code == 204
    restored = c.request("GET", "/dossiers/" + DOMAIN, headers=c.auth(token)).json()
    assert restored["state"] == "failed" and restored["researched_at"] is None and restored["spent_units"] == 0
    assert restored["fields"] == running["fields"]
    assert c.request("POST", "/_test/reset", json=SEED, timeout=10).status_code == 204
    time.sleep(3)
    token = c.login()
    error(c.request("GET", "/dossiers/" + DOMAIN, headers=c.auth(token)), 404, "not_found")


def test_build_accounting_and_refresh(client):
    """R1.2 R1.9 R1.13 R1.43 R1.46 R1.47 R1.48 R1.51 R1.103 R1.105 R1.117 R1.120 R1.127 R1.128 R1.129 R1.130 R1.131 R1.132 R1.163 R1.164."""
    c = client
    t = c.login()
    started = time.monotonic()
    assert create(c, t).status_code == 202
    result = c.finish(DOMAIN, t, seconds=10)
    assert time.monotonic() - started <= 10
    assert result["state"] == "ready"
    assert result["researched_at"] == NOW
    names = {"legal_name", "hq_city", "ceo", "founded_year", "headcount_range", "funding_total"}
    assert set(result["fields"]) == names
    for f in result["fields"].values():
        assert set(f) == {"value", "status", "citations"}
        assert (f["status"] == "unknown" and f["value"] is None and f["citations"] == []) or (f["status"] == "known" and f["value"] is not None and f["citations"])
    calls = c.calls()
    assert 0 < sum(x["cost"] for x in calls) <= 80
    assert result["spent_units"] == sum(x["cost"] for x in calls)
    for call in calls:
        if call["provider"] == "nimble" and call["method"] == "extract" and call["status"] < 400:
            assert call["cost"] == len(call["urls"]), call
        if call["provider"] == "nimble" and call["method"] == "search" and call["status"] < 400:
            assert call["cost"] == {"lite": 1, "fast": 5, "deep": 15}[call["depth"]]
    assert len([x for x in calls if x["method"] == "search" and x["query"] == DOMAIN and x["status"] < 400]) == 1
    research = [x for x in calls if x["method"] == "research" and x["status"] < 400]
    assert research and set(research[0]["fields"]) == names and DOMAIN in research[0]["query"]
    assert c.request("POST", "/dossiers/" + DOMAIN + "/refresh", headers=c.auth(t, "refresh")).status_code == 202
    refreshed = c.finish(DOMAIN, t)
    more = c.calls()[len(calls):]
    assert more and sum(x["cost"] for x in more) <= 80
    assert refreshed["spent_units"] == sum(x["cost"] for x in calls + more)


@pytest.mark.parametrize("mode", ["error", "rate_limit", "throttle", "delay"])
def test_provider_faults_do_not_break_http(client, mode):
    """R1.76 R1.103 R1.129 RL1.12."""
    c = client
    c.control("faults", {"provider": "nimble", "methods": ["search", "extract", "research"], "mode": mode, **({"seconds": 1} if mode == "delay" else {})})
    t = c.login()
    assert create(c, t).status_code == 202
    result = c.finish(DOMAIN, t, seconds=30)
    assert result["state"] in ("ready", "failed")
    if mode == "error":
        assert result["state"] == "failed"
        assert all(f["value"] is None for f in result["fields"].values())
    if mode == "delay":
        assert result["state"] == "ready"
    assert sum(x["cost"] for x in c.calls()) <= 80
