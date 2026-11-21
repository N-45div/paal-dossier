"""Stage-2 browser: polling while building (R2.136), headless Chromium.

Not covered: latest-read-wins under out-of-order responses. The sync Playwright API cannot
hold one response while a later one completes, so that needs an async test.

The screen's own reads are intercepted and their bodies changed to `building` for a while,
so the polling cadence can be measured without a long real build. Ledger ids: R2.136
(re-read at least every 2 s while building; latest read wins, including out-of-order
responses; the screen shows the new fields without a manual reload). Only the cadence part
is checked here.
"""
from __future__ import annotations

import json
import os
import time

import pytest

from conftest import BASE_URL
from test_ui_browser import CHROME, _new_page, _signup

playwright_sync = pytest.importorskip("playwright.sync_api")
SAMPLE = "brightwater-labs.test"


@pytest.fixture(scope="module")
def browser():
    if not os.path.exists(CHROME):
        pytest.skip(f"no Chromium at {CHROME}")
    with playwright_sync.sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
        yield b
        b.close()


def _is_read(route):
    req = route.request
    return req.method == "GET" and req.resource_type in ("fetch", "xhr") \
        and req.url.split("?")[0].endswith(f"/dossiers/{SAMPLE}")


def _as_state(route, state):
    resp = route.fetch()
    body = resp.json()
    body["state"] = state
    route.fulfill(response=resp, body=json.dumps(body), headers={
        **resp.headers, "content-type": "application/json"})


def test_building_is_reread_every_two_seconds(browser):
    # R2.136: while building, the screen reads at least every 2 s; then shows the new state
    ctx, page, errors = _new_page(browser)
    _signup(page)
    page.goto(f"{BASE_URL}/")
    page.get_by_test_id("research-domain").fill(SAMPLE)
    page.get_by_test_id("research-submit").click()
    page.wait_for_url(f"**/dossiers/{SAMPLE}", timeout=15000)
    page.goto(f"{BASE_URL}/dossiers/{SAMPLE}")
    page.get_by_test_id("dossier-state").wait_for(timeout=10000)
    stamps = []
    counter = {"n": 0}

    def handler(route):
        if not _is_read(route):
            return route.continue_()
        stamps.append(time.time())
        counter["n"] += 1
        if counter["n"] <= 4:
            return _as_state(route, "building")
        return route.continue_()

    page.route("**/dossiers/*", handler)
    page.goto(f"{BASE_URL}/dossiers/{SAMPLE}")
    deadline = time.time() + 30
    while len(stamps) < 4 and time.time() < deadline:
        page.wait_for_timeout(200)
    assert len(stamps) >= 4, f"only {len(stamps)} reads while building"
    gaps = [b - a for a, b in zip(stamps, stamps[1:4])]
    assert max(gaps) <= 2.5, gaps
    page.unroute("**/dossiers/*")
    page.wait_for_function(
        "() => document.querySelector('[data-testid=dossier-state]')"
        " && document.querySelector('[data-testid=dossier-state]').innerText.trim() !== 'building'",
        timeout=20000)
    assert page.get_by_test_id("dossier-state").inner_text().strip() in ("ready", "failed")
    assert not errors, errors
    ctx.close()
