import concurrent.futures
import json
import os
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get('DOSSIER_URL', '').rstrip('/')
MOCK = os.environ.get('MOCK_URL', '').rstrip('/')
TOKEN = os.environ.get('MOCK_TOKEN', '')
NOW = '2026-03-01T09:00:00+00:00'
FIXTURE = {'now': NOW, 'users': [
    {'id': 'u_ada', 'email': 'Ada@example.test', 'password': 'correct horse', 'display_name': 'Ada'},
    {'id': 'u_bob', 'email': 'bob@example.test', 'password': 'correct horse', 'display_name': 'Bob'},
]}
FIELDS = {'legal_name', 'hq_city', 'ceo', 'founded_year', 'headcount_range', 'funding_total'}
MISSING = object()


def call(base, method, path, body=MISSING, headers=None, timeout=5):
    headers = dict(headers or {})
    if body is MISSING:
        data = None
    elif isinstance(body, bytes):
        data = body
        headers.setdefault('Content-Type', 'application/json')
    else:
        data = json.dumps(body).encode()
        headers.setdefault('Content-Type', 'application/json')
    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    start = time.monotonic()
    try:
        response = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        raw = response.read()
        elapsed = time.monotonic() - start
        try:
            result = json.loads(raw) if raw else None
        except (ValueError, UnicodeDecodeError):
            result = raw.decode(errors='replace')
        return response.status, result, response.headers, elapsed


class Acceptance(unittest.TestCase):
    def setUp(self):
        if not BASE or not MOCK or not TOKEN:
            self.fail('Set DOSSIER_URL, MOCK_URL and MOCK_TOKEN for a dedicated test instance')
        self.assertEqual(self.mock('POST', '/_mock/reset', {'epoch': 0})[0], 204)
        self.assertEqual(self.api('POST', '/_test/reset', FIXTURE, timeout=10)[0], 204)
        self.ada = self.login('Ada@example.test')['token']
        self.bob = self.login('bob@example.test')['token']

    def api(self, method, path, body=MISSING, token=None, key=None, timeout=5, headers=None):
        h = dict(headers or {})
        if token is not None:
            h['Authorization'] = 'Bearer ' + token
        if key is not None:
            h['Idempotency-Key'] = key
        return call(BASE, method, path, body, h, timeout)

    def mock(self, method, path, body=MISSING):
        return call(MOCK, method, path, body, {'X-Mock-Admin': TOKEN}, 10)

    def login(self, email, password='correct horse'):
        status, body, _, _ = self.api('POST', '/auth/login', {'email': email, 'password': password})
        self.assertEqual(status, 200, body)
        return body

    def err(self, response, status, code):
        self.assertEqual(response[0], status, response[1])
        self.assertIsInstance(response[1], dict)
        self.assertEqual(response[1].get('error', {}).get('code'), code, response[1])
        self.assertIsInstance(response[1]['error'].get('message'), str)

    def create(self, domain='acme-robotics.test', key='create', token=None):
        return self.api('POST', '/dossiers', {'domain': domain}, token or self.ada, key)

    def get(self, domain='acme-robotics.test', token=None):
        return self.api('GET', '/dossiers/' + urllib.parse.quote(domain, safe=''), token=token or self.ada)

    def ready(self, domain='acme-robotics.test', timeout=10):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            result = self.get(domain)
            self.assertEqual(result[0], 200, result[1])
            if result[1]['state'] != 'building':
                return result[1]
            time.sleep(.05)
        self.fail('Build did not complete in %.1f seconds' % timeout)

    def log(self):
        response = self.mock('GET', '/_mock/log')
        self.assertEqual(response[0], 200)
        return response[1]['calls']

    def burst(self, fn, count=50):
        with concurrent.futures.ThreadPoolExecutor(max_workers=count) as pool:
            return list(pool.map(fn, range(count)))
