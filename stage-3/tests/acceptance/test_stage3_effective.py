"""Stage 3 Two times per value: true_from from the page's Effective header, else the UTC date of
published_at, else null (spec part 1). Black-box: the candidate's true_from in the dossier.

Corpus: eff-co.test (valid Effective line), eff2-co.test (invalid Effective date 2026-02-30 and a
published_at with offset -05:00, so the UTC date is the next day), eff3-co.test (no Effective line,
no published_at). Ledger ids: R3B candidate true_from (R3.11-R3.29 range; rows per LEDGER.md).
"""
from conftest import call, mock_reset, new_key, set_clock, start_build, await_settled


def _candidate_true_from(env, domain):
    mock_reset(0)
    set_clock("2026-03-01T09:00:00+00:00")
    assert start_build(env["ada"], domain).status_code == 202
    d = await_settled(env["ada"], domain, timeout=120)
    assert d["state"] == "ready", d["state"]
    cands = d["fields"]["ceo"]["candidates"]
    assert cands, f"{domain}: no ceo candidate"
    return cands[0].get("true_from")


def test_valid_effective_header_gives_true_from(env):
    assert _candidate_true_from(env, "eff-co.test") == "2026-02-01"


def test_invalid_effective_falls_back_to_utc_date_of_published_at(env):
    # Effective 2026-02-30 is not a valid date; published_at 2026-03-20T23:30:00-05:00 is
    # 2026-03-21 in UTC.
    assert _candidate_true_from(env, "eff2-co.test") == "2026-03-21"


def test_no_effective_and_no_published_at_gives_null(env):
    assert _candidate_true_from(env, "eff3-co.test") is None
