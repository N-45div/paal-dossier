"""Request body parsing and the shared field checks (spec §3.5, §5)."""

from __future__ import annotations

import json
from typing import Any

from aiohttp import web

from app.errors import malformed, validation_failed


async def read_json_object(request: web.Request) -> dict[str, Any]:
    """Parse the body as a JSON object; anything else is 400 malformed_request."""
    raw = await request.read()
    try:
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise malformed("request body is not valid JSON") from exc
    if not isinstance(body, dict):
        raise malformed("request body must be a JSON object")
    return body


def required_string(body: dict[str, Any], key: str) -> str:
    """Missing field -> 422; present with a non-string JSON type (null included) -> 400."""
    if key not in body:
        raise validation_failed(f"{key} is required")
    value = body[key]
    if not isinstance(value, str):
        raise malformed(f"{key} must be a string")
    return value


def string_length_ok(value: str, minimum: int, maximum: int | None, key: str) -> None:
    if len(value) < minimum or (maximum is not None and len(value) > maximum):
        raise validation_failed(f"{key} has an invalid length")
