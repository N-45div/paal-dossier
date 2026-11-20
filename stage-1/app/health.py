"""GET /health (spec §3.2): answers once the service can serve requests; no provider call."""

from __future__ import annotations

from .context import App
from .messages import Reply, Request, json_reply


def health(app: App, request: Request) -> Reply:
    return json_reply(200, {"status": "ok"})
