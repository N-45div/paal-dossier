"""Build lifecycle (spec §8): start a build in the background, then apply its outcome."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from app import research
from app.candidates import dedupe
from app.outcome import BuildOutcome, candidates_of
from app.state import Dossier, Store
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
    apply_outcome(dossier, outcome, built_at, spend.total)


def apply_outcome(dossier: Dossier, outcome: BuildOutcome, built_at: datetime,
                  reported: int = 0) -> None:
    """Record a completed build (§8, Rul-4). Spend counts even when the build failed.

    `reported` is what on_spend already added to the dossier; any difference between the
    outcome's total and it is added now, so the dossier ends at the build's net total."""
    dossier.building = False
    dossier.spent_units += outcome.spent_units - reported
    dossier.last_outcome = "ready" if outcome.ok else "failed"
    if outcome.ok:
        gathered = candidates_of(outcome)
        dossier.candidates = {name: dedupe(gathered[name]) for name in FIELDS}
        dossier.researched_at = built_at
