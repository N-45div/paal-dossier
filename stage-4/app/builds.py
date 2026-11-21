"""Build lifecycle (spec §8): start a build in the background, then apply its outcome."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from app import research
from app.candidates import dedupe
from app.feed import append_build
from app.history import feed_entries
from app.outcome import BuildOutcome, candidates_of
from app.records import BuildRecord, versions_of
from app.state import Dossier, State, Store
from app.support import FIELDS

log = logging.getLogger("dossier.builds")


class _BuildSpend:
    """Units this build has reported through on_spend, net of releases."""

    def __init__(self) -> None:
        self.total = 0


def start_build(store: Store, dossier: Dossier, built_at: datetime) -> None:
    """Mark the dossier building and run its build as a background task.

    `built_at` is the clock time of the request that started the build (§8)."""
    dossier.building = True
    spend = _BuildSpend()
    task = asyncio.create_task(
        _run(store, dossier, store.state.generation, built_at, spend))
    store.build_tasks.add(task)
    task.add_done_callback(store.build_tasks.discard)


async def _run(store: Store, dossier: Dossier, generation: int, built_at: datetime,
               spend: _BuildSpend) -> None:
    def on_spend(units: int) -> None:
        # Live counter (Rul-11): a reservation moves the dossier total at once. A state
        # replaced by reset or import no longer owns this build, so it is not counted.
        if store.state.generation != generation:
            return
        spend.total += units
        dossier.spent_units += units

    try:
        outcome = await research.run_build(dossier.domain, on_spend)
    except asyncio.CancelledError:
        # Cancelled by a reset or import: that state no longer exists, so nothing is applied.
        raise
    except Exception:
        log.exception("build failed for %s", dossier.domain)
        # Calls already reserved still count, so the failed outcome carries what was spent.
        outcome = BuildOutcome(ok=False, spent_units=spend.total,
                               fields=research.unknown_fields())
    if store.state.generation != generation:
        return  # a reset or import replaced this state while the build ran
    apply_outcome(store.state, dossier, outcome, built_at, spend.total)
    store.save()


def apply_outcome(state: State, dossier: Dossier, outcome: BuildOutcome, built_at: datetime,
                  reported: int = 0) -> None:
    """Record a completed build (§8, Rul-4, Rul-S3-1). Spend counts even when the build failed.

    The build's record is appended, and its feed entries are appended in the same synchronous
    step (Rul-S3-4). `reported` is what on_spend already added to the dossier; any difference
    between the outcome's total and it is added now, so the dossier ends at the build's net
    total."""
    dossier.building = False
    dossier.spent_units += outcome.spent_units - reported
    dossier.last_outcome = "ready" if outcome.ok else "failed"
    previous = dossier.current_view()
    if outcome.ok:
        versions = versions_of(_gathered(outcome), pages=outcome.pages)
        record = BuildRecord(index=len(dossier.records), time=built_at, ok=True,
                             spent_units=outcome.spent_units, versions=versions)
    else:
        record = BuildRecord(index=len(dossier.records), time=built_at, ok=False,
                             spent_units=outcome.spent_units)
    dossier.records.append(record)
    if outcome.ok:
        current = dossier.current_view()
        entries = feed_entries(previous[1] if previous else None, current[1],
                               first=previous is None, built_at=built_at)
        state.next_seq = append_build(state.feed, state.next_seq, dossier.domain, entries)


def _gathered(outcome: BuildOutcome) -> dict[str, list]:
    gathered = {name: dedupe(found) for name, found in candidates_of(outcome).items()}
    executives = (outcome.candidates or {}).get("executives", [])
    gathered["executives"] = dedupe(executives)
    gathered["investors"] = dedupe((outcome.candidates or {}).get("investors", []))
    return gathered
