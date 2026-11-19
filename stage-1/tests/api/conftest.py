import sys
from pathlib import Path

import pytest
from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.main import create_app  # noqa: E402

FIXTURE = {
    "now": "2026-03-01T09:00:00+00:00",
    "users": [
        {"id": "u_ada", "email": "ada@example.com", "password": "correct horse", "display_name": "Ada"},
        {"id": "u_bob", "email": "bob@example.com", "password": "correct horse", "display_name": "Bob"},
    ],
}


def make_engine(ok=True, fields=None, units=3, delay=0.0):
    import asyncio

    async def engine(domain, spend):
        spend(units)
        if delay:
            await asyncio.sleep(delay)
        return {"ok": ok, "fields": fields or {}}

    return engine


@pytest.fixture
def client():
    with TestClient(create_app(make_engine())) as c:
        assert c.post("/_test/reset", json=FIXTURE).status_code == 204
        yield c


def login(client, email="ada@example.com"):
    r = client.post("/auth/login", json={"email": email, "password": "correct horse"})
    return {"Authorization": "Bearer " + r.json()["token"]}


@pytest.fixture
def ada(client):
    return login(client)
