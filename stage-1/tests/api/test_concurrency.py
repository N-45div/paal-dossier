"""Concurrency guarantees: R1.76, R1.88, R1.120a and reset during builds (R1.23)."""
import asyncio

import httpx
import pytest

from app import builds
from app.main import create_app

FIXTURE = {"now": "2026-03-01T09:00:00+00:00",
           "users": [{"id": "u_ada", "email": "ada@example.com",
                      "password": "correct horse", "display_name": "Ada"}]}


class FakeResearch:
    def __init__(self, delay=0.3):
        self.delay, self.calls, self.cancelled = delay, [], 0

    async def __call__(self, domain, spend):
        self.calls.append(domain)
        spend(5)
        await asyncio.sleep(self.delay)
        try:
            spend(5)
        except builds.BuildCancelled:
            self.cancelled += 1
            raise
        return {"ok": True, "fields": {}}


@pytest.fixture
def research(monkeypatch):
    fake = FakeResearch()
    monkeypatch.setattr(builds, "_research_entry", lambda: fake)
    return fake


def run(scenario):
    async def main():
        app = create_app()
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
            assert (await client.post("/_test/reset", json=FIXTURE)).status_code == 204
            r = await client.post("/auth/login", json={"email": "ada@example.com",
                                                       "password": "correct horse"})
            auth = {"Authorization": "Bearer " + r.json()["token"]}
            return await scenario(client, auth)
    return asyncio.run(main())


async def post_dossier(client, auth, domain, key):
    return await client.post("/dossiers", json={"domain": domain},
                             headers={**auth, "Idempotency-Key": key})


def test_same_key_concurrent_takes_effect_once(research):
    async def scenario(client, auth):
        rs = await asyncio.gather(*[post_dossier(client, auth, "acme.test", "same")
                                    for _ in range(40)])
        assert sorted(r.status_code for r in rs) == [200] * 39 + [202]
        assert len({r.text for r in rs}) == 1
        await asyncio.sleep(0.6)
    run(scenario)
    assert research.calls == ["acme.test"]


def test_same_domain_any_key_one_dossier_one_build(research):
    variants = ["acme.test", "WWW.Acme.TEST.", " acme.test "]

    async def scenario(client, auth):
        rs = await asyncio.gather(*[post_dossier(client, auth, variants[i % 3], f"k{i}")
                                    for i in range(40)])
        assert sorted(r.status_code for r in rs) == [200] * 39 + [202]
        assert len({r.json()["dossier_id"] for r in rs}) == 1
        listing = (await client.get("/dossiers", headers=auth)).json()["dossiers"]
        assert len(listing) == 1
        await asyncio.sleep(0.6)
    run(scenario)
    assert research.calls == ["acme.test"]


def test_refresh_while_building_starts_no_second_build(research):
    async def scenario(client, auth):
        await post_dossier(client, auth, "acme.test", "first")
        rs = await asyncio.gather(*[client.post("/dossiers/acme.test/refresh",
                                                headers={**auth, "Idempotency-Key": f"r{i}"})
                                    for i in range(30)])
        assert {r.status_code for r in rs} == {202}
        assert {r.json()["state"] for r in rs} == {"building"}
        await asyncio.sleep(0.6)
        d = (await client.get("/dossiers/acme.test", headers=auth)).json()
        assert d["state"] == "ready" and d["spent_units"] == 10
        r = await client.post("/dossiers/acme.test/refresh",
                              headers={**auth, "Idempotency-Key": "later"})
        assert r.status_code == 202
        await asyncio.sleep(0.6)
        d = (await client.get("/dossiers/acme.test", headers=auth)).json()
        assert d["spent_units"] == 20
    run(scenario)
    assert research.calls == ["acme.test"] * 2


def test_reads_during_writes_are_consistent(research):
    async def scenario(client, auth):
        async def writer(i):
            await post_dossier(client, auth, f"co{i}.test", f"w{i}")

        async def reader():
            for _ in range(20):
                d = (await client.get("/dossiers?limit=200", headers=auth)).json()
                for item in d["dossiers"]:
                    assert item["state"] in ("building", "ready", "failed")
                    assert item["spent_units"] in (0, 5, 10)
                await asyncio.sleep(0.01)
        await asyncio.gather(*[writer(i) for i in range(20)], *[reader() for _ in range(5)])
        await asyncio.sleep(0.6)
        listing = (await client.get("/dossiers?limit=200", headers=auth)).json()["dossiers"]
        assert len(listing) == 20 and {d["state"] for d in listing} == {"ready"}
    run(scenario)


def test_reset_during_running_builds_leaves_clean_state(research):
    async def scenario(client, auth):
        await asyncio.gather(*[post_dossier(client, auth, f"co{i}.test", f"k{i}")
                               for i in range(10)])
        await asyncio.sleep(0.1)
        assert (await client.post("/_test/reset", json=FIXTURE)).status_code == 204
        r = await client.post("/auth/login", json={"email": "ada@example.com",
                                                   "password": "correct horse"})
        auth = {"Authorization": "Bearer " + r.json()["token"]}
        await asyncio.sleep(0.6)
        assert (await client.get("/dossiers", headers=auth)).json() == {"dossiers": [],
                                                                       "has_more": False}
        r = await post_dossier(client, auth, "co0.test", "k0")
        assert r.status_code == 202
        await asyncio.sleep(0.1)
        d = (await client.get("/dossiers/co0.test", headers=auth)).json()
        assert d["spent_units"] == 5 and d["state"] == "building"
    run(scenario)


def test_request_straddling_reset_is_rejected_not_applied(research):
    """R1.22/R1.120a: a create whose body arrives after a reset cannot use the old token."""
    async def scenario(client, auth):
        async def slow_body():
            yield b'{"domain":'
            await asyncio.sleep(0.3)
            yield b' "race.test"}'
        pending = asyncio.create_task(client.post(
            "/dossiers", content=slow_body(),
            headers={**auth, "Idempotency-Key": "k", "Content-Type": "application/json"}))
        await asyncio.sleep(0.1)
        other = {"now": FIXTURE["now"], "users": [{"id": "u_new", "email": "n@example.com",
                                                   "password": "12345678", "display_name": "N"}]}
        assert (await client.post("/_test/reset", json=other)).status_code == 204
        assert (await pending).status_code == 401
        r = await client.post("/auth/login", json={"email": "n@example.com", "password": "12345678"})
        new_auth = {"Authorization": "Bearer " + r.json()["token"]}
        assert (await client.get("/dossiers", headers=new_auth)).json()["dossiers"] == []
    run(scenario)
    assert research.calls == []
