"""Mixed 50-way load against a running service: latency, 5xx and reset time.

usage: python -I load_test.py BASE_URL [SECONDS]
"""
import asyncio
import random
import sys
import time

import httpx

BASE = sys.argv[1]
SECONDS = float(sys.argv[2]) if len(sys.argv) > 2 else 20
FIXTURE = {"now": "2026-03-01T09:00:00+00:00",
           "users": [{"id": "u_ada", "email": "ada@example.com",
                      "password": "correct horse", "display_name": "Ada"}]}
CORPUS = ["ashgrove-solar", "brightwater-labs", "corvid-security", "ferncliff-foods",
          "halvorsen-robotics", "larkspur-health", "mosaic-freight", "ostrava-mobility",
          "pemberton-analytics", "quillmate", "tidemark-energy", "windrush-bakery"]
samples: list[tuple[str, int, float]] = []


async def call(client, name, method, path, **kw):
    start = time.perf_counter()
    try:
        r = await client.request(method, path, **kw)
        status = r.status_code
    except httpx.HTTPError:
        r, status = None, 599
    samples.append((name, status, time.perf_counter() - start))
    return r


async def worker(client, wid, deadline, tokens):
    n = 0
    while time.perf_counter() < deadline:
        n += 1
        h = {"Authorization": "Bearer " + random.choice(tokens)}
        domain = random.choice(CORPUS) + ".test" if random.random() < .5 else f"co{wid}x{n}.test"
        op = random.choice(["signup", "login", "create", "get", "list", "refresh", "export", "health"])
        if op == "signup":
            await call(client, op, "POST", "/auth/signup", json={
                "email": f"w{wid}n{n}@example.com", "password": "12345678", "display_name": "W"})
        elif op == "login":
            await call(client, op, "POST", "/auth/login",
                       json={"email": "ada@example.com", "password": "correct horse"})
        elif op == "create":
            await call(client, op, "POST", "/dossiers", json={"domain": domain},
                       headers={**h, "Idempotency-Key": f"{wid}-{n}"})
        elif op == "get":
            await call(client, op, "GET", f"/dossiers/{domain}", headers=h)
        elif op == "list":
            await call(client, op, "GET", "/dossiers?limit=200", headers=h)
        elif op == "refresh":
            await call(client, op, "POST", f"/dossiers/{domain}/refresh",
                       headers={**h, "Idempotency-Key": f"r{wid}-{n}"})
        elif op == "export":
            await call(client, op, "GET", "/_test/export")
        else:
            await call(client, op, "GET", "/health")


async def main():
    limits = httpx.Limits(max_connections=60)
    async with httpx.AsyncClient(base_url=BASE, timeout=30, limits=limits) as client:
        r = await call(client, "reset-idle", "POST", "/_test/reset", json=FIXTURE)
        assert r.status_code == 204
        r = await client.post("/auth/login", json={"email": "ada@example.com",
                                                   "password": "correct horse"})
        tokens = [r.json()["token"]]
        starts = await asyncio.gather(*[call(client, "seed-build", "POST", "/dossiers",
                                             json={"domain": f"seed{i}.test"},
                                             headers={"Authorization": "Bearer " + tokens[0],
                                                      "Idempotency-Key": f"seed{i}"})
                                        for i in range(16)])
        deadline = time.perf_counter() + SECONDS
        workers = [asyncio.create_task(worker(client, i, deadline, tokens)) for i in range(50)]
        await asyncio.sleep(SECONDS / 2)
        await call(client, "reset-under-load", "POST", "/_test/reset", json=FIXTURE)
        await asyncio.gather(*workers)
        await call(client, "reset-after", "POST", "/_test/reset", json=FIXTURE)


asyncio.run(main())
by_op: dict[str, list[float]] = {}
for name, status, took in samples:
    by_op.setdefault(name, []).append(took)
bad = [s for s in samples if s[1] >= 500]
for name, times in sorted(by_op.items()):
    times.sort()
    print(f"{name:18} n={len(times):5} p50={times[len(times)//2]*1000:7.0f}ms "
          f"p99={times[int(len(times)*.99)]*1000:7.0f}ms max={times[-1]*1000:7.0f}ms")
worst = max(s[2] for s in samples)
reset = max(s[2] for s in samples if s[0].startswith("reset"))
print(f"requests={len(samples)} 5xx={len(bad)} max_latency={worst:.2f}s max_reset={reset:.2f}s")
assert not bad, bad[:5]
assert worst < 5, worst
assert reset < 10, reset
print("LOAD OK")
