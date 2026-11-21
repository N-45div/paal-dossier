"""The contested screen, `/contested` (stage 2, R2U2): every contested field across all dossiers."""

from __future__ import annotations

from aiohttp import web

from app.ui.layout import page

CONTESTED_BODY = """
<section class="hero">
  <h1>Contested fields</h1>
  <p>Fields where the sources disagree. The selected value is the one the dossier currently uses.</p>
</section>
<section class="panel" aria-labelledby="contested-heading">
  <h2 id="contested-heading" class="visually-hidden">Contested fields across dossiers</h2>
  <p class="status" role="status" aria-live="polite" id="contested-status">Loading contested fields…</p>
  <p class="auth-needed" hidden id="contested-auth"><a href="/login">Log in</a> to view contested fields.</p>
  <ul class="contested-list" data-testid="contested-list" id="contested-list" hidden></ul>
  <p class="empty" data-testid="empty-contested" hidden>No field is contested right now.</p>
</section>
"""


async def contested(request: web.Request) -> web.Response:
    return web.Response(
        text=page("Contested fields", CONTESTED_BODY, script="contested.js"),
        headers={"Content-Type": "text/html; charset=utf-8", "Vary": "Accept"},
    )
