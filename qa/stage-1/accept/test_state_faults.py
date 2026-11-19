import time
import concurrent.futures
import threading
from collections import Counter

import httpx
import pytest

from test_api import auth, create, done, error


def fault(mock, provider, methods, mode, **extra):
    response = mock.post('/_mock/faults', json={'provider': provider, 'methods': methods, 'mode': mode, **extra})
    assert response.status_code == 204


def test_R1_9_R1_62_R1_85_provider_errors(api, mock, seeded):
    'R1.9 R1.62 R1.85'
    for provider, methods in [('nimble', ['search', 'extract', 'research']), ('tavily', ['search', 'extract'])]:
        fault(mock, provider, methods, 'error')
    token = seeded[0]
    assert create(api, token, 'ashgrove-solar.test', 'all-errors').status_code == 202
    dossier = done(api, token, 'ashgrove-solar.test')
    assert dossier['state'] == 'failed' and dossier['spent_units'] == 0
    assert all(field['value'] is None for field in dossier['fields'].values())
    assert sum(x['cost'] for x in mock.get('/_mock/log').json()['calls']) == 0


def test_R1_9_tavily_failure_does_not_prevent_nimble(api, mock, seeded):
    'R1.9'
    fault(mock, 'tavily', ['search', 'extract'], 'error')
    token = seeded[0]
    assert create(api, token, 'ashgrove-solar.test', 'nimble-only').status_code == 202
    assert done(api, token, 'ashgrove-solar.test')['state'] == 'ready'


def test_R1_9_R1_62_R1_85_nimble_failure(api, mock, seeded):
    'R1.9 R1.62 R1.85'
    fault(mock, 'nimble', ['search', 'extract', 'research'], 'error')
    token = seeded[0]
    assert create(api, token, 'ashgrove-solar.test', 'nimble-error').status_code == 202
    dossier = done(api, token, 'ashgrove-solar.test')
    calls = mock.get('/_mock/log').json()['calls']
    succeeded = any(c['status'] < 400 for c in calls)
    assert dossier['state'] == ('ready' if succeeded else 'failed')
    assert dossier['spent_units'] == sum(c['cost'] for c in calls), Counter((c['provider'], c['method'], c['status'], c['cost']) for c in calls)


def test_R1_62_R1_85_R1_87_rate_limits(api, mock, seeded):
    'R1.62 R1.85 R1.87'
    fault(mock, 'nimble', ['search', 'extract', 'research'], 'rate_limit')
    fault(mock, 'tavily', ['search', 'extract'], 'rate_limit')
    token = seeded[0]
    started = time.monotonic()
    assert create(api, token, 'ashgrove-solar.test', 'throttled').status_code == 202
    dossier = done(api, token, 'ashgrove-solar.test')
    calls = mock.get('/_mock/log').json()['calls']
    assert time.monotonic() - started <= 10
    assert dossier['state'] == ('ready' if any(c['status'] < 400 for c in calls) else 'failed')
    assert dossier['spent_units'] == sum(c['cost'] for c in calls), Counter((c['provider'], c['method'], c['status'], c['cost']) for c in calls)


def test_R1_87_delay_under_one_second(api, mock, seeded):
    'R1.87'
    fault(mock, 'nimble', ['search', 'extract', 'research'], 'delay', seconds=.2)
    token = seeded[0]
    started = time.monotonic()
    assert create(api, token, 'ashgrove-solar.test', 'delayed').status_code == 202
    assert done(api, token, 'ashgrove-solar.test')['state'] == 'ready'
    assert time.monotonic() - started <= 10


def test_R1_84_R1_102_concurrent_refresh_one_build(api, mock, seeded, direct_api):
    'R1.84 R1.102'
    token, domain = seeded[0], 'ashgrove-solar.test'
    assert create(api, token, domain, 'initial').status_code == 202
    initial = done(api, token, domain)
    before = mock.get('/_mock/log').json()['calls']
    fault(mock, 'nimble', ['search', 'extract', 'research'], 'delay', seconds=6)
    fault(mock, 'tavily', ['search', 'extract'], 'delay', seconds=6)
    barrier = threading.Barrier(50)
    with httpx.Client(base_url=direct_api.base_url, timeout=5, trust_env=False) as client:
        def one(i):
            barrier.wait(timeout=5)
            started = time.monotonic()
            response = client.post('/dossiers/' + domain + '/refresh', headers=auth(token, 'refresh-' + str(i)))
            return response.status_code, response.json(), time.monotonic() - started
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as pool:
            responses = list(pool.map(one, range(50)))
    assert all(code == 202 and body['state'] == 'building' for code, body, _ in responses)
    assert len({body['dossier_id'] for _, body, _ in responses}) == 1
    assert max(elapsed for _, _, elapsed in responses) < 5
    fault(mock, 'nimble', ['search', 'extract', 'research'], 'none')
    fault(mock, 'tavily', ['search', 'extract'], 'none')
    final = done(api, token, domain, timeout=20)
    calls = mock.get('/_mock/log').json()['calls'][len(before):]
    assert sum(c['method'] == 'search' and c['query'] == domain and c['status'] == 200 for c in calls) == 1
    assert final['spent_units'] == initial['spent_units'] + sum(c['cost'] for c in calls)


