"""Provider-side retry spacing and cost checks for Stage 2 builds."""
import json
import time

import httpx
import pytest

from conftest import ADMIN, docker
from test_candidates import wait_ready


@pytest.mark.parametrize('method', ['search', 'extract', 'research'])
@pytest.mark.parametrize('mode', ['throttle', 'rate_limit'])
def test_R2_22_R2_23_R2_28_R2_30_RL61_refusal_spacing_and_logged_cost(timed_deployment, method, mode):
    """A throttled provider is retried after one second, with refused calls costing zero."""
    domain = 'halvorsen-robotics.test'
    address = docker('inspect', '--format', '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}',
                     timed_deployment['monitor'], timeout=10).stdout.strip()
    with httpx.Client(base_url=timed_deployment['app'], timeout=10, trust_env=False) as api, \
         httpx.Client(base_url=timed_deployment['mock'], headers=ADMIN, timeout=10, trust_env=False) as mock, \
         httpx.Client(base_url=f'http://{address}:8080', timeout=10, trust_env=False) as probe:
        assert mock.post('/_mock/reset', json={'epoch':0}).status_code == 204
        assert mock.post('/_mock/faults', json={'provider':'nimble', 'methods':[method], 'mode':mode}).status_code == 204
        fixture = {'now':'2026-03-01T09:00:00Z', 'users':[
            {'id':'u', 'email':'retry@example.com', 'password':'correct horse', 'display_name':'Retry'}]}
        assert api.post('/_test/reset', json=fixture).status_code == 204
        login = api.post('/auth/login', json={'email':'retry@example.com', 'password':'correct horse'})
        assert login.status_code == 200
        token = login.json()['token']
        baseline = len(probe.get('/_probe/calls').json())
        started = time.monotonic()
        assert api.post('/dossiers', json={'domain':domain},
                        headers={'Authorization':'Bearer ' + token, 'Idempotency-Key':'retry-' + method + '-' + mode}).status_code == 202
        dossier = wait_ready(api, token, domain, timeout=300)
        elapsed = time.monotonic() - started
        assert dossier['state'] == 'ready'
        calls = mock.get('/_mock/log').json()['calls']
        refusals = [call for call in calls if call['provider'] == 'nimble' and
                    call['method'] == method and call['status'] == 429]
        assert refusals, 'scenario must actually exercise the chosen 429'
        assert all(call['cost'] == 0 for call in refusals)
        assert dossier['spent_units'] == sum(call['cost'] for call in calls)
        assert dossier['spent_units'] <= 80
        captured = sorted(probe.get('/_probe/calls').json()[baseline:], key=lambda item:item['start'])
        retries, intervals = [], []
        for i, first in enumerate(captured):
            if first['status'] != 429:
                continue
            identity = (first['method'], first['path'], json.dumps(first['body'], sort_keys=True))
            following = [item for item in captured[i+1:] if
                         (item['method'], item['path'], json.dumps(item['body'], sort_keys=True)) == identity]
            if following:
                retries.append(following[0]['start'] - first['answered'])
                intervals.append((first['answered'], following[0]['start']))
        assert retries, 'scenario must actually retry a refused call'
        assert min(retries) >= 1.05, ('retry issued too early after 429', min(retries))
        if mode == 'rate_limit':
            groups = {}
            for item in captured:
                identity = (item['method'], item['path'], json.dumps(item['body'], sort_keys=True))
                groups.setdefault(identity, []).append(item['status'])
            assert any(len(values) >= 4 and values[:3] == [429,429,429] and values[3] < 400
                       for values in groups.values()), 'three 429s must be retried'
        merged = []
        for start, end in sorted(intervals):
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        excluded_wait = sum(end - start for start, end in merged)
        assert elapsed - excluded_wait <= 10.5, (elapsed, excluded_wait)


@pytest.mark.parametrize('provider', ['kernel', 'browserbase'])
def test_R2_24_R2_25_R2_28_R2_29_exhausted_optional_sessions_do_not_block_build(api, mock, seeded, provider):
    """Four provider sessions fill the cap; another open is refused without cost."""
    endpoint = '/kernel/browsers' if provider == 'kernel' else '/browserbase/v1/sessions'
    id_key = 'session_id' if provider == 'kernel' else 'id'
    sessions = []
    try:
        for _ in range(4):
            response = mock.post(endpoint, json={}, timeout=30)
            assert response.status_code == 200
            sessions.append(response.json()[id_key])
        denied = mock.post(endpoint, json={}, timeout=30)
        assert denied.status_code == 429
        own_calls = mock.get('/_mock/log').json()['calls']
        session_calls = [c for c in own_calls if c['provider'] == provider and c['method'] == 'session']
        assert len(session_calls) == 5 and session_calls[-1]['cost'] == 0
        assert sum(c['cost'] for c in session_calls[:4]) == (0 if provider == 'kernel' else 8)
        domain = 'halvorsen-robotics.test'
        assert api.post('/dossiers', json={'domain':domain}, headers={
            'Authorization':'Bearer ' + seeded[0], 'Idempotency-Key':'session-cap-' + provider}).status_code == 202
        result = wait_ready(api, seeded[0], domain, timeout=300)
        assert result['state'] == 'ready'
        after = mock.get('/_mock/log').json()['calls'][len(own_calls):]
        assert result['spent_units'] == sum(c['cost'] for c in after) <= 80
        assert all(c['cost'] == 0 for c in after if c['status'] == 429)
    finally:
        for session in sessions:
            if provider == 'kernel':
                mock.delete(endpoint + '/' + session, timeout=20)
            else:
                mock.post(endpoint + '/' + session, json={'status':'REQUEST_RELEASE'}, timeout=20)


def test_R2_28_R2_29_idle_optional_provider_sessions_expire_after_one_minute(mock):
    """Unconnected sessions from both browser vendors are closed after 60 seconds."""
    sessions = []
    try:
        for endpoint, key in [('/kernel/browsers', 'session_id'), ('/browserbase/v1/sessions', 'id')]:
            started = time.monotonic()
            response = mock.post(endpoint, json={}, timeout=30)
            assert response.status_code == 200
            path = endpoint + '/' + response.json()[key]
            assert mock.get(path).status_code == 200
            sessions.append((endpoint, path, started))
        expired = {}
        deadline = time.monotonic() + 75
        while time.monotonic() < deadline and len(expired) < len(sessions):
            for _, path, started in sessions:
                if path not in expired and mock.get(path).status_code == 404:
                    expired[path] = time.monotonic() - started
            if len(expired) < len(sessions):
                time.sleep(1)
        assert len(expired) == len(sessions), 'unconnected sessions must expire after one minute'
        assert all(elapsed >= 59.9 for elapsed in expired.values()), expired
    finally:
        for endpoint, path, _ in sessions:
            if endpoint.startswith('/kernel/'):
                mock.delete(path, timeout=20)
            else:
                mock.post(path, json={'status':'REQUEST_RELEASE'}, timeout=20)
