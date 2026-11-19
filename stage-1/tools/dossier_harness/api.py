"""A tiny thread-safe HTTP client that records status, JSON body and latency."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass
class Reply:
    status: int
    body: Any
    seconds: float


def call(method: str, url: str, body: Any = None, headers: dict[str, str] | None = None, timeout: float = 30.0) -> Reply:
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status, raw = response.status, response.read()
    except urllib.error.HTTPError as error:
        status, raw = error.code, error.read()
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
        return Reply(0, None, time.monotonic() - started)
    try:
        payload = json.loads(raw) if raw else None
    except ValueError:
        payload = None
    return Reply(status, payload, time.monotonic() - started)


class ServiceClient:
    """Calls the dossier service and records every reply, with its latency, in `log`."""

    def __init__(self, base: str) -> None:
        self.base = base
        self.log: list[Reply] = []

    def _send(self, method: str, path: str, body: Any = None, headers: dict[str, str] | None = None, timeout: float = 30.0) -> Reply:
        reply = call(method, f"{self.base}{path}", body, headers, timeout)
        self.log.append(reply)
        return reply

    def reset(self, fixture: dict[str, Any]) -> Reply:
        return self._send("POST", "/_test/reset", fixture, timeout=15)

    def signup(self, email: str, password: str, display_name: str) -> Reply:
        return self._send("POST", "/auth/signup", {"email": email, "password": password, "display_name": display_name})

    def login(self, email: str, password: str = "correct horse") -> dict[str, str]:
        reply = self._send("POST", "/auth/login", {"email": email, "password": password})
        return {"Authorization": "Bearer " + reply.body["token"]}

    def create(self, headers: dict[str, str], domain: str, key: str) -> Reply:
        return self._send("POST", "/dossiers", {"domain": domain}, {**headers, "Idempotency-Key": key})

    def refresh(self, headers: dict[str, str], domain: str, key: str) -> Reply:
        return self._send("POST", f"/dossiers/{domain}/refresh", None, {**headers, "Idempotency-Key": key})

    def read(self, headers: dict[str, str], domain: str) -> Reply:
        return self._send("GET", f"/dossiers/{domain}", None, headers)

    def listing(self, headers: dict[str, str], query: str = "") -> Reply:
        return self._send("GET", f"/dossiers{query}", None, headers)

    def wait_built(self, headers: dict[str, str], domain: str, timeout: float) -> Reply:
        """Poll until the dossier leaves `building`; returns the last reply."""
        deadline = time.monotonic() + timeout
        while True:
            reply = self.read(headers, domain)
            if reply.status != 200 or reply.body["state"] != "building" or time.monotonic() > deadline:
                return reply
            time.sleep(0.1)


class MockAdmin:
    """Calls the mock web's admin API."""

    def __init__(self, base: str, token: str) -> None:
        self.base = base
        self.headers = {"X-Mock-Admin": token}

    def reset(self) -> None:
        call("POST", f"{self.base}/_mock/reset", {"epoch": 0}, self.headers)

    def fault(self, provider: str, mode: str, methods: tuple[str, ...] = ("search", "extract", "research"), seconds: float | None = None) -> None:
        body: dict[str, Any] = {"provider": provider, "methods": list(methods), "mode": mode}
        if seconds is not None:
            body["seconds"] = seconds
        call("POST", f"{self.base}/_mock/faults", body, self.headers)

    def log(self) -> list[dict[str, Any]]:
        return call("GET", f"{self.base}/_mock/log", None, self.headers).body["calls"]
