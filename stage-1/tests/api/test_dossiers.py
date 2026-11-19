import time

from starlette.testclient import TestClient

from app.main import create_app
from conftest import FIXTURE, login, make_engine

KNOWN = {"value": "Acme", "status": "known", "citations": [{"url": "https://a.test/x", "excerpt": "e", "provider": "nimble"}]}


def post(client, headers, body, key="k1"):
    return client.post("/dossiers", json=body, headers={**headers, "Idempotency-Key": key})


def wait_ready(client, headers, domain="acme.test"):
    for _ in range(100):
        r = client.get(f"/dossiers/{domain}", headers=headers)
        if r.json()["state"] != "building":
            return r.json()
        time.sleep(0.02)
    raise AssertionError("build did not end")


def test_create_build_read(ada):
    engine = make_engine(fields={"legal_name": KNOWN, "ceo": {"value": "x", "status": "known", "citations": []}}, units=7)
    with TestClient(create_app(engine)) as c:
        c.post("/_test/reset", json=FIXTURE)
        h = login(c)
        r = post(c, h, {"domain": " WWW.Acme.test. "})
        assert r.status_code == 202 and r.json()["state"] == "building" and r.json()["domain"] == "acme.test"
        body = wait_ready(c, h)
        assert body["state"] == "ready" and body["spent_units"] == 7
        assert body["researched_at"] == "2026-03-01T09:00:00+00:00"
        assert body["fields"]["legal_name"] == KNOWN
        assert body["fields"]["ceo"] == {"value": None, "status": "unknown", "citations": []}
        assert list(body["fields"]) == ["legal_name", "hq_city", "ceo", "founded_year", "headcount_range", "funding_total"]
        again = post(c, h, {"domain": "acme.test"}, key="k2")
        assert again.status_code == 200 and again.json()["state"] == "ready"
        assert c.post("/dossiers/ACME.test/refresh", headers={**h, "Idempotency-Key": "r1"}).status_code == 202
        assert wait_ready(c, h)["spent_units"] == 14


def test_failed_build_keeps_fields():
    with TestClient(create_app(make_engine(ok=False))) as c:
        c.post("/_test/reset", json=FIXTURE)
        h = login(c)
        post(c, h, {"domain": "acme.test"})
        body = wait_ready(c, h)
        assert body["state"] == "failed" and body["researched_at"] is None
        assert all(f["status"] == "unknown" for f in body["fields"].values())


def test_engine_exception_is_failed_not_5xx():
    async def boom(domain, spend):
        raise RuntimeError("x")

    with TestClient(create_app(boom)) as c:
        c.post("/_test/reset", json=FIXTURE)
        h = login(c)
        assert post(c, h, {"domain": "acme.test"}).status_code == 202
        assert wait_ready(c, h)["state"] == "failed"


def test_idempotency(client, ada):
    first = post(client, ada, {"domain": "acme.test"}, key="K")
    assert first.status_code == 202
    replay = post(client, ada, {"domain": "acme.test", "extra": 1}, key="K")
    assert replay.status_code == 200 and replay.json() == first.json()
    assert post(client, ada, {"domain": "other.test"}, key="K").status_code == 409
    assert post(client, ada, {"domain": 5}, key="K").status_code == 409  # claimed key beats validation
    assert post(client, ada, {"domain": "ACME.test"}, key="K").status_code == 409
    bob = login(client, "bob@example.com")
    assert post(client, bob, {"domain": "other.test"}, key="K").status_code == 202
    other_path = client.post("/dossiers/acme.test/refresh", headers={**ada, "Idempotency-Key": "K"})
    assert other_path.status_code == 202


def test_idempotency_errors(client, ada):
    assert client.post("/dossiers", json={"domain": "a.test"}, headers=ada).status_code == 400
    assert client.post("/dossiers", json={"domain": "a.test"}, headers={**ada, "Idempotency-Key": "x" * 256}).status_code == 422
    assert client.post("/dossiers", content=b"[]", headers={**ada, "Idempotency-Key": "k"}).status_code == 400
    assert client.post("/dossiers", json={}, headers={**ada, "Idempotency-Key": "k"}).status_code == 422
    assert client.post("/dossiers", json={"domain": 3}, headers={**ada, "Idempotency-Key": "k"}).status_code == 400
    assert client.post("/dossiers", json={"domain": "https://a.test"}, headers={**ada, "Idempotency-Key": "k"}).status_code == 422
    assert post(client, ada, {"domain": "a.test"}, key="k").status_code == 202  # failed key is reusable


def test_refresh_errors_and_building_dedup(ada):
    with TestClient(create_app(make_engine(delay=0.3))) as c:
        c.post("/_test/reset", json=FIXTURE)
        h = login(c)
        assert c.post("/dossiers/nope.test/refresh", headers={**h, "Idempotency-Key": "a"}).status_code == 404
        assert c.post("/dossiers/bad_domain/refresh", headers={**h, "Idempotency-Key": "a"}).status_code == 422
        post(c, h, {"domain": "acme.test"})
        r = c.post("/dossiers/acme.test/refresh", headers={**h, "Idempotency-Key": "b"})
        assert r.status_code == 202 and r.json()["state"] == "building"
        assert wait_ready(c, h)["spent_units"] == 3  # one build only


