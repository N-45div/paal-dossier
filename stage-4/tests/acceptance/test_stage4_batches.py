"""Stage 4 batches (stage-4 spec, Batches; ledger R4.42-R4.56, pkg R4C), black-box over HTTP.

POST /batches and GET /batches/{id}: validation table, idempotency, ownership, the shared budget,
the states, and that a domain with a dossier is not researched by a batch. Expected values come
from the spec table and the clock and corpus this file sets, not from the service.
Ledger ids are named per test; the ledger rows for R4C are the authority for the numbering.
"""
import time

import pytest

from conftest import (SAMPLE_DOMAINS, call, login, new_key, await_settled, start_build, reset_service)

BATCHES = "/batches"


def post_batch(token, body, key=None, raw=None):
    key = new_key() if key is None else key
    if raw is not None:
        return call("POST", BATCHES, token=token, key=key, raw=raw)
    return call("POST", BATCHES, token=token, key=key, body=body)


def get_batch(token, batch_id):
    return call("GET", f"{BATCHES}/{batch_id}", token=token, timeout=10)


def await_batch_done(token, batch_id, timeout=180.0):
    deadline = time.time() + timeout
    while True:
        r = get_batch(token, batch_id)
        assert r.status_code == 200, r.text
        b = r.json()
        if b["state"] == "done":
            return b
        assert time.time() < deadline, f"batch {batch_id} still running after {timeout}s"
        time.sleep(0.3)


# R4.47-R4.51: the validation table
@pytest.mark.parametrize("body", [
    {"budget_units": 200},                                       # domains missing
    {"domains": [], "budget_units": 200},                         # domains empty
    {"domains": ["d%d.test" % i for i in range(51)], "budget_units": 200},  # longer than 50
    {"domains": ["not a domain!"], "budget_units": 200},         # invalid after normalisation
    {"domains": [SAMPLE_DOMAINS[0], SAMPLE_DOMAINS[0].upper()], "budget_units": 200},  # duplicate
    {"domains": [SAMPLE_DOMAINS[0]]},                             # budget missing
    {"domains": [SAMPLE_DOMAINS[0]], "budget_units": 0},          # below 1
    {"domains": [SAMPLE_DOMAINS[0]], "budget_units": 100001},     # above 100000
    {"domains": [SAMPLE_DOMAINS[0]], "budget_units": "200"},      # string is not an integer
    {"domains": [SAMPLE_DOMAINS[0]], "budget_units": True},       # bool is not an integer
    {"domains": [SAMPLE_DOMAINS[0]], "budget_units": 1.5},        # float is not an integer
])
def test_batch_validation_table_is_422_validation_failed(env, body):
    # R4.47, R4.48, R4.49, R4.50, R4.51 (validation rows and the non-integer note of the Batches table)
    r = post_batch(env["ada"], body)
    assert r.status_code == 422, (body, r.status_code, r.text)
    assert r.json()["error"]["code"] == "validation_failed", r.text


def test_batch_limit_of_fifty_domains_is_inclusive(env):
    # R4.47: 50 entries is allowed (a boundary value)
    domains = [f"batch{i:02d}-none.test" for i in range(50)]
    r = post_batch(env["ada"], {"domains": domains, "budget_units": 1})
    assert r.status_code == 202, r.text
    assert len(r.json()["dossiers"]) == 50


def test_budget_boundaries_are_accepted(env):
    # R4.50: 1 and 100000 are the inclusive bounds
    for budget in (1, 100000):
        r = post_batch(env["ada"], {"domains": [f"edge{budget}-none.test"], "budget_units": budget})
        assert r.status_code == 202, (budget, r.text)
        assert r.json()["budget_units"] == budget


# R4.46 and R4.52: the 202 body and the listing order
def test_batch_202_body_lists_domains_in_the_given_order(env):
    domains = [SAMPLE_DOMAINS[1], SAMPLE_DOMAINS[0]]
    r = post_batch(env["ada"], {"domains": domains, "budget_units": 200})
    assert r.status_code == 202, r.text
    b = r.json()
    assert isinstance(b["batch_id"], str) and b["batch_id"]
    assert b["state"] in ("running", "done"), b
    assert b["budget_units"] == 200
    assert b["spent_units"] == 0 or b["state"] == "running"
    assert [d["domain"] for d in b["dossiers"]] == domains
    assert all(d["state"] in ("building", "ready", "failed") for d in b["dossiers"]), b


