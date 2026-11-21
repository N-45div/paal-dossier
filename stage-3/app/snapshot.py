"""Export and import of the whole service state (spec §10, stage 2 Rul-S2-2).

The exported `state` carries ``schema: "stage2"`` and each dossier's candidates. Import also
accepts a stage-1 export, which has no schema marker and records only the selected fields
with their citations; each verified citation becomes one imported candidate. Import validates
the whole object before it replaces anything, so an invalid object changes nothing."""

from __future__ import annotations

from typing import Any

from aiohttp import web

from app.records import BuildRecord, versions_of
from app.candidates import KINDS, PROVIDERS, Candidate, dedupe, from_citation
from app.clock import parse_rfc3339
from app.domain import normalise_domain
from app.errors import json_response, validation_failed
from app.idempotency import MAX_KEY_LENGTH
from app.state import STORE, Dossier, IdemRecord, State, Store, User
from app.support import FIELDS, supported_values
from app.validation import read_json_object

TRACK = "dossier"
FORMAT_VERSION = 1
SCHEMA = "stage2"


def export_state(state: State) -> dict[str, Any]:
    """A snapshot of the state as of this instant. A running build is not in it: a dossier
    exports the outcome and candidates of its last completed build (§10)."""
    return {
        "schema": SCHEMA,
        "users": [
            {"id": user.id, "email": user.email, "display_name": user.display_name,
             "password_hash": user.password_hash}
            for user in state.users_by_id.values()
        ],
        "tokens": [{"token": token, "user_id": user_id}
                   for token, user_id in state.tokens.items()],
        "dossiers": [_export_dossier(dossier) for dossier in state.dossiers_by_domain.values()],
        "idempotency": [
            {"user_id": slot[0], "key": slot[1], "method": slot[2], "path": slot[3],
             "canonical": record.canonical, "body": record.body}
            for slot, record in state.idempotency.items()
        ],
    }


def _export_candidate(candidate: Candidate) -> dict[str, Any]:
    return {"value": candidate.value, "url": candidate.url, "excerpt": candidate.excerpt,
            "provider": candidate.provider, "kind": candidate.kind,
            "published_at": candidate.published_at}


def _export_dossier(dossier: Dossier) -> dict[str, Any]:
    return {
        "id": dossier.id,
        "domain": dossier.domain,
        "state": dossier.last_outcome,
        "researched_at": dossier.researched_at.isoformat() if dossier.researched_at else None,
        "spent_units": dossier.spent_units,
        "candidates": {
            name: [_export_candidate(c) for c in dossier.candidates.get(name, [])]
            for name in FIELDS
        },
    }


def import_state(raw: Any) -> State:
    """Build a State from an exported `state` object, or raise 422 with nothing changed."""
    if not isinstance(raw, dict):
        raise validation_failed("state must be an object")
    schema = raw.get("schema")
    if schema not in (None, SCHEMA):
        raise validation_failed("unknown export schema")
    state = State()
    _import_users(raw, state)
    _import_tokens(raw, state)
    if schema == SCHEMA:
        _import_dossiers(raw, state, _stage2_candidates)
    else:
        _import_dossiers(raw, state, _stage1_candidates)
    _import_idempotency(raw, state)
    return state


def _list(raw: dict[str, Any], key: str) -> list[Any]:
    value = raw.get(key)
    if not isinstance(value, list):
        raise validation_failed(f"state.{key} must be a list")
    return value


def _obj(entry: Any, what: str) -> dict[str, Any]:
    if not isinstance(entry, dict):
        raise validation_failed(f"{what} must be an object")
    return entry


def _text(entry: dict[str, Any], key: str, what: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or value == "":
        raise validation_failed(f"{what}.{key} must be a non-empty string")
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


def _import_dossiers(raw: dict[str, Any], state: State, candidates_of) -> None:
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
        researched = item.get("researched_at")
        records: list[BuildRecord] = []
        if researched is not None:
            # The exported state is one ready build at researched_at (Upgrades, stage 3).
            found = {name: dedupe(items) for name, items in candidates_of(item, domain).items()}
            records.append(BuildRecord(
                index=0, time=parse_rfc3339(researched), ok=True, spent_units=spent,
                versions=versions_of(found, pages={}),
            ))
        state.dossiers_by_domain[domain] = Dossier(
            id=dossier_id,
            domain=domain,
            last_outcome=outcome,
            records=records,
            spent_units=spent,
        )


def _stage2_candidates(item: dict[str, Any], domain: str) -> dict[str, list[Candidate]]:
    """Candidates of a stage-2 export, validated field by field."""
    raw = _obj(item.get("candidates"), "dossier candidates")
    result: dict[str, list[Candidate]] = {}
    for name in FIELDS:
        entries = raw.get(name)
        if not isinstance(entries, list):
            raise validation_failed(f"candidates of {name} must be a list")
        result[name] = [_stage2_candidate(_obj(e, "candidate")) for e in entries]
    return result


def _stage2_candidate(item: dict[str, Any]) -> Candidate:
    value = item.get("value")
    if isinstance(value, bool) or not isinstance(value, (int, str)) or value == "":
        raise validation_failed("candidate value must be a non-empty string or an integer")
    kind = item.get("kind")
    if kind is not None and kind not in KINDS:
        raise validation_failed("candidate kind is not a known page kind")
    provider = _text(item, "provider", "candidate")
    if provider not in PROVIDERS:
        raise validation_failed("candidate provider is not known")
    published = item.get("published_at")
    if published is not None:
        parse_rfc3339(_text(item, "published_at", "candidate"))
    return Candidate(value=value, url=_text(item, "url", "candidate"),
                     excerpt=_text(item, "excerpt", "candidate"), provider=provider,
                     kind=kind, published_at=published)


def _stage1_candidates(item: dict[str, Any], domain: str) -> dict[str, list[Candidate]]:
    """Candidates of a stage-1 export (Rul-S2-2): one per verified citation of each field."""
    fields = _obj(item.get("fields"), "dossier fields")
    result: dict[str, list[Candidate]] = {}
    for name in FIELDS:
        entry = _obj(fields.get(name), f"field {name}")
        value = entry.get("value")
        if value is not None and (isinstance(value, bool) or not isinstance(value, (str, int))):
            raise validation_failed(f"field {name} has an invalid value")
        citations = entry.get("citations")
        if not isinstance(citations, list):
            raise validation_failed(f"field {name} citations must be a list")
        cands: list[Candidate] = []
        for citation in citations:
            cite = _obj(citation, "citation")
            for key in ("url", "excerpt", "provider"):
                _text(cite, key, "citation")
            if value is None:
                continue
            # A stage-1 citation was verified when it was written; keep it only while it
            # still supports the field's value under Appendix A.
            if supported_values(domain, cite["excerpt"]).get(name) == value:
                cands.append(from_citation(value, cite))
        result[name] = cands
    return result


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