def test_read_and_list(client, ada):
    assert client.get("/dossiers/acme.test", headers=ada).status_code == 404
    assert client.get("/dossiers/a%20b", headers=ada).status_code == 422
    for i, d in enumerate(["b.test", "a.test", "ab.test"]):
        post(client, ada, {"domain": d}, key=f"k{i}")
    names = lambda r: [x["domain"] for x in r.json()["dossiers"]]
    assert names(client.get("/dossiers", headers=ada)) == ["a.test", "ab.test", "b.test"]
    assert names(client.get("/dossiers?q=A", headers=ada)) == ["a.test", "ab.test"]
    assert names(client.get("/dossiers?q=", headers=ada)) == ["a.test", "ab.test", "b.test"]
    page = client.get("/dossiers?limit=1&offset=1", headers=ada).json()
    assert [x["domain"] for x in page["dossiers"]] == ["ab.test"] and page["has_more"] is True
    for q in ("limit=0", "limit=201", "limit=1e1", "limit=+4", "limit=4.0", "limit=", "offset=-1", "offset=x"):
        assert client.get("/dossiers?" + q, headers=ada).status_code == 422, q


def test_export_import_roundtrip(client, ada):
    first = post(client, ada, {"domain": "acme.test"}, key="K")
    wait_ready(client, ada)
    exported = client.get("/_test/export").json()
    assert exported["track"] == "dossier" and exported["format_version"] == 1
    client.post("/_test/reset", json=FIXTURE)
    assert client.get("/dossiers/acme.test", headers=ada).status_code == 401
    assert client.post("/_test/import", json=exported).status_code == 204
    assert client.post("/_test/import", json=exported).status_code == 204
    assert client.get("/_test/export").json() == exported
    assert post(client, ada, {"domain": "acme.test"}, key="K").json() == first.json()
    assert client.get("/dossiers/acme.test", headers=ada).json()["state"] == "ready"
    login(client)


def test_import_rejects_bad_state(client):
    before = client.get("/_test/export").json()
    for bad in ({}, {"track": "x", "format_version": 1, "state": {}}, {"track": "dossier", "format_version": 2, "state": {}},
                {"track": "dossier", "format_version": 1}, {"track": "dossier", "format_version": 1, "state": {"users": 1}}):
        assert client.post("/_test/import", json=bad).status_code == 422
    assert client.post("/_test/import", content=b"{").status_code == 400
    assert client.get("/_test/export").json() == before


def test_export_during_build_holds_prior_state():
    with TestClient(create_app(make_engine(delay=0.3))) as c:
        c.post("/_test/reset", json=FIXTURE)
        h = login(c)
        post(c, h, {"domain": "acme.test"})
        exported = c.get("/_test/export").json()
        dossier = exported["state"]["dossiers"][0]
        assert dossier["state"] == "failed" and dossier["spent_units"] == 0
        c.post("/_test/import", json=exported)
        assert c.get("/dossiers/acme.test", headers=h).json()["state"] == "failed"
        time.sleep(0.5)  # the abandoned build must not touch the imported state
        assert c.get("/dossiers/acme.test", headers=h).json()["spent_units"] == 0


def test_huge_integer_query_values(client, ada):
    r = client.get("/dossiers?offset=" + "9" * 5000, headers=ada)
    assert r.status_code == 200 and r.json() == {"dossiers": [], "has_more": False}
    assert client.get("/dossiers?limit=" + "9" * 5000, headers=ada).status_code == 422


def test_build_without_successful_call_fails():
    with TestClient(create_app(make_engine(units=0))) as c:
        c.post("/_test/reset", json=FIXTURE)
        h = login(c)
        post(c, h, {"domain": "acme.test"})
        assert wait_ready(c, h)["state"] == "failed"


def test_leading_zeros_in_integer_parameters(client, ada):
    post(client, ada, {"domain": "a.test"})
    assert client.get("/dossiers?limit=" + "0" * 19 + "1", headers=ada).status_code == 200
    page = client.get("/dossiers?offset=" + "0" * 19, headers=ada).json()
    assert len(page["dossiers"]) == 1


def test_replay_identity_uses_raw_path(client, ada):
    post(client, ada, {"domain": "one.test"}, key="c")
    first = client.post("/dossiers/%6fne.test/refresh", headers={**ada, "Idempotency-Key": "K"})
    second = client.post("/dossiers/one.test/refresh", headers={**ada, "Idempotency-Key": "K"})
    assert (first.status_code, second.status_code) == (202, 202)
    again = client.post("/dossiers/one.test/refresh", headers={**ada, "Idempotency-Key": "K"})
    assert again.status_code == 200
