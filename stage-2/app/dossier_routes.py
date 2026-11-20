"""Dossier endpoints (§8): open, read, refresh, list. Writes go through the idempotency layer."""

import re

from . import dossiers, idempotency
from .domain import normalise_domain
from .errors import not_found, validation
from .wire import parse_json, require_object, required_string

_DIGITS = re.compile(r"[0-9]+")


def register(router) -> None:
    router.add("POST", "/dossiers", open_dossier)
    router.add("GET", "/dossiers", list_dossiers)
    router.add("GET", "/dossiers/{domain}", read_dossier)
    router.add("POST", "/dossiers/{domain}/refresh", refresh_dossier)


def open_dossier(app, request):
    key = idempotency.header_key(request.headers)
    body = require_object(parse_json(request.body))
    identity = {"domain": body["domain"]} if "domain" in body else {}
    with app.store.transact() as (state, generation):
        stored = idempotency.replay(state, request.user_id, request.method, request.path, key, identity)
        if stored is not None:
            return 200, stored
        domain = normalise_domain(required_string(body, "domain"))
        record = state.dossiers.get(domain)
        if record is not None:
            payload = {"dossier_id": record["dossier_id"], "domain": domain, "state": record["state"]}
            status = 200
        else:
            moment = app.clock.now()
            dossier_id = state.next_id("dossier", state.dossier_ids())
            record = dossiers.new_record(dossier_id, domain)
            state.dossiers[domain] = record
            app.runner.start(dossier_id, domain, moment, generation)
            payload = {"dossier_id": dossier_id, "domain": domain, "state": "building"}
            status = 202
        idempotency.claim(state, request.user_id, request.method, request.path, key, identity, status, payload)
        return status, payload


def refresh_dossier(app, request):
    key = idempotency.header_key(request.headers)
    identity: dict = {}  # the body is ignored entirely (§7)
    with app.store.transact() as (state, generation):
        stored = idempotency.replay(state, request.user_id, request.method, request.path, key, identity)
        if stored is not None:
            return 200, stored
        domain = normalise_domain(request.params["domain"])
        record = state.dossiers.get(domain)
        if record is None:
            raise not_found("no dossier for this domain")
        if record["state"] != "building":
            record["state"] = "building"
            app.runner.start(record["dossier_id"], domain, app.clock.now(), generation)
        payload = {"dossier_id": record["dossier_id"], "domain": domain, "state": "building"}
        idempotency.claim(state, request.user_id, request.method, request.path, key, identity, 202, payload)
        return 202, payload


def read_dossier(app, request):
    domain = normalise_domain(request.params["domain"])
    with app.store.transact() as (state, _generation):
        record = state.dossiers.get(domain)
        if record is None:
            raise not_found("no dossier for this domain")
        return 200, dossiers.render(record)


def list_dossiers(app, request):
    query = request.query
    text = _first(query, "q") or ""
    limit = _integer(query, "limit", default=50, low=1, high=200)
    offset = _integer(query, "offset", default=0, low=0, high=None)
    needle = text.lower()
    with app.store.transact() as (state, _generation):
        matched = [
            dossiers.summary(record)
            for domain, record in sorted(state.dossiers.items())
            if _matches(record, needle)
        ]
    page = matched[offset : offset + limit]
    return 200, {"dossiers": page, "has_more": len(matched) > offset + limit}


def _matches(record: dict, needle: str) -> bool:
    if not needle:
        return True
    legal = record["fields"]["legal_name"]["value"] or ""
    return needle in record["domain"] or needle in str(legal).lower()


def _first(query: dict, name: str) -> str | None:
    values = query.get(name)
    return values[0] if values else None


def _integer(query: dict, name: str, *, default: int, low: int, high: int | None) -> int:
    raw = _first(query, name)
    if raw is None:
        return default
    if _DIGITS.fullmatch(raw) is None:
        raise validation(f"{name} must be a plain decimal integer")
    digits = raw.lstrip("0") or "0"
    value = int(digits) if len(digits) <= 18 else 10**18  # beyond any page size: out of range
    if value < low or (high is not None and value > high):
        raise validation(f"{name} is out of range")
    return value


