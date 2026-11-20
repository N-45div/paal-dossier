"""Provider-side retry spacing and cost checks for Stage 2 builds."""
import json
import time

import httpx
import pytest

from conftest import ADMIN, docker
from test_candidates import wait_ready


@pytest.mark.parametrize('method', ['search', 'extract', 'research'])
def test_R2_22_R2_23_R2_28_R2_30_RL61_refusal_spacing_and_logged_cost(timed_deployment, method):
    """A throttled provider is retried after one second, with refused calls costing zero."""
    domain = 'halvorsen-robotics.test'
    address = docker('inspect', '--format', '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}',
                     timed_deployment['monitor'], timeout=10).stdout.strip()
    with httpx.Client(base_url=timed_deployment['app'], timeout=10, trust_env=False) as api, \
         httpx.Client(base_url=timed_deployment['mock'], headers=ADMIN, timeout=10, trust_env=False) as mock, \
         httpx.Client(base_url=f'http://{address}:8080', timeout=10, trust_env=False) as probe:
        assert mock.post('/_mock/reset', json={'epoch':0}).status_code == 204
        assert mock.post('/_mock/faults', json={'provider':'nimble', 'methods':[method], 'mode':'throttle'}).status_code == 204
        fixture = {'now':'2026-03-01T09:00:00Z', 'users':[
            {'id':'u', 'email':'retry@example.com', 'password':'correct horse', 'display_name':'Retry'}]}
        assert api.post('/_test/reset', json=fixture).status_code == 204
        login = api.post('/auth/login', json={'email':'retry@example.com', 'password':'correct horse'})
        assert login.status_code == 200
        token = login.json()['token']
        baseline = len(probe.get('/_probe/calls').json())
        started = time.monotonic()
        assert api.post('/dossiers', json={'domain':domain},
                        headers={'Authorization':'Bearer ' + token, 'Idempotency-Key':'retry-' + method}).status_code == 202
        dossier = wait_ready(api, token, domain)
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
        assert min(retries) >= 1.0, ('retry issued too early after 429', min(retries))
        merged = []
        for start, end in sorted(intervals):
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        excluded_wait = sum(end - start for start, end in merged)
        assert elapsed - excluded_wait <= 10.5, (elapsed, excluded_wait)
