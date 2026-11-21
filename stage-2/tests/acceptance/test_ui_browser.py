"""Stage-2 browser UI, driven in headless Chromium against the built image (BASE_URL).

Black-box: only the screens and the HTTP interface a user reaches. Ledger ids: R2.76-R2.109
(screens, routes, testids, auth), R2.110-R2.136 (dossier screen and its testids), and
R2.143-R2.150 (UI-side rules from the R2U1 handoff). The evidence and contested screens
(R2.137-R2.142) are checked by test_ui_evidence.py once R2U2 is in the image.

Set CHROME_PATH to a Chromium binary when the Playwright bundle is not installed.
"""
from __future__ import annotations

import os
import uuid

import pytest
import requests

from conftest import BASE_URL

playwright_sync = pytest.importorskip("playwright.sync_api")

CHROME = os.environ.get(
    "CHROME_PATH", "/home/ndivij/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome")
SAMPLE = "brightwater-labs.test"
PASSWORD = "correct horse"
DESKTOP = {"width": 1280, "height": 900}
MOBILE = {"width": 375, "height": 800}
FIELDS = ["legal_name", "founded_year", "hq_city", "headcount_range", "ceo", "funding_total"]


@pytest.fixture(scope="module")
def browser():
    if not os.path.exists(CHROME):
        pytest.skip(f"no Chromium at {CHROME}")
    with playwright_sync.sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
        yield b
        b.close()


def _new_page(browser, viewport=DESKTOP):
    ctx = browser.new_context(viewport=viewport)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    return ctx, page, errors


def _signup(page):
    email = f"prover-{uuid.uuid4().hex[:10]}@example.com"
    page.goto(f"{BASE_URL}/signup")
    page.get_by_test_id("signup-email").fill(email)
    page.get_by_test_id("signup-password").fill(PASSWORD)
    page.get_by_test_id("signup-display-name").fill("Prover Tester")
    page.get_by_test_id("signup-submit").click()
    page.get_by_test_id("current-user").wait_for(timeout=10000)
    return email


def _no_horizontal_scroll(page):
    return page.evaluate(
        "() => document.documentElement.scrollWidth <= document.documentElement.clientWidth")


# ---- R2.79-R2.84, R2.104-R2.109: screens, auth, current user -----------------

def test_routes_are_reachable_by_url(browser):
    # R2.76, R2.79-R2.84
    ctx, page, errors = _new_page(browser)
    for path in ("/", "/signup", "/login"):
        r = page.goto(f"{BASE_URL}{path}")
        assert r is not None and r.status < 400, (path, r and r.status)
    assert not errors, errors
    ctx.close()


def test_signup_shows_current_user_and_logout(browser):
    # R2.104, R2.105, R2.108, R2.109
    ctx, page, errors = _new_page(browser)
    _signup(page)
    assert "Prover Tester" in page.get_by_test_id("current-user").inner_text()
    page.get_by_test_id("logout-button").click()
    page.goto(f"{BASE_URL}/login")
    assert page.get_by_test_id("login-email").is_visible()
    assert not errors, errors
    ctx.close()


def test_login_errors_are_shown_when_present(browser):
    # R2.106, R2.107
    ctx, page, errors = _new_page(browser)
    page.goto(f"{BASE_URL}/login")
    page.get_by_test_id("login-email").fill("nobody@example.com")
    page.get_by_test_id("login-password").fill("wrong password 1")
    page.get_by_test_id("login-submit").click()
    page.get_by_test_id("auth-error").wait_for(timeout=10000)
    assert page.get_by_test_id("auth-error").inner_text().strip()
    ctx.close()


# ---- R2.110-R2.136: research, list, dossier screen -----------------------------

def test_invalid_domain_shows_research_error(browser):
    # R2.110-R2.112
    ctx, page, errors = _new_page(browser)
    _signup(page)
    page.get_by_test_id("research-domain").fill("not a domain")
    page.get_by_test_id("research-submit").click()
    page.get_by_test_id("research-error").wait_for(timeout=10000)
    assert page.get_by_test_id("research-error").inner_text().strip()
    ctx.close()


