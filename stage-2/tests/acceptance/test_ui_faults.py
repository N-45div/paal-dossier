"""Stage-2 browser: lost responses after the request commits (R2.113, R2.132), headless Chromium.

Network interception: the browser's POST is sent through to the service, which commits it,
then the response is aborted before the page sees it. The screen must show the uncertain
message (non-empty text, not the error message), and a retry with the same key and body must
succeed. Ledger ids: R2.112-R2.113, R2.131-R2.132, and the uncertain-outcome rule of R2U1.
"""
from __future__ import annotations

import os
import time
import uuid

import pytest

from conftest import BASE_URL
from test_ui_browser import CHROME, _new_page, _signup

playwright_sync = pytest.importorskip("playwright.sync_api")
DOMAIN = "tidemark-energy.test"


@pytest.fixture(scope="module")
def browser():
    if not os.path.exists(CHROME):
        pytest.skip(f"no Chromium at {CHROME}")
    with playwright_sync.sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
        yield b
        b.close()


def _wait_settled(page):
    deadline = time.time() + 90
    while page.get_by_test_id("dossier-state").inner_text().strip() not in ("ready", "failed"):
        assert time.time() < deadline, "build did not settle in 90 s"
        page.wait_for_timeout(500)


def test_lost_research_response_shows_uncertain_and_retry_succeeds(browser):
    # R2.113: a lost response after commit shows research-uncertain, not research-error
    ctx, page, errors = _new_page(browser)
    _signup(page)
    page.goto(f"{BASE_URL}/")

    def lose_response(route):
        if route.request.method == "POST":
            route.fetch()          # the service receives and commits the request
            route.abort()          # the browser never gets the response
        else:
            route.continue_()

    page.route("**/dossiers", lose_response)
    page.get_by_test_id("research-domain").fill(DOMAIN)
    page.get_by_test_id("research-submit").click()
    page.get_by_test_id("research-uncertain").wait_for(timeout=10000)
    assert page.get_by_test_id("research-uncertain").inner_text().strip()
    err = page.get_by_test_id("research-error")
    assert err.count() == 0 or not err.is_visible(), repr(err.inner_text() if err.count() else "")
    page.unroute("**/dossiers")

    # retry: same domain and body, so the same key and the request is retryable
    page.get_by_test_id("research-submit").click()
    page.wait_for_url(f"**/dossiers/{DOMAIN}", timeout=15000)
    _wait_settled(page)
    assert page.get_by_test_id("dossier-domain").inner_text().strip() == DOMAIN
    assert not errors, errors
    ctx.close()


def test_lost_refresh_response_shows_uncertain_and_retry_succeeds(browser):
    # R2.132: a lost refresh response shows refresh-uncertain, not refresh-error
    ctx, page, errors = _new_page(browser)
    _signup(page)
    page.goto(f"{BASE_URL}/dossiers/{DOMAIN}")
    page.get_by_test_id("dossier-state").wait_for(timeout=10000)
    _wait_settled(page)

    def lose_response(route):
        if route.request.method == "POST":
            route.fetch()
            route.abort()
        else:
            route.continue_()

    page.route(f"**/dossiers/{DOMAIN}/refresh", lose_response)
    page.get_by_test_id("dossier-refresh").click()
    page.get_by_test_id("refresh-uncertain").wait_for(timeout=10000)
    assert page.get_by_test_id("refresh-uncertain").inner_text().strip()
    rerr = page.get_by_test_id("refresh-error")
    assert rerr.count() == 0 or not rerr.is_visible(), repr(rerr.inner_text() if rerr.count() else "")
    page.unroute(f"**/dossiers/{DOMAIN}/refresh")

    page.get_by_test_id("dossier-refresh").click()
    page.wait_for_timeout(1000)
    _wait_settled(page)
    assert page.get_by_test_id("refresh-error").count() == 0 or not page.get_by_test_id("refresh-error").is_visible()
    assert not errors, errors
    ctx.close()
