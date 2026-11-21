"""HTTP contract: runtime, reset, clock, errors, authentication, query validation.

Ledger ids named per test. Black-box: only the HTTP interface is used.

Also covers: R1.129, R1.132, R1.134, R1.136-R1.137, R1.140, R1.145, R1.147-R1.148, R1.157
(endpoint-specific errors, error codes, shared ranges, signup/login shape, bearer header).
"""
import concurrent.futures as cf

from conftest import PASSWORD, call, login, reset_service, seed_fixture, set_clock


def _json_ct(r):
    return r.headers.get("Content-Type", "").replace(" ", "").lower() == "application/json;charset=utf-8"


def test_health_ok_without_auth_and_json(mock_ready):
    # R1.54-R1.55, R1.58, R1.72
    r = call("GET", "/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    assert _json_ct(r)


def test_reset_is_unauthenticated_204_and_repeatable(mock_ready):
    # R1.59, R1.62, R1.64, R1.60
    reset_service(seed_fixture())
    reset_service(seed_fixture(now="2026-04-01T00:00:00+00:00"))
    assert login("ada@example.com") and login("bob@example.com")


def test_reset_clears_previous_users_and_sees_only_fixture(mock_ready):
    # R1.61, R1.123
    reset_service()
    signup = call("POST", "/auth/signup", body={"email": "zoe@example.com", "password": "correct horse",
                                                "display_name": "Zoe"})
    assert signup.status_code == 201, signup.text
    reset_service()
    r = call("POST", "/auth/login", body={"email": "zoe@example.com", "password": PASSWORD})
    assert r.status_code == 401 and r.json()["error"]["code"] == "unauthenticated"
    assert login("ada@example.com")


def test_reset_fixture_user_ids_and_login(mock_ready):
    # R1.123, R1.154
    reset_service()
    r = call("POST", "/auth/login", body={"email": "ada@example.com", "password": PASSWORD})
    assert r.status_code == 200
    assert r.json()["user_id"] == "u_ada" and r.json()["display_name"] == "Ada"


def test_reset_duplicate_fixture_email_is_422_and_changes_nothing(mock_ready):
    # R1.124, R1.135
    reset_service()
    bad = seed_fixture(users=[
        {"id": "u_1", "email": "same@example.com", "password": PASSWORD, "display_name": "A"},
        {"id": "u_2", "email": "same@example.com", "password": PASSWORD, "display_name": "B"},
    ])
    r = call("POST", "/_test/reset", body=bad, timeout=10)
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_failed"
    assert login("ada@example.com")  # state from before the failed reset survives


def test_reset_missing_now_is_422_and_changes_nothing(mock_ready):
    # R1.122, R1.135
    reset_service()
    r = call("POST", "/_test/reset", body={"users": []}, timeout=10)
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_failed"
    assert login("ada@example.com")


def test_reset_malformed_json_is_400(mock_ready):
    # R1.125, R1.130, R1.139
    r = call("POST", "/_test/reset", raw="{not json", timeout=10)
    assert r.status_code == 400 and r.json()["error"]["code"] == "malformed_request"


def test_reset_unknown_fields_ignored(mock_ready):
    # R1.74
    body = seed_fixture()
    body["extra_field"] = {"anything": 1}
    r = call("POST", "/_test/reset", body=body, timeout=10)
    assert r.status_code == 204


def test_error_envelope_shape(mock_ready):
    # R1.125-R1.128
    reset_service()
    r = call("GET", "/dossiers")
    assert r.status_code == 401
    err = r.json()["error"]
    assert err["code"] == "unauthenticated" and isinstance(err["message"], str)
    assert _json_ct(r)


def test_clock_rules(mock_ready):
    # R1.67-R1.71
    reset_service(seed_fixture(now="2026-03-01T09:00:00+00:00"))
    set_clock("2026-03-01T10:00:00+00:00")
    # earlier than current clock: 422 and changes nothing
    r = call("POST", "/_test/clock", body={"now": "2026-03-01T09:30:00+00:00"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_failed"
    # equal to current clock is not earlier
    assert call("POST", "/_test/clock", body={"now": "2026-03-01T10:00:00+00:00"}).status_code == 204
    # no explicit offset is an invalid format
    r = call("POST", "/_test/clock", body={"now": "2026-03-01T10:30:00"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_failed"
    # wrong JSON type
    r = call("POST", "/_test/clock", body={"now": 12345})
    assert r.status_code == 400 and r.json()["error"]["code"] == "malformed_request"


def test_clock_endpoint_needs_no_auth_and_ignores_unknown_fields(mock_ready):
    # R1.71, R1.74
    reset_service()
    r = call("POST", "/_test/clock", body={"now": "2027-01-01T00:00:00+00:00", "x": 1})
    assert r.status_code == 204


def test_signup_and_login_contract(mock_ready):
    # R1.77, §6
    reset_service()
    r = call("POST", "/auth/signup", body={"email": "new1@example.com", "password": "longenough",
                                           "display_name": "New One"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert set(body) >= {"user_id", "display_name", "token"}
    assert body["display_name"] == "New One" and body["token"]
    r2 = call("POST", "/auth/login", body={"email": "new1@example.com", "password": "longenough"})
    assert r2.status_code == 200 and r2.json()["user_id"] == body["user_id"]


def test_signup_validation_and_conflict(mock_ready):
    # R1.149-R1.152
    reset_service()
    base = {"email": "dup@example.com", "password": "longenough", "display_name": "D"}
    assert call("POST", "/auth/signup", body=base).status_code == 201
    r = call("POST", "/auth/signup", body=base)
    assert r.status_code == 409 and r.json()["error"]["code"] == "email_taken"
    short = {"email": "short@example.com", "password": "1234567", "display_name": "S"}
    r = call("POST", "/auth/signup", body=short)
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_failed"
    eight = {"email": "eight@example.com", "password": "12345678", "display_name": "S"}
    assert call("POST", "/auth/signup", body=eight).status_code == 201
    bad_email = {"email": "not-an-email", "password": "longenough", "display_name": "B"}
    assert call("POST", "/auth/signup", body=bad_email).status_code == 422
    empty_name = {"email": "empty@example.com", "password": "longenough", "display_name": ""}
    assert call("POST", "/auth/signup", body=empty_name).status_code == 422
    long_name = {"email": "long@example.com", "password": "longenough", "display_name": "x" * 101}
    assert call("POST", "/auth/signup", body=long_name).status_code == 422
    ok_name = {"email": "ok100@example.com", "password": "longenough", "display_name": "x" * 100}
    assert call("POST", "/auth/signup", body=ok_name).status_code == 201


def test_login_failures_are_401(mock_ready):
    # R1.153
    reset_service()
    r = call("POST", "/auth/login", body={"email": "ada@example.com", "password": "wrong password"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "unauthenticated"
    r = call("POST", "/auth/login", body={"email": "nobody@example.com", "password": PASSWORD})
    assert r.status_code == 401 and r.json()["error"]["code"] == "unauthenticated"


def test_tokens_do_not_expire_and_multiple_sessions_valid(mock_ready):
    # R1.158-R1.159
    reset_service()
    t1 = login("ada@example.com")
    t2 = login("ada@example.com")
    assert t1 != t2
    for t in (t1, t2):
        assert call("GET", "/dossiers", token=t).status_code == 200


def test_bearer_token_required_and_precedes_idempotency_key(mock_ready):
    # R1.155-R1.156, R1.131
    reset_service()
    assert call("GET", "/dossiers").status_code == 401
    r = call("POST", "/dossiers", body={"domain": "acme-robotics.test"})  # no token, no key
    assert r.status_code == 401 and r.json()["error"]["code"] == "unauthenticated"
    r = call("GET", "/dossiers", token="not-a-real-token")
    assert r.status_code == 401
    r = call("GET", "/dossiers", headers={"Authorization": "Basic abc"})
    assert r.status_code == 401


def test_unknown_query_params_ignored(env):
    # R1.75
    r = call("GET", "/dossiers?foo=bar&q=&zzz=1", token=env["ada"])
    assert r.status_code == 200 and r.json()["dossiers"] == []


def test_limit_and_offset_validation(env):
    # R1.138, R1.141-R1.143
    bad = ["limit=0", "limit=201", "limit=1e9", "limit=4.0", "limit=%2B4", "limit=abc",
           "offset=-1", "offset=1.5", "offset=x"]
    for q in bad:
        r = call("GET", f"/dossiers?{q}", token=env["ada"])
        assert r.status_code == 422, (q, r.status_code, r.text)
        assert r.json()["error"]["code"] == "validation_failed", q
    for q in ["limit=1", "limit=200", "offset=0", "offset=100000"]:
        assert call("GET", f"/dossiers?{q}", token=env["ada"]).status_code == 200, q


def test_wrong_json_type_is_400_and_bad_json_is_400(env):
    # R1.130, R1.139
    r = call("POST", "/dossiers", token=env["ada"], key="k-type-1", body={"domain": 123})
    assert r.status_code == 400 and r.json()["error"]["code"] == "malformed_request"
    r = call("POST", "/dossiers", token=env["ada"], key="k-type-2", raw="{oops")
    assert r.status_code == 400 and r.json()["error"]["code"] == "malformed_request"


def test_responses_are_json_utf8(env):
    # R1.72
    for r in (call("GET", "/dossiers", token=env["ada"]), call("GET", "/health")):
        assert _json_ct(r), r.headers


def test_no_5xx_on_malformed_inputs_under_load(env):
    # R1.144, R1.49
    cases = [
        ("POST", "/dossiers", dict(token=env["ada"], key="fz-1", raw="[]")),
        ("POST", "/dossiers", dict(token=env["ada"], key="fz-2", body={"domain": None})),
        ("POST", "/dossiers", dict(token=env["ada"], key="x" * 256, body={"domain": "a.test"})),
        ("POST", "/dossiers", dict(token=env["ada"], key="fz-3", body={"domain": "a" * 300 + ".test"})),
        ("POST", "/dossiers/%00%ff/refresh", dict(token=env["ada"], key="fz-4")),
        ("GET", "/dossiers/%20%20", dict(token=env["ada"])),
        ("GET", "/dossiers/" + "a" * 300, dict(token=env["ada"])),
        ("POST", "/auth/signup", dict(body={"email": 5, "password": "x", "display_name": None})),
        ("POST", "/auth/login", dict(raw="nul")),
        ("POST", "/_test/clock", dict(raw="{")),
        ("GET", "/dossiers?limit=99999999999999999999999", dict(token=env["ada"])),
    ]

    def run(c):
        method, path, kw = c
        r = call(method, path, timeout=5, **kw)
        return r.status_code

    with cf.ThreadPoolExecutor(max_workers=16) as ex:
        codes = list(ex.map(run, cases * 3))
    assert all(code < 500 for code in codes), codes
