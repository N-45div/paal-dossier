"""Start the service: listen on 0.0.0.0 at $PORT (default 8080), with the WebRouter engine."""

import os

from dossier.engine import run_build
from dossier.server.service import make_service
from dossier.server.transport import Server


def main() -> None:
    port = int(os.environ.get("PORT", "8080"))
    server = Server(("0.0.0.0", port), make_service(run_build))
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
