"""Starts the service in-process on an ephemeral port for each test."""

from __future__ import annotations

import json
import sys
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

STAGE_ROOT = Path(__file__).resolve().parents[2]
if str(STAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(STAGE_ROOT))

from app.context import create_app  # noqa: E402
from app.routes import Router  # noqa: E402
from app.transport import create_server  # noqa: E402


@dataclass
class Response:
    status: int
    headers: Any
    body: bytes

    def json(self) -> Any:
        return json.loads(self.body)


class Client:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url

    def request(
        self,
        method: str,
        path: str,
        payload: Any = None,
        *,
        raw: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> Response:
        data = raw if raw is not None else (
            None if payload is None else json.dumps(payload).encode("utf-8")
        )
        request = urllib.request.Request(
            self.base_url + path, data=data, method=method, headers=headers or {}
        )
        if data is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return Response(response.status, response.headers, response.read())
        except urllib.error.HTTPError as error:
            return Response(error.code, error.headers, error.read())

    def get(self, path: str, **kwargs: Any) -> Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, payload: Any = None, **kwargs: Any) -> Response:
        return self.request("POST", path, payload, **kwargs)


@pytest.fixture
def client() -> Iterator[Client]:
    server = create_server(create_app(), Router(), "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    try:
        yield Client(f"http://{host}:{port}")
    finally:
        server.shutdown()
        server.server_close()
