import pytest


def signup(client, **over):
    body = {"email": "c@example.com", "password": "12345678", "display_name": "Cy", **over}
    return client.post("/auth/signup", json=body)


def test_signup_and_login(client):
    r = signup(client)
    assert r.status_code == 201
    token = r.json()["token"]
    assert r.json()["user_id"].startswith("u_")
    r2 = client.post("/auth/login", json={"email": "C@example.com", "password": "12345678"})
    assert r2.status_code == 200 and r2.json()["token"] != token
    for t in (token, r2.json()["token"]):
        assert client.get("/dossiers", headers={"Authorization": f"bearer {t}"}).status_code == 200


@pytest.mark.parametrize(
    "over,status,code",
    [
        ({"email": "ada@example.com"}, 409, "email_taken"),
        ({"email": "ADA@example.com"}, 409, "email_taken"),
        ({"password": "short"}, 422, "validation_failed"),
        ({"email": "nodomain"}, 422, "validation_failed"),
        ({"email": "a@b@c"}, 422, "validation_failed"),
        ({"display_name": ""}, 422, "validation_failed"),
        ({"display_name": "x" * 101}, 422, "validation_failed"),
        ({"display_name": 5}, 400, "malformed_request"),
    ],
)
def test_signup_errors(client, over, status, code):
    r = signup(client, **over)
    assert (r.status_code, r.json()["error"]["code"]) == (status, code)


def test_signup_missing_field_and_bad_body(client):
    assert client.post("/auth/signup", json={"email": "a@b.c"}).status_code == 422
    assert client.post("/auth/signup", content=b"nope").status_code == 400


def test_login_failures(client):
    assert client.post("/auth/login", json={"email": "ada@example.com", "password": "bad"}).status_code == 401
    assert client.post("/auth/login", json={"email": "zed@example.com", "password": "correct horse"}).status_code == 401


@pytest.mark.parametrize("header", [None, "Bearer", "Bearer nope", "Basic abc", "Token x"])
def test_bad_tokens(client, header):
    r = client.get("/dossiers", headers={"Authorization": header} if header else {})
    assert r.status_code == 401 and r.json()["error"]["code"] == "unauthenticated"


def test_auth_before_idempotency_key(client):
    r = client.post("/dossiers", json={"domain": "acme.test"})
    assert r.status_code == 401
