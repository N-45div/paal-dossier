from conftest import FIXTURE, login


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}
    assert r.headers["content-type"] == "application/json; charset=utf-8"


def test_error_shape_and_routes(client):
    r = client.get("/nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
    r = client.put("/health")
    assert r.status_code == 405 and r.json()["error"]["code"] == "not_found"


def test_reset_validation_changes_nothing(client):
    assert client.post("/_test/reset", content=b"[]").status_code == 400
    assert client.post("/_test/reset", content=b"{").status_code == 400
    assert client.post("/_test/reset", json={"users": []}).status_code == 422
    bad = {"now": FIXTURE["now"], "users": [FIXTURE["users"][0], {**FIXTURE["users"][1], "email": "ADA@example.com"}]}
    assert client.post("/_test/reset", json=bad).status_code == 422
    login(client)  # seeded users survive failed resets


def test_reset_removes_signed_up_users(client):
    client.post("/auth/signup", json={"email": "c@example.com", "password": "12345678", "display_name": "C"})
    client.post("/_test/reset", json=FIXTURE)
    r = client.post("/auth/login", json={"email": "c@example.com", "password": "12345678"})
    assert r.status_code == 401


def test_clock(client):
    assert client.post("/_test/clock", json={"now": "2026-03-01T09:30:00+02:00"}).status_code == 422  # earlier in UTC
    assert client.post("/_test/clock", json={"now": "2026-03-01T09:30:00+00:00"}).status_code == 204
    assert client.post("/_test/clock", json={"now": "2026-03-01T09:30:00+00:00"}).status_code == 204
    assert client.post("/_test/clock", json={"now": "2026-03-01T09:29:00+00:00"}).status_code == 422
    assert client.post("/_test/clock", json={"now": "2026-03-02T09:30:00"}).status_code == 422
    assert client.post("/_test/clock", json={"now": 5}).status_code == 400
    assert client.post("/_test/clock", json={}).status_code == 422


def test_unknown_fields_and_query_ignored(client):
    r = client.post("/auth/login", json={"email": "ada@example.com", "password": "correct horse", "x": 1}, params={"y": "z"})
    assert r.status_code == 200
    assert r.json()["user_id"] == "u_ada"
