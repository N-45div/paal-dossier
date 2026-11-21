"""Stage 3: history, change feed, as_of, values and executives, black-box over HTTP.

Corpus: history-co.test (prover-corpus). Epoch 0 says Dana Ruiz is CEO (page published
2026-01-10); epoch 1 says Lee Park is CEO (page published 2026-03-20). The mock's epoch is
switched with POST /_mock/epoch between two builds. Clock values are set with POST /_test/clock.

Spec references are to the stage-3 spec (parts 1-3): "Two times per value", "Executives",
"Changes and corrections", "GET /dossiers/{domain}?as_of=", "GET /dossiers/{domain}/values",
"GET /dossiers/{domain}/history", "GET /changes". Ledger ids are named in each test as the
ledger assigns them (see stage-3/LEDGER.md); the id column of this file is filled in when the
ledger rows are final.
"""
from conftest import (await_settled, call, mock, mock_reset, new_key, set_clock, start_build)

DOMAIN = "history-co.test"
T0 = "2026-03-01T09:00:00+00:00"   # first build
T1 = "2026-04-01T09:00:00+00:00"   # second build, after the epoch switch


def _two_builds(env):
    mock_reset(0)
    set_clock(T0)
    assert start_build(env["ada"], DOMAIN).status_code == 202
    d0 = await_settled(env["ada"], DOMAIN, timeout=120)
    assert d0["state"] == "ready", d0["state"]
    assert d0["fields"]["ceo"]["value"] == "Dana Ruiz"
    mock("POST", "/_mock/epoch", body={"epoch": 1})
    set_clock(T1)
    r = call("POST", f"/dossiers/{DOMAIN}/refresh", token=env["ada"], key=new_key(), body={})
    assert r.status_code in (200, 202), r.text
    await_settled(env["ada"], DOMAIN, timeout=120)
    mock("POST", "/_mock/epoch", body={"epoch": 0})


def _get(env, path):
    return call("GET", path, token=env["ada"], timeout=10)


def test_history_has_initial_then_change_with_learned_at(env):
    # Two times per value; history (typed entries, oldest first)
    _two_builds(env)
    r = _get(env, f"/dossiers/{DOMAIN}/history")
    assert r.status_code == 200, r.text
    ceo = r.json()["fields"]["ceo"]
    assert [e["type"] for e in ceo] == ["initial", "change"], ceo
    assert ceo[0]["value"] == "Dana Ruiz" and ceo[0]["learned_at"].startswith("2026-03-01T09:00:00")
    assert ceo[1]["value"] == "Lee Park" and ceo[1]["learned_at"].startswith("2026-04-01T09:00:00")
    assert set(r.json()["fields"]) == {"legal_name", "hq_city", "founded_year", "headcount_range",
                                       "ceo", "funding_total", "executives"}


def test_feed_holds_the_change_exactly_once(env):
    # Every change to a selected value appears exactly once in the feed
    _two_builds(env)
    r = _get(env, "/changes?since=0&limit=200")
    assert r.status_code == 200, r.text
    body = r.json()
    ceo = [c for c in body["changes"] if c["domain"] == DOMAIN and c["field"] == "ceo"]
    assert len(ceo) == 1, ceo
    assert ceo[0]["type"] == "change" and ceo[0]["from"] == "Dana Ruiz" and ceo[0]["to"] == "Lee Park"
    seqs = [c["seq"] for c in body["changes"]]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)
    # a build with the same selected value adds nothing (no duplicate on the next refresh)
    before = len(body["changes"])
    r = call("POST", f"/dossiers/{DOMAIN}/refresh", token=env["ada"], key=new_key(), body={})
    assert r.status_code in (200, 202), r.text
    await_settled(env["ada"], DOMAIN, timeout=120)
    again = _get(env, "/changes?since=0&limit=200").json()["changes"]
    assert len(again) == before, (before, len(again))


def test_changes_since_and_limit_paging(env):
    # GET /changes: since is exclusive, limit 1..200, has_more
    _two_builds(env)
    first = _get(env, "/changes?since=0&limit=1").json()
    assert len(first["changes"]) == 1 and first["has_more"] in (True, False)
    if first["has_more"]:
        nxt = _get(env, f"/changes?since={first['changes'][0]['seq']}&limit=1").json()
        assert nxt["changes"][0]["seq"] > first["changes"][0]["seq"]
    assert _get(env, "/changes?since=0&limit=0").status_code == 422
    assert _get(env, "/changes?since=0&limit=201").status_code == 422


def test_as_of_answers_as_the_service_had_it(env):
    # GET ?as_of= decided by learned_at
    _two_builds(env)
    before = _get(env, f"/dossiers/{DOMAIN}?as_of=2026-03-15T00:00:00+00:00")
    assert before.status_code == 200, before.text
    assert before.json()["fields"]["ceo"]["value"] == "Dana Ruiz"
    after = _get(env, f"/dossiers/{DOMAIN}?as_of=2026-04-02T00:00:00+00:00")
    assert after.status_code == 200 and after.json()["fields"]["ceo"]["value"] == "Lee Park"
    assert _get(env, f"/dossiers/{DOMAIN}?as_of=2026-02-01T00:00:00+00:00").status_code == 404
    assert _get(env, f"/dossiers/{DOMAIN}?as_of=2026-03-15T00:00:00").status_code == 422
    assert _get(env, "/dossiers/nobody.test?as_of=2026-03-15T00:00:00+00:00").status_code == 404


def test_values_at_true_at(env):
    # /values?true_at=: a value per field from the evidence holding on that date
    _two_builds(env)
    early = _get(env, f"/dossiers/{DOMAIN}/values?true_at=2026-02-01&as_of=2026-04-01T09:00:00%2B00:00")
    assert early.status_code == 200, early.text
    assert early.json()["fields"]["ceo"]["value"] == "Dana Ruiz"
    late = _get(env, f"/dossiers/{DOMAIN}/values?true_at=2026-04-01&as_of=2026-04-01T09:00:00%2B00:00")
    assert late.status_code == 200 and late.json()["fields"]["ceo"]["value"] == "Lee Park"
    assert _get(env, f"/dossiers/{DOMAIN}/values?true_at=2026-13-01").status_code == 422


def test_executives_is_a_seventh_field_unknown_without_titles(env):
    # Executives: seventh field, value null and unknown when no cfo, coo or cto is selected
    _two_builds(env)
    d = _get(env, f"/dossiers/{DOMAIN}").json()
    assert "executives" in d["fields"]
    assert d["fields"]["executives"]["value"] is None
    assert d["fields"]["executives"]["status"] == "unknown"
    assert d["fields"]["executives"]["true_from"] is None
    assert d["fields"]["executives"]["learned_at"] is None
