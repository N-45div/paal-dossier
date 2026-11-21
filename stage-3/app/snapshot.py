"""Export and import of the whole service state (spec §10, stage 2 Rul-S2-2).

The exported `state` carries ``schema: "stage3"``: the whole state with build records, history,
the change feed and its next seq (persist.state_json). Import accepts that as it is. Stage-2 and
stage-1 exports are converted by app.imports (one ready build each, the feed starts empty). Import
validates the whole object before it replaces anything, so an invalid object changes nothing."""

from __future__ import annotations

from typing import Any

from aiohttp import web

from app.export_readers import _obj, _text
from app.imports import import_stage1, import_stage2
from app.domain import normalise_domain
from app.errors import json_response, validation_failed
from app.idempotency import MAX_KEY_LENGTH
from app.persist import state_from, state_json
from app.state import STORE, Dossier, IdemRecord, State, Store, User
from app.validation import read_json_object

TRACK = "dossier"
FORMAT_VERSION = 1
STAGE2_SCHEMA = "stage2"
STAGE3_SCHEMA = "stage3"


def export_state(state: State) -> dict[str, Any]:
    """The stage-3 export: the whole state, including build records, history, the change feed
    and its next seq (§10, Upgrades). A running build is not in it."""
    return {"schema": STAGE3_SCHEMA, **state_json(state)}


def import_state(raw: Any) -> State:
    """Build a State from an exported `state` object, or raise 422 with nothing changed.

    Stage-3 exports are loaded as they are. Stage-2 and stage-1 exports go through the
    converters in app.imports, which never touch stage-3 records."""
    if not isinstance(raw, dict):
        raise validation_failed("state must be an object")
    schema = raw.get("schema")
    if schema == STAGE3_SCHEMA:
        try:
            return state_from(raw)
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise validation_failed(f"stage-3 export is malformed: {exc}") from exc
    if schema not in (None, STAGE2_SCHEMA):
        raise validation_failed("unknown export schema")
    state = State()
    _import_users(raw, state)
    _import_tokens(raw, state)
    if schema == STAGE2_SCHEMA:
        _import_dossiers(raw, state, import_stage2)
    else:
        _import_dossiers(raw, state, import_stage1)
    _import_idempotency(raw, state)
    return state


def _list(raw: dict[str, Any], key: str) -> list[Any]:
    value = raw.get(key)
    if not isinstance(value, list):
        raise validation_failed(f"state.{key} must be a list")
    return value


def _import_users(raw: dict[str, Any], state: State) -> None:
    for entry in _list(raw, "users"):
        item = _obj(entry, "user")
        user = User(
            id=_text(item, "id", "user"),
            email=_text(item, "email", "user"),
            display_name=_text(item, "display_name", "user"),
            password_hash=_text(item, "password_hash", "user"),
        )
        if user.id in state.users_by_id or user.email in state.users_by_email:
            raise validation_failed("exported users must have unique ids and emails")
        state.users_by_id[user.id] = user
        state.users_by_email[user.email] = user


def _import_tokens(raw: dict[str, Any], state: State) -> None:
    for entry in _list(raw, "tokens"):
        item = _obj(entry, "token")
        token, user_id = _text(item, "token", "token"), _text(item, "user_id", "token")
        if user_id not in state.users_by_id or token in state.tokens:
            raise validation_failed("token must belong to an exported user and be unique")
        state.tokens[token] = user_id


def _import_dossiers(raw: dict[str, Any], state: State, convert) -> None:
    ids: set[str] = set()
    for entry in _list(raw, "dossiers"):
        item = _obj(entry, "dossier")
        domain = _text(item, "domain", "dossier")
        if normalise_domain(domain) != domain:
            raise validation_failed("dossier domain is not normalised")
        dossier_id = _text(item, "id", "dossier")
        outcome = _text(item, "state", "dossier")
        if outcome not in ("ready", "failed") or domain in state.dossiers_by_domain \
                or dossier_id in ids:
            raise validation_failed("dossier state or identity is invalid")
        ids.add(dossier_id)
        spent = item.get("spent_units")
        if not isinstance(spent, int) or isinstance(spent, bool) or spent < 0:
            raise validation_failed("dossier spent_units must be a non-negative integer")
        # The exported dossier's build records (Rul-S3-8): see app.imports.
        records = list(convert(item, domain))
        state.dossiers_by_domain[domain] = Dossier(
            id=dossier_id,
            domain=domain,
            last_outcome=outcome,
            records=records,
            spent_units=spent,
        )


def _import_idempotency(raw: dict[str, Any], state: State) -> None:
    for entry in _list(raw, "idempotency"):
        item = _obj(entry, "idempotency record")
        user_id = _text(item, "user_id", "idempotency record")
        key = _text(item, "key", "idempotency record")
        if user_id not in state.users_by_id or len(key) > MAX_KEY_LENGTH:
            raise validation_failed("idempotency record must belong to an exported user")
        body = item.get("body")
        if not isinstance(body, dict):
            raise validation_failed("idempotency record body must be an object")
        slot = (user_id, key, _text(item, "method", "idempotency record"),
                _text(item, "path", "idempotency record"))
        if slot in state.idempotency:
            raise validation_failed("idempotency records must be unique")
        state.idempotency[slot] = IdemRecord(canonical=item.get("canonical"), body=body)


async def export(request: web.Request) -> web.Response:
    store: Store = request.app[STORE]
    return json_response({
        "track": TRACK,
        "format_version": FORMAT_VERSION,
        "state": export_state(store.state),
    })


async def import_(request: web.Request) -> web.Response:
    store: Store = request.app[STORE]
    body = await read_json_object(request)
    if body.get("track") != TRACK:
        raise validation_failed("export track must be dossier")
    version = body.get("format_version")
    if not isinstance(version, int) or isinstance(version, bool) or version != FORMAT_VERSION:
        raise validation_failed("unsupported export format_version")
    if "state" not in body:
        raise validation_failed("export state is missing")
    new_state = import_state(body["state"])
    store.replace(new_state)  # all-or-nothing: nothing above touched the current state
    return web.Response(status=204)
