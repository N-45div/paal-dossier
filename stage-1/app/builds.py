"""Background dossier builds.

Each `run_build` executes in a worker thread with its own event loop, so blocking
provider calls and CPU-heavy text analysis cannot stall request handling. Everything
that touches service state (spend, the final write) hops back to the main loop and is
applied only if no reset or import happened since the build started.
"""
import asyncio
import importlib.util
import inspect
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from app.dossiers import Dossier, clean_fields
from app.store import Store

BUILD_DEADLINE_SECONDS = 290  # spec: a build ends ready or failed within 300 s
MAX_PARALLEL_BUILDS = 32

_pool = ThreadPoolExecutor(max_workers=MAX_PARALLEL_BUILDS, thread_name_prefix="build")


class BuildCancelled(BaseException):
    """Raised by `spend` once a reset or import made the build obsolete.

    A BaseException so research code that catches Exception cannot swallow it.
    """


async def _stub_build(domain, spend) -> dict:
    return {"ok": True, "fields": {}}


def _research_entry():
    if importlib.util.find_spec("app.research") is None:
        return _stub_build
    from app.research import run_build
    return run_build


def _run_in_worker(domain: str, spend) -> dict:
    """Worker-thread body: own event loop; run_build may be async or blocking."""
    async def main():
        result = _research_entry()(domain, spend)
        return await result if inspect.isawaitable(result) else result

    return asyncio.run(asyncio.wait_for(main(), BUILD_DEADLINE_SECONDS))


def start(store: Store, dossier: Dossier, started_at: datetime) -> None:
    """Mark the dossier building and run its build in the background."""
    dossier.building = True
    dossier.committed_spent = dossier.spent_units
    task = asyncio.create_task(_run(store, dossier, store.generation, started_at))
    store.tasks.add(task)
    task.add_done_callback(store.tasks.discard)


async def _run(store: Store, dossier: Dossier, generation: int, started_at: datetime) -> None:
    loop = asyncio.get_running_loop()

    def add_spend(units: int) -> None:  # main loop
        if store.generation == generation:
            dossier.spent_units += units

    def spend(units: int) -> None:  # worker thread
        if store.generation != generation:
            raise BuildCancelled()
        loop.call_soon_threadsafe(add_spend, int(units))

    try:
        result = await loop.run_in_executor(_pool, _run_in_worker, dossier.domain, spend)
        ok = bool(result.get("ok"))
        fields = clean_fields(result.get("fields")) if ok else None
    except asyncio.CancelledError:
        raise
    except (Exception, BuildCancelled):
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
