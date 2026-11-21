"""Service skeleton tests: health, errors, reset/clock, auth, domain normalisation."""

from __future__ import annotations

import unittest

from aiohttp.test_utils import TestClient, TestServer

from app.clock import parse_rfc3339
from app.domain import normalise_domain
from app.server import build_app

FIXTURE = {
    "now": "2026-03-01T09:00:00+00:00",
    "users": [
        {"id": "u_ada", "email": "ada@example.com", "password": "correct horse",
         "display_name": "Ada"},
        {"id": "u_bob", "email": "bob@example.com", "password": "correct horse",
         "display_name": "Bob"},
    ],
}


class SkeletonTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.client = TestClient(TestServer(build_app()))
        await self.client.start_server()

    async def asyncTearDown(self) -> None:
        await self.client.close()

    async def reset(self, body: dict | None = None) -> None:
        resp = await self.client.post("/_test/reset", json=body or FIXTURE)
        self.assertEqual(resp.status, 204)

    async def assert_error(self, resp, status: int, code: str) -> None:
        self.assertEqual(resp.status, status)
        self.assertEqual(resp.content_type, "application/json")
        payload = await resp.json()
        self.assertEqual(payload["error"]["code"], code)

    async def test_health(self) -> None:
        resp = await self.client.get("/health")
        self.assertEqual(resp.status, 200)
        self.assertEqual(await resp.json(), {"status": "ok"})

    async def test_reset_seeds_users_who_can_log_in(self) -> None:
        await self.reset()
        resp = await self.client.post(
            "/auth/login", json={"email": "ada@example.com", "password": "correct horse"}
        )
        self.assertEqual(resp.status, 200)
        body = await resp.json()
        self.assertEqual(body["user_id"], "u_ada")
        self.assertEqual(body["display_name"], "Ada")
        self.assertTrue(body["token"])

    async def test_reset_with_duplicate_email_changes_nothing(self) -> None:
        await self.reset()
        bad = {"now": "2027-01-01T00:00:00+00:00", "users": [
            {"id": "u_x", "email": "x@example.com", "password": "correct horse", "display_name": "X"},
            {"id": "u_y", "email": "X@example.com", "password": "correct horse", "display_name": "Y"},
        ]}
        await self.assert_error(
            await self.client.post("/_test/reset", json=bad), 422, "validation_failed"
        )
        resp = await self.client.post(
            "/auth/login", json={"email": "ada@example.com", "password": "correct horse"}
        )
        self.assertEqual(resp.status, 200)

    async def test_reset_missing_now_is_422_and_wrong_type_is_400(self) -> None:
        await self.assert_error(
            await self.client.post("/_test/reset", json={"users": []}), 422, "validation_failed"
        )
        await self.assert_error(
            await self.client.post("/_test/reset", json={"now": 5}), 400, "malformed_request"
        )

    async def test_clock_cannot_move_backwards(self) -> None:
        await self.reset()
        await self.assert_error(
            await self.client.post("/_test/clock", json={"now": "2026-02-01T00:00:00Z"}),
            422, "validation_failed",
        )
        resp = await self.client.post("/_test/clock", json={"now": "2026-03-02T00:00:00.5-05:00"})
        self.assertEqual(resp.status, 204)

    async def test_signup_and_duplicate_email(self) -> None:
        await self.reset()
        payload = {"email": "eve@example.com", "password": "long enough", "display_name": "Eve"}
        resp = await self.client.post("/auth/signup", json=payload)
        self.assertEqual(resp.status, 201)
        body = await resp.json()
        self.assertTrue(body["user_id"].startswith("u_"))
        self.assertEqual(body["display_name"], "Eve")
        await self.assert_error(
            await self.client.post("/auth/signup", json=payload), 409, "email_taken"
        )

    async def test_signup_validation(self) -> None:
        await self.reset()
        cases = [
            {"email": "eve@example.com", "password": "short", "display_name": "Eve"},
            {"email": "not-an-email", "password": "long enough", "display_name": "Eve"},
            {"email": "eve@example.com", "password": "long enough", "display_name": ""},
            {"email": "eve@example.com", "password": "long enough", "display_name": "x" * 101},
        ]
        for case in cases:
            await self.assert_error(
                await self.client.post("/auth/signup", json=case), 422, "validation_failed"
            )
        await self.assert_error(
            await self.client.post("/auth/signup", json={"email": 1, "password": "x" * 9,
                                                         "display_name": "Eve"}),
            400, "malformed_request",
        )

    async def test_login_failures_are_401(self) -> None:
        await self.reset()
        await self.assert_error(
            await self.client.post("/auth/login",
                                   json={"email": "ada@example.com", "password": "wrong pass"}),
            401, "unauthenticated",
        )
        await self.assert_error(
            await self.client.post("/auth/login",
                                   json={"email": "nobody@example.com", "password": "correct horse"}),
            401, "unauthenticated",
        )

    async def test_malformed_json_and_unknown_routes(self) -> None:
        await self.assert_error(
            await self.client.post("/auth/login", data=b"not json"), 400, "malformed_request"
        )
        await self.assert_error(
            await self.client.post("/auth/login", json=["a", "list"]), 400, "malformed_request"
        )
        await self.assert_error(await self.client.get("/nope"), 404, "not_found")

    async def test_reset_clears_previous_users(self) -> None:
        await self.reset()
        await self.reset({"now": "2026-03-01T09:00:00+00:00", "users": []})
        await self.assert_error(
            await self.client.post("/auth/login",
                                   json={"email": "ada@example.com", "password": "correct horse"}),
            401, "unauthenticated",
        )


class TimestampAndDomainTest(unittest.TestCase):
    def test_rfc3339_requires_offset(self) -> None:
        self.assertEqual(parse_rfc3339("2026-03-01T09:30:00+00:00").utcoffset().total_seconds(), 0)
        with self.assertRaises(Exception):
            parse_rfc3339("2026-03-01T09:30:00")

    def test_domain_normalisation(self) -> None:
        self.assertEqual(normalise_domain(" Acme-Robotics.TEST. "), "acme-robotics.test")
        self.assertEqual(normalise_domain("www.acme-robotics.test"), "acme-robotics.test")
        self.assertIsNone(normalise_domain("https://acme.test/x"))
        self.assertIsNone(normalise_domain("localhost"))
        self.assertIsNone(normalise_domain("-bad.test"))
        self.assertIsNone(normalise_domain("a" * 64 + ".test"))


if __name__ == "__main__":
    unittest.main()
