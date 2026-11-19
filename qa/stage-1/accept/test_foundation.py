"""Foundation checks that do not require the later dossier routes."""
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
