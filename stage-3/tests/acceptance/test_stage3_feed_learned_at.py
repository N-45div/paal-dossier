"""Stage 3 feed and history: learned_at of every change and correction entry is the time of the
build that added it (GET /changes, "learned_at is the time of the build that added the entry";
history entries carry the same time). Checked on two companies: history-co.test (Dana Ruiz to
Lee Park) and vers-co.test (three epochs: Ann Aster, Cy Cole, Bo Bell), so the refresh is not only
on the history-co corpus company.
"""
from datetime import datetime

import pytest

from conftest import call, mock, mock_reset, new_key, set_clock, start_build, await_settled

HISTORY_CO = "history-co.test"
VERS_CO = "vers-co.test"
T0 = "2026-03-01T09:00:00+00:00"
T1 = "2026-04-01T09:00:00+00:00"
T2 = "2026-05-01T09:00:00+00:00"
T3 = "2026-06-01T09:00:00+00:00"   # history-co runs after vers-co: the clock may not move backwards
T4 = "2026-07-01T09:00:00+00:00"


def _instant(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _run_builds(env, domain, steps):
    """steps: (epoch, clock) pairs; the first starts the dossier, later ones refresh it."""
    mock_reset(0)
    for i, (epoch, clock) in enumerate(steps):
        mock("POST", "/_mock/epoch", body={"epoch": epoch})
        set_clock(clock)
        if i == 0:
            assert start_build(env["ada"], domain).status_code == 202
        else:
            r = call("POST", f"/dossiers/{domain}/refresh", token=env["ada"], key=new_key(), body={})
            assert r.status_code in (200, 202), r.text
        d = await_settled(env["ada"], domain, timeout=120)
        assert d["state"] == "ready", d["state"]


def _feed(env, domain, field="ceo"):
    r = call("GET", "/changes?since=0&limit=200", token=env["ada"], timeout=10)
    assert r.status_code == 200, r.text
    return [c for c in r.json()["changes"] if c["domain"] == domain and c["field"] == field]


def test_feed_change_entries_carry_the_adding_builds_time(env):
    # Two refreshes at later clocks on two companies; every change entry's learned_at is its build.
    _run_builds(env, VERS_CO, [(0, T0), (1, T1), (2, T2)])
    _run_builds(env, HISTORY_CO, [(0, T3), (1, T4)])
    history = _feed(env, HISTORY_CO)
    vers = _feed(env, VERS_CO)
    # Ann -> Cy (2025 after 2020) is a change; Cy -> Bo (2022, before 2025) is a correction (R3.32)
    assert [c["type"] for c in history] == ["change"], history
    assert [c["type"] for c in vers] == ["change", "correction"], vers
    for entry in history:
        assert entry["learned_at"] is not None, entry
        assert _instant(entry["learned_at"]) == _instant(T4), entry
    assert _instant(vers[0]["learned_at"]) == _instant(T1), vers[0]
    assert _instant(vers[1]["learned_at"]) == _instant(T2), vers[1]


def test_history_entries_carry_the_same_build_time_as_the_feed(env):
    # history (typed entries) and the feed agree on learned_at for the same change.
    _run_builds(env, VERS_CO, [(0, T0), (1, T1), (2, T2)])
    r = call("GET", f"/dossiers/{VERS_CO}/history", token=env["ada"], timeout=10)
    assert r.status_code == 200, r.text
    ceo = r.json()["fields"]["ceo"]
    assert [e["type"] for e in ceo] == ["initial", "change", "correction"], ceo
    assert [_instant(e["learned_at"]) for e in ceo] == [_instant(T0), _instant(T1), _instant(T2)], ceo
    feed = _feed(env, VERS_CO)
    assert [_instant(c["learned_at"]) for c in feed] == [_instant(T1), _instant(T2)], feed


# Sample companies whose own pages change between epoch 0 and epoch 1 (taken from the sample corpus
# files: pages with the same URL and different text in the two epochs).
SAMPLE_MOVERS = ["ashgrove-solar.test", "brightwater-labs.test", "halvorsen-robotics.test",
                 "mosaic-freight.test", "pemberton-analytics.test", "quillmate.test",
                 "tidemark-energy.test"]


@pytest.mark.parametrize("domain", SAMPLE_MOVERS)
def test_every_entry_of_a_sample_company_carries_the_refresh_build_time(env, domain):
    # Sample companies (not the Prover's own): a build at epoch 0, then a refresh at a later clock
    # at epoch 1. Every feed entry and history entry of the company carries its adding build's time:
    # initial entries the first build's, change and correction entries the refresh's.
    _run_builds(env, domain, [(0, T0), (1, T1)])
    r = call("GET", "/changes?since=0&limit=200", token=env["ada"], timeout=10)
    assert r.status_code == 200, r.text
    feed = [c for c in r.json()["changes"] if c["domain"] == domain]
    assert feed, f"{domain}: the epoch-1 refresh must change at least one value"
    for c in feed:
        assert c["type"] in ("change", "correction"), c
        assert c["learned_at"] is not None, c
        assert _instant(c["learned_at"]) == _instant(T1), c
    h = call("GET", f"/dossiers/{domain}/history", token=env["ada"], timeout=10)
    assert h.status_code == 200, h.text
    for name, entries in h.json()["fields"].items():
        for e in entries:
            assert e["learned_at"] is not None, (name, e)
            expected = T0 if e["type"] == "initial" else T1
            assert _instant(e["learned_at"]) == _instant(expected), (name, e)


def test_a_value_that_disappears_carries_the_refresh_build_time(env):
    # gone-co.test: epoch 0 names a CEO, epoch 1 does not. The value becomes null at the refresh:
    # the history entry (value null) and every feed entry carry the refresh build's time (R3.56 ruling;
    # R3.62). Derived from the clock set for the refresh, not from the service.
    _run_builds(env, "gone-co.test", [(0, T0), (1, T1)])
    h = call("GET", "/dossiers/gone-co.test/history", token=env["ada"], timeout=10)
    assert h.status_code == 200, h.text
    ceo = h.json()["fields"]["ceo"]
    assert ceo[0]["type"] == "initial" and ceo[0]["value"] == "Ann Aster", ceo
    assert _instant(ceo[0]["learned_at"]) == _instant(T0), ceo[0]
    assert ceo[-1]["value"] is None, ceo
    assert _instant(ceo[-1]["learned_at"]) == _instant(T1), ceo[-1]
    for c in _feed(env, "gone-co.test"):
        assert c["learned_at"] is not None, c
        assert _instant(c["learned_at"]) == _instant(T1), c
