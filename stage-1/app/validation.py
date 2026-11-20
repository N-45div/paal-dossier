"""Request body parsing and the field rules shared by endpoints."""

from __future__ import annotations

import json
import secrets
from typing import Any

from .errors import malformed, validation_failed

MIN_PASSWORD_LENGTH = 8
MAX_DISPLAY_NAME_LENGTH = 100


def parse_object(raw: bytes) -> dict[str, Any]:
    """Parse a body that must be a JSON object; anything else is 400 malformed_request."""
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise malformed("body is not valid JSON") from exc
    if not isinstance(value, dict):
        raise malformed("body must be a JSON object")
    return value


def required_string(fields: dict[str, Any], name: str) -> str:
    """A missing or null field is 422; a field of another JSON type is 400."""
    value = fields.get(name)
    if value is None:
        raise validation_failed(f"{name} is required")
    if not isinstance(value, str):
        raise malformed(f"{name} must be a string")
    return value


def normalise_email(value: str) -> str:
    """Lowercase, and require exactly one `@` with text on both sides and no whitespace."""
    email = value.lower()
    if any(character.isspace() for character in email) or email.count("@") != 1:
        raise validation_failed("email must be of the form local@domain")
    local, domain = email.split("@")
    if not local or not domain:
        raise validation_failed("email must be of the form local@domain")
    return email


def check_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise validation_failed(f"password must be at least {MIN_PASSWORD_LENGTH} characters")


def check_display_name(display_name: str) -> None:
    if not display_name.strip() or len(display_name) > MAX_DISPLAY_NAME_LENGTH:
        raise validation_failed(
            f"display_name must be 1 to {MAX_DISPLAY_NAME_LENGTH} characters"
        )


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"
