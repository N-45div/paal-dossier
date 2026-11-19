"""Health and the unauthenticated /_test control endpoints (§3.2–§3.4, §10)."""

from datetime import datetime

from .errors import malformed, validation
from .state import FORMAT_VERSION, TRACK
from .store import Fixture, SeededUser
from .validation import is_valid_user_id
from .wire import parse_json, parse_rfc3339, require_object, required_string


def register(router) -> None:
    router.add("GET", "/health", health, public=True)
    router.add("POST", "/_test/reset", reset, public=True)
    router.add("POST", "/_test/clock", set_clock, public=True)
    router.add("GET", "/_test/export", export, public=True)
    router.add("POST", "/_test/import", import_state, public=True)


def health(app, request):
    return 200, {"status": "ok"}


def reset(app, request):
    fixture = parse_fixture(parse_json(request.body))
    app.store.reset(fixture)
    return 204, None


def set_clock(app, request):
    body = require_object(parse_json(request.body))
    moment = parse_timestamp(body)
    if not app.clock.advance_to(moment):
        raise validation("now is earlier than the clock's current time")
    return 204, None


def export(app, request):
    state = app.store.export_state()
    return 200, {"track": TRACK, "format_version": FORMAT_VERSION, "state": state}


def import_state(app, request):
    body = require_object(parse_json(request.body))
    if body.get("track") != TRACK:
        raise validation("track must be dossier")
    version = body.get("format_version")
    if not isinstance(version, int) or isinstance(version, bool) or version != FORMAT_VERSION:
        raise validation("unsupported format_version")
    if "state" not in body:
        raise validation("state is required")
    app.store.import_state(body["state"])
    return 204, None


def parse_timestamp(body: dict) -> datetime:
    text = required_string(body, "now")
    moment = parse_rfc3339(text)
    if moment is None:
        raise validation("now must be an RFC 3339 timestamp with an explicit offset")
    return moment


def parse_fixture(raw) -> Fixture:
    body = require_object(raw)
    now = parse_timestamp(body)
    users_raw = body.get("users", [])
    if not isinstance(users_raw, list):
        raise malformed("users must be a list")
    seen_ids: set[str] = set()
    seen_emails: set[str] = set()
    users: list[SeededUser] = []
    for entry in users_raw:
        if not isinstance(entry, dict):
            raise malformed("each user must be an object")
        user_id = required_string(entry, "id")
        email = required_string(entry, "email")
        password = required_string(entry, "password")
        display_name = required_string(entry, "display_name")
        # RL16: fixture users are not held to the signup rules (email form, password length,
        # display_name length); only the id bounds and the types apply.
        if not is_valid_user_id(user_id):
            raise validation("user id must be 1 to 64 characters")
        if user_id in seen_ids or email.lower() in seen_emails:
            raise validation("fixture holds a duplicate user id or email")
        seen_ids.add(user_id)
        seen_emails.add(email.lower())
        users.append(SeededUser(user_id, email, display_name, password))
    return Fixture(now=now, users=users)
