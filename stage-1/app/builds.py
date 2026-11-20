"""Build lifecycle (spec §8, §9): one build per dossier at a time, applied only if no reset or
import happened while it ran.
"""

from __future__ import annotations

import sys
import threading
import traceback
from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace
from typing import Any

from .context import App
from .dossier_model import Dossier, fields_from_outcome
from .research_port import run_build
from .store import Store


@dataclass(frozen=True)
class BuildJob:
    dossier_id: str
    domain: str
    requested_at: datetime  # the clock when the request that started the build was received
    generation: int  # store generation when the build started


def start_build(app: App, dossier: Dossier, requested_at: datetime) -> None:
    """Mark `dossier` building and run its build on a worker thread. Caller holds store.lock."""
    dossier.building = True
    job = BuildJob(
        dossier_id=dossier.dossier_id,
        domain=dossier.domain,
        requested_at=requested_at,
        generation=app.store.generation,
    )
    threading.Thread(
        target=_run, args=(app.store, job), name=f"build-{job.dossier_id}", daemon=True
    ).start()


def _run(store: Store, job: BuildJob) -> None:
    try:
        outcome: Any = run_build(job.domain)
    except Exception:
        traceback.print_exc(file=sys.stderr)
        outcome = SimpleNamespace(ok=False, fields={}, spent_units=0)
    apply_outcome(store, job, outcome)


def apply_outcome(store: Store, job: BuildJob, outcome: Any) -> None:
    with store.lock:
        if store.generation != job.generation:
            return  # a reset or import happened while this build ran; its result is discarded
        dossier = store.dossier_by_id(job.dossier_id)
        if dossier is None:
            return
        dossier.building = False
        dossier.spent_units += int(outcome.spent_units)
        if outcome.ok:
            dossier.committed_state = "ready"
            dossier.researched_at = job.requested_at
            dossier.fields = fields_from_outcome(outcome.fields)
        else:
            dossier.committed_state = "failed"
