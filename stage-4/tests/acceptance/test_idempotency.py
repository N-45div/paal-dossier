"""Idempotency matrix for POST /dossiers and POST /dossiers/{domain}/refresh.

Ledger ids named per test. Uses the mock only to count provider calls.

Also covers: R1.79 (domain identifies the company), R1.134 (409 idempotency_key_reuse),
R1.162-R1.164 (write paths need a key, key scope), R1.167 (replay definition).
"""
import concurrent.futures as cf
import json

from conftest import (SAMPLE_DOMAINS, await_settled, call, domain_searches, get_dossier,
                      login, mock, mock_calls, mock_faults, new_key, reset_service,
                      start_build)

D = SAMPLE_DOMAINS[0]


def test_missing_or_empty_key_is_400(env):
    # R1.131, R1.170
    r = call("POST", "/dossiers", token=env["ada"], body={"domain": D})
    assert r.status_code == 400 and r.json()["error"]["code"] == "missing_idempotency_key"
    r = call("POST", "/dossiers", token=env["ada"], key="", body={"domain": D})
    assert r.status_code == 400 and r.json()["error"]["code"] == "missing_idempotency_key"
    r = call("POST", "/dossiers/" + D + "/refresh", token=env["ada"])
    assert r.status_code == 400 and r.json()["error"]["code"] == "missing_idempotency_key"


def test_key_length_1_to_255(env):
    # R1.141
    r = call("POST", "/dossiers", token=env["ada"], key="k" * 256, body={"domain": D})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_failed"
    r = call("POST", "/dossiers", token=env["ada"], key="k" * 255, body={"domain": D})
    assert r.status_code in (200, 202), r.text
    await_settled(env["ada"], D)


def test_first_use_202_then_replay_200_identical_body(env):
    # R1.171-R1.172, R1.178
    key = new_key()
    r1 = start_build(env["ada"], D, key)
    assert r1.status_code == 202, r1.text
    body1 = r1.json()
    assert set(body1) >= {"dossier_id", "domain", "state"} and body1["state"] == "building"
    r2 = start_build(env["ada"], D, key)
    assert r2.status_code == 200 and r2.json() == body1
    await_settled(env["ada"], D)
    # replay after the build finished still returns the original response
    r3 = start_build(env["ada"], D, key)
    assert r3.status_code == 200 and r3.json() == body1


def test_replay_does_no_provider_call(env):
    # R1.181-R1.182
    key = new_key()
    assert start_build(env["ada"], D, key).status_code == 202
    await_settled(env["ada"], D)
    before = len(mock_calls())
    assert start_build(env["ada"], D, key).status_code == 200
    assert len(mock_calls()) == before


def test_same_body_different_order_and_whitespace_is_replay(env):
    # R1.175
    key = new_key()
    assert start_build(env["ada"], D, key, raw='{"domain":"%s"}' % D).status_code == 202
    r = start_build(env["ada"], D, key, raw='{  "domain" :   "%s" }' % D)
    assert r.status_code == 200
    await_settled(env["ada"], D)


def test_unknown_fields_do_not_affect_replay(env):
    # R1.176, R1.74
    key = new_key()
    assert start_build(env["ada"], D, key, raw=json.dumps({"domain": D, "x": 1})).status_code == 202
    r = start_build(env["ada"], D, key, raw=json.dumps({"domain": D, "x": 2, "y": "z"}))
    assert r.status_code == 200
    await_settled(env["ada"], D)


def test_same_key_different_body_is_409(env):
    # R1.173
    key = new_key()
    assert start_build(env["ada"], D, key).status_code == 202
    r = start_build(env["ada"], SAMPLE_DOMAINS[1], key)
    assert r.status_code == 409 and r.json()["error"]["code"] == "idempotency_key_reuse"
    await_settled(env["ada"], D)


def test_changing_to_invalid_body_with_claimed_key_is_409(env):
    # R1.183-R1.184
    key = new_key()
    assert start_build(env["ada"], D, key).status_code == 202
    r = start_build(env["ada"], None, key, raw=json.dumps({"domain": "not a domain"}))
    assert r.status_code == 409 and r.json()["error"]["code"] == "idempotency_key_reuse"
    await_settled(env["ada"], D)


def test_domain_case_difference_is_a_different_body(env):
    # R1.169, R1.173
    key = new_key()
    assert start_build(env["ada"], None, key, raw='{"domain":"Brightwater-Labs.test"}').status_code == 202
    r = start_build(env["ada"], None, key, raw='{"domain":"brightwater-labs.test"}')
    assert r.status_code == 409 and r.json()["error"]["code"] == "idempotency_key_reuse"
    await_settled(env["ada"], D)


def test_same_key_and_body_on_refresh_path_is_a_different_request(env):
    # R1.168
    key = new_key()
    assert start_build(env["ada"], D, key).status_code == 202
    await_settled(env["ada"], D)
    r = call("POST", f"/dossiers/{D}/refresh", token=env["ada"], key=key)
    assert r.status_code == 202, r.text
    await_settled(env["ada"], D)


def test_failed_4xx_request_leaves_key_reusable(env):
    # R1.174
    key = new_key()
    r = start_build(env["ada"], None, key, raw='{"domain":"bad domain"}')
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_failed"
    r = start_build(env["ada"], D, key)
    assert r.status_code == 202, r.text
    await_settled(env["ada"], D)


