"""Dossier endpoints (spec §8): create, read, list and refresh.

Every handler takes the clock reading when the request is received; a build's time is that
reading (§8), so `researched_at` is the time the request that started the build arrived.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from urllib.parse import unquote

from .builds import start_build
from .context import App
from .domains import normalise_domain
from .dossier_model import Dossier
from .errors import not_found, validation_failed
from .idempotency import check_key_length, domain_fingerprint, key_header, run_idempotent
from .messages import Reply, Request, json_reply
from .validation import parse_object, required_string

_PLAIN_DIGITS = re.compile(r"[0-9]+")
_MAX_DIGITS = 18  # longer plain digits are beyond any limit; they never reach int()
DEFAULT_LIMIT = 50
MAX_LIMIT = 200


def create_dossier(app: App, request: Request) -> Reply:
    key = key_header(request)
    body = parse_object(request.body)
    key = check_key_length(key)
    requested_at = app.clock.now()
    return run_idempotent(
        app.store,
        request,
        key,
        domain_fingerprint(body),
        lambda: _create(app, body, requested_at),
    )


def refresh_dossier(app: App, request: Request) -> Reply:
    key = check_key_length(key_header(request))
    raw_domain = unquote(request.params["domain"])  # any body is ignored, per §7
    requested_at = app.clock.now()
    return run_idempotent(
        app.store,
        request,
        key,
        None,
        lambda: _refresh(app, raw_domain, requested_at),
    )


def get_dossier(app: App, request: Request) -> Reply:
    domain = normalise_domain(unquote(request.params["domain"]))
    with app.store.lock:
        dossier = app.store.dossier_by_domain(domain)
        if dossier is None:
            raise not_found("no dossier for this domain")
        return json_reply(200, _detail(dossier))


def list_dossiers(app: App, request: Request) -> Reply:
    limit = _int_query(request.query, "limit", DEFAULT_LIMIT, 1, MAX_LIMIT)
    offset = _int_query(request.query, "offset", 0, 0, None)
    needle = (_query_value(request.query, "q") or "").lower()
    with app.store.lock:
        matches = sorted(
            (dossier for dossier in app.store.dossiers() if _matches(dossier, needle)),
            key=lambda dossier: dossier.domain,
        )
        page = matches[offset : offset + limit]
        return json_reply(
            200,
            {
                "dossiers": [_listing(dossier) for dossier in page],
                "has_more": len(matches) > offset + limit,
            },
        )


def _create(app: App, body: dict[str, Any], requested_at: datetime) -> Reply:
    domain = normalise_domain(required_string(body, "domain"))
    with app.store.lock:
        existing = app.store.dossier_by_domain(domain)
        if existing is not None:
            return json_reply(200, _summary(existing))
        dossier = app.store.add_dossier(domain)
        start_build(app, dossier, requested_at)
        return json_reply(202, _summary(dossier))


def _refresh(app: App, raw_domain: str, requested_at: datetime) -> Reply:
    domain = normalise_domain(raw_domain)
    with app.store.lock:
        dossier = app.store.dossier_by_domain(domain)
        if dossier is None:
            raise not_found("no dossier for this domain")
        if not dossier.building:
            start_build(app, dossier, requested_at)
        return json_reply(202, _summary(dossier))


def _summary(dossier: Dossier) -> dict[str, str]:
    return {"dossier_id": dossier.dossier_id, "domain": dossier.domain, "state": dossier.state}


def _detail(dossier: Dossier) -> dict[str, Any]:
    return {
        "dossier_id": dossier.dossier_id,
        "domain": dossier.domain,
        "state": dossier.state,
        "researched_at": _time(dossier.researched_at),
        "spent_units": dossier.spent_units,
        "fields": dossier.fields,
    }


def _listing(dossier: Dossier) -> dict[str, Any]:
    return {
        "dossier_id": dossier.dossier_id,
        "domain": dossier.domain,
        "state": dossier.state,
        "legal_name": dossier.legal_name,
        "researched_at": _time(dossier.researched_at),
        "spent_units": dossier.spent_units,
    }


def _matches(dossier: Dossier, needle: str) -> bool:
    if not needle:
        return True
    if needle in dossier.domain.lower():
        return True
    return dossier.legal_name is not None and needle in dossier.legal_name.lower()


def _time(instant: datetime | None) -> str | None:
    return None if instant is None else instant.isoformat()


def _query_value(query: Mapping[str, list[str]], name: str) -> str | None:
    values = query.get(name)
    return values[0] if values else None


def _int_query(
    query: Mapping[str, list[str]], name: str, default: int, low: int, high: int | None
) -> int:
    text = _query_value(query, name)
    if text is None:
        return default
    if _PLAIN_DIGITS.fullmatch(text) is None:
        raise validation_failed(f"{name} must be plain decimal digits")
    value = int(text) if len(text) <= _MAX_DIGITS else 10**_MAX_DIGITS
    if value < low or (high is not None and value > high):
        raise validation_failed(f"{name} is out of range")
    return value
