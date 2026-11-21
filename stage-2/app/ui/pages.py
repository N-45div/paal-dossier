"""Server-rendered shells for the browser screens. Data arrives from the JSON API in the page."""

from __future__ import annotations

from html import escape

from aiohttp import web

from app.domain import normalise_domain
from app.ui.layout import page

HTML_HEADERS = {"Content-Type": "text/html; charset=utf-8", "Vary": "Accept"}


def html(body: str, status: int = 200) -> web.Response:
    return web.Response(text=body, status=status, headers=HTML_HEADERS)


async def home(request: web.Request) -> web.Response:
    return html(page("Dossiers", HOME_BODY, script="home.js"))


async def signup(request: web.Request) -> web.Response:
    return html(page("Sign up", SIGNUP_BODY, script="auth.js"))


async def login(request: web.Request) -> web.Response:
    return html(page("Log in", LOGIN_BODY, script="auth.js"))


async def dossier(request: web.Request) -> web.Response:
    """The dossier shell for `Accept: text/html`. A non-normalised domain redirects to the
    normalised path (spec §4); an invalid one renders the not-found state directly."""
    raw = request.match_info["domain"]
    domain = normalise_domain(raw)
    if domain is None:
        return html(page("Dossier not found", dossier_not_found_body(raw)), status=404)
    if domain != raw:
        return web.Response(status=302, headers={"Location": f"/dossiers/{domain}",
                                                 "Vary": "Accept"})
    return html(page(domain, dossier_body(domain), script="dossier.js"))


def domain_screen(request: web.Request, *, suffix: str, title: str, body_for, script: str):
    """Serve a per-dossier browser screen at /dossiers/{domain}/{suffix}. The domain is
    normalised as in §4: a non-normalised one redirects, an invalid one renders not-found."""
    raw = request.match_info["domain"]
    domain = normalise_domain(raw)
    if domain is None:
        return html(page("Dossier not found", dossier_not_found_body(raw)), status=404)
    if domain != raw:
        return web.Response(status=302, headers={
            "Location": f"/dossiers/{domain}/{suffix}", "Vary": "Accept"})
    return html(page(title, body_for(domain), script=script))


def dossier_not_found_body(raw: str, heading_level: int = 1) -> str:
    """The not-found block. Inside a dossier screen its heading is a level below the domain h1."""
    heading = f"h{heading_level}"
    return (
        f'<section class="panel"><{heading}>Dossier not found</{heading}>'
        '<p data-testid="dossier-not-found">No dossier exists for '
        f"{escape(raw)}.</p>"
        '<p><a href="/">Back to dossiers</a></p></section>'
    )


def dossier_body(domain: str) -> str:
    safe = escape(domain, quote=True)
    return f"""
<nav class="crumbs" aria-label="Breadcrumb"><a href="/">Dossiers</a><span aria-hidden="true">/</span><span>{safe}</span></nav>
<div id="dossier-root" data-domain="{safe}">
  <header class="dossier-head">
    <h1 data-testid="dossier-domain">{safe}</h1>
    <div class="summary">
      <span data-testid="dossier-state" class="badge state-badge" aria-live="polite">Loading</span>
      <span data-testid="dossier-spent" class="meta"></span>
      <span data-testid="dossier-researched-at" class="meta" hidden></span>
    </div>
    <div class="actions">
      <button type="button" class="btn primary" data-testid="dossier-refresh">Refresh research</button>
      <button type="button" class="btn" data-testid="dossier-reload">Reload</button>
      <a class="btn" data-testid="dossier-evidence-link" href="/dossiers/{safe}/evidence">Evidence</a>
    </div>
    <p class="error" role="alert" data-testid="refresh-error" hidden>
      Refresh failed. Check the message and try again.</p>
    <p class="uncertain" role="status" data-testid="refresh-uncertain" hidden>
      We could not confirm whether the refresh started. Retry to be sure; a retry starts at most one build.</p>
  </header>
  <p class="status" role="status" aria-live="polite" id="dossier-status">Loading dossier…</p>
  <p class="auth-needed" hidden id="dossier-auth">
    <a href="/login">Log in</a> to view this dossier.</p>
  <div class="fields" id="dossier-fields"></div>
  <div class="not-found" hidden>{dossier_not_found_body(domain, heading_level=2)}</div>
</div>
"""