def test_keys_are_scoped_per_user(env):
    # R1.165-R1.166
    key = new_key()
    r_ada = start_build(env["ada"], D, key)
    assert r_ada.status_code == 202
    r_bob = start_build(env["bob"], D, key)
    assert r_bob.status_code == 200, r_bob.text  # same dossier exists; not a 409
    assert r_bob.json()["dossier_id"] == r_ada.json()["dossier_id"]
    await_settled(env["ada"], D)


def test_reset_forgets_stored_idempotent_responses(env):
    # R1.61
    key = new_key()
    assert start_build(env["ada"], D, key).status_code == 202
    await_settled(env["ada"], D)
    reset_service()
    token = login("ada@example.com")
    r = start_build(token, D, key)
    assert r.status_code == 202, r.text
    await_settled(token, D)


def test_domain_normalisation_names_one_dossier(env):
    # R1.83-R1.84
    k1 = new_key()
    r1 = start_build(env["ada"], None, k1, raw='{"domain":" Brightwater-Labs.TEST. "}')
    assert r1.status_code == 202, r1.text
    assert r1.json()["domain"] == D
    r2 = start_build(env["ada"], None, new_key(), raw='{"domain":"www.%s"}' % D)
    assert r2.status_code == 200 and r2.json()["dossier_id"] == r1.json()["dossier_id"]
    assert r2.json()["domain"] == D
    await_settled(env["ada"], D)


def test_concurrent_identical_requests_one_202_rest_200(env):
    # R1.178-R1.180, R1.199
    key = new_key()
    domain = SAMPLE_DOMAINS[2]

    def go(_):
        r = start_build(env["ada"], domain, key)
        return r.status_code, r.json()

    with cf.ThreadPoolExecutor(max_workers=12) as ex:
        results = list(ex.map(go, range(12)))
    codes = sorted(c for c, _ in results)
    assert codes.count(202) == 1 and codes.count(200) == 11, codes
    bodies = {json.dumps(b, sort_keys=True) for _, b in results}
    assert len(bodies) == 1
    await_settled(env["ada"], domain)
    assert len(domain_searches(mock_calls(), domain)) == 1


def test_concurrent_distinct_keys_same_domain_one_dossier_one_build(env):
    # R1.199, R1.100, R1.255
    domain = SAMPLE_DOMAINS[1]

    def go(_):
        r = start_build(env["ada"], domain, new_key())
        return r.status_code, r.json()["dossier_id"]

    with cf.ThreadPoolExecutor(max_workers=20) as ex:
        results = list(ex.map(go, range(20)))
    codes = [c for c, _ in results]
    assert codes.count(202) == 1 and codes.count(200) == 19, codes
    assert len({d for _, d in results}) == 1
    await_settled(env["ada"], domain)
    assert len(domain_searches(mock_calls(), domain)) == 1


def test_refresh_while_building_returns_same_body_and_starts_nothing(env):
    # R1.210-R1.211, R1.100
    domain = SAMPLE_DOMAINS[0]
    mock_faults("nimble", ["search"], "delay", seconds=3)
    mock_faults("tavily", ["search"], "error")
    try:
        r0 = start_build(env["ada"], domain)
        assert r0.status_code == 202, r0.text
        k = new_key()
        r1 = call("POST", f"/dossiers/{domain}/refresh", token=env["ada"], key=k)
        assert r1.status_code == 202, r1.text
        assert r1.json()["state"] == "building"
        r2 = call("POST", f"/dossiers/{domain}/refresh", token=env["ada"], key=new_key())
        assert r2.status_code == 202 and r2.json() == r1.json()
        await_settled(env["ada"], domain)
    finally:
        mock_faults("nimble", ["search"], "none")
        mock_faults("tavily", ["search"], "none")
    assert len(domain_searches(mock_calls(), domain)) == 1


def test_refresh_replay_and_body_ignored_for_replay(env):
    # R1.177, R1.182
    domain = SAMPLE_DOMAINS[0]
    r0 = start_build(env["ada"], domain)
    assert r0.status_code == 202
    await_settled(env["ada"], domain)
    k = new_key()
    r1 = call("POST", f"/dossiers/{domain}/refresh", token=env["ada"], key=k, body={"x": 1})
    assert r1.status_code == 202
    await_settled(env["ada"], domain)
    before = len(mock_calls())
    r2 = call("POST", f"/dossiers/{domain}/refresh", token=env["ada"], key=k, body={"y": 2})
    assert r2.status_code == 200 and r2.json() == r1.json()
    assert len(mock_calls()) == before


def test_refresh_researches_again(env):
    # R1.212
    domain = SAMPLE_DOMAINS[0]
    start_build(env["ada"], domain)
    await_settled(env["ada"], domain)
    before = len(domain_searches(mock_calls(), domain))
    r = call("POST", f"/dossiers/{domain}/refresh", token=env["ada"], key=new_key())
    assert r.status_code == 202
    await_settled(env["ada"], domain)
    assert len(domain_searches(mock_calls(), domain)) == before + 1


def test_refresh_unknown_dossier_is_404(env):
    # R1.213
    r = call("POST", "/dossiers/no-such-dossier.test/refresh", token=env["ada"], key=new_key())
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
