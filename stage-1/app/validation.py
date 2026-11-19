"""Field rules shared by the endpoints (§4, §6, RL8)."""

import re

_WHITESPACE = re.compile(r"\s")


def is_valid_email(value: str) -> bool:
    """`local@domain`: exactly one `@`, non-empty both sides, no whitespace (RL8)."""
    local, sep, domain = value.partition("@")
    return bool(sep) and bool(local) and bool(domain) and "@" not in domain and not _WHITESPACE.search(value)


def is_valid_user_id(value: str) -> bool:
    """Opaque id: 1 to 64 characters without whitespace."""
    return 1 <= len(value) <= 64 and not _WHITESPACE.search(value)


def is_valid_display_name(value: str) -> bool:
    return 1 <= len(value) <= 100


def is_valid_password(value: str) -> bool:
    return len(value) >= 8
