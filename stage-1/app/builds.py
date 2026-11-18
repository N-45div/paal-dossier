"""Background dossier builds.

Every `run_build` runs on one dedicated engine event loop in its own thread, so
blocking provider calls and CPU-heavy text analysis cannot stall request handling,
and the research engine's per-loop HTTP client and in-flight limiter are shared by
all builds (no connection or socket is created per build). Everything that touches
service state (spend, the final write) hops back to the main loop and is applied
only if no reset or import happened since the build started.
"""
import asyncio
import threading
from datetime import datetime

from app.dossiers import Dossier, clean_fields
from app.research import run_build
from app.store import Store

BUILD_DEADLINE_SECONDS = 290  # spec: a build ends ready or failed within 300 s


class BuildCancelled(BaseException):
    """Raised by `spend` once a reset or import made the build obsolete.

    A BaseException so research code that catches Exception cannot swallow it.
    """


class _EngineLoop:
    """A background thread running one event loop for all builds."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def loop(self) -> asyncio.AbstractEventLoop:
        with self._lock:
            if self._loop is None:
                loop = asyncio.new_event_loop()
                threading.Thread(target=loop.run_forever, name="build-engine", daemon=True).start()
                self._loop = loop
            return self._loop

    def submit(self, coroutine) -> "asyncio.Future":
        return asyncio.wrap_future(asyncio.run_coroutine_threadsafe(coroutine, self.loop()))


_engine = _EngineLoop()


async def _execute(domain: str, spend) -> dict:
    """Engine-loop body: one research build under the overall deadline."""
    return await asyncio.wait_for(run_build(domain, spend), BUILD_DEADLINE_SECONDS)


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
        result = await _engine.submit(_execute(dossier.domain, spend))
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
