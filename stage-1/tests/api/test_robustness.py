"""Odd inputs never produce a 5xx (R1.58)."""
import pytest
from starlette.testclient import TestClient

from app.main import create_app

FIXTURE = {"now": "2026-03-01T09:00:00+00:00",
           "users": [{"id": "u_ada", "email": "ada@example.com",
                      "password": "correct horse", "display_name": "Ada"}]}
FIELDS = ("legal_name", "hq_city", "ceo", "founded_year", "headcount_range", "funding_total")


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app(), raise_server_exceptions=False) as c:
        c.post("/_test/reset", json=FIXTURE)
        yield c


@pytest.fixture(scope="module")
def auth(client):
    r = client.post("/auth/login", json={"email": "ada@example.com", "password": "correct horse"})
    return {"Authorization": "Bearer " + r.json()["token"]}


BODIES = [b"\xff\xfe\x00", b"[" * 100000, b'{"a":' * 50000, b"1" * 6000,
          b'{"domain": 1' + b"0" * 6000 + b"}", b"NaN", b'{"domain": NaN}', b'"\\ud800"',
          b'{"domain": "\\ud800.test"}', b"", b"null",
          b'{"now": "0000-01-01T00:00:00+00:00"}', b'{"now": "9999-12-31T23:59:59-23:59"}',
          b'{"email": "\\ud800@x", "password": "\\ud800\\ud800\\ud800\\ud800", "display_name": "x"}']
PATHS = ["/auth/signup", "/auth/login", "/_test/reset", "/_test/clock", "/_test/import",
         "/dossiers", "/dossiers/acme.test/refresh"]


@pytest.mark.parametrize("path", PATHS)
def test_odd_bodies(client, auth, path):
    for body in BODIES:
        r = client.post(path, content=body, headers={**auth, "Idempotency-Key": "odd"})
        assert r.status_code < 500, (path, body[:30], r.status_code)
    client.post("/_test/reset", json=FIXTURE)


def test_odd_headers_and_paths(client, auth):
    for headers in ({**auth, "Idempotency-Key": "é".encode("latin-1")},
                    {**auth, "Idempotency-Key": b"x" * 100000},
                    {"Authorization": b"Bearer \xff\xfe"}, {"Authorization": b"Bearer"},
                    {"Authorization": "Bearer " + "a" * 100000}):
        for method, path in (("POST", "/dossiers"), ("GET", "/dossiers"),
                             ("POST", "/dossiers/acme.test/refresh")):
            r = client.request(method, path, headers=headers, json={"domain": "a.test"})
            assert r.status_code < 500
    for path in ("/dossiers/%ff", "/dossiers/%00", "/dossiers/" + "a" * 5000 + ".test",
                 "/dossiers/%E2%82%AC.test", "/dossiers?q=%ff&limit=%ff", "/dossiers?offset=%00",
                 "/dossiers/a.test/refresh/", "//dossiers"):
        assert client.get(path, headers=auth).status_code < 500
        assert client.post(path, headers={**auth, "Idempotency-Key": "k"}).status_code < 500


def test_odd_import_states(client):
    base = {"track": "dossier", "format_version": 1}
    field = {"value": "x", "citations": "zz"}
    states = [{"users": [{"id": 1}], "tokens": {}, "dossiers": [], "idempotency": []},
              {"users": [], "tokens": {"t": []}, "dossiers": [], "idempotency": []},
              {"users": [], "tokens": {}, "dossiers": [{"outcome": "ready"}], "idempotency": []},
              {"users": [], "tokens": {}, "dossiers": [], "idempotency": [{"body": 5}]},
              {"users": [], "tokens": {}, "dossiers": [{
                  "dossier_id": "d", "domain": "a.test", "outcome": "ready", "spent_units": 1,
                  "researched_at": 5, "fields": {k: field for k in FIELDS}}], "idempotency": []},
              None, 5, [], "x"]
    for state in states:
        r = client.post("/_test/import", json={**base, "state": state})
        assert r.status_code == 422, (state, r.status_code)
    for bad in ({"track": [], "format_version": 1}, {"track": "dossier", "format_version": True},
                {"track": "dossier", "format_version": 1.0, "state": {}}):
        assert client.post("/_test/import", json=bad).status_code == 422
    client.post("/_test/reset", json=FIXTURE)
