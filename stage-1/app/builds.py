"""Runs dossier builds in the background and applies their outcome."""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from .fields import clean_fields
from .research_adapter import RunBuild
from .state import Dossier, Store

if TYPE_CHECKING:
    from .service import Service

BUILD_DEADLINE_SECONDS = 290.0


class BuildRunner:
    def __init__(self, service: "Service", run_build: RunBuild) -> None:
        self._service = service
        self._run_build = run_build
        self._tasks: set[asyncio.Task[None]] = set()

    def start(self, dossier: Dossier) -> None:
        """Start a build of the dossier; the caller has checked none is running."""
        dossier.building = True
        dossier.running_spent = 0
        task = asyncio.create_task(self._run(self._service.store, dossier, self._service.clock.now_text()))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def abandon_all(self) -> None:
        for task in list(self._tasks):
            task.cancel()

    async def _run(self, store: Store, dossier: Dossier, build_time: str) -> None:
        def spend(units: int) -> None:
            dossier.running_spent += int(units)

        result: dict[str, Any] | None
        try:
            result = await asyncio.wait_for(self._run_build(dossier.domain, spend), BUILD_DEADLINE_SECONDS)
        except Exception:  # a failing engine ends the build as failed, never a 5xx
            result = None
        if store is not self._service.store:
            return
        # A successful provider call always costs units, so a build that spent nothing made no call that succeeded.
        succeeded = isinstance(result, dict) and result.get("ok") is True and dossier.running_spent > 0
        if succeeded:
            dossier.fields = clean_fields(result.get("fields"))
            dossier.researched_at = build_time
        dossier.outcome = "ready" if succeeded else "failed"
        dossier.spent_units += dossier.running_spent
        dossier.running_spent = 0
        dossier.building = False
