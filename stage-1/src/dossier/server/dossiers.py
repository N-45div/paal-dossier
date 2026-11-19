"""The dossier endpoints (spec 8): create, refresh, read and list."""

import secrets
from urllib.parse import unquote

from dossier.server import builds, views
from dossier.server.errors import not_found
from dossier.server.fields import parse_object, read_fields
from dossier.server.domains import require_domain
from dossier.server.idempotency import canonical, check_key_length, require_key_present, run_idempotent
from dossier.server.query import integer_param
from dossier.server.request import require_current
from dossier.server.model import Dossier
from dossier.server.request import Request
from dossier.server.service import Service


def post_dossiers(service: Service, request: Request) -> tuple[int, dict]:
    key = require_key_present(request)
    body = parse_object(request.body)
    check_key_length(key)
    claimed = {"domain": body["domain"]} if "domain" in body else {}
    return run_idempotent(
        service.store, request, key, canonical(claimed), lambda: _create(service, body, request)
    )


def post_refresh(service: Service, request: Request) -> tuple[int, dict]:
    key = require_key_present(request)
    check_key_length(key)
    raw_domain = request.params["domain"]
    return run_idempotent(
        service.store, request, key, "", lambda: _refresh(service, raw_domain, request)
    )


def get_dossier(service: Service, request: Request) -> tuple[int, dict]:
    domain = require_domain(unquote(request.params["domain"]))
    with service.store.lock:
        require_current(service.store, request)
        dossier = service.store.dossiers.get(domain)
        if dossier is None:
            raise not_found("no dossier for this domain")
        return 200, views.dossier_view(dossier)


def list_dossiers(service: Service, request: Request) -> tuple[int, dict]:
    query = request.query.get("q")
    limit = integer_param(request.query.get("limit"), 50, 1, 200)
    offset = integer_param(request.query.get("offset"), 0, 0, None)
    needle = (query or "").lower()
    with service.store.lock:
        require_current(service.store, request)
        matching = [
            dossier
            for dossier in sorted(service.store.dossiers.values(), key=lambda d: d.domain)
            if _matches(dossier, needle)
        ]
        page = matching[offset : offset + limit]
        rows = [views.list_row(dossier) for dossier in page]
    return 200, {"dossiers": rows, "has_more": len(matching) > offset + limit}


def _create(service: Service, body: dict, request: Request) -> tuple[int, dict]:
    fields = read_fields(body, {"domain": str})
    domain = require_domain(fields["domain"])
    with service.store.lock:
        require_current(service.store, request)
        existing = service.store.dossiers.get(domain)
        if existing is not None:
            return 200, views.dossier_ref(existing)
        dossier = Dossier(dossier_id=_new_dossier_id(service), domain=domain)
        service.store.dossiers[domain] = dossier
        builds.start_build(service, dossier)
        return 202, views.dossier_ref(dossier)


def _refresh(service: Service, raw_domain: str, request: Request) -> tuple[int, dict]:
    domain = require_domain(unquote(raw_domain))
    with service.store.lock:
        require_current(service.store, request)
        dossier = service.store.dossiers.get(domain)
        if dossier is None:
            raise not_found("no dossier for this domain")
        if dossier.build is None:
            builds.start_build(service, dossier)
        return 202, views.dossier_ref(dossier)


def _matches(dossier: Dossier, needle: str) -> bool:
    if not needle:
        return True
    legal_name = dossier.fields["legal_name"].value
    return needle in dossier.domain or (isinstance(legal_name, str) and needle in legal_name.lower())


def _new_dossier_id(service: Service) -> str:
    taken = {d.dossier_id for d in service.store.dossiers.values()}
    while True:
        candidate = "d_" + secrets.token_hex(6)
        if candidate not in taken:
            return candidate
