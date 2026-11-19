"""Names, ports and paths for the builder-a integration stack."""
from __future__ import annotations

import os
from pathlib import Path

HANDLE = os.environ.get("HARNESS_HANDLE", "builder-a")
STAGE_DIR = Path(__file__).resolve().parents[2]
MOCK_CONTEXT = Path(
    os.environ.get("MOCK_WEB_DIR", "/home/ndivij/buildathon/sf-buildathon-2026/challenges/dossier/web")
)
CORPUS_DIR = Path(os.environ.get("MOCK_CORPUS_DIR", str(MOCK_CONTEXT / "corpus" / "sample")))

SERVICE_IMAGE = f"{HANDLE}-dossier-service"
MOCK_IMAGE = f"{HANDLE}-dossier-web"
NETWORK = f"{HANDLE}-net"
SERVICE_CONTAINER = f"{HANDLE}-svc"
MOCK_CONTAINER = f"{HANDLE}-web"

SERVICE_PORT = int(os.environ.get("HARNESS_SERVICE_PORT", "18010"))
MOCK_PORT = int(os.environ.get("HARNESS_MOCK_PORT", "18011"))
ADMIN_TOKEN = "local-admin"
HEAVY_LOCK = "/tmp/factory-heavy.lock"

FIXTURE_NOW = "2026-03-01T09:00:00+00:00"
USERS = [
    {"id": "u_ada", "email": "ada@example.com", "password": "correct horse", "display_name": "Ada"},
    {"id": "u_bob", "email": "bob@example.com", "password": "correct horse", "display_name": "Bob"},
]
