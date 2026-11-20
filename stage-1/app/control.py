"""Test control endpoints: reset and clock (spec §3.3, §3.4). No authentication."""

from __future__ import annotations

from .clock import parse_rfc3339
from .context import App
from .fixture import parse_fixture
from .messages import Reply, Request, no_content
from .validation import parse_object, required_string


def reset(app: App, request: Request) -> Reply:
    fixture = parse_fixture(parse_object(request.body))
    with app.store.lock:
        app.clock.reset_to(fixture.now)
        app.store.reset(fixture.users)
    return no_content()


def move_clock(app: App, request: Request) -> Reply:
    body = parse_object(request.body)
    instant = parse_rfc3339(required_string(body, "now"))
    app.clock.move_to(instant)
    return no_content()
