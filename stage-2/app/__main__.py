"""Entry point: `python -m app` listens on 0.0.0.0 at $PORT (default 8080)."""

import logging
import os
import sys

from .app import App
from .server import make_server


def _port() -> int:
    raw = os.environ.get("PORT", "8080")
    if not raw.isdigit() or not 1 <= int(raw) <= 65535:
        sys.exit(f"PORT must be an integer from 1 to 65535, got {raw!r}")
    return int(raw)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    server = make_server("0.0.0.0", _port(), App())
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
