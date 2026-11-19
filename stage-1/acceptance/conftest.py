"""Black-box Docker and mock-web fixtures. No product modules are imported."""
import os
import re
import shutil
import socket
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

import pytest
import requests

from long_examples import write_fixtures

STAGE = Path(os.environ.get("DOSSIER_STAGE", Path(__file__).resolve().parents[1])).resolve()
WEB = Path(os.environ.get("DOSSIER_MOCK", "/home/ndivij/buildathon/sf-buildathon-2026/challenges/dossier/web")).resolve()
CORPUS = Path(os.environ.get("DOSSIER_CORPUS", WEB / "corpus/sample")).resolve()
RESOURCE_PREFIX = os.environ.get("DOSSIER_RESOURCE_PREFIX", "prover").rstrip("-")
PORT_MIN = int(os.environ.get("DOSSIER_PORT_MIN", "18200"))
PORT_MAX = int(os.environ.get("DOSSIER_PORT_MAX", "18299"))
if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]*", RESOURCE_PREFIX):
    raise ValueError("DOSSIER_RESOURCE_PREFIX must be a Docker-compatible lowercase name")
if not 1 <= PORT_MIN < PORT_MAX <= 65535:
    raise ValueError("DOSSIER_PORT_MIN and DOSSIER_PORT_MAX must specify at least two valid ports")
NOW = "2026-03-01T09:00:00+00:00"
SEED = {"now": NOW, "users": [
    {"id": "u_ada", "email": "ada@example.com", "password": "correct horse", "display_name": "Ada"},
    {"id": "u_bob", "email": "bob@example.com", "password": "correct horse", "display_name": "Bob"},
]}


def docker(*args, timeout=60, check=True):
    return subprocess.run(["docker", *map(str, args)], check=check, timeout=timeout,
                          text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def free_port(exclude=()):
    for port in range(PORT_MIN, PORT_MAX + 1):
        if port in exclude:
            continue
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port in {PORT_MIN}-{PORT_MAX}")


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
    tag = RESOURCE_PREFIX + "-" + uuid.uuid4().hex[:10]
    network, ingress = tag + "-net", tag + "-ingress"
    mock_name, api_name, proxy_name = tag + "-web", tag + "-api", tag + "-proxy"
    mock_image, api_image = tag + "-web-image", tag + "-api-image"
    api_port = free_port()
    mock_port = free_port((api_port,))
    corpus_copy = tempfile.TemporaryDirectory(prefix=RESOURCE_PREFIX + "-corpus-")
    try:
        shutil.copytree(CORPUS, corpus_copy.name, dirs_exist_ok=True)
        for fixture in Path(__file__).parent.glob("*.test.json"):
            shutil.copyfile(fixture, Path(corpus_copy.name) / fixture.name)
        write_fixtures(corpus_copy.name)
        for image, path in ((mock_image, WEB), (api_image, STAGE)):
            lock = [] if os.environ.get("DOSSIER_LOCK_HELD") == "1" else ["flock", "/tmp/factory-heavy.lock"]
            subprocess.run([*lock, "docker", "build", "-t", image, str(path)],
                           check=True, timeout=900)
        docker("network", "create", "--internal", network)
        docker("network", "create", ingress)
        docker("run", "-d", "--name", mock_name, "--network", network,
               "-e", "MOCK_ADMIN_TOKEN=prover-local",
               "-v", f"{corpus_copy.name}:/data/corpus:ro", mock_image)
        # This relay accepts only two fixed destinations. The service stays on the
        # internal network; only the relay has an ingress network and published ports.
        relay = '''import select, socket, socketserver, threading
class Handler(socketserver.BaseRequestHandler):
 def handle(self):
  try:
   peer = socket.create_connection((self.server.destination, 8080), timeout=5)
   sockets = [self.request, peer]
   while True:
    ready, _, _ = select.select(sockets, [], [], 60)
    if not ready: break
    for source in ready:
     data = source.recv(65536)
     if not data: return
     (peer if source is self.request else self.request).sendall(data)
  except OSError: pass
  finally:
   if 'peer' in locals(): peer.close()
class Server(socketserver.ThreadingTCPServer):
 allow_reuse_address = True
 daemon_threads = True
for port, dest in [(8081, %r), (8082, %r)]:
 server = Server(('', port), Handler)
 server.destination = dest
 threading.Thread(target=server.serve_forever, daemon=True).start()
threading.Event().wait()
''' % (mock_name, api_name)
        docker("run", "-d", "--name", proxy_name, "--network", ingress,
               "-p", f"127.0.0.1:{mock_port}:8081", "-p", f"127.0.0.1:{api_port}:8082",
               "--entrypoint", "python3", mock_image, "-u", "-c", relay)
        docker("network", "connect", network, proxy_name)
        healthy(f"http://127.0.0.1:{mock_port}/_mock/health")
        docker("run", "-d", "--name", api_name, "--network", network,
               "--cpus", "2", "--memory", "3g",
               "-e", "PORT=8080", "-e", "NIMBLE_API_KEY=local", "-e", f"NIMBLE_BASE_URL=http://{mock_name}:8080/nimble",
               api_image)
        healthy(f"http://127.0.0.1:{api_port}/health")
        yield System(f"http://127.0.0.1:{api_port}", f"http://127.0.0.1:{mock_port}")
    finally:
        for name in (api_name, mock_name, proxy_name):
            docker("rm", "-f", name, check=False)
        docker("network", "rm", network, check=False)
        docker("network", "rm", ingress, check=False)
        for image in (api_image, mock_image):
            docker("image", "rm", image, check=False)
        corpus_copy.cleanup()


@pytest.fixture
def client(system):
    response = system.request("POST", "/_test/reset", json=SEED, timeout=10)
    assert response.status_code == 204, response.text
    system.control("reset", {"epoch": 0})
    return system
