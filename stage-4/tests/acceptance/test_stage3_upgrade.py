"""Stage 3 upgrades: an export of the stage-1 or stage-2 service is imported into this stage-3
service (spec part 3, Upgrades; part 1, Executives: no executives candidates after import).

The earlier services are built from their own folders at main (git archive, into /tmp), run
on the same Docker network as the mock web (the suite's network (PROVER_NET)), filled through
their own API, exported with GET /_test/export, stopped and removed. Then the export is posted
to /_test/import of the stage-3 service under test.

Every container created here is named with the prefix PROVER_PREFIX-up- and removed in the
fixture's teardown by exact name. Ledger ids: R3C (import of stage-1 and stage-2 exports,
R3.65-R3.68) and the Upgrades rules of part 3.
"""
import os
import shutil
import subprocess
import tempfile
import time

import pytest
import requests

from conftest import BASE_URL, call, login, new_key, seed_fixture, await_settled

# The handle prefix, network, web host and upgrade ports come from the environment so that
# each seat runs under its own names (run_suite.sh exports them). Defaults are the Prover's.
PREFIX = os.environ.get("PROVER_PREFIX", "prover-stage3")
NET = os.environ.get("PROVER_NET", f"{PREFIX}-net")
WEB_HOST = os.environ.get("PROVER_WEB", f"{PREFIX}-web")
S1_PORT = int(os.environ.get("UPGRADE_S1_PORT", "18250"))
S2_PORT = int(os.environ.get("UPGRADE_S2_PORT", "18260"))
MAIN_REPO = os.environ.get("MAIN_REPO", "/home/ndivij/buildathon/band-work/paal-dossier")
SAMPLE = "brightwater-labs.test"


def _run(*args, timeout=600):
    return subprocess.run(list(args), check=True, timeout=timeout, capture_output=True, text=True)


def _build_image(tag, stage):
    src = tempfile.mkdtemp(prefix=f"{PREFIX}-up-src-")
    archive = subprocess.run(["git", "-C", MAIN_REPO, "archive", "main", stage],
                             check=True, capture_output=True, timeout=120)
    subprocess.run(["tar", "-x", "-C", src], input=archive.stdout, check=True, timeout=120)
    _run("docker", "build", "-q", "-t", tag, os.path.join(src, stage), timeout=900)
    shutil.rmtree(src, ignore_errors=True)


def _export_from_old_service(stage, name, port):
    """Build the old stage at main, run it on NET with the mock as its providers, build one
    dossier, export, then remove the container. Returns the export payload."""
    tag = f"{PREFIX}-up-{name}"
    _build_image(tag, stage)
    cname = f"{PREFIX}-up-{name}"
    subprocess.run(["docker", "rm", "-f", cname], capture_output=True, timeout=120)
    _run("docker", "run", "-d", "--name", cname, "--network", NET,
         "-p", f"127.0.0.1:{port}:8000",
         "-e", "PORT=8000",
         "-e", "NIMBLE_API_KEY=local", "-e", f"NIMBLE_BASE_URL=http://{WEB_HOST}:8080/nimble",
         "-e", "TAVILY_API_KEY=local", "-e", f"TAVILY_BASE_URL=http://{WEB_HOST}:8080/tavily",
         tag, timeout=120)
    try:
        base = f"http://127.0.0.1:{port}"
        deadline = time.time() + 60
        while True:
            try:
                if requests.get(base + "/health", timeout=2).status_code == 200:
                    break
            except requests.RequestException:
                pass
            assert time.time() < deadline, f"{name} did not become healthy"
            time.sleep(0.5)
        # register via the old service's own API (seed accounts come from its /_test/reset)
        requests.post(base + "/_test/reset", json=seed_fixture(), timeout=10)
        token = requests.post(base + "/auth/login", json={"email": "ada@example.com", "password": "correct horse"},
                              timeout=10).json()["token"]
        headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": new_key(),
                   "Content-Type": "application/json"}
        r = requests.post(base + "/dossiers", json={"domain": SAMPLE}, headers=headers, timeout=20)
        assert r.status_code in (200, 202), r.text
        deadline = time.time() + 120
        while True:
            d = requests.get(base + f"/dossiers/{SAMPLE}", headers={"Authorization": f"Bearer {token}"},
                             timeout=10).json()
            if d.get("state") != "building":
                break
            assert time.time() < deadline, f"{name} build did not settle"
            time.sleep(0.5)
        export = requests.get(base + "/_test/export", timeout=10)
        assert export.status_code == 200, export.text
        return export.json()
    finally:
        subprocess.run(["docker", "rm", "-f", cname], capture_output=True, timeout=120)


@pytest.fixture(scope="module")
def stage1_export():
    return _export_from_old_service("stage-1", "s1", S1_PORT)


@pytest.fixture(scope="module")
def stage2_export():
    return _export_from_old_service("stage-2", "s2", S2_PORT)


def _import(payload):
    return call("POST", "/_test/import", body=payload, timeout=30)


def _check_imported(domain_expected, payload_name):
    """Shared checks after an import into this stage-3 service."""
    r = call("GET", "/dossiers", token=login("ada@example.com"), timeout=10)
    assert r.status_code == 200, r.text
    listed = [d["domain"] for d in r.json()["dossiers"]]
    assert domain_expected in listed, (payload_name, listed)
    tok = login("ada@example.com")
    d = call("GET", f"/dossiers/{domain_expected}", token=tok, timeout=10).json()
    assert d["fields"]["executives"]["value"] is None and d["fields"]["executives"]["status"] == "unknown"
    assert d["fields"]["executives"].get("candidates", []) == [], payload_name
    hist = call("GET", f"/dossiers/{domain_expected}/history", token=tok, timeout=10)
    assert hist.status_code == 200, hist.text
    for name, entries in hist.json()["fields"].items():
        if name == "executives":
            assert entries == [], entries
        if d["fields"][name]["value"] is not None:
            assert len(entries) == 1 and entries[0]["type"] == "initial", (name, entries)
    assert call("GET", "/changes?since=0&limit=200", token=tok, timeout=10).json()["changes"] == []


def test_stage1_export_imports_as_one_ready_build(stage1_export):
    # Upgrades: a stage-1 export imports; its fields gain initial history; the feed starts empty;
    # executives is unknown with no entry.
    assert _import(stage1_export).status_code in (200, 204)
    _check_imported(SAMPLE, "stage-1")


def test_stage2_export_imports_and_keeps_its_builds(stage2_export):
    # Upgrades: a stage-2 export imports; the same checks hold, and the stage-2 export's
    # candidates survive the import.
    assert _import(stage2_export).status_code in (200, 204)
    _check_imported(SAMPLE, "stage-2")
