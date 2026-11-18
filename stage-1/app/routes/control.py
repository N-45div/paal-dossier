"""Health, reset and clock endpoints (§3.2–§3.4)."""
import asyncio

from starlette.requests import Request

from app.clock import Clock, parse_timestamp
from app.errors import ApiError, invalid, malformed
from app.fields import check_types
from app import snapshot
from app.http import json_object, json_response, no_content, parse_json
from app.passwords import hash_password
from app.store import State, Store, User

USER_FIELDS = ("id", "email", "password", "display_name")


async def health(request: Request):
    return json_response({"status": "ok"})


def _users_of(body: dict) -> list[dict]:
    users = body.get("users")
    if users is None:
        return []
    if not isinstance(users, list) or not all(isinstance(u, dict) for u in users):
        raise malformed("users must be a list of objects")
    for user in users:
        check_types(user, USER_FIELDS)
    return users


def _validated_fixture(body: dict):
    if "now" not in body:
        raise invalid("now is required")
    check_types(body, ("now",))
    now = parse_timestamp(body["now"])
    users = _users_of(body)
    seen_emails, seen_ids = set(), set()
    for user in users:
        for name in USER_FIELDS:
            if name not in user:
                raise invalid(f"user {name} is required")
        email, user_id = user["email"].lower(), user["id"]
        if not user_id or len(user_id) > 64:
            raise invalid("user id must be 1 to 64 characters")
        if email in seen_emails or user_id in seen_ids:
            raise invalid("duplicate user in fixture")
        seen_emails.add(email)
        seen_ids.add(user_id)
    return now, users


async def reset(request: Request):
    store: Store = request.app.state.store
    now, users = _validated_fixture(await json_object(request))
    hashes = [await asyncio.to_thread(hash_password, u["password"]) for u in users]
    state = State(clock=Clock(now))
    for user, password_hash in zip(users, hashes):
        state.add_user(User(user["id"], user["email"], user["display_name"], password_hash))
    store.replace(state)
    return no_content()


async def set_clock(request: Request):
    store: Store = request.app.state.store
    body = await json_object(request)
    if "now" not in body:
        raise invalid("now is required")
    check_types(body, ("now",))
    store.state.clock.advance(parse_timestamp(body["now"]))
    return no_content()


async def export_state(request: Request):
    store: Store = request.app.state.store
    return json_response(snapshot.export_state(store.state))


async def import_state(request: Request):
    store: Store = request.app.state.store
    payload = parse_json(await request.body())
    if not isinstance(payload, dict):
        raise invalid("import body must be a JSON object")
    state = snapshot.build_state(payload, store.state.clock)
    store.replace(state)
    return no_content()