def test_R1_85_failed_refresh_preserves_ready_fields(api, mock, seeded):
    'R1.85'
    token, domain = seeded[0], 'ashgrove-solar.test'
    assert create(api, token, domain, 'initial').status_code == 202
    initial = done(api, token, domain)
    assert initial['state'] == 'ready'
    fault(mock, 'nimble', ['search', 'extract', 'research'], 'error')
    fault(mock, 'tavily', ['search', 'extract'], 'error')
    assert api.post('/dossiers/' + domain + '/refresh', headers=auth(token, 'failed')).status_code == 202
    failed = done(api, token, domain)
    assert failed['state'] == 'failed'
    assert failed['fields'] == initial['fields']
    assert failed['researched_at'] == initial['researched_at']
    assert failed['spent_units'] == initial['spent_units']


def test_R1_85_R1_125_R1_126_R1_128_snapshot_failed_and_running_refresh(api, mock, seeded):
    """R1.85 R1.125 R1.126 R1.128: retain a failed outcome and prior fields in snapshots."""
    token, domain = seeded[0], 'ashgrove-solar.test'
    assert create(api, token, domain, 'first').status_code == 202
    ready = done(api, token, domain)
    assert ready['state'] == 'ready'
    fault(mock, 'nimble', ['search', 'extract', 'research'], 'error')
    fault(mock, 'tavily', ['search', 'extract'], 'error')
    assert api.post('/dossiers/' + domain + '/refresh', headers=auth(token, 'failed')).status_code == 202
    failed = done(api, token, domain)
    assert failed['state'] == 'failed' and failed['fields'] == ready['fields']
    assert failed['researched_at'] == ready['researched_at']
    saved = api.get('/_test/export', timeout=10).json()
    assert api.post('/_test/import', json=saved, timeout=10).status_code == 204
    assert api.get('/dossiers/' + domain, headers=auth(token)).json() == failed
    fault(mock, 'nimble', ['search', 'extract', 'research'], 'delay', seconds=.3)
    fault(mock, 'tavily', ['search', 'extract'], 'delay', seconds=.3)
    assert api.post('/dossiers/' + domain + '/refresh', headers=auth(token, 'running')).status_code == 202
    assert api.get('/dossiers/' + domain, headers=auth(token)).json()['state'] == 'building'
    during = api.get('/_test/export', timeout=10).json()
    assert api.post('/_test/import', json=during, timeout=10).status_code == 204
    restored = api.get('/dossiers/' + domain, headers=auth(token)).json()
    assert restored['state'] == 'failed' and restored['fields'] == failed['fields']
    assert restored['researched_at'] == failed['researched_at']
    time.sleep(10.2)
    assert api.get('/dossiers/' + domain, headers=auth(token)).json() == restored


def test_R1_23_R1_84_R1_128_reset_during_build(api, mock, seeded):
    'R1.23 R1.84 R1.128'
    fault(mock, 'nimble', ['search', 'extract', 'research'], 'delay', seconds=.3)
    fault(mock, 'tavily', ['search', 'extract'], 'delay', seconds=.3)
    token = seeded[0]
    assert create(api, token, 'ashgrove-solar.test', 'slow').status_code == 202
    assert api.get('/dossiers/ashgrove-solar.test', headers=auth(token)).json()['state'] == 'building'
    response = api.post('/_test/reset', json={'now':'2026-03-02T00:00:00+00:00','users':[]}, timeout=10)
    assert response.status_code == 204
    time.sleep(10.2)
    error(api.get('/dossiers', headers=auth(token)), 401, 'unauthenticated')
    assert api.post('/auth/signup', json={'email':'new@example.com','password':'correct horse','display_name':'New'}).status_code == 201
    new_token = api.post('/auth/login', json={'email':'new@example.com','password':'correct horse'}).json()['token']
    assert api.get('/dossiers', headers=auth(new_token)).json()['dossiers'] == []


