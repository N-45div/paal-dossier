"""The docker stack: mock web and service on a private network, all named with the seat handle."""
from __future__ import annotations

import time
from contextlib import contextmanager
from collections.abc import Iterator

from . import config
from .api import MockAdmin, ServiceClient, call
from .shell import run, run_heavy


def build_images() -> None:
    run_heavy(["docker", "build", "-q", "-t", config.SERVICE_IMAGE, str(config.STAGE_DIR)], timeout=900)
    run_heavy(["docker", "build", "-q", "-t", config.MOCK_IMAGE, str(config.MOCK_CONTEXT)], timeout=1200)


def remove_containers() -> None:
    run(["docker", "rm", "-f", config.SERVICE_CONTAINER, config.MOCK_CONTAINER], timeout=60, check=False)


def start_mock() -> None:
    run(["docker", "network", "create", config.NETWORK], timeout=30, check=False)
    run(
        ["docker", "run", "-d", "--name", config.MOCK_CONTAINER, "--network", config.NETWORK,
         "-e", f"MOCK_ADMIN_TOKEN={config.ADMIN_TOKEN}",
         "-v", f"{config.CORPUS_DIR}:/data/corpus:ro",
         "-p", f"{config.MOCK_PORT}:8080", config.MOCK_IMAGE],
        timeout=60,
    )
    wait_healthy(f"http://127.0.0.1:{config.MOCK_PORT}/_mock/health", 60)


def start_service(tavily: bool = True) -> float:
    """Start the service under the stated limits; returns seconds from `docker run` to first healthy answer."""
    web = f"http://{config.MOCK_CONTAINER}:8080"
    env = ["-e", f"PORT={config.SERVICE_PORT}", "-e", "NIMBLE_API_KEY=local", "-e", f"NIMBLE_BASE_URL={web}/nimble"]
    if tavily:
        env += ["-e", "TAVILY_API_KEY=local", "-e", f"TAVILY_BASE_URL={web}/tavily"]
    started = time.monotonic()
    run(
        ["docker", "run", "-d", "--name", config.SERVICE_CONTAINER, "--network", config.NETWORK,
         "--cpus", "2", "--memory", "3g", "-p", f"{config.SERVICE_PORT}:{config.SERVICE_PORT}", *env, config.SERVICE_IMAGE],
        timeout=120,
    )
    wait_healthy(f"http://127.0.0.1:{config.SERVICE_PORT}/health", 90)
    return time.monotonic() - started


def stop_service() -> None:
    run(["docker", "rm", "-f", config.SERVICE_CONTAINER], timeout=60, check=False)


def wait_healthy(url: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if call("GET", url, timeout=2).status == 200:
            return
        time.sleep(0.1)
    raise TimeoutError(f"{url} not healthy within {timeout}s")


@contextmanager
def running(tavily: bool = True, build: bool = True) -> Iterator[tuple[ServiceClient, MockAdmin]]:
    """Build (optionally), start mock and service, yield clients, and always clean up."""
    remove_containers()
    try:
        if build:
            build_images()
        start_mock()
        start_service(tavily)
        yield ServiceClient(f"http://127.0.0.1:{config.SERVICE_PORT}"), MockAdmin(f"http://127.0.0.1:{config.MOCK_PORT}", config.ADMIN_TOKEN)
    finally:
        remove_containers()
        run(["docker", "network", "rm", config.NETWORK], timeout=30, check=False)
