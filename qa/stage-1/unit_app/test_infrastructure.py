"""Infrastructure tests for the deliverable and its runtime limits (RL27.4).

Index of claimed ids covered in this module:
    R1.6 -> test_r1_6_deliverables_build_and_start_with_documented_commands
    R1.7 -> test_r1_7_image_is_self_contained_and_serves_http
    R1.8 -> test_r1_8_image_takes_its_port_from_the_environment_and_publishes_it
    R1.11 -> test_r1_11_dockerfile_installs_webrouter_with_the_extras
    R1.14 -> test_r1_14_hashing_uses_two_worker_threads_and_no_processes
    R1.15 -> test_r1_15_health_answers_within_five_seconds_of_start
    R1.16 -> test_r1_16_fifty_concurrent_requests_succeed_within_the_limit
    R1.19 -> test_r1_19_no_write_is_required_outside_memory
    R1.21 -> test_r1_21_binds_all_interfaces_on_port_or_8080

Run from the repository root:  PYTHONPATH=stage-1 python3 -m unittest discover -s qa/stage-1/unit_app -t qa/stage-1/unit_app
"""

import http.client
import inspect
import os
import pathlib
import re
import socket
import tempfile
import threading
import time
import unittest

from app import __main__ as entry
from app import passwords
from app.app import App
from app.clock import Clock
from app.server import make_server

STAGE = pathlib.Path(__file__).resolve().parents[3] / "stage-1"
APP_DIR = STAGE / "app"
WEBROUTER_PIP = 'pip install "webrouter[search,extract,research]>=0.12.0"'


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def start_server(port: int = 0):
    server = make_server("127.0.0.1", port, App(Clock()))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def health(port: int) -> int:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    connection.request("GET", "/health")
    status = connection.getresponse().status
    connection.close()
    return status


