"""Bind test servers only inside the seat's assigned port range (never port 0).

builder-a's range is 18000-18099. DOSSIER_TEST_PORT_RANGE, as "low-high", overrides it.
"""

import os

from dossier.server.transport import Server

DEFAULT_RANGE = "18000-18099"


def assigned_ports() -> range:
    low, high = os.environ.get("DOSSIER_TEST_PORT_RANGE", DEFAULT_RANGE).split("-")
    return range(int(low), int(high) + 1)


def bind_server(service) -> Server:
    for port in assigned_ports():
        try:
            return Server(("127.0.0.1", port), service)
        except OSError:
            continue  # in use: try the next port of the range
    raise RuntimeError("no free port in the assigned test range")
