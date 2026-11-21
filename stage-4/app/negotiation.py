"""Content negotiation for the shared dossier route (stage 2, Rul-S2-6).

``/dossiers/{domain}`` answers HTML to a browser (``Accept: text/html``) and JSON to every
other client. The UI registers its renderer under ``HTML_RENDERER``; until it does, every
request gets JSON."""

from __future__ import annotations

from aiohttp import web

HTML_RENDERER: web.AppKey = web.AppKey("html_renderer", object)


def wants_html(request: web.Request) -> bool:
    return "text/html" in request.headers.get("Accept", "")
