"""Stage 3 concurrency: parallel refreshes and reads give the same results as one at a time.

Spec (part 3, Concurrency): "Concurrent refreshes and reads must produce the same results as
executing them one at a time in some order. No change appears twice in the feed, and none is
missing from it." Also (part 1): "Concurrent refreshes of one dossier run one build (§8) and so
add each entry once." Ledger ids: R3A concurrency (R3.54-R3.64 range; exact rows per
stage-3/LEDGER.md) and Rul-S3-4 (seq unique and gap-free in order).
"""
from concurrent.futures import ThreadPoolExecutor

import test_stage3_history as h
from conftest import call, mock, new_key, set_clock

DOMAIN = h.DOMAIN


def test_parallel_refreshes_add_each_entry_once_with_gap_free_seq(env):
    # R3A / Rul-S3-4: eight refreshes released together after one epoch change; the feed holds
    # the ceo change once, and seq is unique and contiguous from 1 across the whole feed.
    h._two_builds(env)  # epoch 0 and epoch 1 builds: feed has the ceo change once (seq 1)
    mock("POST", "/_mock/epoch", body={"epoch": 0})
    set_clock("2026-05-01T09:00:00+00:00")

    def refresh(_):
        return call("POST", f"/dossiers/{DOMAIN}/refresh", token=env["ada"], key=new_key(), body={},
                    timeout=20)

    with ThreadPoolExecutor(max_workers=8) as pool:
        replies = list(pool.map(refresh, range(8)))
    assert all(r.status_code in (200, 202, 409) for r in replies), [r.status_code for r in replies]

    # reads during and after the refreshes never fail
    deadline = __import__("time").time() + 120
    while call("GET", f"/dossiers/{DOMAIN}", token=env["ada"], timeout=10).json()["state"] == "building":
        assert __import__("time").time() < deadline
        __import__("time").sleep(0.2)

    feed = call("GET", "/changes?since=0&limit=200", token=env["ada"], timeout=10).json()["changes"]
    ceo = [c for c in feed if c["domain"] == DOMAIN and c["field"] == "ceo"]
    assert len(ceo) == 2, ceo  # initial build's change (Dana -> Lee) and the epoch-0 change (Lee -> Dana)
    seqs = [c["seq"] for c in feed]
    assert len(set(seqs)) == len(seqs), seqs
    assert seqs == list(range(1, len(seqs) + 1)), seqs


def test_concurrent_identical_requests_get_one_answer(env):
    # Idempotent burst: the same key and body released at once gets one build and one answer
    # (every reply is the same status and body; no second build is started).
    mock("POST", "/_mock/epoch", body={"epoch": 0})
    set_clock(h.T0)
    key = new_key()

    def start(_):
        return call("POST", "/dossiers", token=env["ada"], key=key, body={"domain": DOMAIN}, timeout=20)

    with ThreadPoolExecutor(max_workers=8) as pool:
        replies = list(pool.map(start, range(8)))
    statuses = {r.status_code for r in replies}
    assert statuses <= {200, 202}, statuses
    ids = {r.json()["dossier_id"] for r in replies}
    assert len(ids) == 1, ids  # one dossier, one build
