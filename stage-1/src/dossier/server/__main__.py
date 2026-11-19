"""Start the service: listen on 0.0.0.0 at $PORT (default 8080)."""

import os

from dossier.server.store import Store
from dossier.server.transport import Server


def main() -> None:
    port = int(os.environ.get("PORT", "8080"))
    server = Server(("0.0.0.0", port), Store())
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
