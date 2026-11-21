"""`GET /dossiers/{domain}/values?true_at=` (stage 3): the value each field had on a date, from
the evidence this service had at `as_of` (default: now). Needs a bearer token, like every endpoint
but those named in §6. The fold is in ``app.values``; this module reads the request and the store."""

from __future__ import annotations

import re
from datetime import date, datetime

from aiohttp import web

from app.auth import authenticate
from app.clock import format_timestamp, parse_rfc3339
from app.dossiers import valid_domain
from app.errors import json_response, not_found, validation_failed
from app.state import STORE, Store
from app.values import values_at

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _true_at(raw: str | None) -> date:
    if raw is None or _DATE.match(raw) is None:
        raise validation_failed("true_at must be a YYYY-MM-DD date")
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise validation_failed("true_at must be a YYYY-MM-DD date") from None


def _as_of(request: web.Request, store: Store) -> datetime:
    raw = request.query.get("as_of")
    if raw is None:
        return store.clock.now()
    try:
        return parse_rfc3339(raw)
    except ValueError:
        raise validation_failed("as_of must be an RFC 3339 timestamp with an explicit offset") from None


async def values(request: web.Request) -> web.Response:
    store: Store = request.app[STORE]
    authenticate(request, store)
    true_at = _true_at(request.query.get("true_at"))
    as_of = _as_of(request, store)
    dossier = store.state.dossiers_by_domain.get(valid_domain(request.match_info["domain"]))
    if dossier is None:
        raise not_found("no dossier for this domain")
    records = [r for r in dossier.records if r.time <= as_of]
    if not any(r.ok for r in records):
        raise not_found("no build of this dossier completed ready at or before as_of")
    answers = values_at(records, true_at)
    return json_response({
        "domain": dossier.domain,
        "true_at": true_at.isoformat(),
        "as_of": format_timestamp(as_of),
        "fields": {
            name: {
                "value": answer.value,
                "true_from": answer.true_from.isoformat() if answer.true_from else None,
                "citations": list(answer.citations) if answer.value is not None else [],
            }
            for name, answer in answers.items()
        },
    })