def test_domains_are_normalised_in_the_listing(env):
    # R4.52: the listed domains are the normalised ones (§4): case folded here
    r = post_batch(env["ada"], {"domains": ["Batch-Norm.TEST"], "budget_units": 50})
    assert r.status_code == 202, r.text
    assert r.json()["dossiers"][0]["domain"] == "batch-norm.test"


# R4.53: a dossier that already exists is not researched by the batch
def test_existing_dossier_is_not_researched_and_costs_the_batch_nothing(env):
    existing = SAMPLE_DOMAINS[0]
    assert start_build(env["ada"], existing).status_code == 202
    first = await_settled(env["ada"], existing)
    spent_before = first["spent_units"]
    r = post_batch(env["ada"], {"domains": [existing], "budget_units": 200})
    assert r.status_code == 202, r.text
    b = await_batch_done(env["ada"], r.json()["batch_id"])
    assert b["spent_units"] == 0, b
    after = await_settled(env["ada"], existing)
    assert after["spent_units"] == spent_before, (after["spent_units"], spent_before)
    assert after["researched_at"] == first["researched_at"]


# R4.54: a batch builds the new dossiers, the batch ends done and its spend is within budget
def test_batch_builds_new_dossiers_and_stays_within_budget(env):
    domains = [SAMPLE_DOMAINS[0], SAMPLE_DOMAINS[1]]
    r = post_batch(env["ada"], {"domains": domains, "budget_units": 200})
    assert r.status_code == 202, r.text
    b = await_batch_done(env["ada"], r.json()["batch_id"])
    assert b["state"] == "done"
    assert 0 < b["spent_units"] <= 200, b["spent_units"]
    for domain in domains:
        d = await_settled(env["ada"], domain)
        assert d["state"] == "ready", (domain, d["state"])
    per_dossier = sum(await_settled(env["ada"], dom)["spent_units"] for dom in domains)
    assert per_dossier == b["spent_units"], (per_dossier, b["spent_units"])


# R4.55: a tight shared budget ends the batch and never exceeds it
def test_tight_shared_budget_is_never_exceeded(env):
    domains = list(SAMPLE_DOMAINS)
    r = post_batch(env["ada"], {"domains": domains, "budget_units": 1})
    assert r.status_code == 202, r.text
    b = await_batch_done(env["ada"], r.json()["batch_id"])
    assert b["state"] == "done"
    assert b["spent_units"] <= 1, b["spent_units"]
    for domain in domains:
        d = await_settled(env["ada"], domain)
        assert d["state"] in ("ready", "failed"), (domain, d["state"])
        assert d["spent_units"] <= 1, (domain, d["spent_units"])


# R4.44: idempotency
def test_same_key_and_body_replays_the_original_response(env):
    key = new_key()
    body = {"domains": [SAMPLE_DOMAINS[2]], "budget_units": 150}
    first = post_batch(env["ada"], body, key=key)
    again = post_batch(env["ada"], body, key=key)
    assert first.status_code == 202, first.text
    assert again.status_code in (200, 202), again.text
    assert again.json()["batch_id"] == first.json()["batch_id"]
    assert again.json() == first.json()


def test_same_key_different_body_is_409(env):
    key = new_key()
    assert post_batch(env["ada"], {"domains": [SAMPLE_DOMAINS[0]], "budget_units": 150}, key=key).status_code == 202
    r = post_batch(env["ada"], {"domains": [SAMPLE_DOMAINS[1]], "budget_units": 150}, key=key)
    assert r.status_code == 409, r.text


def test_batch_request_without_idempotency_key_is_rejected(env):
    # R4.44: Idempotency-Key is required (§7)
    r = call("POST", BATCHES, token=env["ada"], key=None,
             body={"domains": [SAMPLE_DOMAINS[0]], "budget_units": 50})
    assert r.status_code == 400, r.text
    assert r.json()["error"]["code"] == "missing_idempotency_key", r.text


# R4.43 and R4.56: ownership and unknown ids
def test_another_users_batch_is_not_found(env):
    r = post_batch(env["ada"], {"domains": [SAMPLE_DOMAINS[0]], "budget_units": 50})
    assert r.status_code == 202, r.text
    batch_id = r.json()["batch_id"]
    assert get_batch(env["bob"], batch_id).status_code == 404
    assert get_batch(env["ada"], batch_id).status_code == 200


def test_unknown_batch_is_not_found(env):
    assert get_batch(env["ada"], "b_does_not_exist").status_code == 404
