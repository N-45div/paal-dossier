"""Dossier endpoints (§8)."""
from __future__ import annotations

import re
from typing import Any

from starlette.requests import Request
from starlette.responses import Response

from .auth import authenticate, object_body
from .domain import InvalidDomain, normalise_domain
from .errors import invalid, malformed, not_found
from .http import json_response
from .idempotency import read_key, remember, replay
from .service import Service
from .state import Dossier

_DIGITS = re.compile(r"[0-9]+")  # ASCII digits only, unlike \d
DEFAULT_LIMIT = 50
MAX_LIMIT = 200
MAX_SIGNIFICANT_DIGITS = 6
HUGE = 10**7  # any value past six significant digits: beyond every possible page


def _path_domain(raw: str) -> str:
    try:
        return normalise_domain(raw)
    except InvalidDomain as exc:
        raise invalid("domain is not a valid host name") from exc


def raw_path(request: Request) -> str:
    """The path exactly as sent, percent-encoding kept: replay identity is per raw path (ruling L1.03)."""
    raw = request.scope.get("raw_path")
    return raw.decode("latin-1") if raw else request.url.path


def _handle(dossier: Dossier) -> dict[str, Any]:
    return {"dossier_id": dossier.dossier_id, "domain": dossier.domain, "state": dossier.state}


def _digits_param(request: Request, name: str) -> int | None:
    """Ruling L1.28: plain ASCII digits only; None when absent, HUGE when over six significant digits."""
    raw = request.query_params.get(name)
    if raw is None:
        return None
    if _DIGITS.fullmatch(raw) is None:
        raise invalid(f"{name} must be plain decimal digits")
    significant = raw.lstrip("0") or "0"
    return HUGE if len(significant) > MAX_SIGNIFICANT_DIGITS else int(significant)


def _limit(request: Request) -> int:
    value = _digits_param(request, "limit")
    if value is None:
        return DEFAULT_LIMIT
    if not 1 <= value <= MAX_LIMIT:
        raise invalid("limit must be between 1 and 200")
    return value


def _offset(request: Request) -> int:
    value = _digits_param(request, "offset")
    return 0 if value is None else value


class DossierHandlers:
    def __init__(self, service: Service) -> None:
        self.service = service

    async def create(self, request: Request) -> Response:
        raw = await request.body()
        service = self.service
        store = service.store
        user_id = authenticate(request, store)
        body = object_body(raw)
        key = read_key(request)
        compared = {"domain": body["domain"]} if "domain" in body else {}
        path = raw_path(request)
        stored = replay(store, user_id, "POST", path, key, compared)
        if stored is not None:
            return json_response(stored, 200)
        if "domain" not in body:
            raise invalid("domain is required")
        if not isinstance(body["domain"], str):
            raise malformed("domain must be a string")
        domain = _path_domain(body["domain"])
        dossier = store.dossiers.get(domain)
        status = 200
        if dossier is None:
            dossier = store.new_dossier(domain)
            service.builds.start(dossier)
            status = 202
        response = _handle(dossier)
        remember(store, user_id, "POST", path, key, compared, response)
        return json_response(response, status)

    async def refresh(self, request: Request) -> Response:
        await request.body()
        service = self.service
        store = service.store
        user_id = authenticate(request, store)
        key = read_key(request)
        path = raw_path(request)
        stored = replay(store, user_id, "POST", path, key, None)
        if stored is not None:
            return json_response(stored, 200)
        domain = _path_domain(request.path_params["domain"])
        dossier = store.dossiers.get(domain)
        if dossier is None:
            raise not_found("no dossier for this domain")
        if not dossier.building:
            service.builds.start(dossier)
        response = _handle(dossier)
        remember(store, user_id, "POST", path, key, None, response)
        return json_response(response, 202)

    async def read(self, request: Request) -> Response:
        store = self.service.store
        authenticate(request, store)
        dossier = store.dossiers.get(_path_domain(request.path_params["domain"]))
        if dossier is None:
            raise not_found("no dossier for this domain")
        return json_response(
            {
                **_handle(dossier),
                "researched_at": dossier.researched_at,
                "spent_units": dossier.total_spent,
                "fields": dossier.fields,
            }
        )

    async def listing(self, request: Request) -> Response:
        store = self.service.store
        authenticate(request, store)
        limit = _limit(request)
        offset = _offset(request)
        needle = request.query_params.get("q", "").lower()
        matching = [
            d
            for d in sorted(store.dossiers.values(), key=lambda d: d.domain)
            if needle in d.domain.lower() or needle in (d.fields["legal_name"]["value"] or "").lower()
        ]
        page = matching[offset : offset + limit]
        return json_response(
            {
                "dossiers": [
                    {
                        **_handle(d),
                        "legal_name": d.fields["legal_name"]["value"],
                        "researched_at": d.researched_at,
                        "spent_units": d.total_spent,
                    }
                    for d in page
                ],
                "has_more": offset + limit < len(matching),
            }
        )
