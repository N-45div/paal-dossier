"""Export and import of the whole service state (§10); format is versioned."""
from app.clock import parse_timestamp, render
from app.dossiers import FIELD_NAMES, Dossier, clean_fields
from app.errors import invalid
from app.idempotency import Record
from app.store import State, User

TRACK = "dossier"
FORMAT_VERSION = 1


def export_state(state: State) -> dict:
    """A detached snapshot; a running build shows as its pre-build dossier."""
    dossiers = []
    for d in state.dossiers.values():
        dossiers.append({
            "dossier_id": d.dossier_id, "domain": d.domain, "fields": d.fields,
            "researched_at": render(d.researched_at) if d.researched_at else None,
            "spent_units": d.committed_spent if d.building else d.spent_units,
            "outcome": d.outcome or "failed"})
    return {"track": TRACK, "format_version": FORMAT_VERSION, "state": {
        "users": [{"id": u.user_id, "email": u.email, "display_name": u.display_name,
                   "password_hash": u.password_hash} for u in state.users.values()],
        "tokens": dict(state.tokens),
        "dossiers": dossiers,
        "idempotency": [{"user_id": k[0], "method": k[1], "path": k[2], "key": k[3],
                         "signature": list(r.signature) if r.signature is not None else None,
                         "body": r.body} for k, r in state.idempotency.items()],
    }}


def _check(condition: bool) -> None:
    if not condition:
        raise invalid("state is invalid")


def _int(value) -> int:
    _check(isinstance(value, int) and not isinstance(value, bool) and value >= 0)
    return value


def _text(value) -> str:
    _check(isinstance(value, str))
    return value


def build_state(payload: dict, clock) -> State:
    """A fresh State from an export payload, or 422 validation_failed."""
    _check(payload.get("track") == TRACK)
    version = payload.get("format_version")
    _check(isinstance(version, int) and not isinstance(version, bool) and version == FORMAT_VERSION)
    raw = payload.get("state")
    _check(isinstance(raw, dict))
    state = State(clock=clock)
    try:
        for u in raw["users"]:
            state.add_user(User(_text(u["id"]), _text(u["email"]), _text(u["display_name"]),
                                _text(u["password_hash"])))
        _check(isinstance(raw["tokens"], dict))
        for token, user_id in raw["tokens"].items():
            _check(user_id in state.users)
            state.tokens[token] = user_id
        for d in raw["dossiers"]:
            _check(d["outcome"] in ("ready", "failed"))
            _check(isinstance(d["fields"], dict) and set(d["fields"]) == set(FIELD_NAMES))
            at = d["researched_at"]
            dossier = Dossier(_text(d["dossier_id"]), _text(d["domain"]),
                              clean_fields(d["fields"]),
                              parse_timestamp(at) if at is not None else None,
                              _int(d["spent_units"]), _int(d["spent_units"]), d["outcome"])
            state.dossiers[dossier.domain] = dossier
        for r in raw["idempotency"]:
            sig = r["signature"]
            _check(sig is None or isinstance(sig, list))
            _check(isinstance(r["body"], dict))
            scope = (_text(r["user_id"]), _text(r["method"]), _text(r["path"]), _text(r["key"]))
            state.idempotency[scope] = Record(tuple(sig) if sig is not None else None, r["body"])
    except (KeyError, TypeError, AttributeError):
        raise invalid("state is invalid")
    return state
