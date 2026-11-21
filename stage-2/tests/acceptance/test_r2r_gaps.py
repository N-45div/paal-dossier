"""Stage-2 research-engine gap tests (R2R ids with no direct test, from builder-b's trace).

Black-box: the dossier API and the mock web's call log (served pages per call). Ledger ids:
R2.17 (a citation's provider served the text its excerpt came from), R2.49 (every page a
research claim cites is gathered and read), R2.50 (an unsupported research claim is never a
candidate), R2.51 (a candidate's provider is a provider that served the excerpt's text, when
another provider is down).
"""
from conftest import (await_settled, check_dossier_fields, mock_calls, mock_faults,
                      start_build)

RANK = "rank-co.test"
TRAP = "trap-co.test"
DUP = "dup-co.test"
FIELDS = ["legal_name", "founded_year", "hq_city", "headcount_range", "ceo", "funding_total"]


def _build(env, domain):
    r = start_build(env["ada"], domain)
    assert r.status_code == 202, r.text
    return await_settled(env["ada"], domain, timeout=120)


def _served_by(calls, provider, url):
    """True when a call by `provider` served the text of `url` (status 200)."""
    return any(c["provider"] == provider and c.get("status") == 200
               and any(s["url"] == url for s in c.get("served", []))
               for c in calls)


def _all_candidates(d):
    for name in FIELDS:
        for c in d["fields"][name].get("candidates", []):
            yield name, c


def test_r2_17_candidate_provider_served_the_excerpt_text(env):
    # R2.17
    d = _build(env, RANK)
    calls = mock_calls()
    seen = list(_all_candidates(d))
    assert seen, "rank-co must have candidates"
    for name, c in seen:
        assert _served_by(calls, c["provider"], c["url"]), (name, c["provider"], c["url"])


def test_r2_49_every_cited_page_is_read(env):
    # R2.49: trap-co cites page-1 for research claims that page does not support; the build
    # must still read that page like any other.
    d = _build(env, TRAP)
    calls = mock_calls()
    cited = {"https://trap-co.test/page-1"}
    for url in cited:
        assert any(s["url"] == url for c in calls for s in c.get("served", [])), url
    check_dossier_fields(d, TRAP, calls)


def test_r2_50_unsupported_research_claim_is_not_a_candidate(env):
    # R2.50: trap-co's research excerpts are not sentences of any served page.
    d = _build(env, TRAP)
    for name in FIELDS:
        assert d["fields"][name].get("candidates", []) == [], name
        assert d["fields"][name]["value"] is None, name


def test_r2_51_provider_is_one_that_served_the_text_when_another_is_down(env):
    # R2.51: nimble extract is down; any candidate's provider must still be one that served
    # the excerpt's text.
    mock_faults("nimble", ["extract"], "error")
    try:
        d = _build(env, RANK)
        calls = mock_calls()
    finally:
        mock_faults("nimble", ["extract"], "none")
    for name, c in _all_candidates(d):
        assert _served_by(calls, c["provider"], c["url"]), (name, c["provider"], c["url"])
    check_dossier_fields(d, RANK, calls)
