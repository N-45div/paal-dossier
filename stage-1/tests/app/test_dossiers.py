"""Dossier API, idempotency, build lifecycle and export/import (spec §7-§10), with a fake build
engine standing in for the research package.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest

from app import builds
from app.context import App, create_app
from app.routes import Router
from app.transport import create_server

from .conftest import Client

FIXTURE_NOW = "2026-03-01T09:00:00+00:00"
USERS = [
    {"id": "u_ada", "email": "ada@example.com", "password": "correct horse", "display_name": "Ada"},
    {"id": "u_bob", "email": "bob@example.com", "password": "correct horse", "display_name": "Bob"},
]
ACME_FIELDS = {
    "legal_name": {"value": "Acme Robotics, Inc.", "citations": [
        {"url": "https://acme-robotics.test/about", "excerpt": "Acme Robotics, Inc. is ...",
         "provider": "nimble"}]},
    "founded_year": {"value": 2014, "citations": [
        {"url": "https://acme-robotics.test/about", "excerpt": "Founded in 2014.",
         "provider": "nimble"}]},
}


class FakeEngine:
    """Replaces `app.builds.run_build`; records calls and can block until released."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.outcome: Any = SimpleNamespace(ok=True, fields=ACME_FIELDS, spent_units=34)
        self.gate: threading.Event | None = None

    def __call__(self, domain: str) -> Any:
        self.calls.append(domain)
        if self.gate is not None:
            self.gate.wait(10)
        if self.outcome.ok and domain != "acme-robotics.test":
            return SimpleNamespace(ok=True, fields={}, spent_units=1)
        return self.outcome


@pytest.fixture
def engine(monkeypatch: pytest.MonkeyPatch) -> FakeEngine:
    fake = FakeEngine()
    monkeypatch.setattr(builds, "run_build", fake)
    return fake


