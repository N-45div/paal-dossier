"""Stage 4 restarts (stage-4 spec, Restarts; ledger R4.62-R4.66, pkg R4D; Rul-S4-4, Rul-S4-6),
against the real container, black-box over HTTP plus docker on the one container this suite runs.

The container is killed abruptly (docker kill) and started again on the same filesystem
(docker start). Provider calls are slowed with the mock's `delay` fault (at most 10 s per call), so
a build is still running at the stop. The fault is cleared in `finally` so no other test sees it.

SVC_CONTAINER (default prover-stage4-svc) is the container to kill and start; the runner exports it.

Expected values come from the spec text and the ledger rows named per test, not from the service.
"""
import os
import subprocess
import time

import pytest
import requests

from conftest import BASE_URL, SAMPLE_DOMAINS, await_settled, call, mock_calls, mock_faults, mock_reset, new_key, start_build

SVC = os.environ.get("SVC_CONTAINER", "prover-stage4-svc")
PROVIDERS = ("nimble", "tavily")
METHODS = ("search", "extract", "research")
DELAY_S = 10  # the mock's maximum delay per call; with it a build runs long enough to be stopped
BATCH_BUDGET = 80
HEALTH_BOUND_S = 10.0


def _set_faults(mode, seconds=None):
    for provider in PROVIDERS:
        for method in METHODS:
            mock_faults(provider, [method], mode, seconds)


def _restart():
    """Kill the container abruptly, start it again; /health must answer 200 within HEALTH_BOUND_S
    (R4.63 and the stage-4 restart rule: answered within 10 seconds of the restart)."""
    subprocess.run(["docker", "kill", SVC], check=True, timeout=60, capture_output=True)
    subprocess.run(["docker", "start", SVC], check=True, timeout=60, capture_output=True)
    started = time.monotonic()
    deadline = started + 60
    while True:
        try:
            if requests.get(BASE_URL + "/health", timeout=2).status_code == 200:
                elapsed = time.monotonic() - started
                assert elapsed <= HEALTH_BOUND_S, f"/health took {elapsed:.2f}s after restart, bound {HEALTH_BOUND_S}s"
                return elapsed
        except requests.RequestException:
            pass
        assert time.monotonic() < deadline, "service did not answer /health within 60 s after restart"
        time.sleep(0.05)


def _dossier(token, domain):
    r = call("GET", f"/dossiers/{domain}", token=token, timeout=10)
    assert r.status_code == 200, r.text
    return r.json()


def _batch(token, batch_id):
    r = call("GET", f"/batches/{batch_id}", token=token, timeout=10)
    assert r.status_code == 200, r.text
    return r.json()


def _wait_spent(read, timeout=60.0):
    """Poll `read()` until its spent_units is above zero (a provider call has been billed)."""
    deadline = time.time() + timeout
    while True:
        body = read()
        if body.get("spent_units", 0) > 0:
            return body
        assert time.time() < deadline, f"no spend recorded within {timeout}s: {body}"
        time.sleep(0.1)


def _post_batch(token, domains, budget):
    r = call("POST", "/batches", token=token, key=new_key(),
             body={"domains": domains, "budget_units": budget}, timeout=10)
    assert r.status_code == 202, r.text
    return r.json()["batch_id"]


def _await_batch_done(token, batch_id, timeout=180.0):
    deadline = time.time() + timeout
    while True:
        b = _batch(token, batch_id)
        if b["state"] == "done":
            return b
        assert time.time() < deadline, f"batch {batch_id} still running after {timeout}s"
        time.sleep(0.2)


@pytest.fixture
def slow_providers(env):
    """Every provider call takes DELAY_S seconds; cleared and drained however the test ends."""
    _set_faults("delay", DELAY_S)
    try:
        yield env
    finally:
        _drain(env["ada"])


def _drain(token):
    """Leave nothing behind for the next module: clear the fault, wait out delayed calls of killed
    builds (at least DELAY_S + 1 s), wait until no dossier of this module is building, reset the mock
    and check its call log is empty."""
    _set_faults("none")
    before = mock_calls()
    last_seq = max((c["seq"] for c in before), default=0)
    time.sleep(DELAY_S + 1)
    deadline = time.time() + 180
    while True:
        states = []
        for d in SAMPLE_DOMAINS[:2]:
            r = call("GET", f"/dossiers/{d}", token=token, timeout=10)
            states.append("absent" if r.status_code == 404 else r.json()["state"])
        if all(s != "building" for s in states):
            break
        assert time.time() < deadline, f"dossiers still building after the restart tests: {states}"
        time.sleep(0.5)
    time.sleep(DELAY_S + 1)  # calls that started while the dossiers were settling
    late = [c for c in mock_calls() if c["seq"] > last_seq]
    print(f"drain: {len(late)} mock calls logged after this test's last call (seq > {last_seq}): "
          + "; ".join(f"seq {c['seq']} {c['provider']}/{c['method']}" for c in late[:20]), flush=True)
    mock_reset(0)
    leftover = mock_calls()
    assert leftover == [], f"mock call log not empty after reset: {len(leftover)} calls"


