"""Small HTTP helpers: JSON responses and strict body parsing."""
from __future__ import annotations

import json
from typing import Any

from starlette.responses import Response

JSON_TYPE = "application/json; charset=utf-8"


def json_response(payload: Any, status: int = 200) -> Response:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return Response(body, status_code=status, media_type=JSON_TYPE)


def no_content() -> Response:
    return Response(status_code=204)


def _reject_constant(name: str) -> Any:
    raise ValueError(f"invalid JSON constant {name}")


def parse_json(raw: bytes) -> Any:
    """Parse a request body; raises ValueError when it is not valid JSON."""
    try:
        return json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
    except (UnicodeDecodeError, RecursionError) as exc:
        raise ValueError(str(exc)) from exc
