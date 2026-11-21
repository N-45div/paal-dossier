"""Durable state (stage 3, Rul-S3-2): one versioned JSON document on the container filesystem.

Every acknowledged change is written before its response is sent: the state is serialised,
written to a temporary file, fsynced, renamed over the document, and the directory fsynced.
A dossier left `building` by an abrupt stop becomes `failed` on load, with no history or feed
entry (Rul-S3-2). The format is versioned so a later version can read it."""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

from app.candidates import Candidate
from app.feed import FeedRow
from app.records import BuildRecord, PageVersion
from app.budget import SharedBudget
from app.state import Batch, Dossier, IdemRecord, State, User

FORMAT = "dossier-state"
VERSION = 1


def _when(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _day(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _candidate_json(c: Candidate) -> dict[str, Any]:
    return {"value": c.value, "url": c.url, "excerpt": c.excerpt, "provider": c.provider,
            "kind": c.kind, "published_at": c.published_at, "title": c.title,
            "true_from": _day(c.true_from), "origin": c.origin}


def _candidate(raw: dict[str, Any]) -> Candidate:
    return Candidate(value=raw["value"], url=raw["url"], excerpt=raw["excerpt"],
                     provider=raw["provider"], kind=raw["kind"],
                     published_at=raw["published_at"], title=raw["title"],
                     true_from=date.fromisoformat(raw["true_from"]) if raw["true_from"] else None,
                     origin=raw.get("origin"))


def _record_json(record: BuildRecord) -> dict[str, Any]:
    return {
        "index": record.index, "time": _when(record.time), "ok": record.ok,
        "spent_units": record.spent_units,
        "versions": [
            {"url": v.url, "true_from": _day(v.true_from), "origin": v.origin,
             "candidates": {name: [_candidate_json(c) for c in found]
                            for name, found in v.candidates.items()}}
            for v in record.versions
        ],
    }


def _record(raw: dict[str, Any]) -> BuildRecord:
    versions = tuple(
        PageVersion(
            url=v["url"],
            true_from=date.fromisoformat(v["true_from"]) if v["true_from"] else None,
            candidates={name: tuple(_candidate(c) for c in found)
                        for name, found in v["candidates"].items()},
            origin=v.get("origin"),
        )
        for v in raw["versions"]
    )
    return BuildRecord(index=raw["index"], time=datetime.fromisoformat(raw["time"]),
                       ok=raw["ok"], spent_units=raw["spent_units"], versions=versions)


def dossier_json(d: Dossier, *, exporting: bool = False) -> dict[str, Any]:
    """A dossier as JSON. The durable document keeps the running flag, so a build cut short by a
    stop loads as failed (Rul-S3-2). An export holds the state before the running build: it is
    not building, and its last_outcome is that of the last completed build (Rul-7)."""
    return {"id": d.id, "domain": d.domain, "last_outcome": d.last_outcome,
            "building": False if exporting else d.building, "spent_units": d.spent_units,
            "records": [_record_json(r) for r in d.records]}


def dossier_from(raw: dict[str, Any]) -> Dossier:
    """A dossier from its JSON. A build recorded as running is loaded as failed (Rul-S3-2)."""
    was_building = raw["building"]
    return Dossier(
        id=raw["id"], domain=raw["domain"], building=False,
        last_outcome="failed" if was_building else raw["last_outcome"],
        records=[_record(r) for r in raw["records"]], spent_units=raw["spent_units"],
    )


def feed_json(rows: list[FeedRow]) -> list[dict[str, Any]]:
    return [{"seq": r.seq, "domain": r.domain, "field": r.field, "type": r.type,
             "previous": r.previous, "value": r.value, "true_from": _day(r.true_from),
             "learned_at": _when(r.learned_at)} for r in rows]


def feed_from(raw: list[dict[str, Any]]) -> list[FeedRow]:
    return [
        FeedRow(seq=f["seq"], domain=f["domain"], field=f["field"], type=f["type"],
                previous=f["previous"], value=f["value"],
                true_from=date.fromisoformat(f["true_from"]) if f["true_from"] else None,
                learned_at=datetime.fromisoformat(f["learned_at"]) if f["learned_at"] else None)
        for f in raw
    ]


def state_json(state: State, *, exporting: bool = False) -> dict[str, Any]:
    """The whole state as JSON, without a format header: the body of the stage-3 export and of
    the durable document. Dossiers are in build order; the feed is in seq order."""
    return {
        "next_seq": state.next_seq,
        "users": [{"id": u.id, "email": u.email, "display_name": u.display_name,
                   "password_hash": u.password_hash} for u in state.users_by_id.values()],
        "tokens": dict(state.tokens),
        "dossiers": [dossier_json(d, exporting=exporting)
                     for d in state.dossiers_by_domain.values()],
        "idempotency": [
            {"user_id": k[0], "key": k[1], "method": k[2], "path": k[3],
             "canonical": rec.canonical, "body": rec.body}
            for k, rec in state.idempotency.items()
        ],
        "feed": feed_json(state.feed),
        "batches": [
            {"id": b.id, "user_id": b.user_id, "budget_units": b.budget.limit,
             "spent_units": b.budget.spent, "domains": list(b.domains), "started": list(b.started)}
            for b in state.batches.values()
        ],
    }


def state_from(raw: dict[str, Any]) -> State:
    """A State from `state_json` output. Raises KeyError, TypeError or ValueError on bad input."""
    state = State()
    state.next_seq = raw["next_seq"]
    for u in raw["users"]:
        user = User(id=u["id"], email=u["email"], display_name=u["display_name"],
                    password_hash=u["password_hash"])
        state.users_by_id[user.id] = user
        state.users_by_email[user.email] = user
    state.tokens = dict(raw["tokens"])
    for d in raw["dossiers"]:
        dossier = dossier_from(d)
        state.dossiers_by_domain[dossier.domain] = dossier
    for i in raw["idempotency"]:
        state.idempotency[(i["user_id"], i["key"], i["method"], i["path"])] = IdemRecord(
            canonical=i["canonical"], body=i["body"])
    state.feed = feed_from(raw["feed"])
    for b in raw.get("batches", []):
        batch = Batch(id=b["id"], user_id=b["user_id"],
                      budget=SharedBudget(b["budget_units"], b["spent_units"]),
                      domains=list(b["domains"]), started=list(b["started"]))
        state.batches[batch.id] = batch
    return state


def dump(state: State, clock_fixed: datetime | None) -> dict[str, Any]:
    return {"format": FORMAT, "version": VERSION, "clock": _when(clock_fixed),
            **state_json(state)}


def load(raw: dict[str, Any]) -> tuple[State, datetime | None]:
    if raw.get("format") != FORMAT or raw.get("version") != VERSION:
        raise ValueError("unsupported state document")
    clock = datetime.fromisoformat(raw["clock"]) if raw["clock"] else None
    return state_from(raw), clock


class Persister:
    """Writes the whole state to one file, atomically and durably."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def exists(self) -> bool:
        return self.path.exists()

    def read(self) -> dict[str, Any]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, state: State, clock_fixed: datetime | None) -> None:
        payload = json.dumps(dump(state, clock_fixed), ensure_ascii=False, sort_keys=True)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + ".tmp")
        with open(temporary, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.path)
        directory = os.open(self.path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
