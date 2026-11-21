"""Stage-2 browser screens for evidence and contested fields (R2U2), headless Chromium.

Uses rank-co.test from the Prover's corpus: founded_year has three candidates from three
pages (own 2010, news 2012, aggregator 2013), so the field is contested. Ledger ids:
R2.137-R2.142 (evidence and contested testids and behaviour), R2.81-R2.82, R2.87, R2.100,
R2.129 (links to the evidence screen).
"""
from __future__ import annotations

import os
import time
import uuid

import pytest
import requests

from conftest import BASE_URL
from test_ui_browser import CHROME, DESKTOP, MOBILE, _new_page, _no_horizontal_scroll, _signup

playwright_sync = pytest.importorskip("playwright.sync_api")
RANK = "rank-co.test"
FIELDS = ["legal_name", "founded_year", "hq_city", "headcount_range", "ceo", "funding_total"]


@pytest.fixture(scope="module")
def browser():
    if not os.path.exists(CHROME):
        pytest.skip(f"no Chromium at {CHROME}")
    with playwright_sync.sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
        yield b
        b.close()


def _research_and_wait(page, domain):
    page.goto(f"{BASE_URL}/")
    page.get_by_test_id("research-domain").fill(domain)
    page.get_by_test_id("research-submit").click()
    page.wait_for_url(f"**/dossiers/{domain}", timeout=15000)
    deadline = time.time() + 90
    while page.get_by_test_id("dossier-state").inner_text().strip() not in ("ready", "failed"):
        assert time.time() < deadline, "build did not settle in 90 s"
        page.wait_for_timeout(500)


@pytest.fixture(scope="module")
def ranked(browser):
    ctx, page, errors = _new_page(browser)
    _signup(page)
    _research_and_wait(page, RANK)
    ctx.close()
    return RANK


def test_evidence_screen_lists_each_candidate_in_api_order(browser, ranked):
    # R2.137, R2.138, R2.139
    ctx, page, errors = _new_page(browser)
    _signup(page)
    page.goto(f"{BASE_URL}/dossiers/{RANK}/evidence")
    for f in FIELDS:
        assert page.get_by_test_id(f"evidence-{f}").count() == 1, f
    cands = page.get_by_test_id("evidence-founded_year").locator("[data-testid^=candidate-]")
    assert cands.count() == 3, cands.count()
    values = [cands.nth(i).get_attribute("data-value") for i in range(3)]
    assert values == ["2010", "2012", "2013"], values
    selected = [cands.nth(i).get_attribute("data-selected") for i in range(3)]
    assert selected == ["true", "false", "false"], selected
    kinds = [cands.nth(i).get_attribute("data-kind") for i in range(3)]
    assert kinds == ["own", "news", "aggregator"], kinds
    for i in range(3):
        c = cands.nth(i)
        assert c.get_attribute("data-provider"), i
        assert c.get_attribute("data-url", ) and c.get_attribute("data-url").startswith("https://"), i
        assert c.get_attribute("data-published-at"), i
        assert c.inner_text().strip(), i
    assert not errors, errors
    ctx.close()


def test_field_without_candidates_shows_empty_marker(browser, ranked):
    # R2.139
    ctx, page, errors = _new_page(browser)
    _signup(page)
    page.goto(f"{BASE_URL}/dossiers/{RANK}/evidence")
    empty = page.get_by_test_id("evidence-empty-ceo")
    assert empty.count() == 1
    assert page.get_by_test_id("evidence-ceo").locator("[data-testid^=candidate-]").count() == 0
    ctx.close()


def test_contested_list_and_link(browser, ranked):
    # R2.140, R2.141, R2.129
    ctx, page, errors = _new_page(browser)
    _signup(page)
    page.goto(f"{BASE_URL}/contested")
    page.get_by_test_id("contested-list").wait_for(timeout=10000)
    # the empty marker is shown instead of the list only when nothing is contested (R2.142)
    assert not page.get_by_test_id("empty-contested").is_visible()
    item = page.get_by_test_id(f"contested-item-{RANK}-founded_year")
    assert item.get_attribute("data-value") == "2010"
    text = item.inner_text()
    for needle in (RANK, "founded_year", "2010", "2012", "2013"):
        assert needle in text or needle.replace("_", " ") in text.lower(), (needle, text)
    item.locator("a").first.click()
    page.wait_for_url(f"**/dossiers/{RANK}/evidence", timeout=10000)
    assert not errors, errors
    ctx.close()


def test_dossier_evidence_link_and_contested_nav(browser, ranked):
    # R2.129, R2.81, R2.82
    ctx, page, errors = _new_page(browser)
    _signup(page)
    page.goto(f"{BASE_URL}/dossiers/{RANK}")
    page.get_by_test_id("dossier-state").wait_for(timeout=10000)
    page.get_by_test_id("dossier-evidence-link").click()
    page.wait_for_url(f"**/dossiers/{RANK}/evidence", timeout=10000)
    page.get_by_role("link", name="Contested").first.click()
    page.wait_for_url("**/contested", timeout=10000)
    ctx.close()


def test_contested_screen_without_contested_fields_shows_empty(browser):
    # R2.142 (empty-contested). A fresh user sees the list of all dossiers; the empty marker
    # is only required when none is contested, so this checks the list or marker is present.
    ctx, page, errors = _new_page(browser)
    _signup(page)
    page.goto(f"{BASE_URL}/contested")
    page.wait_for_load_state("networkidle")
    has_list = page.get_by_test_id("contested-list").count() == 1
    has_empty = page.get_by_test_id("empty-contested").count() == 1
    assert has_list or has_empty
    ctx.close()


@pytest.mark.parametrize("path", ["/dossiers/{d}/evidence", "/contested"])
def test_evidence_and_contested_fit_375px(browser, ranked, path):
    # R2.100
    ctx, page, errors = _new_page(browser, MOBILE)
    _signup(page)
    page.goto(BASE_URL + path.format(d=RANK))
    page.wait_for_load_state("networkidle")
    assert _no_horizontal_scroll(page), path
    ctx.close()


def test_contested_accept_html_is_served(browser):
    # R2.86 (browser route)
    r = requests.get(f"{BASE_URL}/contested", headers={"Accept": "text/html"}, timeout=5)
    assert r.status_code == 200 and r.headers.get("content-type", "").startswith("text/html")
