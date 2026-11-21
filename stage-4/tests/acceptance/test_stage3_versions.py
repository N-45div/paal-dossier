"""Stage 3 page versions (R3.46, ruling of the lead): one URL gathered three times, with true_from
A=2020-01-01 (epoch 0), C=2025-01-01 (epoch 1), then B=2022-01-01 (epoch 2). Each build replaces
the earlier versions of the URL whose true_from is on or after its own; A must end on 2022-01-01,
so that only B holds at 2023. Corpus: vers-co.test (prover-corpus/). Black-box through /values.
"""
from conftest import call, mock, mock_reset, new_key, set_clock, start_build, await_settled

DOMAIN = "vers-co.test"


def _values(env, true_at):
    r = call("GET", f"/dossiers/{DOMAIN}/values?true_at={true_at}&as_of=2027-01-01T00:00:00%2B00:00",
             token=env["ada"], timeout=10)
    assert r.status_code == 200, r.text
    return r.json()["fields"]["ceo"]["value"]


def test_later_version_ends_earlier_versions_by_true_from(env):
    # R3.46: A (2020) is gathered; C (2025) arrives and A stops holding on 2025; B (2022) arrives,
    # replaces C, and A stops holding on 2022. Holds at 2021: A. At 2023: B. At 2026: B.
    mock_reset(0)
    for epoch, clock in ((0, "2026-03-01T09:00:00+00:00"), (1, "2026-04-01T09:00:00+00:00"),
                         (2, "2026-05-01T09:00:00+00:00")):
        mock("POST", "/_mock/epoch", body={"epoch": epoch})
        set_clock(clock)
        if epoch == 0:
            assert start_build(env["ada"], DOMAIN).status_code == 202
        else:
            r = call("POST", f"/dossiers/{DOMAIN}/refresh", token=env["ada"], key=new_key(), body={})
            assert r.status_code in (200, 202), r.text
        d = await_settled(env["ada"], DOMAIN, timeout=120)
        assert d["state"] == "ready", d["state"]
    assert _values(env, "2021-06-01") == "Ann Aster"
    assert _values(env, "2023-01-01") == "Bo Bell"
    assert _values(env, "2026-06-01") == "Bo Bell"
