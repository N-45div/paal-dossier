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


def test_r2_54_candidate_url_excerpt_provider_follow_citation_rules(env):
    # R2.54: a candidate's url, excerpt and provider follow the citation rules of section 4:
    # the excerpt is copied from the prose the provider served for that url (R1.104-R1.105),
    # and the provider is one that served it (R2.51).
    from conftest import served_index
    from oracle import excerpt_in_prose
    checked = 0
    for domain in (RANK, DUP, "recency-co.test"):
        d = _build(env, domain)
        idx = served_index(mock_calls())
        for name, c in _all_candidates(d):
            proses = idx.get((c["provider"], c["url"]), [])
            assert proses, (domain, name, c["provider"], c["url"])
            assert any(excerpt_in_prose(p, c["excerpt"]) for p in proses), (domain, name, c["excerpt"])
            checked += 1
    assert checked > 0


def test_r2_154_stage1_import_one_candidate_per_value_per_page(env):
    # R2.154: a stage-1 export imports one candidate per value per page. Two verified
    # citations of the same value on the same page (different sentences) give one candidate,
    # whose excerpt is the first one (R2.155).
    from conftest import call
    _build(env, DUP)
    url = f"https://{DUP}/about"
    payload = call("GET", "/_test/export", timeout=10).json()
    state = payload["state"]
    state.pop("schema", None)
    stage1_dossiers = []
    for entry in state["dossiers"]:
        if entry["domain"] != DUP:
            continue
        fields = {}
        for name in FIELDS:
            fields[name] = {"value": None, "status": "unknown", "citations": []}
        fields["founded_year"] = {"value": 2010, "status": "known", "citations": [
            {"url": url, "excerpt": "Dup Co was founded in 2010.", "provider": "nimble"},
            {"url": url, "excerpt": "Dup Co was founded in 2010 by two engineers.",
             "provider": "nimble"},
        ]}
        stage1_dossiers.append({"id": entry["id"], "domain": DUP, "state": "ready",
                                "spent_units": entry["spent_units"],
                                "researched_at": entry["researched_at"], "fields": fields})
    assert stage1_dossiers, "dup-co must be in the export"
    state["dossiers"] = stage1_dossiers
    r = call("POST", "/_test/import", body=payload, timeout=10)
    assert r.status_code in (200, 204), r.text
    token = env["ada"]
    d = call("GET", f"/dossiers/{DUP}", token=token, timeout=10).json()
    cands = d["fields"]["founded_year"]["candidates"]
    assert [(c["value"], c["url"]) for c in cands] == [(2010, url)], cands
    assert cands[0]["excerpt"] == "Dup Co was founded in 2010.", cands[0]["excerpt"]
