"""Build lifecycle: runs research builds on a bounded pool, off the request path (RL12, RL13)."""

import logging
import time
from concurrent.futures import ThreadPoolExecutor

log = logging.getLogger("dossier.build")

BUILD_BUDGET_UNITS = 80
BUILD_WALL_SECONDS = 240.0
POOL_WORKERS = 16


class BuildRunner:
    def __init__(self, store, run_build) -> None:
        self._store = store
        self._run_build = run_build
        self._pool = ThreadPoolExecutor(max_workers=POOL_WORKERS, thread_name_prefix="build")

    def start(self, dossier_id: str, domain: str, requested_at, generation: int) -> None:
        """Queue a build. Never blocks on the build itself."""
        self._pool.submit(self._run, dossier_id, domain, requested_at, generation)

    def _run(self, dossier_id: str, domain: str, requested_at, generation: int) -> None:
        started = time.monotonic()
        reported = [0]
        applied = False

        def on_spend(units: int) -> None:
            reported[0] += units
            self._store.add_spend(dossier_id, generation, units)

        def cancelled() -> bool:
            return self._store.generation != generation or time.monotonic() - started > BUILD_WALL_SECONDS

        try:
            try:
                result = self._run_build(domain, budget=BUILD_BUDGET_UNITS, on_spend=on_spend, cancelled=cancelled)
            except Exception:
                log.exception("build for %s raised", domain)
                result = None
            self._store.finish_build(dossier_id, generation, requested_at, result, reported[0])
            applied = True
        finally:
            if not applied:
                # Any failure while applying the result ends the build failed, fields unchanged.
                log.error("build for %s could not be applied; ending it failed", domain)
                self._store.fail_build(dossier_id, generation)
