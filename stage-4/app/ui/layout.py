"""The shared page shell: document head, site header with session controls, and main slot."""

from __future__ import annotations

from html import escape

NAV_LINKS = (
    ("/", "Dossiers"),
    ("/contested", "Contested"),
)


def _nav() -> str:
    links = "".join(f'<a href="{href}">{label}</a>' for href, label in NAV_LINKS)
    return f'<nav class="primary-nav" aria-label="Primary">{links}</nav>'


def _session_controls() -> str:
    return (
        '<div class="session">'
        '<span class="session-in">Signed in as '
        '<span data-testid="current-user" class="current-user"></span></span>'
        '<button type="button" class="btn small session-in" data-testid="logout-button">'
        "Log out</button>"
        '<a class="session-out" href="/login">Log in</a>'
        '<a class="session-out btn small" href="/signup">Sign up</a>'
        "</div>"
    )


def page(title: str, body: str, *, script: str | None = None) -> str:
    """Return a complete HTML document. `body` is trusted markup built by the page modules;
    any text from data or users must already be escaped by the caller."""
    module = (
        f'<script type="module" src="/static/js/{escape(script, quote=True)}"></script>'
        if script else ""
    )
    return (
        "<!DOCTYPE html>"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{escape(title)} · Dossier</title>"
        '<link rel="stylesheet" href="/static/app.css">'
        '</head><body data-session="out">'
        '<a class="skip-link" href="#main">Skip to content</a>'
        '<header class="site-header">'
        '<a class="brand" href="/">Dossier</a>'
        f"{_nav()}{_session_controls()}"
        "</header>"
        f'<main id="main" tabindex="-1" class="container">{body}</main>'
        '<script type="module" src="/static/js/layout.js"></script>'
        f"{module}"
        "</body></html>"
    )
