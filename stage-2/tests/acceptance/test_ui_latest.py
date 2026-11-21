"""Stage-2 browser: latest-read-wins with out-of-order responses (R2.136), async Playwright.

The first read of the dossier is delayed and reports `building`; the screen's next read is
answered at once with the service's current state. When the delayed earlier read finally
arrives, the screen must still show the later state. Ledger id: R2.136.
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid

import pytest

from conftest import BASE_URL
from test_ui_browser import CHROME

SAMPLE = "brightwater-labs.test"


def _is_read(route):
    req = route.request
    return req.method == "GET" and req.resource_type in ("fetch", "xhr") \
        and req.url.split("?")[0].endswith(f"/dossiers/{SAMPLE}")


async def _run():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
        ctx = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        # sign up through the UI
        await page.goto(f"{BASE_URL}/signup")
        await page.get_by_test_id("signup-email").fill(f"prover-{uuid.uuid4().hex[:10]}@example.com")
        await page.get_by_test_id("signup-password").fill("correct horse")
        await page.get_by_test_id("signup-display-name").fill("Prover Tester")
        await page.get_by_test_id("signup-submit").click()
        await page.get_by_test_id("current-user").wait_for(timeout=10000)

        # research the sample domain so the dossier exists (ready)
        await page.goto(f"{BASE_URL}/")
        await page.get_by_test_id("research-domain").fill(SAMPLE)
        await page.get_by_test_id("research-submit").click()
        await page.wait_for_url(f"**/dossiers/{SAMPLE}", timeout=15000)
        for _ in range(180):
            if await page.get_by_test_id("dossier-state").inner_text() in ("ready", "failed"):
                break
            await page.wait_for_timeout(500)

        # now the stale read: the first read after this point is delayed and says `building`
        seen = {"n": 0}

        async def handler(route):
            if not _is_read(route):
                return await route.continue_()
            seen["n"] += 1
            if seen["n"] == 1:
                resp = await route.fetch()
                await asyncio.sleep(3.0)
                body = await resp.json()
                body["state"] = "building"
                return await route.fulfill(response=resp, body=json.dumps(body),
                                           headers={**resp.headers,
                                                    "content-type": "application/json"})
            return await route.continue_()

        await page.route("**/dossiers/*", handler)
        await page.goto(f"{BASE_URL}/dossiers/{SAMPLE}")
        # the later read answers `ready`; wait past the delayed earlier read's arrival
        await page.wait_for_timeout(5500)
        state = await page.get_by_test_id("dossier-state").inner_text()
        await page.unroute("**/dossiers/*")
        await ctx.close()
        await browser.close()
        return seen["n"], state.strip(), errors


def test_latest_read_wins_over_a_delayed_earlier_read(tmp_path):
    # R2.136
    if not os.path.exists(CHROME):
        pytest.skip(f"no Chromium at {CHROME}")
    reads, state, errors = asyncio.run(_run())
    assert reads >= 2, f"the screen made only {reads} read(s); the test did not reorder reads"
    assert state in ("ready", "failed"), f"stale read overwrote the later state: {state!r}"
    assert not errors, errors
