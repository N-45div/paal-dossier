"""The change feed and the per-field history (stage 3): `GET /changes` and
`GET /dossiers/{domain}/history`. Both need a bearer token, as every endpoint but those
named in §6 does."""

from __future__ import annotations

from aiohttp import web

from app import history as history_views
from app.auth import authenticate
from app.dossiers import integer_param, valid_domain
from app.errors import json_response, not_found
from app.history import Entry
from app.state import STORE, Store
from app.feed import FeedRow


def _change_json(row: FeedRow) -> dict:
    return {
        "seq": row.seq,
        "domain": row.domain,
        "field": row.field,
        "type": row.type,
        "from": row.previous,
        "to": row.value,
        "true_from": row.true_from.isoformat() if row.true_from else None,
        "learned_at": row.learned_at.isoformat() if row.learned_at else None,
    }


async def changes(request: web.Request) -> web.Response:
    store: Store = request.app[STORE]
    authenticate(request, store)
    since = integer_param(request.query.get("since"), 0, 0, None, "since")
    limit = integer_param(request.query.get("limit"), 50, 1, 200, "limit")
    pending = [row for row in store.state.feed if row.seq > since]
    page = pending[:limit]
    return json_response({
        "changes": [_change_json(row) for row in page],
        "has_more": len(pending) > limit,
    })


def _entry_json(entry: Entry) -> dict:
    return {
        "type": entry.type,
        "value": entry.value,
        "true_from": entry.true_from.isoformat() if entry.true_from else None,
        "learned_at": entry.learned_at.isoformat() if entry.learned_at else None,
        "citations": list(entry.citations),
    }


async def history(request: web.Request) -> web.Response:
    store: Store = request.app[STORE]
    authenticate(request, store)
    dossier = store.state.dossiers_by_domain.get(valid_domain(request.match_info["domain"]))
    if dossier is None:
        raise not_found("no dossier for this domain")
    entries = history_views.history(dossier.records)
    return json_response({
        "domain": dossier.domain,
        "fields": {name: [_entry_json(entry) for entry in found]
                   for name, found in entries.items()},
    })
