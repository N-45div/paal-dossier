"""Stage 3 restarts: the container is killed abruptly (docker kill) and started again with the
same container and filesystem (docker start). Black-box over HTTP plus docker on the one
container this suite runs, by its exact name, prover-stage3-svc (run_suite.sh).

Ledger ids: R3D (R3.70-R3.78): durability, accounts and tokens, dossiers, as_of, values,
history, feed seq, idempotent replay, clock. Rul-S3-2 (durability, building becomes failed),
Rul-S3-4 (seq continues after restart).

Spec (part 3, Restarts): "The container may be stopped abruptly at any time ... and then started
again. When no build is running at the stop, the service answers after the restart exactly as
it did before the stop", with the list of checks used below.
"""
import subprocess
import time

import requests

from conftest import BASE_URL, call, login, mock, mock_faults, mock_reset, new_key, set_clock, start_build
import test_stage3_history as h

SVC = "prover-stage3-svc"
DOMAIN = h.DOMAIN


def _restart():
    subprocess.run(["docker", "kill", SVC], check=True, timeout=60, capture_output=True)
    subprocess.run(["docker", "start", SVC], check=True, timeout=60, capture_output=True)
    deadline = time.time() + 60
    while True:
        try:
            if requests.get(BASE_URL + "/health", timeout=2).status_code == 200:
                return
        except requests.RequestException:
            pass
        assert time.time() < deadline, "service did not answer /health within 60 s after restart"
        time.sleep(0.5)


def _snapshot(token):
    return {
        "dossier": call("GET", f"/dossiers/{DOMAIN}", token=token, timeout=10).json(),
        "as_of": call("GET", f"/dossiers/{DOMAIN}?as_of={h.T0.replace('+', '%2B')}", token=token, timeout=10).json(),
        "values": call("GET", f"/dossiers/{DOMAIN}/values?true_at=2026-02-01&as_of={h.T1.replace('+', '%2B')}",
                       token=token, timeout=10).json(),
        "history": call("GET", f"/dossiers/{DOMAIN}/history", token=token, timeout=10).json(),
        "changes": call("GET", "/changes?since=0&limit=200", token=token, timeout=10).json(),
    }


def test_restart_keeps_accounts_tokens_dossiers_history_feed_and_clock(env):
    # R3D: accounts sign in, tokens valid, dossiers / as_of / values / history / feed unchanged;
    # idempotent replay answers as before; the clock keeps its time; new feed seq is larger.
    h._two_builds(env)
    token = env["ada"]
    key = new_key()
    first = start_build(token, DOMAIN, key=key)            # idempotent request before the stop
    before = _snapshot(token)
    max_seq = max(c["seq"] for c in before["changes"]["changes"])
    set_clock(h.T1)

    _restart()

    # accounts and tokens
    assert login("ada@example.com").startswith("tok_")
    after = _snapshot(token)
    assert after == before, "dossier, as_of, values, history or feed changed across the restart"
    # the idempotent replay answers as it did before the stop
    replay = start_build(token, DOMAIN, key=key)
    assert replay.status_code == first.status_code, (replay.status_code, first.status_code)
    assert replay.json() == first.json()
    # the clock still reads the time it had before the stop (no POST /_test/clock here)
    mock("POST", "/_mock/epoch", body={"epoch": 0})
    r = call("POST", f"/dossiers/{DOMAIN}/refresh", token=token, key=new_key(), body={}, timeout=10)
    assert r.status_code in (200, 202), r.text
    deadline = time.time() + 120
    while call("GET", f"/dossiers/{DOMAIN}", token=token, timeout=10).json()["state"] == "building":
        assert time.time() < deadline
        time.sleep(0.2)
    feed = call("GET", "/changes?since=0&limit=200", token=token, timeout=10).json()["changes"]
    new = [c for c in feed if c["seq"] > max_seq]
    assert new, "the refresh after the restart added no feed entry"
    assert all(c["seq"] > max_seq for c in new)
    assert all(c["learned_at"].startswith(h.T1[:19]) for c in new), new
    assert len({c["seq"] for c in feed}) == len(feed)
    mock("POST", "/_mock/epoch", body={"epoch": 0})


def test_build_in_flight_at_stop_becomes_failed_with_no_entries(env):
    # Rul-S3-2: a dossier left building after an abrupt stop becomes failed on start, and the
    # stopped build adds no history or feed entry.
    h._two_builds(env)
    token = env["ada"]
    mock("POST", "/_mock/epoch", body={"epoch": 1})
    set_clock("2026-05-01T09:00:00+00:00")
    mock_faults("nimble", ["extract"], "delay", seconds=10)
    try:
        r = call("POST", f"/dossiers/{DOMAIN}/refresh", token=token, key=new_key(), body={}, timeout=10)
        assert r.status_code in (200, 202), r.text
        assert call("GET", f"/dossiers/{DOMAIN}", token=token, timeout=10).json()["state"] == "building"
        history_before = call("GET", f"/dossiers/{DOMAIN}/history", token=token, timeout=10).json()
        feed_before = call("GET", "/changes?since=0&limit=200", token=token, timeout=10).json()
        _restart()
    finally:
        mock_faults("nimble", ["extract"], "none")
    d = call("GET", f"/dossiers/{DOMAIN}", token=token, timeout=10).json()
    assert d["state"] == "failed", d["state"]
    assert call("GET", f"/dossiers/{DOMAIN}/history", token=token, timeout=10).json() == history_before
    assert call("GET", "/changes?since=0&limit=200", token=token, timeout=10).json() == feed_before
    mock("POST", "/_mock/epoch", body={"epoch": 0})
