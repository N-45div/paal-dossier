import pytest
from starlette.testclient import TestClient

from app.main import create_app

FIXTURE = {"now": "2026-03-01T09:00:00+00:00",
           "users": [{"id": "u_ada", "email": "ada@example.com",
                      "password": "correct horse", "display_name": "Ada"}]}


@pytest.fixture
def client():
    c = TestClient(create_app(), raise_server_exceptions=False)
    assert c.post("/_test/reset", json=FIXTURE).status_code == 204
    return c


def code(r):
    return r.json()["error"]["code"]


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_seeded_login_and_signup_flow(client):
    r = client.post("/auth/login", json={"email": "ADA@example.com", "password": "correct horse"})
    assert r.status_code == 200 and r.json()["user_id"] == "u_ada"
    r = client.post("/auth/signup", json={"email": "z@example.com", "password": "12345678",
                                          "display_name": "Z"})
    assert r.status_code == 201 and r.json()["token"]
    r = client.post("/auth/signup", json={"email": "Z@example.com", "password": "12345678",
                                          "display_name": "Z"})
    assert (r.status_code, code(r)) == (409, "email_taken")


@pytest.mark.parametrize("body,status", [
    ({"email": "a@b.c", "password": "short", "display_name": "x"}, 422),
    ({"email": "nope", "password": "12345678", "display_name": "x"}, 422),
    ({"email": "a@b.c", "password": "12345678", "display_name": " "}, 422),
    ({"email": "a@b.c", "password": "12345678"}, 422),
    ({"email": "a@b.c", "password": 12345678, "display_name": "x"}, 400),
])
def test_signup_validation(client, body, status):
    assert client.post("/auth/signup", json=body).status_code == status


def test_login_failures(client):
    for body in ({"email": "ada@example.com", "password": "bad"},
                 {"email": "who@example.com", "password": "correct horse"}):
        r = client.post("/auth/login", json=body)
        assert (r.status_code, code(r)) == (401, "unauthenticated")


def test_clock(client):
    assert client.post("/_test/clock", json={"now": "2026-03-01T11:30:00+02:00"}).status_code == 204
    assert client.post("/_test/clock", json={"now": "2026-03-01T11:30:00+02:00"}).status_code == 204
    r = client.post("/_test/clock", json={"now": "2026-03-01T09:00:00+00:00"})
    assert (r.status_code, code(r)) == (422, "validation_failed")
    assert client.post("/_test/clock", json={"now": "2026-03-01T09:30:00"}).status_code == 422
    assert client.post("/_test/clock", json={"now": 5}).status_code == 400


def test_reset_errors_change_nothing(client):
    dup = {"now": FIXTURE["now"], "users": FIXTURE["users"] * 2}
    assert client.post("/_test/reset", json=dup).status_code == 422
    assert client.post("/_test/reset", content=b"{").status_code == 400
    assert client.post("/_test/reset", json={}).status_code == 422
    assert client.post("/auth/login", json={"email": "ada@example.com",
                                            "password": "correct horse"}).status_code == 200


def test_reset_drops_state(client):
    client.post("/auth/signup", json={"email": "z@example.com", "password": "12345678",
                                      "display_name": "Z"})
    client.post("/_test/reset", json={"now": FIXTURE["now"]})
    r = client.post("/auth/login", json={"email": "ada@example.com", "password": "correct horse"})
    assert r.status_code == 401


def test_unknown_route_and_method(client):
    r = client.get("/nope")
    assert (r.status_code, code(r)) == (404, "not_found")
    r = client.get("/auth/login")
    assert r.status_code == 405 and code(r) == "not_found"
    assert r.headers["content-type"] == "application/json; charset=utf-8"