def test_R1_23_R1_67_R1_93_R1_129_reset_races_authenticated_opens(api, mock, seeded, direct_api):
    """R1.23 R1.67 R1.93 R1.129: reset and old-token writes must be serializable."""
    fault(mock, 'nimble', ['search', 'extract', 'research'], 'error')
    fault(mock, 'tavily', ['search', 'extract'], 'error')
    for iteration in range(5):
        fixture = {'now':'2026-03-01T09:00:00+00:00', 'users':[
            {'id':'race-user', 'email':'race@example.com', 'password':'correct horse', 'display_name':'Race'}]}
        assert api.post('/_test/reset', json=fixture, timeout=10).status_code == 204
        login = api.post('/auth/login', json={'email':'race@example.com','password':'correct horse'})
        assert login.status_code == 200
        token = login.json()['token']
        barrier = threading.Barrier(50)
        with httpx.Client(base_url=direct_api.base_url, timeout=5, trust_env=False) as client:
            def request(i):
                barrier.wait(timeout=5)
                if i == 0:
                    return client.post('/_test/reset', json={'now':'2026-03-01T09:00:00+00:00','users':[]}, timeout=10).status_code
                return client.post('/dossiers', headers=auth(token, f'race-{iteration}-{i}'),
                                   json={'domain':f'race-{iteration}-{i}.test'}).status_code
            with concurrent.futures.ThreadPoolExecutor(max_workers=50) as pool:
                statuses = list(pool.map(request, range(50)))
        assert statuses[0] == 204 and all(code in (202, 401) for code in statuses[1:])
        error(api.get('/dossiers', headers=auth(token)), 401, 'unauthenticated')
        signup = api.post('/auth/signup', json={'email':'after-reset@example.com', 'password':'correct horse', 'display_name':'After'})
        assert signup.status_code == 201
        response = api.get('/dossiers', headers=auth(signup.json()['token']))
        assert response.status_code == 200 and response.json()['dossiers'] == []


def test_R1_70_R1_124_R1_125_R1_126_R1_127_export_import_roundtrip(api, mock, seeded):
    'R1.70 R1.124 R1.125 R1.126 R1.127'
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
    {'track':'dossier','format_version':1,'state':None},
    {'track':'dossier','format_version':1,'state':[]},
    {'track':'dossier','format_version':1,'state':{}}])
def test_R1_126_invalid_import_does_not_replace_state(api, seeded, body):
    'R1.126'
    token = seeded[0]
    error(api.post('/_test/import', json=body), 422, 'validation_failed')
    assert api.get('/dossiers', headers=auth(token)).status_code == 200
    error(api.post('/_test/import', content=b'{', headers={'Content-Type':'application/json'}), 400, 'malformed_request')


def test_R1_128_export_first_build_in_progress(api, mock, seeded):
    'R1.128'
    fault(mock, 'nimble', ['search', 'extract', 'research'], 'delay', seconds=.3)
    fault(mock, 'tavily', ['search', 'extract'], 'delay', seconds=.3)
    token = seeded[0]
    assert create(api, token, 'ashgrove-solar.test', 'inflight').status_code == 202
    assert api.get('/dossiers/ashgrove-solar.test', headers=auth(token)).json()['state'] == 'building'
    snapshot = api.get('/_test/export', timeout=10).json()
    assert api.post('/_test/import', json=snapshot, timeout=10).status_code == 204
    item = api.get('/dossiers/ashgrove-solar.test', headers=auth(token)).json()
    assert item['state'] == 'failed' and item['researched_at'] is None
    assert all(v['value'] is None and v['status'] == 'unknown' and v['citations'] == [] for v in item['fields'].values())
    time.sleep(10.2)
    assert api.get('/dossiers/ashgrove-solar.test', headers=auth(token)).json() == item


def test_R1_97_R1_128_export_refresh_in_progress(api, mock, seeded):
    'R1.97 R1.128'
    token = seeded[0]
    assert create(api, token, 'ashgrove-solar.test', 'first').status_code == 202
    original = done(api, token, 'ashgrove-solar.test')
    fault(mock, 'nimble', ['search', 'extract', 'research'], 'delay', seconds=.3)
    fault(mock, 'tavily', ['search', 'extract'], 'delay', seconds=.3)
    assert api.post('/dossiers/ashgrove-solar.test/refresh', headers=auth(token, 'second')).status_code == 202
    during = api.get('/dossiers/ashgrove-solar.test', headers=auth(token)).json()
    assert during['state'] == 'building' and during['fields'] == original['fields']
    snapshot = api.get('/_test/export', timeout=10).json()
    assert api.post('/_test/import', json=snapshot, timeout=10).status_code == 204
    restored = api.get('/dossiers/ashgrove-solar.test', headers=auth(token)).json()
    assert restored['state'] == original['state']
    assert restored['fields'] == original['fields'] and restored['researched_at'] == original['researched_at']
    time.sleep(10.2)
    assert api.get('/dossiers/ashgrove-solar.test', headers=auth(token)).json() == restored
