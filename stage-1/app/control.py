"""Test control endpoints: reset, clock, export and import (spec §3.3, §3.4, §10).
No authentication.
"""

from __future__ import annotations

from . import snapshot
from .clock import parse_rfc3339
from .context import App
from .fixture import parse_fixture
from .messages import Reply, Request, json_reply, no_content
from .store import StoreState
from .validation import parse_object, required_string


def reset(app: App, request: Request) -> Reply:
    fixture = parse_fixture(parse_object(request.body))
    with app.store.lock:
        app.clock.reset_to(fixture.now)
        app.store.replace(StoreState(users=list(fixture.users)))
    return no_content()


def move_clock(app: App, request: Request) -> Reply:
    body = parse_object(request.body)
    instant = parse_rfc3339(required_string(body, "now"))
    app.clock.move_to(instant)
    return no_content()


def export_state(app: App, request: Request) -> Reply:
    return json_reply(200, snapshot.export_document(app.store))


def import_state(app: App, request: Request) -> Reply:
    state = snapshot.parse_document(parse_object(request.body))
    app.store.replace(state)
    return no_content()
