#!/usr/bin/env python3
"""Independent HTTP acceptance checks; never imports the deliverable."""
import concurrent.futures
import json
import os
import re
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from make_cases import CASES
from support_oracle import norm, prose, sentences, supports

BASE = os.environ['PROVER_URL']
DEST = os.environ.get('PROVER_DEST', BASE)
DEFAULT = os.environ.get('PROVER_DEFAULT', BASE)
MOCK = os.environ['PROVER_MOCK']
CORPUS = Path(os.environ['PROVER_CORPUS'])
FIELDS = ('legal_name', 'hq_city', 'ceo', 'founded_year', 'headcount_range', 'funding_total')
NOW = '2026-03-01T09:00:00+00:00'
FIXTURE = {'now': NOW, 'users': [
    {'id': 'u_ada', 'email': 'ada@example.test', 'password': 'correct horse', 'display_name': 'Ada'},
    {'id': 'u_bob', 'email': 'bob@example.test', 'password': 'correct horse', 'display_name': 'Bob'}]}


def request(base, method, path, body=None, token=None, key=None, raw=None, timeout=5, scheme='Bearer'):
    headers = {'Content-Type': 'application/json; charset=utf-8'}
    if token is not None:
        headers['Authorization'] = scheme + ' ' + token
    if key is not None:
        headers['Idempotency-Key'] = key
    if base == MOCK:
        headers['X-Mock-Admin'] = 'prover-local'
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    started = time.monotonic()
    try:
        response = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        content = response.read()
        try:
            obj = json.loads(content) if content else None
        except (ValueError, UnicodeDecodeError):
            obj = content.decode(errors='replace')
        return response.status, obj, time.monotonic() - started, {name.lower(): value for name, value in response.headers.items()}


def app(method, path, **kwargs):
    return request(BASE, method, path, **kwargs)


def mock(method, path, **kwargs):
    return request(MOCK, method, path, **kwargs)


def poll(domain, token, bound=15, reason='R1.83 M1.2'):
    deadline = time.monotonic() + bound
    last = None
    while time.monotonic() < deadline:
        status, last, _, _ = app('GET', '/dossiers/' + domain, token=token)
        if status == 200 and last['state'] != 'building':
            return last
        time.sleep(.05)
    raise AssertionError(reason + ': build did not finish: ' + repr(last))


class OracleSelfCheck(unittest.TestCase):
    def test_published_labels_and_spec_examples_R1_121_R1_129(self):
        key = json.loads((CORPUS / 'key.json').read_text())
        for domain, entry in key.items():
            for label in entry.get('supports', []):
                if label['field'] in FIELDS:
                    with self.subTest(domain=domain, label=label):
                        self.assertTrue(supports(domain, label['field'], label['value'], label['excerpt']))
        for domain, (text, expected) in CASES.items():
            for field, value in expected.items():
                with self.subTest(domain=domain, field=field):
                    self.assertTrue(any(supports(domain, field, value, s) for s in sentences(text)))
        self.assertFalse(supports('acme-robotics.test', 'funding_total', 40000000, 'Acme Robotics is reportedly in talks to raise $40M.'))
        self.assertFalse(supports('acme-robotics.test', 'hq_city', 'Porto', 'Acme Robotics opened a sales office in Porto.'))


class Acceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        elapsed = max(0, time.time() - float(os.environ.get('PROVER_START', time.time())))
        deadline = time.monotonic() + max(0, 60 - elapsed)
        while True:
            try:
                if (app('GET', '/health', timeout=1)[:2] == (200, {'status': 'ok'}) and
                    request(DEST, 'GET', '/health', timeout=1)[:2] == (200, {'status': 'ok'}) and
                    request(DEFAULT, 'GET', '/health', timeout=1)[:2] == (200, {'status': 'ok'})):
                    break
            except (OSError, TimeoutError):
                pass
            if time.monotonic() >= deadline:
                raise AssertionError('R1.13 R1.19 R1.20 M1.3 health not ready within 60s')
            time.sleep(.2)

    def setUp(self):
        self.assertEqual(app('POST', '/_test/reset', body=FIXTURE, timeout=10)[0], 204, 'R1.21')
        self.assertEqual(mock('POST', '/_mock/reset', body={'epoch': 0})[0], 204)
        status, data, _, _ = app('POST', '/auth/login', body={'email': 'ada@example.test', 'password': 'correct horse'})
        self.assertEqual(status, 200, 'R1.51 R1.60')
        self.assertEqual(data['user_id'], 'u_ada', 'R1.62')
        self.token = data['token']

    def error(self, response, status, code, ids):
        self.assertEqual(response[0], status, f'{ids}: {response[:2]}')
        self.assertIsInstance(response[1], dict, ids)
        self.assertEqual(response[1].get('error', {}).get('code'), code, ids)
        self.assertIsInstance(response[1]['error'].get('message'), str, ids)

    def create(self, domain='acme-robotics.test', key='create'):
        return app('POST', '/dossiers', body={'domain': domain}, token=self.token, key=key)

    def test_health_auth_and_reset_R1_19_R1_20_R1_21_R1_51_R1_52_R1_59_R1_60_R1_61_R1_62_R1_66_R1_67(self):
        self.assertEqual(app('GET', '/health')[:2], (200, {'status': 'ok'}))
        self.assertEqual(mock('GET', '/_mock/log')[1]['calls'], [], 'R1.20')
        for path in ('/dossiers', '/dossiers/example.test'):
            self.error(app('GET', path), 401, 'unauthenticated', 'R1.66')
        signup = {'email': 'NEW@Example.test', 'password': 'eight888', 'display_name': 'New'}
        result = app('POST', '/auth/signup', body=signup)
        self.assertEqual(result[0], 201, 'R1.59')
        self.assertLessEqual(len(result[1]['user_id']), 64, 'R1.33')
        self.error(app('POST', '/auth/signup', body=signup), 409, 'email_taken', 'R1.61 L1.07')
        login = app('POST', '/auth/login', body={'email': 'new@example.test', 'password': 'eight888'})
        self.assertEqual(login[0], 200, 'R1.60 L1.07')
        for token in (result[1]['token'], login[1]['token']):
            self.assertEqual(app('GET', '/dossiers', token=token)[0], 200, 'R1.67')
        self.assertEqual(app('GET', '/dossiers', token=self.token, scheme='bearer')[0], 200, 'L1.09')
        self.error(app('GET', '/dossiers', token=self.token, scheme='Basic'), 401, 'unauthenticated', 'R1.66 L1.09')
        for body in ({**signup, 'password': 'short'}, {**signup, 'display_name': '   '}, {**signup, 'email': 'a@@b'}):
            self.error(app('POST', '/auth/signup', body=body), 422, 'validation_failed', 'R1.61 L1.08')
        self.error(app('POST', '/auth/login', body={'email': 'new@example.test', 'password': 'wrong'}), 401, 'unauthenticated', 'R1.61')
        duplicate = {'now': NOW, 'users': FIXTURE['users'] + [{**FIXTURE['users'][0], 'email': 'ADA@EXAMPLE.TEST'}]}
        self.error(app('POST', '/_test/reset', body=duplicate), 422, 'validation_failed', 'R1.52')
        self.assertEqual(app('GET', '/dossiers', token=self.token)[0], 200, 'R1.52 atomic')
        self.assertEqual(app('POST', '/_test/reset', body=FIXTURE)[0], 204)
        self.error(app('GET', '/dossiers', token=self.token), 401, 'unauthenticated', 'R1.22')

    def test_default_port_R1_18(self):
        self.assertEqual(request(DEFAULT, 'GET', '/health')[:2], (200, {'status':'ok'}), 'R1.18')

    def test_clock_validation_R1_25_R1_26_R1_27_R1_28_R1_29_R1_30(self):
        for payload, status, code in [({}, 422, 'validation_failed'), ({'now': 42}, 400, 'malformed_request'),
                                      ({'now': '2026-03-01T09:00:00'}, 422, 'validation_failed'),
                                      ({'now': '2026-03-01T08:59:59+00:00'}, 422, 'validation_failed')]:
            self.error(app('POST', '/_test/clock', body=payload), status, code, 'R1.29 L1.05')
        self.assertEqual(app('POST', '/_test/clock', body={'now': NOW})[0], 204, 'L1.05')
        self.assertEqual(app('POST', '/_test/clock', body={'now': '2026-03-01T11:30:00+02:00'})[0], 204, 'R1.26')
        response = self.create('clock.test')
        self.assertEqual(response[0], 202)
        item = poll('clock.test', self.token)
        if item['state'] == 'ready':
            self.assertEqual(item['researched_at'], '2026-03-01T11:30:00+02:00', 'R1.25 R1.32 L1.05')

    def test_errors_precedence_R1_53_R1_54_R1_55_R1_56_R1_57_R1_78(self):
        self.error(app('POST', '/dossiers', raw=b'{'), 401, 'unauthenticated', 'R1.66 L1.02')
        self.error(app('POST', '/dossiers', raw=b'{', token=self.token), 400, 'malformed_request', 'L1.02')
        self.error(app('POST', '/dossiers', body={}, token=self.token), 400, 'missing_idempotency_key', 'L1.02')
        self.error(app('POST', '/dossiers', body={}, token=self.token, key='x'*256), 422, 'validation_failed', 'R1.57')
        self.error(app('POST', '/dossiers', body={'domain': 1}, token=self.token, key='x'), 400, 'malformed_request', 'R1.54')
        self.error(app('POST', '/dossiers', body={}, token=self.token, key='x'), 422, 'validation_failed', 'R1.89')
        self.assertEqual(self.create('sample.test', 'x')[0], 202, 'R1.73 failed key reusable')
        self.error(app('POST', '/dossiers', body={'domain': 1}, token=self.token, key='x'), 409, 'idempotency_key_reuse', 'R1.78')
        for param in ('limit=0', 'limit=201', 'limit=', 'limit=1e9', 'limit=4.0', 'limit=%2B4', 'offset=-1', 'offset='):
            self.error(app('GET', '/dossiers?' + param, token=self.token), 422, 'validation_failed', 'R1.56 R1.57')
        self.error(app('GET', '/unknown-route'), 404, 'not_found', 'L1.10')
        self.error(app('PUT', '/health'), 405, 'not_found', 'L1.10')
        poll('sample.test', self.token)

    def test_validation_boundaries_R1_21_R1_29_R1_33_R1_36_R1_51_R1_53_R1_55_R1_57_R1_61(self):
        for raw, status, code in [(b'{', 400, 'malformed_request'), (b'[]', 400, 'malformed_request'),
                                  (b'{}', 422, 'validation_failed'), (b'{"now":42}', 400, 'malformed_request')]:
            self.error(app('POST', '/_test/reset', raw=raw), status, code, 'R1.21 L1.06')
            self.assertEqual(app('GET', '/dossiers', token=self.token)[0], 200, 'R1.21 reset atomic')
        for key in ('x', 'x'*255):
            response = self.create('boundary.test', key)
            self.assertIn(response[0], (200, 202), 'R1.57')
        max_domain = '.'.join(['a'*63, 'b'*63, 'c'*63, 'd'*61])
        self.assertEqual(len(max_domain), 253)
        self.assertEqual(self.create(max_domain, 'max-domain')[0], 202, 'R1.36 maximum')
        self.error(self.create(max_domain + 'd', 'too-long'), 422, 'validation_failed', 'R1.36')
        for name, status, code in [('', 422, 'validation_failed'), (' '*2, 422, 'validation_failed'), ('x'*101, 422, 'validation_failed'), (123, 400, 'malformed_request')]:
            self.error(app('POST', '/auth/signup', body={'email':'fresh@example.test','password':'password','display_name':name}), status, code, 'R1.61')
        good = app('POST', '/auth/signup', body={'email':'fresh@example.test','password':'password','display_name':'x'*100,'ignored':True})
        self.assertEqual(good[0], 201, 'R1.33 R1.61')
        for email in ('no-at', '@host', 'local@', 'a@b@c', 'a b@c'):
            self.error(app('POST', '/auth/signup', body={'email':email,'password':'password','display_name':'Name'}), 422, 'validation_failed', 'R1.61 L1.07')
        for param in ('limit=1', 'limit=200', 'offset=0', 'offset=999999'):
            self.assertEqual(app('GET', '/dossiers?' + param, token=self.token)[0], 200, 'R1.57')
        poll('boundary.test', self.token)
        poll(max_domain, self.token)

    def test_reset_null_users_R1_21_R1_54(self):
        self.error(app('POST', '/_test/reset', body={'now':NOW,'users':None}), 400, 'malformed_request', 'R1.54')
        self.assertEqual(app('GET', '/dossiers', token=self.token)[0], 200, 'R1.21 invalid reset must not change state')

    def test_huge_query_digits_R1_56_R1_58(self):
        huge = '9' * 5000
        huge_offset = app('GET', '/dossiers?offset=' + huge, token=self.token)
        self.assertEqual(huge_offset[0], 200, f'R1.56 huge offset: {huge_offset[:2]}')
        self.assertEqual(huge_offset[1]['dossiers'], [], 'R1.56 huge offset')
        self.error(app('GET', '/dossiers?limit=' + huge, token=self.token), 422, 'validation_failed', 'R1.56 huge limit')

    def test_domains_and_idempotency_R1_35_R1_36_R1_37_R1_70_R1_71_R1_72_R1_73_R1_74_R1_75_R1_77(self):
        first = self.create(' WWW.Example.TEST. ', 'key')
        self.assertEqual(first[0], 202, 'R1.86')
        self.assertEqual(first[1]['domain'], 'example.test', 'R1.35')
        replay = app('POST', '/dossiers', body={'ignored': 'x', 'domain': ' WWW.Example.TEST. '}, token=self.token, key='key')
        self.assertEqual(replay[:2], (200, first[1]), 'R1.74')
        self.error(self.create('example.test', 'key'), 409, 'idempotency_key_reuse', 'R1.72')
        same = self.create('example.test', 'other')
        self.assertEqual(same[0], 200, 'R1.87')
        self.assertEqual(same[1]['dossier_id'], first[1]['dossier_id'], 'R1.37')
        bob = app('POST', '/auth/login', body={'email': 'bob@example.test', 'password': 'correct horse'})[1]['token']
        self.assertEqual(app('POST', '/dossiers', token=bob, key='key', body={'domain': 'example.test'})[0], 200, 'R1.71')
        for i, domain in enumerate(('localhost', '-a.test', 'a-.test', 'a..test', 'a'*64+'.test', 'http://a.test', 'a.test/path', 'a.test..')):
            self.error(self.create(domain, 'bad'+str(i)), 422, 'validation_failed', 'R1.36')
        self.error(app('GET', '/dossiers/-bad.test', token=self.token), 422, 'validation_failed', 'L1.04')
        self.error(app('GET', '/dossiers/missing.test', token=self.token), 404, 'not_found', 'R1.95a')
        poll('example.test', self.token)
        refresh = app('POST', '/dossiers/example.test/refresh', token=self.token, key='same', raw=b'ignored')
        self.assertEqual(refresh[0], 202, 'R1.106')
        retry = app('POST', '/dossiers/example.test/refresh', token=self.token, key='same', body={'anything': 1})
        self.assertEqual(retry[:2], (200, refresh[1]), 'R1.75')
        path_key = app('POST', '/dossiers/example.test/refresh', token=self.token, key='key')
        self.assertEqual(path_key[0], 202, 'R1.72 same key on a different path')
        alternate = app('POST', '/dossiers/EXAMPLE.TEST/refresh', token=self.token, key='key')
        self.assertEqual(alternate[0], 202, 'R1.72 raw path identity')
        self.assertEqual(self.create(' WWW.Example.TEST. ', 'key')[:2], (200, first[1]), 'R1.77')
        poll('example.test', self.token)

    def test_concurrent_writes_and_listing_R1_12_R1_58_R1_76_R1_80_R1_88_R1_109_R1_111_R1_112_R1_113(self):
        def send(i):
            return self.create('parallel.test', 'same' if i < 25 else 'key-'+str(i))
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as pool:
            replies = list(pool.map(send, range(50)))
        self.assertEqual(sum(r[0] == 202 for r in replies), 1, 'R1.76 R1.88')
        self.assertTrue(all(r[0] in (200, 202) and r[2] < 5 for r in replies), 'R1.58 M1.4')
        self.assertEqual(len({r[1]['dossier_id'] for r in replies}), 1, 'R1.88')
        self.assertTrue(all(r[1] == replies[0][1] for r in replies[:25]), 'R1.76')
        for domain in ('aaa.test', 'zzz.test'):
            self.assertEqual(self.create(domain, domain)[0], 202)
        result = app('GET', '/dossiers?limit=2&offset=0&ignored=1', token=self.token)[1]
        self.assertEqual([x['domain'] for x in result['dossiers']], ['aaa.test', 'parallel.test'], 'R1.112')
        self.assertTrue(result['has_more'], 'R1.113')
        self.assertEqual([x['domain'] for x in app('GET', '/dossiers?q=PARALLEL', token=self.token)[1]['dossiers']], ['parallel.test'], 'R1.111')
        self.assertEqual(app('GET', '/dossiers?offset=3', token=self.token)[1]['dossiers'], [], 'R1.113')
        for domain in ('aaa.test', 'parallel.test', 'zzz.test'):
            poll(domain, self.token)

    def test_conflicting_key_burst_R1_73_R1_76_R1_78_M1_4(self):
        def send(i):
            return self.create('left.test' if i % 2 else 'right.test', 'contended')
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as pool:
            replies = list(pool.map(send, range(50)))
        winner = [r for r in replies if r[0] == 202]
        self.assertEqual(len(winner), 1, 'R1.76')
        self.assertEqual(sum(r[0] == 200 for r in replies), 24, 'R1.73')
        self.assertEqual(sum(r[0] == 409 and r[1]['error']['code'] == 'idempotency_key_reuse' for r in replies), 25, 'R1.73 R1.78')
        self.assertTrue(all(r[2] < 5 for r in replies), 'M1.4')
        poll(winner[0][1]['domain'], self.token)

    def test_concurrent_refresh_R1_77_R1_80_R1_106_R1_107_R1_120a(self):
        domain = 'halvorsen-robotics.test'
        self.assertEqual(self.create(domain, 'first')[0], 202)
        before = poll(domain, self.token)
        self.assertEqual(before['state'], 'ready')
        self.assertEqual(mock('POST', '/_mock/reset', body={'epoch': 0})[0], 204)
        self.assertEqual(mock('POST', '/_mock/faults', body={'provider':'nimble','methods':['search','extract','research'],'mode':'delay','seconds':1})[0], 204)
        barrier = threading.Barrier(50)
        def refresh(i):
            barrier.wait(timeout=5)
            return app('POST', '/dossiers/' + domain + '/refresh', token=self.token, key='refresh-' + str(i))
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as pool:
            replies = list(pool.map(refresh, range(50)))
        self.assertTrue(all(r[0] == 202 and r[1]['state'] == 'building' and r[2] < 5 for r in replies), 'R1.106 M1.4')
        self.assertEqual(len({r[1]['dossier_id'] for r in replies}), 1, 'R1.80')
        after = poll(domain, self.token, bound=10)
        self.assertGreater(after['spent_units'], before['spent_units'], 'R1.107')
        calls = mock('GET', '/_mock/log')[1]['calls']
        self.assertEqual(sum(c['method'] == 'search' and c['query'] == domain and 200 <= c['status'] < 300 for c in calls), 1, 'R1.80 R1.44')
        replay = app('POST', '/dossiers/' + domain + '/refresh', token=self.token, key='refresh-0')
        self.assertEqual(replay[:2], (200, replies[0][1]), 'R1.77')
        self.assertEqual(mock('GET', '/_mock/log')[1]['calls'], calls, 'R1.77')

    def test_provider_error_preserves_last_ready_R1_58_R1_81_R1_143(self):
        domain = 'halvorsen-robotics.test'
        self.assertEqual(self.create(domain)[0], 202)
        before = poll(domain, self.token)
        self.assertEqual(before['state'], 'ready')
        self.assertEqual(mock('POST', '/_mock/reset', body={'epoch': 0})[0], 204)
        self.assertEqual(mock('POST', '/_mock/faults', body={'provider':'nimble','methods':['search','extract','research'],'mode':'error'})[0], 204)
        response = app('POST', '/dossiers/' + domain + '/refresh', token=self.token, key='failure')
        self.assertEqual(response[0], 202, 'R1.58')
        failed = poll(domain, self.token)
        self.assertEqual(failed['state'], 'failed', 'R1.81')
        self.assertEqual(failed['fields'], before['fields'], 'R1.81')
        self.assertEqual(failed['researched_at'], before['researched_at'], 'R1.93')
        self.assertEqual(failed['spent_units'], before['spent_units'], 'R1.143')
        self.assertTrue(mock('GET', '/_mock/log')[1]['calls'], 'Provider fault must actually be exercised')

    def test_provider_rate_limit_R1_58_R1_81_R1_83_R1_143(self):
        domain = 'halvorsen-robotics.test'
        self.assertEqual(mock('POST', '/_mock/faults', body={'provider':'nimble','methods':['search','extract','research'],'mode':'rate_limit'})[0], 204)
        started = time.monotonic()
        self.assertEqual(self.create(domain, 'throttle')[0], 202, 'R1.58')
        item = poll(domain, self.token, bound=10)
        self.assertLessEqual(time.monotonic() - started, 10, 'R1.83')
        calls = mock('GET', '/_mock/log')[1]['calls']
        self.assertTrue(any(c['status'] == 429 for c in calls), 'Rate-limit fault must be exercised')
        self.assertTrue(all(c['cost'] == 0 for c in calls if c['status'] == 429), 'R1.143')
        self.assertEqual(item['spent_units'], sum(c['cost'] for c in calls), 'R1.143')
        if any(200 <= c['status'] < 300 for c in calls):
            self.assertEqual(item['state'], 'ready', 'R1.81')
        elif all(c['status'] == 429 for c in calls):
            self.assertEqual(item['state'], 'failed', 'R1.81')

    def test_export_import_R1_114_R1_115_R1_116_R1_117_R1_118_R1_119(self):
        original = self.create('snapshot.test', 'snapshot')
        self.assertEqual(original[0], 202)
        before = poll('snapshot.test', self.token)
        snapshot = app('GET', '/_test/export', timeout=10)
        self.assertEqual(snapshot[0], 200, 'R1.114')
        self.assertEqual(snapshot[1]['track'], 'dossier')
        self.assertEqual(snapshot[1]['format_version'], 1)
        self.assertIsInstance(snapshot[1]['state'], dict)
        destination_fixture = {'now':'2027-01-01T00:00:00+00:00', 'users':[{'id':'u_old','email':'old@example.test','password':'password-old','display_name':'Old'}]}
        self.assertEqual(request(DEST, 'POST', '/_test/reset', body=destination_fixture, timeout=10)[0], 204)
        old_token = request(DEST, 'POST', '/auth/login', body={'email':'old@example.test','password':'password-old'})[1]['token']
        calls_before = len(mock('GET', '/_mock/log')[1]['calls'])
        self.assertEqual(request(DEST, 'POST', '/_test/import', body=snapshot[1], timeout=10)[0], 204, 'R1.115 cross-process')
        self.assertEqual(len(mock('GET', '/_mock/log')[1]['calls']), calls_before, 'R1.118 cross-process import')
        self.assertEqual(request(DEST, 'GET', '/dossiers/snapshot.test', token=self.token)[1], before, 'R1.117 cross-process')
        self.error(request(DEST, 'GET', '/dossiers', token=old_token), 401, 'unauthenticated', 'R1.119 destination credentials removed')
        self.assertEqual(request(DEST, 'POST', '/auth/login', body={'email':'ada@example.test','password':'correct horse'})[0], 200, 'R1.117 imported login')
        self.error(request(DEST, 'POST', '/_test/clock', body={'now':'2026-12-31T23:59:59+00:00'}), 422, 'validation_failed', 'R1.119 import preserves destination clock')
        replay = request(DEST, 'POST', '/dossiers', body={'domain': 'snapshot.test'}, token=self.token, key='snapshot')
        self.assertEqual(replay[:2], (200, original[1]), 'R1.117 cross-process retry')
        self.error(request(DEST, 'POST', '/_test/import', body={'track': 'dossier', 'format_version': 1, 'state': {}}, timeout=10), 422, 'validation_failed', 'R1.116')
        self.assertEqual(request(DEST, 'GET', '/dossiers/snapshot.test', token=self.token)[1], before, 'R1.116 atomic')
        self.assertEqual(app('POST', '/_test/reset', body={'now': NOW})[0], 204)
        for bad in ({}, {'track': 'wrong', 'format_version': 1, 'state': {}}, {'track': 'dossier', 'format_version': True, 'state': {}}):
            self.error(app('POST', '/_test/import', body=bad, timeout=10), 422, 'validation_failed', 'R1.116')
        calls = len(mock('GET', '/_mock/log')[1]['calls'])
        for _ in range(2):
            self.assertEqual(app('POST', '/_test/import', body=snapshot[1], timeout=10)[0], 204, 'R1.115')
        self.assertEqual(len(mock('GET', '/_mock/log')[1]['calls']), calls, 'R1.118')
        self.assertEqual(app('GET', '/dossiers/snapshot.test', token=self.token)[1], before, 'R1.117')
        self.assertEqual(self.create('snapshot.test', 'snapshot')[:2], (200, original[1]), 'R1.117')
        login = app('POST', '/auth/login', body={'email': 'ada@example.test', 'password': 'correct horse'})
        self.assertEqual(login[0], 200, 'R1.117')

    def test_refresh_replaces_state_and_snapshot_R1_79_R1_90_R1_91_R1_93_R1_94_R1_107_R1_110_R1_120(self):
        self.assertEqual(self.create('halvorsen-robotics.test', 'initial')[0], 202)
        before = poll('halvorsen-robotics.test', self.token)
        self.assertEqual(before['state'], 'ready')
        self.assertEqual(before['researched_at'], NOW, 'R1.79 R1.93')
        listed = app('GET', '/dossiers', token=self.token)[1]['dossiers'][0]
        self.assertEqual(listed['legal_name'], before['fields']['legal_name']['value'], 'R1.110')
        mock('POST', '/_mock/faults', body={'provider': 'nimble', 'methods': ['search', 'extract', 'research'], 'mode': 'delay', 'seconds': 1})
        self.assertEqual(app('POST', '/_test/clock', body={'now': '2026-03-01T10:00:00+00:00'})[0], 204)
        started = time.monotonic()
        self.assertEqual(app('POST', '/dossiers/halvorsen-robotics.test/refresh', token=self.token, key='refresh')[0], 202)
        during = app('GET', '/dossiers/halvorsen-robotics.test', token=self.token)[1]
        self.assertEqual(during['state'], 'building', 'R1.91')
        self.assertEqual(during['fields'], before['fields'], 'R1.92')
        snap = app('GET', '/_test/export', timeout=10)[1]
        after = poll('halvorsen-robotics.test', self.token, bound=10)
        self.assertLess(time.monotonic() - started, 10, 'M1.2')
        self.assertEqual(after['researched_at'], '2026-03-01T10:00:00+00:00', 'R1.79')
        self.assertGreater(after['spent_units'], before['spent_units'], 'R1.107')
        self.assertEqual(app('POST', '/_test/import', body=snap, timeout=10)[0], 204)
        self.assertEqual(app('GET', '/dossiers/halvorsen-robotics.test', token=self.token)[1], before, 'R1.120 L1.15')

    def test_contract_misc_R1_24_R1_31_R1_34_R1_68_R1_108(self):
        response = app('GET', '/health')
        self.assertEqual(response[3].get('content-type', '').lower(), 'application/json; charset=utf-8', 'R1.31')
        bob = app('POST', '/auth/login', body={'email':'bob@example.test','password':'correct horse'})[1]['token']
        self.error(app('POST', '/dossiers/missing.test/refresh', token=bob, key='unknown'), 404, 'not_found', 'R1.108')
        self.assertEqual(self.create('shared.test')[0], 202)
        self.assertEqual(app('GET', '/dossiers/shared.test', token=bob)[0], 200, 'R1.34')
        poll('shared.test', self.token)
        snapshot = app('GET', '/_test/export', timeout=10)[1]
        self.assertNotIn('correct horse', json.dumps(snapshot), 'R1.68: plaintext password present in export')

    def test_faults_and_inflight_export_R1_23_R1_81_R1_92_R1_120(self):
        mock('POST', '/_mock/faults', body={'provider': 'nimble', 'methods': ['search', 'extract', 'research'], 'mode': 'delay', 'seconds': 1})
        started = time.monotonic()
        self.assertEqual(self.create('inflight.test', 'first')[0], 202)
        self.assertEqual(app('GET', '/dossiers/inflight.test', token=self.token)[1]['state'], 'building', 'R1.91: delay fixture did not hold the build open')
        snapshot = app('GET', '/_test/export', timeout=10)
        self.assertEqual(snapshot[0], 200)
        self.assertEqual(app('POST', '/_test/import', body=snapshot[1], timeout=10)[0], 204)
        restored = app('GET', '/dossiers/inflight.test', token=self.token)[1]
        self.assertEqual(restored['state'], 'failed', 'R1.120')
        self.assertEqual(restored['spent_units'], 0, 'L1.15')
        self.assertTrue(all(x == {'value': None, 'status': 'unknown', 'citations': []} for x in restored['fields'].values()), 'R1.92 R1.120')
        time.sleep(max(0, 10.5 - (time.monotonic() - started)))
        self.assertEqual(app('GET', '/dossiers/inflight.test', token=self.token)[1], restored, 'L1.14')
        mock('POST', '/_mock/reset', body={'epoch': 0})
        mock('POST', '/_mock/faults', body={'provider': 'nimble', 'methods': ['search', 'extract', 'research'], 'mode': 'error'})
        self.assertEqual(self.create('failure.test', 'failure')[0], 202, 'R1.58')
        failed = poll('failure.test', self.token)
        self.assertEqual(failed['state'], 'failed', 'R1.81 L1.13')

    def test_reset_during_build_R1_22_R1_23(self):
        domain = 'halvorsen-robotics.test'
        mock('POST', '/_mock/faults', body={'provider':'nimble','methods':['search','extract','research'],'mode':'delay','seconds':1})
        started = time.monotonic()
        self.assertEqual(self.create(domain, 'before-reset')[0], 202)
        self.assertEqual(app('GET', '/dossiers/' + domain, token=self.token)[1]['state'], 'building', 'R1.23 requires delayed build')
        time.sleep(.2)
        self.assertEqual(app('POST', '/_test/reset', body=FIXTURE, timeout=10)[0], 204)
        self.error(app('GET', '/dossiers/' + domain, token=self.token), 401, 'unauthenticated', 'R1.22')
        self.token = app('POST', '/auth/login', body={'email':'ada@example.test','password':'correct horse'})[1]['token']
        mock('POST', '/_mock/faults', body={'provider':'nimble','methods':['search','extract','research'],'mode':'error'})
        self.assertEqual(self.create(domain, 'before-reset')[0], 202, 'R1.22 key cleared')
        after_reset = poll(domain, self.token)
        self.assertEqual(after_reset['state'], 'failed')
        time.sleep(max(0, 10.5 - (time.monotonic() - started)))
        self.assertEqual(app('GET', '/dossiers/' + domain, token=self.token)[1], after_reset, 'R1.23 old build changed new state')

    def test_delay_budget_R1_83_R1_100_R1_148_M1_1_M1_2(self):
        mock('POST', '/_mock/faults', body={'provider': 'nimble', 'methods': ['search', 'extract', 'research'], 'mode': 'delay', 'seconds': 1})
        started = time.monotonic()
        self.assertEqual(self.create('halvorsen-robotics.test')[0], 202)
        item = poll('halvorsen-robotics.test', self.token, bound=10)
        self.assertLessEqual(time.monotonic() - started, 10, 'R1.83 M1.2')
        log = mock('GET', '/_mock/log')[1]['calls']
        self.assertTrue(log, 'M1.2 requires at least one delayed provider call')
        cost = sum(call['cost'] for call in log)
        self.assertLessEqual(cost, 80, 'R1.02 R1.148 M1.1')
        self.assertEqual(item['spent_units'], cost, 'R1.94 R1.141')

    def test_five_second_search_L1_25_R1_84(self):
        domain = 'halvorsen-robotics.test'
        self.assertEqual(mock('POST', '/_mock/faults', body={'provider':'nimble','methods':['search'],'mode':'delay','seconds':5})[0], 204)
        started = time.monotonic()
        response = self.create(domain, 'slow')
        self.assertEqual(response[0], 202)
        self.assertLess(response[2], 5, 'R1.15')
        item = poll(domain, self.token, bound=300, reason='INCONCLUSIVE: slow-provider harness wait expired')
        calls = mock('GET', '/_mock/log')[1]['calls']
        self.assertTrue(any(c['method'] == 'search' and c['query'] == domain and 200 <= c['status'] < 300 for c in calls), 'L1.25 5-second search abandoned')
        self.assertGreaterEqual(time.monotonic() - started, 5, 'L1.25 delayed answer was not awaited')
        self.assertEqual(item['state'], 'ready', 'R1.81')

    def test_controlled_support_R1_49_R1_50_R1_121_R1_122_R1_123_R1_124_R1_125_R1_126_R1_127_R1_128_R1_129_R1_130_R1_131_R1_132_R1_133_R1_134_R1_135_R1_136_R1_137_R1_138_R1_139_R1_140(self):
        for domain, (prose, expected) in CASES.items():
            with self.subTest(domain=domain):
                self.assertEqual(self.create(domain, domain)[0], 202)
                item = poll(domain, self.token)
                self.assertEqual(item['state'], 'ready')
                for field in FIELDS:
                    actual = item['fields'][field]
                    value = expected.get(field)
                    self.assertEqual(actual['value'], value, f'Appendix A {domain} {field}: {prose}')
                    if value is None:
                        self.assertEqual(actual['status'], 'unknown')
                        self.assertEqual(actual['citations'], [])
                    else:
                        self.assertEqual(actual['status'], 'known')
                        self.assertTrue(actual['citations'])
                        for citation in actual['citations']:
                            self.assertEqual(citation['url'], 'https://' + domain + '/about')
                            self.assertIn(' '.join(citation['excerpt'].split()), ' '.join(prose.split()))

    def test_corpus_R1_01a_R1_06_R1_38_R1_39_R1_40_R1_41_R1_42_R1_44_R1_45_R1_46_R1_47_R1_48_R1_82_R1_141_R1_149_M1_5(self):
        key = json.loads((CORPUS / 'key.json').read_text())
        all_costs = []
        for domain, entry in sorted(key.items()):
            with self.subTest(domain=domain):
                self.assertEqual(mock('POST', '/_mock/reset', body={'epoch': 0})[0], 204)
                start = self.create(domain, domain)
                self.assertEqual(start[0], 202, 'R1.86')
                item = poll(domain, self.token)
                self.assertEqual(item['state'], 'ready', 'R1.06')
                self.assertEqual(item['domain'], domain)
                self.assertEqual(set(item['fields']), set(FIELDS), 'R1.38 R1.92')
                calls = mock('GET', '/_mock/log')[1]['calls']
                cost = sum(call['cost'] for call in calls)
                all_costs.append(cost)
                self.assertLessEqual(cost, 80, 'R1.02 R1.148 M1.1')
                self.assertEqual(item['spent_units'], cost, 'R1.94 R1.141')
                domain_searches = [c for c in calls if c['method'] == 'search' and c['query'] == domain and 200 <= c['status'] < 300]
                self.assertEqual(len(domain_searches), 1, 'R1.44 L1.21')
                for call in calls:
                    if call['method'] == 'search':
                        self.assertLessEqual(len(call['served']), 10, 'R1.142')
                        if 200 <= call['status'] < 300:
                            prices = {'nimble': {'lite': 1, 'fast': 5, 'deep': 15}, 'tavily': {'lite': 8, 'fast': 16, 'deep': 16}}
                            self.assertEqual(call['cost'], prices[call['provider']][call['depth']], 'R1.141')
                    if call['method'] == 'extract' and call['provider'] == 'nimble' and 200 <= call['status'] < 300:
                        self.assertEqual(call['cost'], len(call['urls']), 'R1.141 R1.144 no render')
                    if call['method'] == 'research':
                        self.assertIn(domain, call['query'], 'R1.149')
                        self.assertEqual(set(call['fields']), set(FIELDS), 'R1.149')
                        if 200 <= call['status'] < 300:
                            self.assertEqual(call['cost'], 25, 'R1.141')
                oracle = entry.get('expected', {}).get('1', {}).get('0')
                for name, field in item['fields'].items():
                    if oracle is not None:
                        expected = oracle.get(name)
                        choices = expected if isinstance(expected, list) else [expected]
                        self.assertIn(field['value'], choices, f'R1.82 M1.5 {domain} {name}')
                    if field['value'] is None:
                        self.assertEqual(field, {'value': None, 'status': 'unknown', 'citations': []}, 'R1.41')
                    else:
                        self.assertEqual(field['status'], 'known', 'R1.41')
                        self.assertTrue(field['citations'], 'R1.41')
                    self.assertLessEqual(len(field['citations']), 5, 'L1.12')
                    for citation in field['citations']:
                        self.assertIn(citation['provider'], ('nimble', 'tavily'), 'R1.42')
                        excerpt = citation['excerpt']
                        self.assertTrue(1 <= len(excerpt) <= 500, 'R1.45')
                        self.assertTrue(supports(domain, name, field['value'], excerpt), f'R1.46 Appendix A unsupported citation: {domain} {name} {citation!r}')
                        served = [(c['method'], s['text']) for c in calls if c['provider'] == citation['provider'] for s in c['served'] if s['url'] == citation['url']]
                        valid = any((method == 'research' and excerpt == text) or (method != 'research' and norm(excerpt) in [norm(s) for s in sentences(prose(text))]) for method, text in served)
                        self.assertTrue(valid, f'R1.01a R1.42 R1.45 unserved prose citation: {citation!r}')
                before_read = len(calls)
                app('GET', '/dossiers/' + domain, token=self.token)
                app('GET', '/dossiers', token=self.token)
                self.assertEqual(len(mock('GET', '/_mock/log')[1]['calls']), before_read, 'R1.85')
        if all_costs:
            print('M1.1 sample costs: max=%s mean=%.2f' % (max(all_costs), sum(all_costs)/len(all_costs)), flush=True)


if __name__ == '__main__':
    unittest.main(verbosity=2)

