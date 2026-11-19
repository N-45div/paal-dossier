"""The service object the HTTP layer hands to every handler."""

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable

from dossier.server.store import Store

# run_build(domain, cancel) -> BuildResult-like object (RL1.3). Injected so tests need no engine.
Runner = Callable[[str, threading.Event], object]


@dataclass(frozen=True)
class Service:
    store: Store
    runner: Runner
    executor: ThreadPoolExecutor


def make_service(runner: Runner, workers: int = 16) -> Service:
    return Service(Store(), runner, ThreadPoolExecutor(max_workers=workers, thread_name_prefix="build"))
