"""Build lifecycle (spec §8): start a build in the background, then apply its outcome."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from app import research
from app.research import BuildOutcome
from app.state import Dossier, Store

log = logging.getLogger("dossier.builds")


def start_build(store: Store, dossier: Dossier, built_at: datetime) -> None:
    """Mark the dossier building and run its build as a background task.

    `built_at` is the clock time of the request that started the build (§8)."""
    dossier.building = True
    task = asyncio.create_task(_run(store, dossier, store.state.generation, built_at))
    store.build_tasks.add(task)
    task.add_done_callback(store.build_tasks.discard)


async def _run(store: Store, dossier: Dossier, generation: int, built_at: datetime) -> None:
    try:
        outcome = await research.run_build(dossier.domain)
    except asyncio.CancelledError:
        # Cancelled by a reset or import: that state no longer exists, so nothing is applied.
        raise
    except Exception:
        log.exception("build failed for %s", dossier.domain)
        outcome = BuildOutcome(ok=False, spent_units=0, fields=research.unknown_fields())
    if store.state.generation != generation:
        return  # a reset or import replaced this state while the build ran
    apply_outcome(dossier, outcome, built_at)


def apply_outcome(dossier: Dossier, outcome: BuildOutcome, built_at: datetime) -> None:
    """Record a completed build (§8, Rul-4). Spend counts even when the build failed."""
    dossier.building = False
    dossier.spent_units += outcome.spent_units
    dossier.last_outcome = "ready" if outcome.ok else "failed"
    if outcome.ok:
        dossier.fields = dict(outcome.fields)
        dossier.researched_at = built_at
