import time

import pytest
from starlette.testclient import TestClient

from app.main import create_app

FIXTURE = {"now": "2026-03-01T09:00:00+00:00",
           "users": [{"id": "u_ada", "email": "ada@example.com",
                      "password": "correct horse", "display_name": "Ada"},
                     {"id": "u_bob", "email": "bob@example.com",
                      "password": "correct horse", "display_name": "Bob"}]}


@pytest.fixture
def client():
    with TestClient(create_app(), raise_server_exceptions=False) as c:
        assert c.post("/_test/reset", json=FIXTURE).status_code == 204
        yield c


def login(c, who="ada"):
    r = c.post("/auth/login", json={"email": f"{who}@example.com", "password": "correct horse"})
    return {"Authorization": "Bearer " + r.json()["token"]}


def code(r):
    return r.json()["error"]["code"]


def test_create_replay_and_conflict(client):
    h = {**login(client), "Idempotency-Key": "k1"}
    r = client.post("/dossiers", json={"domain": "WWW.Acme-Robotics.TEST."}, headers=h)
    assert r.status_code == 202 and r.json()["domain"] == "acme-robotics.test"
    first = r.json()
    r = client.post("/dossiers", json={"domain": "WWW.Acme-Robotics.TEST.", "x": 1}, headers=h)
    assert r.status_code == 200 and r.json() == first
    r = client.post("/dossiers", json={"domain": "other.test"}, headers=h)
    assert (r.status_code, code(r)) == (409, "idempotency_key_reuse")
    r = client.post("/dossiers", json={"domain": "acme-robotics.test"},
                    headers={**login(client), "Idempotency-Key": "k2"})
    assert r.status_code == 200 and r.json()["dossier_id"] == first["dossier_id"]


def test_validation_order(client):
    auth = login(client)
    assert client.post("/dossiers", json={"domain": "a.test"}).status_code == 401
    r = client.post("/dossiers", json={"domain": "a.test"}, headers=auth)
    assert code(r) == "missing_idempotency_key"
    h = {**auth, "Idempotency-Key": "k"}
    assert client.post("/dossiers", json={"domain": "http://a.test/x"}, headers=h).status_code == 422
    assert client.post("/dossiers", json={}, headers=h).status_code == 422
    assert client.post("/dossiers", json={"domain": 3}, headers=h).status_code == 400
    assert client.post("/dossiers", content=b"[", headers=h).status_code == 400
    h["Idempotency-Key"] = "x" * 256
    assert client.post("/dossiers", json={"domain": "a.test"}, headers=h).status_code == 422


def test_build_read_refresh_list(client):
    auth = login(client)
    client.post("/dossiers", json={"domain": "acme.test"}, headers={**auth, "Idempotency-Key": "a"})
    for _ in range(50):
        d = client.get("/dossiers/ACME.test", headers=auth).json()
        if d["state"] != "building":
            break
        time.sleep(0.05)
    assert d["state"] == "ready" and d["researched_at"] == "2026-03-01T09:00:00+00:00"
    assert d["fields"]["ceo"] == {"value": None, "status": "unknown", "citations": []}
    r = client.post("/dossiers/acme.test/refresh", headers={**auth, "Idempotency-Key": "r"})
    assert r.status_code == 202 and r.json()["state"] == "building"
    assert client.post("/dossiers/nope.test/refresh",
                       headers={**auth, "Idempotency-Key": "r2"}).status_code == 404
    assert client.get("/dossiers/zzz.test", headers=auth).status_code == 404
    items = client.get("/dossiers?q=ACM&limit=1", headers=auth).json()
    assert items["has_more"] is False and items["dossiers"][0]["domain"] == "acme.test"
    for q in ("limit=0", "limit=201", "limit=1e1", "offset=-1", "offset=", "limit=+4"):
        assert client.get("/dossiers?" + q, headers=auth).status_code == 422


def test_export_import_roundtrip(client):
    auth = login(client)
    client.post("/dossiers", json={"domain": "acme.test"}, headers={**auth, "Idempotency-Key": "a"})
    exported = client.get("/_test/export").json()
    assert exported["track"] == "dossier" and exported["format_version"] == 1
    client.post("/_test/reset", json={"now": FIXTURE["now"]})
    assert client.post("/_test/import", json=exported).status_code == 204
    assert client.get("/dossiers/acme.test", headers=auth).status_code == 200
    r = client.post("/dossiers", json={"domain": "acme.test"}, headers={**auth, "Idempotency-Key": "a"})
    assert r.status_code == 200
    assert client.post("/_test/import", json={**exported, "format_version": 2}).status_code == 422
    assert client.post("/_test/import", content=b"x").status_code == 400
    assert client.post("/_test/import", json={"track": "dossier", "format_version": 1,
                                              "state": {}}).status_code == 422
    assert client.get("/dossiers/acme.test", headers=auth).status_code == 200


def test_huge_integer_query_parameters_are_not_5xx(client):
    auth = login(client)
    r = client.get("/dossiers?offset=" + "9" * 5000, headers=auth)
    assert r.status_code == 200 and r.json() == {"dossiers": [], "has_more": False}
    assert client.get("/dossiers?offset=" + "0" * 5000, headers=auth).status_code == 200
    assert client.get("/dossiers?limit=" + "9" * 5000, headers=auth).status_code == 422


def test_query_integers_reject_trailing_newline_and_other_non_digits(client):
    auth = login(client)
    for q in ("limit=5%0A", "offset=0%0A", "limit=%0A5", "limit=5%20", "limit=%EF%BC%95",
              "offset=%D9%A0"):
        assert client.get("/dossiers?" + q, headers=auth).status_code == 422, q
    assert client.get("/dossiers?limit=5&offset=0", headers=auth).status_code == 200


def test_domain_labels_and_timestamps_reject_embedded_newlines(client):
    auth = login(client)
    h = {**auth, "Idempotency-Key": "nl"}
    for domain in ("acme\n.test", "acme.te\nst", "a\r\n.test"):
        r = client.post("/dossiers", json={"domain": domain}, headers={**h, "Idempotency-Key": domain})
        assert r.status_code == 422, repr(domain)
    assert client.post("/_test/clock", json={"now": "2027-03-01T09:00:00+00:00\n"}).status_code == 422
