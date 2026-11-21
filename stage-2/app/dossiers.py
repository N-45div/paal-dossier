"""Dossier endpoints (spec §8): create, read, list and refresh."""

from __future__ import annotations

import re
import secrets

from aiohttp import web

from app.auth import authenticate
from app.builds import start_build
from app.domain import normalise_domain
from app.errors import ApiError, json_response, not_found, validation_failed
from app.idempotency import check_key_length, read_key, run_idempotent
from app.research import FIELD_NAMES, FieldResult
from app.state import STORE, Dossier, Store
from app.validation import read_json_object, required_string

_DIGITS = re.compile(r"[0-9]+")
DEFAULT_LIMIT = 50
MAX_LIMIT = 200


def valid_domain(raw: str) -> str:
    domain = normalise_domain(raw)
    if domain is None:
        raise validation_failed("domain is not a valid host name")
    return domain


def summary(dossier: Dossier) -> dict:
    return {"dossier_id": dossier.id, "domain": dossier.domain, "state": dossier.live_state}


def field_json(result: FieldResult) -> dict:
    known = result.value is not None
    return {
        "value": result.value,
        "status": "known" if known else "unknown",
        "citations": list(result.citations) if known else [],
    }


def details(dossier: Dossier) -> dict:
    return {
        **summary(dossier),
        "researched_at": dossier.researched_at.isoformat() if dossier.researched_at else None,
        "spent_units": dossier.spent_units,
        "fields": {name: field_json(dossier.fields[name]) for name in FIELD_NAMES},
    }


def _store(request: web.Request) -> Store:
    return request.app[STORE]


def _raw_path(request: web.Request) -> str:
    return request.raw_path.split("?", 1)[0]


async def create(request: web.Request) -> web.Response:
    store = _store(request)
    user = authenticate(request, store)
    key = read_key(request)
    body = await read_json_object(request)
    check_key_length(key)
    canonical = {name: body[name] for name in ("domain",) if name in body}

    def effect() -> tuple[int, dict]:
        domain = valid_domain(required_string(body, "domain"))
        existing = store.state.dossiers_by_domain.get(domain)
        if existing is not None:
            return 200, summary(existing)  # no build starts for an existing dossier
        dossier = Dossier(id="d_" + secrets.token_hex(8), domain=domain)
        store.state.dossiers_by_domain[domain] = dossier
        start_build(store, dossier, store.clock.now())
        return 202, summary(dossier)

    return run_idempotent(store, user, key, "POST", _raw_path(request), canonical, effect)


async def refresh(request: web.Request) -> web.Response:
    store = _store(request)
    user = authenticate(request, store)
    key = read_key(request)
    check_key_length(key)
    raw_domain = request.match_info["domain"]

    def effect() -> tuple[int, dict]:
        domain = valid_domain(raw_domain)
        dossier = store.state.dossiers_by_domain.get(domain)
        if dossier is None:
            raise not_found("no dossier for this domain")
        if not dossier.building:
            start_build(store, dossier, store.clock.now())
        return 202, summary(dossier)

    # The refresh body is ignored (§8), so it plays no part in deciding a replay.
    return run_idempotent(store, user, key, "POST", _raw_path(request), None, effect)


async def get_one(request: web.Request) -> web.Response:
    store = _store(request)
    authenticate(request, store)
    dossier = store.state.dossiers_by_domain.get(valid_domain(request.match_info["domain"]))
    if dossier is None:
        raise not_found("no dossier for this domain")
    return json_response(details(dossier))


async def list_all(request: web.Request) -> web.Response:
    store = _store(request)
    authenticate(request, store)
    query = request.query
    limit = _integer_param(query.get("limit"), DEFAULT_LIMIT, 1, MAX_LIMIT, "limit")
    offset = _integer_param(query.get("offset"), 0, 0, None, "offset")
    needle = query.get("q", "").lower()

    matches = [
        dossier for dossier in store.state.dossiers_by_domain.values()
        if needle in dossier.domain or needle in _legal_name(dossier).lower()
    ]
    matches.sort(key=lambda dossier: dossier.domain)
    page = matches[offset:offset + limit]
    return json_response({
        "dossiers": [_list_item(dossier) for dossier in page],
        "has_more": len(matches) > offset + limit,
    })


def _legal_name(dossier: Dossier) -> str:
    value = dossier.fields["legal_name"].value
    return value if isinstance(value, str) else ""


def _list_item(dossier: Dossier) -> dict:
    return {
        **summary(dossier),
        "legal_name": dossier.fields["legal_name"].value,
        "researched_at": dossier.researched_at.isoformat() if dossier.researched_at else None,
        "spent_units": dossier.spent_units,
    }


def _integer_param(raw: str | None, default: int, low: int, high: int | None, name: str) -> int:
    if raw is None:
        return default
    if not _DIGITS.fullmatch(raw):
        raise validation_failed(f"{name} must be a plain decimal integer")
    value = int(raw)
    if value < low or (high is not None and value > high):
        raise ApiError(422, "validation_failed", f"{name} is out of range")
    return value