@pytest.fixture
def service(engine: FakeEngine) -> Iterator[tuple[Client, App]]:
    app = create_app()
    server = create_server(app, Router(), "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    client = Client(f"http://{host}:{port}")
    assert client.post("/_test/reset", {"now": FIXTURE_NOW, "users": USERS}).status == 204
    try:
        yield client, app
    finally:
        server.shutdown()
        server.server_close()


def token_for(client: Client, email: str = "ada@example.com") -> str:
    return client.post("/auth/login", {"email": email, "password": "correct horse"}).json()["token"]


def auth(token: str, key: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if key is not None:
        headers["Idempotency-Key"] = key
    return headers


def wait_until_idle(client: Client, token: str, domain: str) -> dict[str, Any]:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        body = client.get(f"/dossiers/{domain}", headers=auth(token)).json()
        if body["state"] != "building":
            return body
        time.sleep(0.02)
    raise AssertionError("build did not finish")


def test_dossier_writes_require_bearer_before_key(service: tuple[Client, App]) -> None:
    client, _ = service
    response = client.post("/dossiers", {"domain": "acme-robotics.test"})
    assert response.status == 401
    assert response.json()["error"]["code"] == "unauthenticated"
    response = client.post("/dossiers/acme-robotics.test/refresh")
    assert response.status == 401


def test_missing_idempotency_key_is_400_after_auth(service: tuple[Client, App]) -> None:
    client, _ = service
    token = token_for(client)
    response = client.post("/dossiers", {"domain": "acme-robotics.test"}, headers=auth(token))
    assert response.status == 400
    assert response.json()["error"]["code"] == "missing_idempotency_key"


def test_create_starts_build_and_ready_state_carries_fields(
    service: tuple[Client, App], engine: FakeEngine
) -> None:
    client, _ = service
    token = token_for(client)
    created = client.post("/dossiers", {"domain": "Acme-Robotics.TEST."},
                          headers=auth(token, "k1"))
    assert created.status == 202
    body = created.json()
    assert body["domain"] == "acme-robotics.test"
    assert body["state"] == "building"
    done = wait_until_idle(client, token, "acme-robotics.test")
    assert done["state"] == "ready"
    assert done["spent_units"] == 34
    assert done["researched_at"] == FIXTURE_NOW
    assert done["fields"]["legal_name"]["status"] == "known"
    assert done["fields"]["ceo"] == {"value": None, "status": "unknown", "citations": []}
    assert engine.calls == ["acme-robotics.test"]


def test_same_domain_in_other_spelling_is_existing_dossier(service: tuple[Client, App]) -> None:
    client, _ = service
    token = token_for(client)
    first = client.post("/dossiers", {"domain": "acme-robotics.test"}, headers=auth(token, "a"))
    second = client.post("/dossiers", {"domain": "www.acme-robotics.test"},
                         headers=auth(token, "b"))
    assert first.status == 202
    assert second.status == 200
    assert second.json()["dossier_id"] == first.json()["dossier_id"]


def test_replay_returns_original_body_as_200(service: tuple[Client, App]) -> None:
    client, _ = service
    token = token_for(client)
    original = client.post("/dossiers", {"domain": "acme-robotics.test"},
                           headers=auth(token, "replay"))
    replay = client.post("/dossiers", {"domain": "acme-robotics.test", "unknown": 1},
                         headers=auth(token, "replay"))
    assert original.status == 202
    assert replay.status == 200
    assert replay.json() == original.json()


def test_same_key_different_body_is_409(service: tuple[Client, App]) -> None:
    client, _ = service
    token = token_for(client)
    client.post("/dossiers", {"domain": "acme-robotics.test"}, headers=auth(token, "k"))
    response = client.post("/dossiers", {"domain": "other.test"}, headers=auth(token, "k"))
    assert response.status == 409
    assert response.json()["error"]["code"] == "idempotency_key_reuse"


def test_claimed_key_is_resolved_before_field_validation(service: tuple[Client, App]) -> None:
    client, _ = service
    token = token_for(client)
    client.post("/dossiers", {"domain": "acme-robotics.test"}, headers=auth(token, "v"))
    response = client.post("/dossiers", {"domain": "not a domain"}, headers=auth(token, "v"))
    assert response.status == 409


def test_same_key_on_other_path_is_independent(service: tuple[Client, App]) -> None:
    client, _ = service
    token = token_for(client)
    client.post("/dossiers", {"domain": "acme-robotics.test"}, headers=auth(token, "p"))
    response = client.post("/dossiers/acme-robotics.test/refresh", headers=auth(token, "p"))
    assert response.status == 202


def test_key_is_scoped_per_user(service: tuple[Client, App]) -> None:
    client, _ = service
    ada = token_for(client)
    bob = token_for(client, "bob@example.com")
    assert client.post("/dossiers", {"domain": "acme-robotics.test"},
                       headers=auth(ada, "shared")).status == 202
    assert client.post("/dossiers", {"domain": "beta.test"},
                       headers=auth(bob, "shared")).status == 202


def test_key_longer_than_255_is_422(service: tuple[Client, App]) -> None:
    client, _ = service
    token = token_for(client)
    response = client.post("/dossiers", {"domain": "acme-robotics.test"},
                           headers=auth(token, "x" * 256))
    assert response.status == 422


def test_failed_4xx_releases_the_key(service: tuple[Client, App]) -> None:
    client, _ = service
    token = token_for(client)
    bad = client.post("/dossiers", {"domain": "not a domain"}, headers=auth(token, "again"))
    assert bad.status == 422
    good = client.post("/dossiers", {"domain": "acme-robotics.test"}, headers=auth(token, "again"))
    assert good.status == 202


def test_invalid_domain_and_wrong_types(service: tuple[Client, App]) -> None:
    client, _ = service
    token = token_for(client)
    assert client.post("/dossiers", {}, headers=auth(token, "1")).status == 422
    assert client.post("/dossiers", {"domain": None}, headers=auth(token, "2")).status == 422
    assert client.post("/dossiers", {"domain": 5}, headers=auth(token, "3")).status == 400
    assert client.post("/dossiers", {"domain": "https://a.test"},
                       headers=auth(token, "4")).status == 422


def test_failed_build_keeps_fields_and_reports_failed(
    service: tuple[Client, App], engine: FakeEngine
) -> None:
    client, _ = service
    token = token_for(client)
    engine.outcome = SimpleNamespace(ok=False, fields={}, spent_units=5)
    client.post("/dossiers", {"domain": "acme-robotics.test"}, headers=auth(token, "f"))
    done = wait_until_idle(client, token, "acme-robotics.test")
    assert done["state"] == "failed"
    assert done["spent_units"] == 5
    assert done["researched_at"] is None
    assert all(field["status"] == "unknown" for field in done["fields"].values())


def test_refresh_while_building_starts_no_second_build(
    service: tuple[Client, App], engine: FakeEngine
) -> None:
    client, _ = service
    token = token_for(client)
    engine.gate = threading.Event()
    first = client.post("/dossiers", {"domain": "acme-robotics.test"}, headers=auth(token, "c"))
    refresh = client.post("/dossiers/acme-robotics.test/refresh", headers=auth(token, "r1"))
    assert refresh.status == 202
    assert refresh.json() == first.json() | {"state": "building"}
    engine.gate.set()
    wait_until_idle(client, token, "acme-robotics.test")
    assert engine.calls == ["acme-robotics.test"]


def test_refresh_of_unknown_domain_is_404(service: tuple[Client, App]) -> None:
    client, _ = service
    token = token_for(client)
    response = client.post("/dossiers/nobody.test/refresh", headers=auth(token, "n"))
    assert response.status == 404
    assert response.json()["error"]["code"] == "not_found"


def test_get_unknown_and_invalid_domains(service: tuple[Client, App]) -> None:
    client, _ = service
    token = token_for(client)
    assert client.get("/dossiers/nobody.test", headers=auth(token)).status == 404
    assert client.get("/dossiers/not_valid", headers=auth(token)).status == 422
    assert client.get("/dossiers/nobody.test").status == 401


def test_list_filters_orders_and_paginates(service: tuple[Client, App]) -> None:
    client, _ = service
    token = token_for(client)
    for index, domain in enumerate(["beta.test", "acme-robotics.test", "gamma.test"]):
        client.post("/dossiers", {"domain": domain}, headers=auth(token, f"l{index}"))
    listing = client.get("/dossiers", headers=auth(token)).json()
    assert [item["domain"] for item in listing["dossiers"]] == [
        "acme-robotics.test", "beta.test", "gamma.test",
    ]
    assert listing["has_more"] is False
    page = client.get("/dossiers?limit=2&offset=1", headers=auth(token)).json()
    assert [item["domain"] for item in page["dossiers"]] == ["beta.test", "gamma.test"]
    filtered = client.get("/dossiers?q=ACME", headers=auth(token)).json()
    assert [item["domain"] for item in filtered["dossiers"]] == ["acme-robotics.test"]
    everything = client.get("/dossiers?q=", headers=auth(token)).json()
    assert len(everything["dossiers"]) == 3


@pytest.mark.parametrize("query", ["limit=1e9", "limit=4.0", "limit=+4", "limit=0",
                                   "limit=201", "offset=-1", "offset=", "limit=abc"])
def test_list_rejects_non_plain_or_out_of_range_integers(
    service: tuple[Client, App], query: str
) -> None:
    client, _ = service
    token = token_for(client)
    assert client.get(f"/dossiers?{query}", headers=auth(token)).status == 422


def test_reset_during_build_discards_its_result(
    service: tuple[Client, App], engine: FakeEngine
) -> None:
    client, _ = service
    token = token_for(client)
    engine.gate = threading.Event()
    client.post("/dossiers", {"domain": "acme-robotics.test"}, headers=auth(token, "rr"))
    assert client.post("/_test/reset", {"now": FIXTURE_NOW, "users": USERS}).status == 204
    token = token_for(client)
    engine.gate.set()
    time.sleep(0.2)
    assert client.get("/dossiers", headers=auth(token)).json()["dossiers"] == []


def test_export_import_round_trip_keeps_tokens_keys_and_dossiers(
    service: tuple[Client, App], engine: FakeEngine
) -> None:
    client, _ = service
    token = token_for(client)
    created = client.post("/dossiers", {"domain": "acme-robotics.test"},
                          headers=auth(token, "keep"))
    done = wait_until_idle(client, token, "acme-robotics.test")
    export = client.get("/_test/export").json()
    assert export["track"] == "dossier" and export["format_version"] == 1

    assert client.post("/_test/reset", {"now": FIXTURE_NOW, "users": []}).status == 204
    assert client.post("/_test/import", export).status == 204
    assert client.get("/dossiers/acme-robotics.test", headers=auth(token)).json() == done
    replay = client.post("/dossiers", {"domain": "acme-robotics.test"},
                         headers=auth(token, "keep"))
    assert replay.status == 200
    assert replay.json() == created.json()
    assert engine.calls == ["acme-robotics.test"]
    assert client.post("/auth/login", {"email": "ada@example.com",
                                       "password": "correct horse"}).status == 200


def test_import_rejects_bad_documents_and_changes_nothing(service: tuple[Client, App]) -> None:
    client, _ = service
    export = client.get("/_test/export").json()
    before = client.get("/_test/export").json()
    assert client.post("/_test/import", {"track": "other", "format_version": 1,
                                         "state": {}}).status == 422
    assert client.post("/_test/import", {"track": "dossier", "format_version": 2,
                                         "state": {}}).status == 422
    assert client.post("/_test/import", {"track": "dossier", "format_version": 1}).status == 422
    assert client.post("/_test/import", raw=b"{").status == 400
    assert client.get("/_test/export").json() == before
    assert export["state"]["users"]
