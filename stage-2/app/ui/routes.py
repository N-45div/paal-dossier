"""Registers the browser UI: screen routes, the negotiated dossier renderer and static files."""

from __future__ import annotations

from pathlib import Path

from aiohttp import web

from app.negotiation import HTML_RENDERER
from app.ui import pages

STATIC_DIR = Path(__file__).parent / "static"


def register(app: web.Application) -> None:
    """Add the UI to `app`. Screen modules added later (evidence, contested) register here."""
    app[HTML_RENDERER] = pages.dossier
    app.router.add_get("/", pages.home)
    app.router.add_get("/signup", pages.signup)
    app.router.add_get("/login", pages.login)
    app.router.add_static("/static/", STATIC_DIR, name="static", show_index=False)
