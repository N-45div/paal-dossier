"""HTTP helpers: JSON responses and strict JSON body parsing."""
import json
from typing import Any

from starlette.requests import Request
from starlette.responses import Response

from app.errors import ApiError, malformed

JSON_TYPE = "application/json; charset=utf-8"


def json_response(data: Any, status: int = 200, headers: dict | None = None) -> Response:
    body = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    response = Response(body, status_code=status, headers=headers)
    response.headers["content-type"] = JSON_TYPE
    return response


def no_content() -> Response:
    return Response(status_code=204)


def error_response(err: ApiError, headers: dict | None = None) -> Response:
    return json_response({"error": {"code": err.code, "message": err.message}}, err.status, headers)


def _reject_constant(name: str):
    raise ValueError(name)


def parse_json(raw: bytes) -> Any:
    try:
        return json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
    except (ValueError, RecursionError):
        raise malformed("body is not valid JSON")


async def json_object(request: Request) -> dict:
    """The request body as a JSON object, else 400 malformed_request."""
    value = parse_json(await request.body())
    if not isinstance(value, dict):
        raise malformed("body must be a JSON object")
    return value


def raw_path(request: Request) -> str:
    raw = request.scope.get("raw_path")
    return raw.decode("latin-1") if raw else request.url.path
