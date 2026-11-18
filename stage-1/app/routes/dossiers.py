"""Dossier endpoints (§8) with idempotent writes (§7)."""
import re

from starlette.requests import Request

from app import builds, domains, idempotency
from app.auth_guard import authenticate
from app.dossiers import Dossier
from app.errors import ApiError, invalid, malformed, not_found
from app.http import json_object, json_response, parse_json, raw_path
from app.idempotency import Record
from app.store import Store, new_id

_DIGITS = re.compile(r"^[0-9]+$")


def _remember(state, scope: tuple, signature, body: dict) -> None:
    state.idempotency[scope] = Record(signature, body)


async def create(request: Request):
    store: Store = request.app.state.store
    authenticate(request, store.state)
    body = await json_object(request)
    user = authenticate(request, store.state)  # a reset may have run while the body arrived
    key = idempotency.key_of(request)
    state = store.state
    scope = (user.user_id, "POST", raw_path(request), key)
    signature = ("domain" in body, body.get("domain"))
    replay = idempotency.lookup(state.idempotency, scope, signature)
    if replay:
        return replay
    if "domain" not in body:
        raise invalid("domain is required")
    if not isinstance(body["domain"], str):
        raise malformed("domain must be a string")
    domain = domains.normalise_valid(body["domain"])
    dossier = state.dossiers.get(domain)
    status = 200
    if dossier is None:
        dossier = Dossier(new_id("d"), domain)
        state.dossiers[domain] = dossier
        builds.start(store, dossier, state.clock.now())
        status = 202
    response = dossier.summary()
    _remember(state, scope, signature, response)
    return json_response(response, status)


async def refresh(request: Request):
    store: Store = request.app.state.store
    user = authenticate(request, store.state)
    key = idempotency.key_of(request)
    state = store.state
    scope = (user.user_id, "POST", raw_path(request), key)
    replay = idempotency.lookup(state.idempotency, scope, None)
    if replay:
        return replay
    domain = domains.normalise_valid(request.path_params["domain"])
    dossier = state.dossiers.get(domain)
    if dossier is None:
        raise not_found("no dossier for this domain")
    if not dossier.building:
        builds.start(store, dossier, state.clock.now())
    response = dossier.summary()
    _remember(state, scope, None, response)
    return json_response(response, 202)


async def read(request: Request):
    store: Store = request.app.state.store
    authenticate(request, store.state)
    domain = domains.normalise_valid(request.path_params["domain"])
    dossier = store.state.dossiers.get(domain)
    if dossier is None:
        raise not_found("no dossier for this domain")
    return json_response(dossier.view())


def _int_param(request: Request, name: str, default: int, low: int, high: int | None) -> int:
    raw = request.query_params.get(name)
    if raw is None:
        return default
    if not _DIGITS.match(raw):
        raise invalid(f"{name} must be a plain decimal integer")
    digits = raw.lstrip("0") or "0"
    value = int(digits) if len(digits) <= 18 else 10 ** 18  # beyond any real bound
    if value < low or (high is not None and value > high):
        raise invalid(f"{name} is out of range")
    return value


async def listing(request: Request):
    store: Store = request.app.state.store
    authenticate(request, store.state)
    limit = _int_param(request, "limit", 50, 1, 200)
    offset = _int_param(request, "offset", 0, 0, None)
    needle = request.query_params.get("q", "").lower()
    matching = [d for d in store.state.dossiers.values()
                if needle in d.domain.lower()
                or needle in (d.fields["legal_name"]["value"] or "").lower()]
    matching.sort(key=lambda d: d.domain)
    page = matching[offset:offset + limit]
    return json_response({"dossiers": [d.list_item() for d in page],
                          "has_more": offset + limit < len(matching)})
