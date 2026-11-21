"""The evidence screen, `/dossiers/{domain}/evidence` (stage 2, R2U2): every candidate of every field."""

from __future__ import annotations

from html import escape

from aiohttp import web

from app.ui.layout import page
from app.ui.pages import domain_screen

def evidence_body(domain: str) -> str:
    safe = escape(domain, quote=True)
    return f"""
<nav class="crumbs" aria-label="Breadcrumb"><a href="/">Dossiers</a><span aria-hidden="true">/</span><a href="/dossiers/{safe}">{safe}</a><span aria-hidden="true">/</span><span>Evidence</span></nav>
<div id="evidence-root" data-domain="{safe}">
  <header class="dossier-head">
    <h1 data-testid="evidence-domain">Evidence for {safe}</h1>
    <p class="meta">Every source that mentions a field, with the value it gives. Candidates are listed in the order the service ranks them.</p>
    <p class="status" role="status" aria-live="polite" id="evidence-status">Loading evidence…</p>
    <p class="auth-needed" hidden id="evidence-auth"><a href="/login">Log in</a> to view this evidence.</p>
  </header>
  <div class="fields" id="evidence-fields"></div>
  <div class="not-found" hidden>
    <section class="panel"><h2>Dossier not found</h2>
      <p data-testid="dossier-not-found">No dossier exists for {safe}.</p>
      <p><a href="/">Back to dossiers</a></p></section>
  </div>
</div>
"""


async def evidence(request: web.Request) -> web.Response:
    return domain_screen(
        request, suffix="evidence", title="Evidence",
        body_for=evidence_body, script="evidence.js",
    )
