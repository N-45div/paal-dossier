"""`POST /batches` and `GET /batches/{id}` (stage 4, R4C, R4.42-R4.56).

A batch researches several companies under one shared budget. A domain with no dossier gets
one and its first build runs under the batch's budget; a domain that already has a dossier is
not researched and costs nothing. A batch belongs to its creator: another user's batch is
404 `not_found`.
"""

from __future__ import annotations

import secrets

from aiohttp import web

from app.auth import authenticate
from app.budget import SharedBudget
from app.builds import start_build
from app.domain import normalise_domain
from app.errors import json_response, not_found, validation_failed
from app.idempotency import check_key_length, read_key, run_idempotent
from app.state import STORE, Batch, Dossier, Store
from app.validation import read_json_object

MAX_DOMAINS = 50
MIN_BUDGET_UNITS = 1
MAX_BUDGET_UNITS = 100_000


def _domains(body: dict) -> list[str]:
    """The normalised domains in the order given. Missing, empty, over 50, an invalid entry or
    a repeated domain after normalisation are all 422 validation_failed (R4.47-R4.49)."""
    if "domains" not in body or not isinstance(body["domains"], list):
        raise validation_failed("domains must be a list")
    raw = body["domains"]
    if not raw or len(raw) > MAX_DOMAINS:
        raise validation_failed("domains must hold between 1 and 50 entries")
    domains: list[str] = []
    for item in raw:
        domain = normalise_domain(item) if isinstance(item, str) else None
        if domain is None:
            raise validation_failed("a domains entry is not a valid host name")
        if domain in domains:
            raise validation_failed("domains must be distinct after normalisation")
        domains.append(domain)
    return domains


def _budget(body: dict) -> int:
    """`budget_units` as an integer from 1 to 100000. Any other JSON type is 422 (R4.50-R4.51)."""
    value = body.get("budget_units")
    if isinstance(value, bool) or not isinstance(value, int):
        raise validation_failed("budget_units must be an integer")
    if not MIN_BUDGET_UNITS <= value <= MAX_BUDGET_UNITS:
        raise validation_failed("budget_units is out of range")
    return value


def batch_json(store: Store, batch: Batch) -> dict:
    """The batch as §R4.46 shows it: its state, budget, spend and each dossier's state."""
    running = any(store.state.dossiers_by_domain[d].building for d in batch.started)
    return {
        "batch_id": batch.id,
        "state": "running" if running else "done",
        "budget_units": batch.budget.limit,
        "spent_units": batch.budget.spent,
        "dossiers": [{"domain": d, "state": store.state.dossiers_by_domain[d].live_state}
                     for d in batch.domains],
    }


def _store(request: web.Request) -> Store:
    return request.app[STORE]


async def create(request: web.Request) -> web.Response:
    store = _store(request)
    user = authenticate(request, store)
    key = read_key(request)
    body = await read_json_object(request)
    check_key_length(key)
    canonical = {"domains": body.get("domains"), "budget_units": body.get("budget_units")}

    def effect() -> tuple[int, dict]:
        domains = _domains(body)
        budget = _budget(body)
        token = secrets.token_hex(8)
        batch = Batch(id="b_" + token, user_id=user.id, budget=SharedBudget(budget), domains=domains)
        store.state.batches[batch.id] = batch
        for domain in domains:
            dossier = store.state.dossiers_by_domain.get(domain)
            if dossier is None:
                dossier = Dossier(id="d_" + secrets.token_hex(8), domain=domain)
                store.state.dossiers_by_domain[domain] = dossier
                start_build(store, dossier, store.clock.now(), batch.budget)
                batch.started.append(domain)
        store.save()
        return 202, batch_json(store, batch)

    return run_idempotent(store, user, key, "POST", "/batches", canonical, effect)


async def get_one(request: web.Request) -> web.Response:
    store = _store(request)
    user = authenticate(request, store)
    batch = store.state.batches.get(request.match_info["batch_id"])
    if batch is None or batch.user_id != user.id:
        raise not_found("no batch with this id")
    return json_response(batch_json(store, batch))
