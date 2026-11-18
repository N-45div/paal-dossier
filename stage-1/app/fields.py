"""Typed access to JSON body fields: wrong type is 400, missing is 422."""
from typing import Any

from app.errors import invalid, malformed


def check_types(body: dict, names: tuple[str, ...], kind: type = str) -> None:
    """400 when any present field is not of the expected JSON type."""
    for name in names:
        value = body.get(name)
        if name in body and not (isinstance(value, kind) and not isinstance(value, bool)):
            raise malformed(f"{name} must be a {kind.__name__}")


def require(body: dict, names: tuple[str, ...]) -> list[Any]:
    """Values of required fields: type errors first (400), then missing (422)."""
    check_types(body, names)
    for name in names:
        if name not in body:
            raise invalid(f"{name} is required")
    return [body[name] for name in names]
