"""Stage 3, RULING-BASED (not in the specification): Rul-S3-2 says a dossier left building after
an abrupt stop becomes failed on start, with no history or feed entry. The specification's
Restarts section only constrains restarts when no build is running, so a failure in this file is
a ruling failure, never a specification failure.

The 10-second delay on nimble extract (mock fault) keeps the build in flight long enough for the
stop. A service that finishes its build faster than the delay does not exercise the rule and
the test then fails at the state check, so builders should not treat that as a spec failure.

Container: SVC_CONTAINER (default prover-stage3-svc), killed with docker kill, started again with
docker start.
"""
import os
import subprocess
import time

import requests

from conftest import BASE_URL, call, mock, mock_faults, new_key, set_clock
import test_stage3_history as h

SVC = os.environ.get("SVC_CONTAINER", "prover-stage3-svc")
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


def test_ruling_build_in_flight_at_stop_becomes_failed_with_no_entries(env):
    # Rul-S3-2 (ruling, not spec): see the module docstring.
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
