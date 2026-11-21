"""Browser UI routes (stage 2, R2U1): shells, negotiation of /dossiers/{domain}, static files."""

from __future__ import annotations

import unittest

from aiohttp.test_utils import TestClient, TestServer

from app.server import build_app

HTML = {"Accept": "text/html"}


class UiTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.client = TestClient(TestServer(build_app()))
        await self.client.start_server()

    async def asyncTearDown(self) -> None:
        await self.client.close()

    async def test_screen_routes_render_html_with_their_testids(self) -> None:
        expectations = {
            "/": ["research-domain", "research-submit", "dossier-list", "empty-dossiers"],
            "/signup": ["signup-email", "signup-password", "signup-display-name", "signup-submit"],
            "/login": ["login-email", "login-password", "login-submit", "auth-error"],
        }
        for path, testids in expectations.items():
            with self.subTest(path=path):
                response = await self.client.get(path)
                self.assertEqual(response.status, 200)
                self.assertIn("text/html", response.headers["Content-Type"])
                body = await response.text()
                for testid in testids:
                    self.assertIn(f'data-testid="{testid}"', body)
                self.assertIn('data-testid="current-user"', body)
                self.assertIn('data-testid="logout-button"', body)

    async def test_dossier_route_serves_shell_for_html_and_json_otherwise(self) -> None:
        html = await self.client.get("/dossiers/acme-robotics.test", headers=HTML)
        self.assertEqual(html.status, 200)
        self.assertIn("text/html", html.headers["Content-Type"])
        self.assertIn('data-testid="dossier-domain"', await html.text())

        json_reply = await self.client.get("/dossiers/acme-robotics.test")
        self.assertEqual(json_reply.status, 401)
        self.assertEqual(json_reply.headers["Content-Type"].split(";")[0], "application/json")

    async def test_browser_domain_is_normalised_by_redirect(self) -> None:
        response = await self.client.get("/dossiers/ACME-Robotics.test.", headers=HTML,
                                         allow_redirects=False)
        self.assertEqual(response.status, 302)
        self.assertEqual(response.headers["Location"], "/dossiers/acme-robotics.test")

    async def test_invalid_domain_renders_not_found_in_html(self) -> None:
        response = await self.client.get("/dossiers/not%20a%20domain", headers=HTML)
        self.assertEqual(response.status, 404)
        self.assertIn('data-testid="dossier-not-found"', await response.text())

    async def test_static_assets_are_served_locally(self) -> None:
        css = await self.client.get("/static/app.css")
        self.assertEqual(css.status, 200)
        self.assertIn("text/css", css.headers["Content-Type"])
        js = await self.client.get("/static/js/dossier.js")
        self.assertEqual(js.status, 200)
        self.assertEqual((await self.client.get("/static/js/missing.js")).status, 404)


if __name__ == "__main__":
    unittest.main()