HOME_BODY = """
<section class="hero">
  <h1>Company dossiers</h1>
  <p>Research a company's domain and see each fact with the evidence behind it.</p>
</section>
<section class="panel" aria-labelledby="research-heading">
  <h2 id="research-heading">Research a company</h2>
  <form id="research-form" class="research-form" novalidate>
    <div class="field-group">
      <label for="research-domain">Company domain</label>
      <input id="research-domain" data-testid="research-domain" name="domain" type="text"
             autocomplete="off" spellcheck="false" placeholder="acme-robotics.test"
             aria-describedby="research-help">
      <p id="research-help" class="help">For example acme-robotics.test.</p>
    </div>
    <button type="submit" class="btn primary" data-testid="research-submit">Research</button>
  </form>
  <p class="error" role="alert" data-testid="research-error" hidden></p>
  <p class="uncertain" role="status" data-testid="research-uncertain" hidden>
    We could not confirm whether this research started. Retry with the same domain to be sure.</p>
</section>
<section class="panel" aria-labelledby="list-heading">
  <div class="list-head">
    <h2 id="list-heading">Dossiers</h2>
    <div class="field-group search">
      <label for="dossier-search">Search by domain or name</label>
      <input id="dossier-search" data-testid="dossier-search" type="search" autocomplete="off">
    </div>
  </div>
  <p class="status" role="status" aria-live="polite" id="list-status">Loading dossiers…</p>
  <ul class="dossier-list" data-testid="dossier-list" id="dossier-list"></ul>
  <p class="empty" data-testid="empty-dossiers" hidden>No dossier matches.</p>
</section>
"""


def _auth_form(heading: str, fields: str, submit_id: str, submit_label: str,
               alt: str) -> str:
    return f"""
<section class="panel narrow" aria-labelledby="auth-heading">
  <h1 id="auth-heading">{heading}</h1>
  <form id="auth-form" class="stacked" novalidate>
    {fields}
    <p class="error" role="alert" data-testid="auth-error" hidden></p>
    <button type="submit" class="btn primary" data-testid="{submit_id}">{submit_label}</button>
  </form>
  <p class="alt">{alt}</p>
</section>
"""


SIGNUP_BODY = _auth_form(
    "Create an account",
    """
    <div class="field-group"><label for="signup-display-name">Display name</label>
      <input id="signup-display-name" data-testid="signup-display-name" name="display_name"
             type="text" autocomplete="name" required></div>
    <div class="field-group"><label for="signup-email">Email</label>
      <input id="signup-email" data-testid="signup-email" name="email" type="email"
             autocomplete="email" required></div>
    <div class="field-group"><label for="signup-password">Password</label>
      <input id="signup-password" data-testid="signup-password" name="password" type="password"
             autocomplete="new-password" minlength="8" required>
      <p class="help">At least 8 characters.</p></div>
    """,
    "signup-submit",
    "Sign up",
    'Already have an account? <a href="/login">Log in</a>.',

)

LOGIN_BODY = _auth_form(
    "Log in",
    """
    <div class="field-group"><label for="login-email">Email</label>
      <input id="login-email" data-testid="login-email" name="email" type="email"
             autocomplete="email" required></div>
    <div class="field-group"><label for="login-password">Password</label>
      <input id="login-password" data-testid="login-password" name="password" type="password"
             autocomplete="current-password" required></div>
    """,
    "login-submit",
    "Log in",
    'New here? <a href="/signup">Sign up</a>.',

)
