"""Platform behaviour: health, error bodies, routing, clock, reset, auth (spec §3, §5, §6)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .conftest import Client

FIXTURE_NOW = "2026-03-01T09:00:00+00:00"


def seed(client: Client, users: list[dict] | None = None, now: str = FIXTURE_NOW) -> None:
    body = {"now": now, "users": users if users is not None else [
        {"id": "u_ada", "email": "ada@example.com", "password": "correct horse",
         "display_name": "Ada"},
        {"id": "u_bob", "email": "bob@example.com", "password": "correct horse",
         "display_name": "Bob"},
    ]}
    response = client.post("/_test/reset", body)
    assert response.status == 204, response.body


def assert_error(response, status: int, code: str) -> None:
    assert response.status == status, response.body
    assert response.headers["Content-Type"] == "application/json; charset=utf-8"
    error = response.json()["error"]
    assert error["code"] == code
    assert isinstance(error["message"], str)


def test_health_is_ok_without_state(client: Client) -> None:
    response = client.get("/health")
    assert response.status == 200
    assert response.json() == {"status": "ok"}


def test_unknown_path_is_404_and_wrong_method_is_405(client: Client) -> None:
    assert_error(client.get("/nope"), 404, "not_found")
    assert_error(client.post("/health", {}), 405, "method_not_allowed")
    assert_error(client.request("PUT", "/health"), 405, "method_not_allowed")
    assert_error(client.request("FROBNICATE", "/health"), 405, "method_not_allowed")


def test_invalid_json_body_is_400(client: Client) -> None:
    assert_error(client.post("/_test/reset", raw=b"{not json"), 400, "malformed_request")
    assert_error(client.post("/_test/reset", raw=b"[1, 2]"), 400, "malformed_request")


def test_reset_requires_now_and_rejects_bad_timestamps(client: Client) -> None:
    assert_error(client.post("/_test/reset", {}), 422, "validation_failed")
    assert_error(client.post("/_test/reset", {"now": 5}), 400, "malformed_request")
    assert_error(
        client.post("/_test/reset", {"now": "2026-03-01T09:00:00"}), 422, "validation_failed"
    )
    assert_error(
        client.post("/_test/reset", {"now": "2026-02-30T09:00:00+00:00"}),
        422, "validation_failed",
    )


def test_reset_with_duplicate_email_changes_nothing(client: Client) -> None:
    seed(client)
    bad = {"now": "2026-05-05T00:00:00+00:00", "users": [
        {"id": "u_x", "email": "X@example.com", "password": "pw-one-long", "display_name": "X"},
        {"id": "u_y", "email": "x@example.com", "password": "pw-two-long", "display_name": "Y"},
    ]}
    assert_error(client.post("/_test/reset", bad), 422, "validation_failed")
    assert client.post("/auth/login", {"email": "ada@example.com",
                                       "password": "correct horse"}).status == 200
    assert client.post("/auth/login", {"email": "x@example.com",
                                       "password": "pw-one-long"}).status == 401


def test_seeded_users_log_in_immediately_with_fixture_ids(client: Client) -> None:
    seed(client)
    response = client.post("/auth/login", {"email": "Ada@Example.com",
                                           "password": "correct horse"})
    assert response.status == 200
    body = response.json()
    assert body["user_id"] == "u_ada"
    assert body["display_name"] == "Ada"
    assert body["token"]


def test_reset_drops_previous_users(client: Client) -> None:
    seed(client)
    seed(client, users=[])
    assert client.post("/auth/login", {"email": "ada@example.com",
                                       "password": "correct horse"}).status == 401


def test_clock_is_set_by_reset_and_moves_forward_only(client: Client) -> None:
    seed(client, now="2026-03-01T09:00:00+00:00")
    client.post("/_test/clock", {"now": "2026-03-01T09:30:00+00:00"})
    assert client.post("/_test/clock", {"now": "2026-03-01T09:30:00+00:00"}).status == 204
    assert_error(
        client.post("/_test/clock", {"now": "2026-03-01T09:29:59+00:00"}),
        422, "validation_failed",
    )
    assert_error(client.post("/_test/clock", {}), 422, "validation_failed")
    assert_error(client.post("/_test/clock", {"now": "2026-03-01T09:30:00"}),
                 422, "validation_failed")


def test_reset_may_move_clock_backwards(client: Client) -> None:
    seed(client, now="2026-03-01T09:00:00+00:00")
    client.post("/_test/clock", {"now": "2026-04-01T00:00:00+00:00"})
    seed(client, now="2026-02-01T00:00:00+00:00")
    assert client.post("/_test/clock", {"now": "2026-02-01T00:00:00+00:00"}).status == 204


def test_clock_follows_system_time_before_first_reset() -> None:
    from app.clock import Clock

    before = datetime.now(timezone.utc) - timedelta(seconds=2)
    now = Clock().now()
    assert now.utcoffset() == timedelta(0)
    assert before <= now <= datetime.now(timezone.utc) + timedelta(seconds=2)


def test_signup_then_login_and_bearer_token_shape(client: Client) -> None:
    seed(client, users=[])
    created = client.post("/auth/signup", {"email": "New@Example.com",
                                           "password": "longenough",
                                           "display_name": "New"})
    assert created.status == 201
    body = created.json()
    assert set(body) == {"user_id", "display_name", "token"}
    assert body["display_name"] == "New"
    login = client.post("/auth/login", {"email": "new@example.com",
                                        "password": "longenough"})
    assert login.status == 200
    assert login.json()["user_id"] == body["user_id"]
    assert login.json()["token"] != body["token"]


def test_signup_validation_matrix(client: Client) -> None:
    seed(client, users=[])
    valid = {"email": "a@example.com", "password": "correct horse", "display_name": "Ada"}
    cases = [
        ({**valid, "password": "short"}, 422, "validation_failed"),
        ({**valid, "email": "no-at-sign"}, 422, "validation_failed"),
        ({**valid, "email": "a@b@example.com"}, 422, "validation_failed"),
        ({**valid, "email": "@example.com"}, 422, "validation_failed"),
        ({**valid, "email": "a b@example.com"}, 422, "validation_failed"),
        ({**valid, "display_name": ""}, 422, "validation_failed"),
        ({**valid, "display_name": "   "}, 422, "validation_failed"),
        ({**valid, "display_name": "x" * 101}, 422, "validation_failed"),
        ({**valid, "display_name": 7}, 400, "malformed_request"),
        ({k: v for k, v in valid.items() if k != "email"}, 422, "validation_failed"),
    ]
    for payload, status, code in cases:
        assert_error(client.post("/auth/signup", payload), status, code)


def test_signup_rejects_duplicate_email_case_insensitively(client: Client) -> None:
    seed(client)
    assert_error(
        client.post("/auth/signup", {"email": "ADA@example.com", "password": "longenough",
                                     "display_name": "Other"}),
        409, "email_taken",
    )


def test_invalid_fields_are_checked_before_duplicate_email(client: Client) -> None:
    seed(client)
    assert_error(
        client.post("/auth/signup", {"email": "ada@example.com", "password": "x",
                                     "display_name": "Other"}),
        422, "validation_failed",
    )


def test_wrong_login_is_401(client: Client) -> None:
    seed(client)
    assert_error(client.post("/auth/login", {"email": "ada@example.com",
                                             "password": "wrong password"}),
                 401, "unauthenticated")
    assert_error(client.post("/auth/login", {"email": "who@example.com",
                                             "password": "correct horse"}),
                 401, "unauthenticated")
    assert_error(client.post("/auth/login", {"email": "ada@example.com"}),
                 422, "validation_failed")


def test_tokens_do_not_expire_and_many_sessions_coexist(client: Client) -> None:
    seed(client)
    first = client.post("/auth/login", {"email": "ada@example.com",
                                        "password": "correct horse"}).json()["token"]
    second = client.post("/auth/login", {"email": "ada@example.com",
                                         "password": "correct horse"}).json()["token"]
    assert first != second
    assert first != "" and second != ""
    # The bearer check itself is exercised by the dossier endpoints (stage 1 WP4); here the
    # token is only confirmed to be issued and distinct per session.


def test_passwords_are_not_stored_in_plaintext(client: Client) -> None:
    from app.passwords import verify_password, hash_password

    stored = hash_password("correct horse")
    assert "correct horse" not in stored
    assert verify_password("correct horse", stored)
    assert not verify_password("correct hors", stored)