class InfrastructureTests(unittest.TestCase):
    def test_r1_6_deliverables_build_and_start_with_documented_commands(self):
        """Covers R1.6: a Dockerfile and RUN.md with build and run commands that need no placeholders."""
        self.assertTrue((STAGE / "Dockerfile").is_file())
        run_md = (STAGE / "RUN.md").read_text(encoding="utf-8")
        commands = [line.strip() for line in run_md.splitlines() if line.strip().startswith("docker ")]
        self.assertTrue(any(c.startswith("docker build") for c in commands), commands)
        self.assertTrue(any(c.startswith("docker run") for c in commands), commands)
        for command in commands:
            self.assertNotRegex(command, r"[<>\[\]{}]", f"placeholder in: {command}")

    def test_r1_7_image_is_self_contained_and_serves_http(self):
        """Covers R1.7: the image starts the HTTP service itself; it does not import or run host files."""
        dockerfile = (STAGE / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn('CMD ["python", "-m", "app"]', dockerfile)
        self.assertEqual(re.findall(r"^(?:COPY|ADD)\s+(.*)$", dockerfile, re.MULTILINE), ["requirements.txt ./", ". ./"])
        self.assertTrue((APP_DIR / "__main__.py").is_file())

    def test_r1_8_image_takes_its_port_from_the_environment_and_publishes_it(self):
        """Covers R1.8: the image reads PORT, exposes it, and RUN.md maps it with -e PORT and -p."""
        dockerfile = (STAGE / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("PORT=8080", dockerfile)
        self.assertIn("EXPOSE 8080", dockerfile)
        run_md = (STAGE / "RUN.md").read_text(encoding="utf-8")
        self.assertIn("-e PORT=", run_md)
        self.assertRegex(run_md, r"-p \d+:\d+")

    def test_r1_11_dockerfile_installs_webrouter_with_the_extras(self):
        """Covers R1.11: the Dockerfile installs webrouter with its extras; requirements.txt lists webrouter>=0.12.0."""
        self.assertIn(WEBROUTER_PIP, (STAGE / "Dockerfile").read_text(encoding="utf-8"))
        self.assertIn("webrouter>=0.12.0", (STAGE / "requirements.txt").read_text(encoding="utf-8"))

    def test_r1_14_hashing_uses_two_worker_threads_and_no_processes(self):
        """Covers R1.14: the CPU budget is 2 vCPU; fixture hashing uses 2 threads and the service starts no processes."""
        source = inspect.getsource(passwords.hash_fixture_passwords)
        self.assertIn("max_workers=2", source)
        for path in APP_DIR.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("multiprocessing", text, path.name)
            self.assertNotIn("ProcessPool", text, path.name)

    def test_r1_15_health_answers_within_five_seconds_of_start(self):
        """Covers R1.15: the server answers /health within 5 s of starting."""
        started = time.monotonic()
        server = start_server()
        try:
            port = server.server_address[1]
            self.assertEqual(health(port), 200)
            self.assertLess(time.monotonic() - started, 5.0)
        finally:
            server.shutdown()
            server.server_close()

    def test_r1_16_fifty_concurrent_requests_succeed_within_the_limit(self):
        """Covers R1.16: 50 requests in flight all succeed, each well within its 5 s limit."""
        server = start_server()
        port = server.server_address[1]
        results: list[tuple[int, float]] = []
        lock = threading.Lock()

        def one():
            begun = time.monotonic()
            status = health(port)
            with lock:
                results.append((status, time.monotonic() - begun))

        try:
            threads = [threading.Thread(target=one) for _ in range(50)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(30)
            self.assertEqual(len(results), 50)
            self.assertTrue(all(status == 200 for status, _ in results))
            self.assertLess(max(elapsed for _, elapsed in results), 5.0)
        finally:
            server.shutdown()
            server.server_close()

    def test_r1_19_no_write_is_required_outside_memory(self):
        """Covers R1.19: the service writes nothing to disk; a full session runs with a read-only working directory."""
        previous = os.getcwd()
        with tempfile.TemporaryDirectory() as scratch:
            os.chmod(scratch, 0o555)  # read and search only: the service must not need to create files here
            os.chdir(scratch)
            try:
                app = App(Clock())
                reset = app.handle("POST", "/_test/reset", {}, b'{"now":"2026-03-01T09:00:00+00:00","users":[]}')
                self.assertEqual(reset.status, 204)
                signup = app.handle("POST", "/auth/signup", {}, b'{"email":"a@example.test","password":"longenough","display_name":"A"}')
                self.assertEqual(signup.status, 201)
                self.assertEqual(app.handle("GET", "/_test/export", {}, b"").status, 200)
                self.assertEqual(os.listdir(scratch), [])
            finally:
                os.chdir(previous)
                os.chmod(scratch, 0o755)

    def test_r1_21_binds_all_interfaces_on_port_or_8080(self):
        """Covers R1.21: binds 0.0.0.0 on PORT; with PORT unset the default is 8080 (two instances, both served)."""
        saved = os.environ.pop("PORT", None)
        servers = []
        try:
            self.assertEqual(entry._port(), 8080)
            configured = free_port()
            os.environ["PORT"] = str(configured)
            self.assertEqual(entry._port(), configured)
            servers.append(make_server("0.0.0.0", entry._port(), App(Clock())))
            self.assertIn('"0.0.0.0"', inspect.getsource(entry.main))
            os.environ.pop("PORT", None)
            servers.append(make_server("0.0.0.0", entry._port(), App(Clock())))  # 8080; a busy port fails the test
            for server in servers:
                threading.Thread(target=server.serve_forever, daemon=True).start()
            self.assertEqual([server.server_address[0] for server in servers], ["0.0.0.0", "0.0.0.0"])
            self.assertEqual(health(configured), 200)
            self.assertEqual(health(8080), 200)
        finally:
            for server in servers:
                server.shutdown()
                server.server_close()
            if saved is None:
                os.environ.pop("PORT", None)
            else:
                os.environ["PORT"] = saved
