"""Load check (PD): run against a live container. Usage: load_check.py http://127.0.0.1:PORT

Sends 50 concurrent identical POST /dossiers, then 50 mixed requests, and reports status counts."""
import asyncio, sys, time, collections
import aiohttp

B = sys.argv[1]
TOKEN_EMAIL = ("ada@example.com", "correct horse")

async def main():
    async with aiohttp.ClientSession() as s:
        async def post(path, body=None, headers=None, data=None):
            async with s.post(B + path, json=body, data=data, headers=headers or {}) as r:
                return r.status, await r.text()
        async def get(path, headers=None):
            async with s.get(B + path, headers=headers or {}) as r:
                return r.status, await r.text()

        st, _ = await post("/_test/reset", {"now": "2026-03-01T09:00:00+00:00", "users": [
            {"id": "u_ada", "email": TOKEN_EMAIL[0], "password": TOKEN_EMAIL[1], "display_name": "Ada"}]})
        assert st == 204, st
        st, body = await post("/auth/login", {"email": TOKEN_EMAIL[0], "password": TOKEN_EMAIL[1]})
        tok = __import__("json").loads(body)["token"]
        auth = {"Authorization": f"Bearer {tok}"}

        # 1) 50 concurrent identical POST /dossiers with the same key
        h = dict(auth, **{"Idempotency-Key": "same-key"})
        res = await asyncio.gather(*[post("/dossiers", {"domain": "acme-robotics.test"}, h) for _ in range(50)])
        codes = collections.Counter(c for c, _ in res)
        bodies = {b for _, b in res}
        print("identical same-key:", dict(codes), "distinct bodies:", len(bodies))

        # 2) 50 concurrent mixed requests
        async def mixed(i):
            k = {"Authorization": f"Bearer {tok}", "Idempotency-Key": f"mix-{i}"}
            kind = i % 6
            if kind == 0: return await post("/dossiers", {"domain": f"c{i}.test"}, k)
            if kind == 1: return await get(f"/dossiers/c{i-1}.test", auth)
            if kind == 2: return await get("/dossiers?limit=10&offset=0", auth)
            if kind == 3: return await post(f"/dossiers/c{i-3}.test/refresh", None, k)
            if kind == 4: return await post("/dossiers", {"domain": "not a domain"}, k)
            return await post("/auth/login", {"email": "nobody@x.test", "password": "wrong pass"})
        res = await asyncio.gather(*[mixed(i) for i in range(50)])
        codes = collections.Counter(c for c, _ in res)
        print("mixed:", dict(codes))
        five = [c for c, _ in res if c >= 500]
        print("5xx in mixed:", len(five))

        st, _ = await get("/health")
        print("health after load:", st)
        await asyncio.sleep(1)

asyncio.run(main())
