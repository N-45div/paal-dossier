"""Foundation checks that do not require the later dossier routes."""
import time

import pytest

from test_api import auth, error


def test_R1_23_R1_48_R1_63_R1_66_seed_and_reset(api, seeded):
    duplicate = {'now': '2026-03-02T00:00:00+00:00', 'users': [
        {'id': 'a', 'email': 'duplicate@example.com', 'password': 'correct horse', 'display_name': 'A'},
        {'id': 'b', 'email': 'DUPLICATE@example.com', 'password': 'correct horse', 'display_name': 'B'}]}
    error(api.post('/_test/reset', json=duplicate, timeout=10), 422, 'validation_failed')
    login = api.post('/auth/login', json={'email':'ADA@example.com', 'password':'correct horse'})
    assert login.status_code == 200 and login.json()['user_id'] == 'u_ada'
    assert api.post('/_test/reset', json={'now':'2026-03-02T00:00:00+00:00','users':[]}, timeout=10).status_code == 204
    error(api.post('/auth/login', json={'email':'ada@example.com', 'password':'correct horse'}), 401, 'unauthenticated')


def test_R1_24_R1_25_R1_27_R1_28_clock_public_and_monotonic(api, seeded):
    assert api.post('/_test/clock', json={'now':'2026-03-01T09:00:00+00:00'}).status_code == 204
    assert api.post('/_test/clock', json={'now':'2026-03-01T10:00:00+00:00'}).status_code == 204
    error(api.post('/_test/clock', json={'now':'2026-03-01T09:59:59+00:00'}), 422, 'validation_failed')
    error(api.post('/_test/clock', json={'now':'2026-03-01T11:00:00'}), 422, 'validation_failed')
    error(api.post('/_test/clock', json={'now':1}), 400, 'malformed_request')
    assert api.post('/_test/clock', json={'now':'2026-03-01T11:00:00+01:00'}).status_code == 204


def test_R1_70_R1_124_R1_125_R1_126_R1_127_foundation_snapshot(api, seeded):
    exported = api.get('/_test/export', timeout=10)
    assert exported.status_code == 200
    snapshot = exported.json()
    assert snapshot['track'] == 'dossier' and snapshot['format_version'] == 1 and isinstance(snapshot['state'], dict)
    assert 'correct horse' not in exported.text
    assert api.post('/_test/reset', json={'now':'2026-04-01T00:00:00+00:00','users':[]}, timeout=10).status_code == 204
    assert api.post('/_test/import', json=snapshot, timeout=10).status_code == 204
    login = api.post('/auth/login', json={'email':'ada@example.com','password':'correct horse'})
    assert login.status_code == 200 and login.json()['user_id'] == 'u_ada'
    assert api.post('/_test/import', json=snapshot, timeout=10).status_code == 204
    error(api.post('/_test/clock', json={'now':'2026-03-02T00:00:00+00:00'}), 422, 'validation_failed')


def test_R1_49_R1_50_R1_54_error_envelope_unknown_route(api, seeded):
    error(api.get('/no-such-route', headers=auth(seeded[0])), 404, 'not_found')


def test_R1_23_R1_34_R1_48_R1_66_fixture_values_and_import(api, seeded):
    fixture = {'now':'2026-01-01T00:00:00+00:00', 'users': [
        {'id':'x'*64, 'email':'no-at-sign', 'password':'', 'display_name':''},
        {'id':'u2', 'email':'another invalid email', 'password':'abc', 'display_name':'N'*101}]}
    assert api.post('/_test/reset', json=fixture, timeout=10).status_code == 204
    for user in fixture['users']:
        login = api.post('/auth/login', json={'email':user['email'],'password':user['password']})
        assert login.status_code == 200 and login.json()['user_id'] == user['id']
        error(api.post('/auth/login', json={'email':user['email'],'password':user['password']+'wrong'}), 401, 'unauthenticated')
    snapshot = api.get('/_test/export', timeout=10).json()
    assert api.post('/_test/reset', json={'now':'2026-01-02T00:00:00+00:00','users':[]}, timeout=10).status_code == 204
    assert api.post('/_test/import', json=snapshot, timeout=10).status_code == 204
    for user in fixture['users']:
        login = api.post('/auth/login', json={'email':user['email'],'password':user['password']})
        assert login.status_code == 200 and login.json()['user_id'] == user['id']


@pytest.mark.parametrize('changes,status,code', [
    ({'id':''}, 422, 'validation_failed'),
    ({'id':'x'*65}, 422, 'validation_failed'),
    ({'id':7}, 400, 'malformed_request'),
    ({'email':None}, 400, 'malformed_request'),
    ({'password':[]}, 400, 'malformed_request'),
    ({'display_name':False}, 400, 'malformed_request'),
])
def test_R1_23_R1_33_R1_48_fixture_validation_atomic(api, seeded, changes, status, code):
    user = {'id':'test', 'email':'not-email', 'password':'', 'display_name':''}
    user.update(changes)
    error(api.post('/_test/reset', json={'now':'2026-01-01T00:00:00+00:00','users':[user]}, timeout=10), status, code)
    login = api.post('/auth/login', json={'email':'ada@example.com','password':'correct horse'})
    assert login.status_code == 200 and login.json()['user_id'] == 'u_ada'


def test_R1_23_R1_48_fixture_duplicate_ids_atomic(api, seeded):
    first = {'id':'same', 'email':'first', 'password':'', 'display_name':''}
    second = {'id':'same', 'email':'second', 'password':'', 'display_name':''}
    error(api.post('/_test/reset', json={'now':'2026-01-01T00:00:00+00:00','users':[first,second]}, timeout=10), 422, 'validation_failed')
    assert api.post('/auth/login', json={'email':'ada@example.com','password':'correct horse'}).status_code == 200


def test_R1_23_R1_25_reset_can_move_clock_backwards(api, seeded):
    assert api.post('/_test/clock', json={'now':'2026-04-01T00:00:00+00:00'}).status_code == 204
    assert api.post('/_test/reset', json={'now':'2020-01-01T00:00:00+00:00'}, timeout=10).status_code == 204
    assert api.post('/_test/clock', json={'now':'2020-01-02T00:00:00+00:00'}).status_code == 204


def test_R1_17_R1_23_R1_48_500_seeded_users(api, seeded):
    users = [{'id':f'u{i}', 'email':f'user{i}@fixture.test', 'password':'fixture password',
              'display_name':f'User {i}'} for i in range(500)]
    start = time.monotonic()
    result = api.post('/_test/reset', json={'now':'2026-03-01T00:00:00+00:00','users':users}, timeout=10)
    elapsed = time.monotonic() - start
    assert result.status_code == 204
    assert elapsed <= 5, f'500-user reset took {elapsed:.3f}s'
    for user in (users[0], users[249], users[-1]):
        response = api.post('/auth/login', json={'email':user['email'],'password':user['password']})
        assert response.status_code == 200 and response.json()['user_id'] == user['id']


def test_R1_27_fractional_clock_precision(api, seeded):
    assert api.post('/_test/clock', json={'now':'2026-03-01T10:00:00.123456789+00:00'}).status_code == 204
    error(api.post('/_test/clock', json={'now':'2026-03-01T10:00:00.123456788+00:00'}), 422, 'validation_failed')
    assert api.post('/_test/clock', json={'now':'2026-03-01T10:00:00.123456790+00:00'}).status_code == 204