def test_build_running_at_stop_loads_failed_with_its_spend(slow_providers):
    # R4.62, R4.63 (not left `building`: ends failed at once after restart), R4.65 (billed spend kept),
    # Rul-S4-6 (running build loads failed with spend counted)
    token = slow_providers["ada"]
    domain = SAMPLE_DOMAINS[0]
    r = start_build(token, domain, key=new_key())
    assert r.status_code == 202, r.text
    before = _wait_spent(lambda: _dossier(token, domain))
    assert before["state"] == "building", before

    _restart()

    after = _dossier(token, domain)
    assert after["state"] == "failed", after
    assert after["spent_units"] >= before["spent_units"] > 0, (before["spent_units"], after["spent_units"])


def test_batch_running_at_stop_reads_done_with_shared_spend_kept(slow_providers):
    # R4.62 (batch restart rules), R4.64 (a batch's builds never spend more than budget_units),
    # R4.65 (batch spent_units keeps what was billed), Rul-S4-4 (shared counter), Rul-S4-6 (done once
    # no dossier is building)
    token = slow_providers["ada"]
    domains = SAMPLE_DOMAINS[:2]
    batch_id = _post_batch(token, domains, BATCH_BUDGET)
    before = _wait_spent(lambda: _batch(token, batch_id))
    assert before["state"] == "running", before

    _restart()

    after = _await_batch_done(token, batch_id, timeout=HEALTH_BOUND_S)
    assert after["spent_units"] >= before["spent_units"] > 0, (before["spent_units"], after["spent_units"])
    assert after["spent_units"] <= after["budget_units"] == BATCH_BUDGET, after
    for item in after["dossiers"]:
        assert item["state"] != "building", item


def test_batch_budget_still_enforced_after_restart(slow_providers):
    # R4.64 (a batch's builds together never spend more than budget_units): after the restart the
    # batch's shared spend keeps counting against its budget, so a refresh of its dossiers cannot
    # push the batch over budget_units.
    token = slow_providers["ada"]
    domains = SAMPLE_DOMAINS[:2]
    batch_id = _post_batch(token, domains, BATCH_BUDGET)
    before = _wait_spent(lambda: _batch(token, batch_id))
    _restart()
    _await_batch_done(token, batch_id, timeout=HEALTH_BOUND_S)
    # clear the delay so the batch's dossiers can be refreshed and billed normally
    _set_faults("none")
    for domain in domains:
        r = call("POST", f"/dossiers/{domain}/refresh", token=token, key=new_key(), body={}, timeout=10)
        assert r.status_code in (200, 202), r.text
    deadline = time.time() + 120
    while True:
        after = _batch(token, batch_id)
        if all(item["state"] != "building" for item in after["dossiers"]):
            break
        assert time.time() < deadline, after
        time.sleep(0.2)
    assert after["spent_units"] >= before["spent_units"], (before["spent_units"], after["spent_units"])
    assert after["spent_units"] <= BATCH_BUDGET, after


def test_refresh_after_restart_starts_a_new_build(slow_providers):
    # R4.66: after the restart, POST /dossiers/{domain}/refresh starts a new build of the dossier
    token = slow_providers["ada"]
    domain = SAMPLE_DOMAINS[0]
    r = start_build(token, domain, key=new_key())
    assert r.status_code == 202, r.text
    _wait_spent(lambda: _dossier(token, domain))
    _restart()
    failed = _dossier(token, domain)
    assert failed["state"] == "failed", failed

    _set_faults("none")
    r = call("POST", f"/dossiers/{domain}/refresh", token=token, key=new_key(), body={}, timeout=10)
    assert r.status_code == 202, r.text
    assert r.json()["state"] == "building", r.text
    started = await_settled(token, domain, timeout=120)
    assert started["state"] == "ready", started
    assert started["spent_units"] >= failed["spent_units"], (failed["spent_units"], started["spent_units"])


def test_ready_build_keeps_its_full_spend_across_restart_and_refresh_adds_to_it(env):
    # R4.64 (one build across restart: spend counted, not reset), R4.65 (every billed unit kept),
    # R4.66 (refresh after restart starts a new build whose spend adds to the dossier total)
    token = env["ada"]
    domain = SAMPLE_DOMAINS[0]
    r = start_build(token, domain, key=new_key())
    assert r.status_code == 202, r.text
    ready = await_settled(token, domain, timeout=120)
    assert ready["state"] == "ready", ready
    spent = ready["spent_units"]
    assert spent > 0, ready

    _restart()

    after = _dossier(token, domain)
    assert after["state"] == "ready", after
    assert after["spent_units"] == spent, (spent, after["spent_units"])
    assert after["spent_units"] <= 80, after  # one build spends at most 80 units (R4.64, §9)

    r = call("POST", f"/dossiers/{domain}/refresh", token=token, key=new_key(), body={}, timeout=10)
    assert r.status_code == 202, r.text
    refreshed = await_settled(token, domain, timeout=120)
    assert refreshed["state"] == "ready", refreshed
    assert refreshed["spent_units"] > spent, (spent, refreshed["spent_units"])
