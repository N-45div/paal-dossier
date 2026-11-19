"""Request body parsing and field checks, in the order RL1.4 and RL1.9 require.

Wrong JSON type is 400 and is checked for every present field before any missing field
is reported as 422.
"""

import json
from typing import Any, Mapping

from dossier.server.errors import malformed, validation


def parse_object(raw: bytes) -> dict:
    """Parse a request body as a JSON object; anything else is 400 malformed_request."""
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise malformed() from None
    if not isinstance(value, dict):
        raise malformed()
    return value


def read_fields(body: Mapping[str, Any], spec: Mapping[str, type]) -> dict:
    """Return the named fields. Wrong type -> 400 first, then missing -> 422."""
    for key, kind in spec.items():
        if key in body and not isinstance(body[key], kind):
            raise malformed(f"field {key} has the wrong JSON type")
    for key in spec:
        if key not in body:
            raise validation(f"field {key} is required")
    return {key: body[key] for key in spec}
