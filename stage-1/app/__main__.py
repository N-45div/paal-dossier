"""Entry point: `python -m app` listens on 0.0.0.0:$PORT (default 8080)."""

from __future__ import annotations

import os

from .context import create_app
from .routes import Router
from .transport import create_server

DEFAULT_PORT = 8080


def main() -> None:
    port = int(os.environ.get("PORT") or DEFAULT_PORT)
    server = create_server(create_app(), Router(), "0.0.0.0", port)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
