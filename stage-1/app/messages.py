"""Request and reply values passed from the transport to the router and handlers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .store import User


@dataclass
class Request:
    method: str
    path: str  # raw path as sent, not percent-decoded
    query: dict[str, list[str]]
    headers: Mapping[str, str]
    body: bytes
    params: dict[str, str] = field(default_factory=dict)
    user: User | None = None  # set by the router for authenticated routes


@dataclass(frozen=True)
class Reply:
    status: int
    body: Any = None  # JSON-serialisable; None means no body


def json_reply(status: int, body: Any) -> Reply:
    return Reply(status, body)


def no_content() -> Reply:
    return Reply(204)
