"""Black-box Docker and mock-web fixtures. No product modules are imported."""
import os
import socket
import subprocess
import time
import uuid
from pathlib import Path

import pytest
import requests

STAGE = Path(os.environ.get("DOSSIER_STAGE", Path(__file__).resolve().parents[1])).resolve()
WEB = Path(os.environ.get("DOSSIER_MOCK", "/home/ndivij/buildathon/sf-buildathon-2026/challenges/dossier/web")).resolve()
CORPUS = Path(os.environ.get("DOSSIER_CORPUS", WEB / "corpus/sample")).resolve()
NOW = "2026-03-01T09:00:00+00:00"
SEED = {"now": NOW, "users": [
    {"id": "u_ada", "email": "ada@example.com", "password": "correct horse", "display_name": "Ada"},
    {"id": "u_bob", "email": "bob@example.com", "password": "correct horse", "display_name": "Bob"},
]}


def docker(*args, timeout=60, check=True):
    return subprocess.run(["docker", *map(str, args)], check=check, timeout=timeout,
                          text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def free_port(exclude=()):
    for port in range(18200, 18300):
        if port in exclude:
            continue
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No free port in 18200-18299")


def healthy(url, seconds=60):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            if requests.get(url, timeout=1).status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(.1)
    raise AssertionError(f"{url} was not healthy within {seconds}s")


class System:
    def __init__(self, api, mock):
        self.api = api
        self.mock = mock
        self.admin = {"X-Mock-Admin": "prover-local"}

    def request(self, method, path, **kwargs):
        return requests.request(method, self.api + path, timeout=kwargs.pop("timeout", 5), **kwargs)

    def control(self, path, data):
        response = requests.post(self.mock + "/_mock/" + path, headers=self.admin, json=data, timeout=5)
        assert response.status_code == 204, response.text

    def calls(self):
        response = requests.get(self.mock + "/_mock/log", headers=self.admin, timeout=5)
        response.raise_for_status()
        return response.json()["calls"]

    def login(self, email="ada@example.com"):
        response = self.request("POST", "/auth/login", json={"email": email, "password": "correct horse"})
        assert response.status_code == 200, response.text
        return response.json()["token"]

    def auth(self, token, key=None):
        headers = {"Authorization": "Bearer " + token}
        if key is not None:
            headers["Idempotency-Key"] = key
        return headers

    def finish(self, domain, token, seconds=10):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            response = self.request("GET", "/dossiers/" + domain, headers=self.auth(token))
            assert response.status_code == 200, response.text
            result = response.json()
            if result["state"] != "building":
                return result
            time.sleep(.05)
        raise AssertionError(f"{domain} still building after {seconds}s")


@pytest.fixture(scope="session")
def system():
    """R1.7 R1.8 R1.14 R1.15 R1.18 R1.20 R1.21 RL1.14."""
    tag = "prover-" + uuid.uuid4().hex[:10]
    network, mock_name, api_name = tag + "-net", tag + "-web", tag + "-api"
    mock_image, api_image = tag + "-web-image", tag + "-api-image"
    api_port = free_port()
    mock_port = free_port((api_port,))
    try:
        for image, path in ((mock_image, WEB), (api_image, STAGE)):
            subprocess.run(["flock", "/tmp/factory-heavy.lock", "docker", "build", "-t", image, str(path)],
                           check=True, timeout=900)
        docker("network", "create", "--internal", network)
        docker("run", "-d", "--name", mock_name, "--network", network,
               "-p", f"127.0.0.1:{mock_port}:8080", "-e", "MOCK_ADMIN_TOKEN=prover-local",
               "-v", f"{CORPUS}:/data/corpus:ro", mock_image)
        healthy(f"http://127.0.0.1:{mock_port}/_mock/health")
        docker("run", "-d", "--name", api_name, "--network", network,
               "--cpus", "2", "--memory", "3g", "-p", f"127.0.0.1:{api_port}:8080",
               "-e", "PORT=8080", "-e", "NIMBLE_API_KEY=local", "-e", f"NIMBLE_BASE_URL=http://{mock_name}:8080/nimble",
               api_image)
        healthy(f"http://127.0.0.1:{api_port}/health")
        yield System(f"http://127.0.0.1:{api_port}", f"http://127.0.0.1:{mock_port}")
    finally:
        for name in (api_name, mock_name):
            docker("rm", "-f", name, check=False)
        docker("network", "rm", network, check=False)
        for image in (api_image, mock_image):
            docker("image", "rm", image, check=False)


@pytest.fixture
def client(system):
    system.control("reset", {"epoch": 0})
    response = system.request("POST", "/_test/reset", json=SEED, timeout=10)
    assert response.status_code == 204, response.text
    return system
