"""Regression: builds must not leak file descriptors (R1.58).

A previous revision created one event loop (and so one HTTP client per build) per
build; 1000+ builds exhausted the container's descriptors and killed the listener.
"""
import asyncio
import os
import socket
import weakref

import httpx

from app import builds
from app.main import create_app

FIXTURE = {"now": "2026-03-01T09:00:00+00:00", "users": [
    {"id": "u", "email": "a@example.com", "password": "correct horse", "display_name": "A"}]}


def open_fds() -> int:
    return len(os.listdir("/proc/self/fd"))


_clients: "weakref.WeakKeyDictionary" = weakref.WeakKeyDictionary()


def _per_loop_client():
    loop = asyncio.get_running_loop()
    if loop not in _clients:
        _clients[loop] = socket.socketpair()  # stands in for a pooled connection


async def build_that_opens_a_client(domain, spend):
    # Like the research engine: a client per call, closed when done.
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200))) as c:
        await c.get("http://mock.test/")
    _per_loop_client()  # like the engine's router: one per event loop, never closed
    spend(1)
    return {"ok": True, "fields": {}}


def test_300_sequential_builds_keep_open_fds_flat(monkeypatch):
    monkeypatch.setattr(builds, "run_build", build_that_opens_a_client)

    async def scenario():
        app = create_app()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="http://t") as client:
            await client.post("/_test/reset", json=FIXTURE)
            r = await client.post("/auth/login", json={"email": "a@example.com",
                                                       "password": "correct horse"})
            auth = {"Authorization": "Bearer " + r.json()["token"]}

            async def build(i):
                domain = f"co{i}.test"
                await client.post("/dossiers", json={"domain": domain},
                                  headers={**auth, "Idempotency-Key": f"k{i}"})
                for _ in range(200):
                    state = (await client.get(f"/dossiers/{domain}", headers=auth)).json()["state"]
                    if state != "building":
                        return state
                    await asyncio.sleep(0.01)
                raise AssertionError("build did not finish")

            for i in range(20):  # warm up threads, loops and caches
                assert await build(i) == "ready"
            before = open_fds()
            for i in range(20, 320):
                assert await build(i) == "ready"
            assert open_fds() - before <= 5

    asyncio.run(scenario())
