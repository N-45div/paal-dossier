"""Stage 4 investors and origins (stage-4 spec, Own pages, Origins, Investors; ledger R4.10-R4.41),
black-box over HTTP against the real mock. Each test names the ledger ids it checks.

The expectations are the spec rules applied to the response's own candidates and to the investor
names the mock corpus writes in its pages (for example "Fallowfield Holdings", "Thornbury Ventures",
"Marlowe Equity" on brightwater-labs.test). Nothing here reads service source.
"""
from conftest import SAMPLE_DOMAINS, await_settled, call, new_key, start_build, reset_service, login

import pytest

DOMAIN = SAMPLE_DOMAINS[0]  # brightwater-labs.test
CORPUS_INVESTORS = ("Fallowfield Holdings", "Thornbury Ventures", "Marlowe Equity")
FIELD_ORDER_TAIL = ["executives", "investors"]
INVESTOR_KEYS = {"value", "status", "true_from", "learned_at", "citations", "candidates",
                 "origins", "corroborated", "corroborated_since"}


@pytest.fixture(scope="module")
def built(env_module):
    """One ready build of each sample domain, shared by the tests in this module."""
    ada = env_module["ada"]
    out = {}
    for domain in SAMPLE_DOMAINS:
        r = start_build(ada, domain, key=new_key())
        assert r.status_code == 202, r.text
        out[domain] = await_settled(ada, domain, timeout=120)
    return {"token": ada, "dossiers": out}


@pytest.fixture(scope="module")
def env_module(mock_ready_module):
    reset_service()
    return {"ada": login("ada@example.com")}


@pytest.fixture(scope="module")
def mock_ready_module():
    import requests
    from conftest import MOCK_URL, mock_reset, mock_weather
    r = requests.get(MOCK_URL + "/_mock/health", timeout=5)
    assert r.status_code == 200, "mock web not reachable at MOCK_URL"
    mock_reset(0)
    mock_weather(False)
    yield


def _members(field):
    """Member names by the spec: a name is a member when a candidate with it has kind own or filing,
    or those candidates have two or more distinct origins (R4.32)."""
    by_name = {}
    for c in field["candidates"]:
        by_name.setdefault(c["value"], []).append(c)
    members = set()
    for name, cs in by_name.items():
        if any(c.get("kind") in ("own", "filing") for c in cs):
            members.add(name)
        elif len({c["origin"] for c in cs}) >= 2:
            members.add(name)
    return members


# R4.29: the eighth field, after executives, in every dossier response
def test_investors_is_the_eighth_field_after_executives(built):
    for d in built["dossiers"].values():
        names = list(d["fields"])
        assert len(names) == 8, names
        assert names[-2:] == FIELD_ORDER_TAIL, names


# R4.30: investor names come from the statement phrases; the corpus names appear as candidates
def test_corpus_investor_names_are_candidates_and_the_company_is_not(built):
    fld = built["dossiers"][DOMAIN]["fields"]["investors"]
    names = {c["value"] for c in fld["candidates"]}
    for name in CORPUS_INVESTORS:
        assert name in names, (name, sorted(names))
    assert "Brightwater Labs" not in names, names


# R4.31: each candidate's value is one investor name; a research claim is never a candidate
def test_each_investor_candidate_is_a_single_name_string(built):
    for d in built["dossiers"].values():
        for c in d["fields"]["investors"]["candidates"]:
            assert isinstance(c["value"], str) and c["value"].strip() == c["value"], c
            assert "\n" not in c["value"] and len(c["value"].split()) >= 1, c


# R4.33: the value is the sorted array of member names, null when there is no member; known iff it has one
def test_investors_value_is_sorted_member_array_and_status_follows_membership(built):
    for d in built["dossiers"].values():
        fld = d["fields"]["investors"]
        members = _members(fld)
        if members:
            assert fld["value"] == sorted(members), (fld["value"], sorted(members))
            assert fld["status"] == "known", fld
        else:
            assert fld["value"] is None, fld
            assert fld["status"] == "unknown", fld


# R4.34: the investors field has the keys of the example object
def test_investors_field_has_the_stage4_keys(built):
    fld = built["dossiers"][DOMAIN]["fields"]["investors"]
    assert INVESTOR_KEYS <= set(fld), sorted(fld)


# R4.35: selected is true on every candidate whose name is a member, false on the others
def test_selected_marks_members_only(built):
    for d in built["dossiers"].values():
        fld = d["fields"]["investors"]
        members = _members(fld)
        for c in fld["candidates"]:
            assert c["selected"] is (c["value"] in members), c


# R4.37: citations are, for each member in value order, the url, excerpt and provider of its candidates
def test_investor_citations_follow_member_order(built):
    for d in built["dossiers"].values():
        fld = d["fields"]["investors"]
        if fld["value"] is None:
            continue
        expected = []
        for name in fld["value"]:
            for c in fld["candidates"]:
                if c["value"] == name:
                    expected.append((c["url"], c["excerpt"], c["provider"]))
        got = [(c["url"], c["excerpt"], c["provider"]) for c in fld["citations"]]
        assert got == expected, (got, expected)


# R4.19, R4.21, R4.22, R4.23 (origins keys on every field): candidates carry origin; origins sorted
# distinct; corroborated iff two or more origins; corroborated_since null while not corroborated
def test_origins_keys_on_every_field(built):
    for d in built["dossiers"].values():
        for name, fld in d["fields"].items():
            for c in fld["candidates"]:
                assert "origin" in c and isinstance(c["origin"], str) and c["origin"], (name, c)
            assert {"origins", "corroborated", "corroborated_since"} <= set(fld), (name, sorted(fld))
            assert fld["origins"] == sorted(set(fld["origins"])), (name, fld["origins"])
            assert fld["corroborated"] is (len(fld["origins"]) >= 2), (name, fld["origins"], fld["corroborated"])
            if fld["status"] == "unknown":
                assert fld["origins"] == [], (name, fld)
            if not fld["corroborated"]:
                assert fld["corroborated_since"] is None, (name, fld)


# R4.25-R4.28: investors origins and corroboration are over its members' candidates
def test_investors_origins_and_corroboration_follow_members(built):
    for d in built["dossiers"].values():
        fld = d["fields"]["investors"]
        members = _members(fld)
        if not members:
            assert fld["origins"] == [] and fld["corroborated"] is False, fld
            continue
        member_origins = sorted({c["origin"] for c in fld["candidates"] if c["value"] in members})
        assert fld["origins"] == member_origins, (fld["origins"], member_origins)
        per_member = {m: {c["origin"] for c in fld["candidates"] if c["value"] == m} for m in members}
        assert fld["corroborated"] is all(len(o) >= 2 for o in per_member.values()), fld


# R4.39: the values endpoint gives investors from the candidates at true_at
def test_values_endpoint_gives_investors(built):
    token = built["token"]
    r = call("GET", f"/dossiers/{DOMAIN}/values?true_at=2026-03-01", token=token, timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    values = body.get("fields", body)
    assert "investors" in values, sorted(values)
    got = values["investors"]
    dossier_value = built["dossiers"][DOMAIN]["fields"]["investors"]["value"]
    assert (got.get("value") if isinstance(got, dict) else got) == dossier_value, (got, dossier_value)
