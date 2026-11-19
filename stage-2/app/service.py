"""Service root: the clock, the replaceable store and the running builds."""
from __future__ import annotations

import asyncio

from .builds import BuildRunner
from .clock import Clock
from .research_adapter import RunBuild
from .state import Store


class Service:
    def __init__(self, run_build: RunBuild) -> None:
        self.clock = Clock()
        self.store = Store()
        self.builds = BuildRunner(self, run_build)

    def replace_store(self, store: Store) -> None:
        """Swap all state at once; builds of the old state stop and can no longer write."""
        self.store = store
        self.builds.abandon_all()
