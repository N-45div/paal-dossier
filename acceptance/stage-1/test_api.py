import json
import time
import urllib.parse
from common import Acceptance, FIXTURE, FIELDS, NOW


class API(Acceptance):
    def test_R1_68_password_not_stored_in_plaintext(self):
        secret = 'distinct-stage-one-password-78!'
        signup = self.api('POST', '/auth/signup', {'email': 'newpass@example.test', 'password': secret, 'display_name': 'Example'})
        self.assertEqual(signup[0], 201)
        exported = self.api('GET', '/_test/export')
        self.assertEqual(exported[0], 200)
        self.assertFalse(secret in json.dumps(exported[1]), 'Plaintext password found in export')
        self.assertEqual(self.login('newpass@example.test', secret)['user_id'], signup[1]['user_id'])

    def test_R1_31_R1_53_http_errors_and_content_type(self):
        success = self.api('GET', '/health')
        self.assertIn('application/json', success[2].get('Content-Type', '').lower())
        self.assertIn('charset=utf-8', success[2].get('Content-Type', '').lower())
        self.err(self.api('GET', '/route-that-does-not-exist'), 404, 'not_found')
        self.err(self.api('DELETE', '/health'), 405, 'not_found')

    def test_R1_21_R1_51_R1_52_fixture_validation_preserves_state(self):
        cases = [([], 400, 'malformed_request'), ({}, 422, 'validation_failed'),
                 ({'now': NOW, 'users': 'bad'}, 400, 'malformed_request'),
                 ({'now': NOW, 'users': [{'id': 'u', 'email': 'a@b'}]}, 422, 'validation_failed'),
                 ({'now': NOW, 'users': [dict(FIXTURE['users'][0], id=9)]}, 400, 'malformed_request')]
        for body, status, code in cases:
            self.err(self.api('POST', '/_test/reset', body, timeout=10), status, code)
            self.assertEqual(self.login('ada@example.test')['user_id'], 'u_ada')

    def test_R1_19_R1_20_R1_24_R1_30_health_controls(self):
        before = self.log()
        response = self.api('GET', '/health')
        self.assertEqual((response[0], response[1]), (200, {'status': 'ok'}))
        self.assertEqual(self.api('POST', '/_test/clock', {'now': NOW})[0], 204)
        self.assertEqual(self.log(), before)

    def test_R1_26_R1_27_R1_29_clock_validation_and_equal(self):
        for value, code in [(None, 400), (3, 400), ('2026-03-01T09:00:00', 422), ('2026-03-01T08:59:59+00:00', 422)]:
            self.err(self.api('POST', '/_test/clock', {'now': value}), code, 'malformed_request' if code == 400 else 'validation_failed')
        self.err(self.api('POST', '/_test/clock', {}), 422, 'validation_failed')
        self.assertEqual(self.api('POST', '/_test/clock', {'now': NOW})[0], 204)
        self.assertEqual(self.api('POST', '/_test/clock', {'now': '2026-03-01T11:30:00+02:00'})[0], 204)
        self.err(self.api('POST', '/_test/clock', {'now': '2026-03-01T09:29:59+00:00'}), 422, 'validation_failed')

    def test_R1_21_R1_22_R1_51_R1_52_R1_62_reset_atomic_and_repeated(self):
        self.assertEqual(self.login('ADA@example.test')['user_id'], 'u_ada')
        bad = {'now': NOW, 'users': [FIXTURE['users'][0], dict(FIXTURE['users'][0], id='other', email='ADA@example.test')]}
        self.err(self.api('POST', '/_test/reset', bad), 422, 'validation_failed')
        self.assertEqual(self.login('ada@example.test')['user_id'], 'u_ada')
        self.assertEqual(self.api('POST', '/_test/reset', {'now': NOW})[0], 204)
        self.err(self.api('GET', '/dossiers', token=self.ada), 401, 'unauthenticated')
        self.err(self.api('POST', '/auth/login', {'email': 'ada@example.test', 'password': 'correct horse'}), 401, 'unauthenticated')
        self.assertEqual(self.api('POST', '/_test/reset', FIXTURE)[0], 204)
        self.assertEqual(self.api('POST', '/_test/reset', FIXTURE)[0], 204)

    def test_R1_25_R1_26_R1_27_R1_28_R1_29_R1_32_clock(self):
        for value, code in [(None, 400), (3, 400), ('2026-03-01T09:00:00', 422), ('2026-03-01T08:59:59+00:00', 422)]:
            self.err(self.api('POST', '/_test/clock', {'now': value}), code, 'malformed_request' if code == 400 else 'validation_failed')
        self.err(self.api('POST', '/_test/clock', {}), 422, 'validation_failed')
        self.assertEqual(self.api('POST', '/_test/clock', {'now': NOW})[0], 204)
        self.assertEqual(self.api('POST', '/_test/clock', {'now': '2026-03-01T11:30:00+02:00'})[0], 204)
        self.assertEqual(self.create()[0], 202)
        first = self.ready()
        self.assertEqual(first['researched_at'], '2026-03-01T11:30:00+02:00')
        self.assertEqual(self.api('POST', '/dossiers/acme-robotics.test/refresh', token=self.ada, key='refresh')[0], 202)
        self.assertEqual(self.ready()['researched_at'], first['researched_at'])

    def test_R1_53_R1_54_R1_55_R1_59_R1_60_R1_61_auth_validation(self):
        good = {'email': 'new@example.test', 'password': 'abcdefgh', 'display_name': 'N' * 100}
        response = self.api('POST', '/auth/signup', good)
        self.assertEqual(response[0], 201, response[1])
        self.assertTrue(response[1]['token'])
        self.assertEqual(self.login('NEW@example.test', 'abcdefgh')['user_id'], response[1]['user_id'])
        self.err(self.api('POST', '/auth/signup', good), 409, 'email_taken')
        for update in ({'password': '1234567'}, {'email': 'a@@b'}, {'email': 'a @b'}, {'display_name': '  '}, {'display_name': 'x' * 101}):
            self.err(self.api('POST', '/auth/signup', dict(good, **update)), 422, 'validation_failed')
        for update in ({'email': 1}, {'password': None}, {'display_name': []}):
            self.err(self.api('POST', '/auth/signup', dict(good, **update)), 400, 'malformed_request')
        self.err(self.api('POST', '/auth/signup', b'{'), 400, 'malformed_request')
        self.err(self.api('POST', '/auth/login', {'email': 'new@example.test', 'password': 'bad'}), 401, 'unauthenticated')
        self.err(self.api('POST', '/auth/login', {'email': 'missing@example.test', 'password': 'bad'}), 401, 'unauthenticated')

    def test_R1_33_R1_34_R1_66_R1_67_sessions_and_unknowns(self):
        other = self.login('ada@example.test')['token']
        self.assertNotEqual(other, self.ada)
        for token in (self.ada, other, self.bob):
            self.assertEqual(self.api('GET', '/dossiers?unknown=yes', token=token)[0], 200)
        self.assertEqual(self.api('GET', '/dossiers', headers={'Authorization': 'bearer ' + self.ada})[0], 200)
        for auth in ('Basic x', 'Bearer invalid', 'Bearer', ''):
            self.err(self.api('POST', '/dossiers', {}, headers={'Authorization': auth}), 401, 'unauthenticated')
        self.err(self.api('POST', '/dossiers', {}), 401, 'unauthenticated')
        self.assertEqual(self.api('POST', '/auth/signup', {'email': 'extra@example.test', 'password': '12345678', 'display_name': 'Extra', 'ignored': [1]})[0], 201)

    def test_R1_35_R1_36_R1_37_R1_89_R1_95a_domains(self):
        r = self.create('  WWW.Acme-Robotics.TEST.  ')
        self.assertEqual(r[0], 202, r[1])
        self.assertEqual(r[1]['domain'], 'acme-robotics.test')
        other = self.create('acme-robotics.test', key='other')
        self.assertEqual(other[0], 200)
        self.assertEqual(other[1]['dossier_id'], r[1]['dossier_id'])
        self.assertEqual(self.get('WWW.Acme-Robotics.TEST.')[1]['dossier_id'], r[1]['dossier_id'])
        for n, invalid in enumerate(('a', '-a.test', 'a-.test', 'a..test', 'a_b.test', 'https://a.test', 'a.test..', 'a' * 64 + '.test', ('a.' * 127) + 'aa')):
            self.err(self.create(invalid, 'invalid' + str(n)), 422, 'validation_failed')
        self.err(self.api('POST', '/dossiers', {}, self.ada, 'missing'), 422, 'validation_failed')
        self.err(self.api('POST', '/dossiers', {'domain': 1}, self.ada, 'wrong'), 400, 'malformed_request')
        self.err(self.get('bad_domain.test'), 422, 'validation_failed')
        self.err(self.get('missing.test'), 404, 'not_found')

    def test_R1_56_R1_57_R1_109_R1_111_R1_112_R1_113_listing(self):
        for i, domain in enumerate(('zeta.test', 'alpha.test', 'beta.test')):
            self.assertEqual(self.create(domain, 'key' + str(i))[0], 202)
        result = self.api('GET', '/dossiers?limit=1&offset=1', token=self.ada)
        self.assertEqual(result[0], 200)
        self.assertEqual([d['domain'] for d in result[1]['dossiers']], ['beta.test'])
        self.assertTrue(result[1]['has_more'])
        self.assertEqual([d['domain'] for d in self.api('GET', '/dossiers?q=ALP', token=self.bob)[1]['dossiers']], ['alpha.test'])
        self.assertEqual(len(self.api('GET', '/dossiers?q=', token=self.ada)[1]['dossiers']), 3)
        self.assertFalse(self.api('GET', '/dossiers?offset=3', token=self.ada)[1]['has_more'])
        for query in ('limit=0', 'limit=201', 'limit=', 'offset=', 'offset=-1', 'limit=1e9', 'limit=4.0', 'limit=%2B4'):
            self.err(self.api('GET', '/dossiers?' + query, token=self.ada), 422, 'validation_failed')
        self.err(self.create(key='x' * 256), 422, 'validation_failed')

    def test_R1_70_R1_71_R1_72_R1_73_R1_74_R1_78_idempotency(self):
        self.err(self.api('POST', '/dossiers', {'domain': 'a.test'}, self.ada), 400, 'missing_idempotency_key')
        self.err(self.api('POST', '/dossiers', b'{', self.ada), 400, 'malformed_request')
        self.err(self.api('POST', '/dossiers', {'domain': 5}, self.ada, 'recover'), 400, 'malformed_request')
        first = self.api('POST', '/dossiers', {'domain': 'Acme-Robotics.test', 'extra': 1}, self.ada, 'recover')
        self.assertEqual(first[0], 202, first[1])
        replay = self.api('POST', '/dossiers', {'extra': 'different', 'domain': 'Acme-Robotics.test'}, self.ada, 'recover')
        self.assertEqual((replay[0], replay[1]), (200, first[1]))
        for body in ({'domain': 'acme-robotics.test'}, {'domain': 3}, {}):
            self.err(self.api('POST', '/dossiers', body, self.ada, 'recover'), 409, 'idempotency_key_reuse')
        self.assertEqual(self.api('POST', '/dossiers', {'domain': 'different.test'}, self.bob, 'recover')[0], 202)
        self.assertEqual(self.api('POST', '/dossiers/Acme-Robotics.test/refresh', token=self.ada, key='recover')[0], 202)
        self.assertEqual(self.api('POST', '/dossiers/acme-robotics.test/refresh', token=self.ada, key='recover')[0], 202)

    def test_R1_75_R1_77_R1_85_R1_106_R1_107_R1_108_replay_and_refresh(self):
        first = self.create()
        self.assertEqual(first[0], 202)
        self.ready()
        before = len(self.log())
        replay = self.create()
        self.assertEqual((replay[0], replay[1]), (200, first[1]))
        self.api('GET', '/dossiers', token=self.ada)
        self.get()
        self.assertEqual(len(self.log()), before)
        self.err(self.api('POST', '/dossiers/nope.test/refresh', token=self.ada, key='absent'), 404, 'not_found')
        refresh = self.api('POST', '/dossiers/acme-robotics.test/refresh', b'not json', self.ada, 'refresh')
        self.assertEqual(refresh[0], 202, refresh[1])
        self.assertEqual(self.api('POST', '/dossiers/acme-robotics.test/refresh', {'anything': 1}, self.ada, 'refresh')[:2], (200, refresh[1]))
        self.ready()
        self.assertGreater(len(self.log()), before)

    def test_R1_12_R1_15_R1_58_R1_76_R1_88_R1_120a_concurrent_bursts(self):
        responses = self.burst(lambda _: self.create('burst.test', 'same'))
        self.assertEqual(sum(r[0] == 202 for r in responses), 1)
        self.assertEqual(sum(r[0] == 200 for r in responses), 49)
        self.assertTrue(all(r[1] == responses[0][1] for r in responses))
        self.assertTrue(all(r[3] < 5 for r in responses))
        conflicts = self.burst(lambda i: self.create('left.test' if i % 2 else 'right.test', 'conflict'))
        self.assertEqual(sum(r[0] == 202 for r in conflicts), 1)
        self.assertEqual(sum(r[0] == 200 for r in conflicts), 24)
        self.assertEqual(sum(r[0] == 409 and r[1]['error']['code'] == 'idempotency_key_reuse' for r in conflicts), 25)
        self.assertTrue(all(r[3] < 5 for r in conflicts))
        winning_domain = next(r[1]['domain'] for r in conflicts if r[0] == 202)
        self.ready(winning_domain)
        self.ready('burst.test')
        responses = self.burst(lambda i: self.create('race.test', 'key' + str(i)))
        self.assertEqual(sum(r[0] == 202 for r in responses), 1)
        self.assertEqual(sum(r[0] == 200 for r in responses), 49)
        self.assertEqual(len({r[1]['dossier_id'] for r in responses}), 1)
        self.assertTrue(all(r[3] < 5 for r in responses))
        self.ready('race.test')

    def test_R1_02a_R1_38_R1_40_R1_41_R1_86_R1_87_R1_90_R1_91_R1_92_R1_93_shape(self):
        created = self.create()
        self.assertEqual(created[0], 202)
        self.assertEqual(created[1]['state'], 'building')
        self.assertLessEqual(len(created[1]['dossier_id']), 64)
        item = self.ready()
        self.assertEqual(item['dossier_id'], created[1]['dossier_id'])
        self.assertEqual(item['domain'], 'acme-robotics.test')
        self.assertEqual(set(item['fields']), FIELDS)
        for field in item['fields'].values():
            self.assertEqual(field['status'], 'known' if field['value'] is not None else 'unknown')
            self.assertEqual(bool(field['citations']), field['value'] is not None)
        self.assertIn(item['state'], ('ready', 'failed'))
        self.assertIsInstance(item['spent_units'], int)
        existing = self.create(key='new')
        self.assertEqual(existing[0], 200)
        self.assertEqual(existing[1]['dossier_id'], created[1]['dossier_id'])

    def test_R1_114_R1_115_R1_116_R1_117_R1_118_R1_119_export_import(self):
        original = self.create()
        dossier = self.ready()
        snapshot = self.api('GET', '/_test/export')
        self.assertEqual(snapshot[0], 200)
        self.assertEqual(snapshot[1]['track'], 'dossier')
        self.assertEqual(snapshot[1]['format_version'], 1)
        self.assertIsInstance(snapshot[1]['state'], dict)
        self.assertEqual(self.api('POST', '/_test/reset', {'now': '2026-04-01T00:00:00+00:00', 'users': []})[0], 204)
        self.assertEqual(self.api('POST', '/_test/import', snapshot[1], timeout=10)[0], 204)
        self.assertEqual(self.get()[1], dossier)
        self.assertEqual(self.login('ada@example.test')['user_id'], 'u_ada')
        self.assertEqual(self.create()[:2], (200, original[1]))
        self.assertEqual(self.api('POST', '/_test/import', snapshot[1], timeout=10)[0], 204)
        self.assertEqual(self.get()[1], dossier)
        for bad in ({}, {'track': 'wrong', 'format_version': 1, 'state': {}}, {'track': 'dossier', 'format_version': True, 'state': {}}, {'track': 'dossier', 'format_version': 1, 'state': {}}):
            self.err(self.api('POST', '/_test/import', bad), 422, 'validation_failed')
            self.assertEqual(self.get()[1], dossier)
        self.err(self.api('POST', '/_test/import', b'{'), 400, 'malformed_request')
        self.assertEqual(self.api('POST', '/_test/clock', {'now': '2026-03-31T23:59:59+00:00'})[0], 422)
