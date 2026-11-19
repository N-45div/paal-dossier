import time

import pytest

from test_api import auth, create, done, error


def fault(mock, provider, methods, mode, **extra):
    response = mock.post('/_mock/faults', json={'provider': provider, 'methods': methods, 'mode': mode, **extra})
    assert response.status_code == 204


def test_R1_9_R1_62_R1_85_provider_errors(api, mock, seeded):
    for provider, methods in [('nimble', ['search', 'extract', 'research']), ('tavily', ['search', 'extract'])]:
        fault(mock, provider, methods, 'error')
    token = seeded[0]
    assert create(api, token, 'ashgrove-solar.test', 'all-errors').status_code == 202
    dossier = done(api, token, 'ashgrove-solar.test')
    assert dossier['state'] == 'failed' and dossier['spent_units'] == 0
    assert all(field['value'] is None for field in dossier['fields'].values())
    assert sum(x['cost'] for x in mock.get('/_mock/log').json()['calls']) == 0


def test_R1_9_tavily_failure_does_not_prevent_nimble(api, mock, seeded):
    fault(mock, 'tavily', ['search', 'extract'], 'error')
    token = seeded[0]
    assert create(api, token, 'ashgrove-solar.test', 'nimble-only').status_code == 202
    assert done(api, token, 'ashgrove-solar.test')['state'] == 'ready'


def test_R1_9_R1_62_R1_85_nimble_failure(api, mock, seeded):
    fault(mock, 'nimble', ['search', 'extract', 'research'], 'error')
    token = seeded[0]
    assert create(api, token, 'ashgrove-solar.test', 'nimble-error').status_code == 202
    dossier = done(api, token, 'ashgrove-solar.test')
    calls = mock.get('/_mock/log').json()['calls']
    succeeded = any(c['status'] < 400 for c in calls)
    assert dossier['state'] == ('ready' if succeeded else 'failed')
    assert dossier['spent_units'] == sum(c['cost'] for c in calls)


def test_R1_87_delay_under_one_second(api, mock, seeded):
    fault(mock, 'nimble', ['search', 'extract', 'research'], 'delay', seconds=.2)
    token = seeded[0]
    started = time.monotonic()
    assert create(api, token, 'ashgrove-solar.test', 'delayed').status_code == 202
    assert done(api, token, 'ashgrove-solar.test')['state'] == 'ready'
    assert time.monotonic() - started <= 10


def test_R1_23_R1_84_R1_128_reset_during_build(api, mock, seeded):
    fault(mock, 'nimble', ['search', 'extract', 'research'], 'delay', seconds=2)
    fault(mock, 'tavily', ['search', 'extract'], 'delay', seconds=2)
    token = seeded[0]
    assert create(api, token, 'ashgrove-solar.test', 'slow').status_code == 202
    assert api.get('/dossiers/ashgrove-solar.test', headers=auth(token)).json()['state'] == 'building'
    response = api.post('/_test/reset', json={'now':'2026-03-02T00:00:00+00:00','users':[]}, timeout=10)
    assert response.status_code == 204
    time.sleep(3)
    error(api.get('/dossiers', headers=auth(token)), 401, 'unauthenticated')
    assert api.post('/auth/signup', json={'email':'new@example.com','password':'correct horse','display_name':'New'}).status_code == 201
    new_token = api.post('/auth/login', json={'email':'new@example.com','password':'correct horse'}).json()['token']
    assert api.get('/dossiers', headers=auth(new_token)).json()['dossiers'] == []


def test_R1_70_R1_124_R1_125_R1_126_R1_127_export_import_roundtrip(api, mock, seeded):
    token = seeded[0]
    original = create(api, token, 'ashgrove-solar.test', 'snapshot-key')
    assert original.status_code == 202
    old = done(api, token, 'ashgrove-solar.test')
    export = api.get('/_test/export', timeout=10)
    assert export.status_code == 200
    snapshot = export.json()
    assert snapshot['track'] == 'dossier' and snapshot['format_version'] == 1 and isinstance(snapshot['state'], dict)
    assert 'correct horse' not in export.text
    assert api.post('/_test/reset', json={'now':'2026-04-01T00:00:00+00:00','users':[]}, timeout=10).status_code == 204
    assert api.post('/_test/import', json=snapshot, timeout=10).status_code == 204
    restored = api.get('/dossiers/ashgrove-solar.test', headers=auth(token))
    assert restored.status_code == 200 and restored.json() == old
    replay = create(api, token, 'ashgrove-solar.test', 'snapshot-key')
    assert replay.status_code == 200 and replay.json() == original.json()
    assert api.post('/auth/login', json={'email':'ada@example.com','password':'correct horse'}).status_code == 200
    before = mock.get('/_mock/log').json()['calls']
    assert api.post('/_test/import', json=snapshot, timeout=10).status_code == 204
    assert mock.get('/_mock/log').json()['calls'] == before
    error(api.post('/_test/clock', json={'now':'2026-03-02T00:00:00+00:00'}), 422, 'validation_failed')


@pytest.mark.parametrize('body', [
    {}, {'track':'other','format_version':1,'state':{}},
    {'track':'dossier','format_version':999,'state':{}},
    {'track':'dossier','format_version':1,'state':{}}])
def test_R1_126_invalid_import_does_not_replace_state(api, seeded, body):
    token = seeded[0]
    error(api.post('/_test/import', json=body), 422, 'validation_failed')
    assert api.get('/dossiers', headers=auth(token)).status_code == 200
    error(api.post('/_test/import', content=b'{', headers={'Content-Type':'application/json'}), 400, 'malformed_request')


def test_R1_128_export_first_build_in_progress(api, mock, seeded):
    fault(mock, 'nimble', ['search', 'extract', 'research'], 'delay', seconds=2)
    fault(mock, 'tavily', ['search', 'extract'], 'delay', seconds=2)
    token = seeded[0]
    assert create(api, token, 'ashgrove-solar.test', 'inflight').status_code == 202
    assert api.get('/dossiers/ashgrove-solar.test', headers=auth(token)).json()['state'] == 'building'
    snapshot = api.get('/_test/export', timeout=10).json()
    assert api.post('/_test/import', json=snapshot, timeout=10).status_code == 204
    item = api.get('/dossiers/ashgrove-solar.test', headers=auth(token)).json()
    assert item['state'] == 'failed' and item['researched_at'] is None
    assert all(v['value'] is None and v['status'] == 'unknown' and v['citations'] == [] for v in item['fields'].values())


def test_R1_97_R1_128_export_refresh_in_progress(api, mock, seeded):
    token = seeded[0]
    assert create(api, token, 'ashgrove-solar.test', 'first').status_code == 202
    original = done(api, token, 'ashgrove-solar.test')
    fault(mock, 'nimble', ['search', 'extract', 'research'], 'delay', seconds=2)
    fault(mock, 'tavily', ['search', 'extract'], 'delay', seconds=2)
    assert api.post('/dossiers/ashgrove-solar.test/refresh', headers=auth(token, 'second')).status_code == 202
    during = api.get('/dossiers/ashgrove-solar.test', headers=auth(token)).json()
    assert during['state'] == 'building' and during['fields'] == original['fields']
    snapshot = api.get('/_test/export', timeout=10).json()
    assert api.post('/_test/import', json=snapshot, timeout=10).status_code == 204
    restored = api.get('/dossiers/ashgrove-solar.test', headers=auth(token)).json()
    assert restored['state'] == original['state']
    assert restored['fields'] == original['fields'] and restored['researched_at'] == original['researched_at']
