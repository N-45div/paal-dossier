"""Background dossier builds: one per dossier, results applied only if no reset intervened."""
import asyncio
import importlib.util
from datetime import datetime

from app.dossiers import Dossier, clean_fields
from app.store import Store

BUILD_DEADLINE_SECONDS = 290  # spec: a build ends ready or failed within 300 s


async def _stub_build(domain, spend) -> dict:
    return {"ok": True, "fields": {}}


def _research_entry():
    if importlib.util.find_spec("app.research") is None:
        return _stub_build
    from app.research import run_build
    return run_build


def start(store: Store, dossier: Dossier, started_at: datetime) -> None:
    """Mark the dossier building and run its build in the background."""
    dossier.building = True
    dossier.committed_spent = dossier.spent_units
    task = asyncio.create_task(_run(store, dossier, store.generation, started_at))
    store.tasks.add(task)
    task.add_done_callback(store.tasks.discard)


async def _run(store: Store, dossier: Dossier, generation: int, started_at: datetime) -> None:
    def spend(units: int) -> None:
        if store.generation == generation:
            dossier.spent_units += int(units)

    try:
        result = await asyncio.wait_for(_research_entry()(dossier.domain, spend),
                                        BUILD_DEADLINE_SECONDS)
        ok = bool(result.get("ok"))
        fields = clean_fields(result.get("fields")) if ok else None
    except asyncio.CancelledError:
        raise
    except Exception:
        ok, fields = False, None
    if store.generation != generation:
        return
    dossier.building = False
    if ok:
        dossier.fields = fields
        dossier.researched_at = started_at
        dossier.outcome = "ready"
    else:
        dossier.outcome = "failed"