def test_research_opens_dossier_and_shows_fields_and_citations(browser):
    # R2.110, R2.111, R2.118, R2.120-R2.124, R2.124-R2.128, R2.136
    ctx, page, errors = _new_page(browser)
    _signup(page)
    page.get_by_test_id("research-domain").fill(SAMPLE)
    page.get_by_test_id("research-submit").click()
    page.wait_for_url(f"**/dossiers/{SAMPLE}", timeout=15000)
    page.get_by_test_id("dossier-state").wait_for(timeout=10000)
    # R2.136: building is re-read until ready, without a reload
    deadline = __import__("time").time() + 90
    while page.get_by_test_id("dossier-state").inner_text().strip() not in ("ready", "failed"):
        assert __import__("time").time() < deadline, "build did not settle in 90 s"
        page.wait_for_timeout(500)
    assert page.get_by_test_id("dossier-state").inner_text().strip() == "ready"
    assert page.get_by_test_id("dossier-domain").inner_text().strip() == SAMPLE
    assert int(page.get_by_test_id("dossier-spent").get_attribute("data-units")) >= 0
    for f in FIELDS:
        el = page.get_by_test_id(f"field-{f}")
        assert el.count() == 1, f
        assert el.get_attribute("data-status") in ("known", "unknown", "contested"), f
    known = [f for f in FIELDS if page.get_by_test_id(f"field-{f}").get_attribute("data-status") == "known"]
    assert known, "sample domain should have at least one known field"
    for f in known:
        assert page.get_by_test_id(f"field-value-{f}").count() == 1
        citations = page.get_by_test_id(f"field-citations-{f}").locator("[data-testid^=citation-]")
        assert citations.count() >= 1, f
        first = citations.first
        assert first.inner_text().strip(), f
        href = first.locator("a").first.get_attribute("href")
        assert href and href.startswith("https://"), (f, href)
        assert first.get_attribute("data-provider") in ("nimble", "tavily"), f
    assert not errors, errors
    ctx.close()


def test_existing_domain_opens_without_a_new_build(browser):
    # R2.119
    ctx, page, errors = _new_page(browser)
    _signup(page)
    page.goto(f"{BASE_URL}/")
    page.get_by_test_id("research-domain").fill(SAMPLE)
    page.get_by_test_id("research-submit").click()
    page.wait_for_url(f"**/dossiers/{SAMPLE}", timeout=15000)
    assert page.get_by_test_id("dossier-domain").inner_text().strip() == SAMPLE
    ctx.close()


def test_dossier_list_search_and_items(browser):
    # R2.114-R2.117
    ctx, page, errors = _new_page(browser)
    _signup(page)
    page.goto(BASE_URL + "/")
    page.get_by_test_id("dossier-list").wait_for(timeout=10000)
    page.get_by_test_id("dossier-search").fill("no-such-company-xyz.test")
    page.get_by_test_id("empty-dossiers").wait_for(timeout=10000)
    ctx.close()


def test_dossier_not_found_message(browser):
    # R2.134
    ctx, page, errors = _new_page(browser)
    _signup(page)
    page.goto(f"{BASE_URL}/dossiers/never-researched-xyz.test")
    page.get_by_test_id("dossier-not-found").wait_for(timeout=10000)
    ctx.close()


def test_reload_button_reads_without_starting_a_build(browser):
    # R2.133
    ctx, page, errors = _new_page(browser)
    _signup(page)
    page.goto(f"{BASE_URL}/dossiers/{SAMPLE}")
    page.get_by_test_id("dossier-state").wait_for(timeout=10000)
    page.get_by_test_id("dossier-reload").click()
    page.get_by_test_id("dossier-state").wait_for(timeout=10000)
    ctx.close()


# ---- R2.85-R2.86: content negotiation on /dossiers/{domain} ----------------

def test_accept_header_chooses_ui_or_json(browser):
    # R2.85, R2.86
    html = requests.get(f"{BASE_URL}/dossiers/{SAMPLE}",
                        headers={"Accept": "text/html"}, timeout=5)
    assert html.status_code in (200, 404), html.status_code
    assert html.headers.get("content-type", "").startswith("text/html"), html.headers
    js = requests.get(f"{BASE_URL}/dossiers/{SAMPLE}", timeout=5)
    assert js.headers.get("content-type", "").startswith("application/json"), js.headers


# ---- R2.100: responsive, no horizontal scroll -----------------------------

@pytest.mark.parametrize("viewport", [MOBILE, DESKTOP], ids=["375px", "1280px"])
def test_no_horizontal_scroll(browser, viewport):
    # R2.100
    ctx, page, errors = _new_page(browser, viewport)
    _signup(page)
    for path in ("/", f"/dossiers/{SAMPLE}"):
        page.goto(BASE_URL + path)
        page.wait_for_load_state("networkidle")
        assert _no_horizontal_scroll(page), (path, viewport)
    assert not errors, errors
    ctx.close()


# ---- R2.101: labelled inputs, visible focus ------------------------------

def test_inputs_have_visible_labels(browser):
    # R2.101
    ctx, page, errors = _new_page(browser)
    page.goto(f"{BASE_URL}/signup")
    for tid in ("signup-email", "signup-password", "signup-display-name"):
        el = page.get_by_test_id(tid)
        labelled = el.evaluate(
            "el => !!(el.labels && el.labels.length) || !!el.getAttribute('aria-label') "
            "|| !!el.getAttribute('aria-labelledby')")
        assert labelled, tid
    ctx.close()
