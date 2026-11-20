"""Stage 1 export/import and idempotency across the Stage 2 upgrade."""
import base64
import json
import threading
from urllib.parse import urlsplit

import httpx
import pytest

from conftest import ADMIN
from selection_oracle import assert_field, instant
from test_candidates import wait_ready
from test_browser import login, node, present
from test_browser_faults import assert_same_write, records_after_commit


def test_R2_108_R2_109_RL59_stage1_export_sessions_and_candidates_survive_upgrade(frozen_deployment, deployment):
    """A real Stage 1 export imports without provider calls and retains sessions and keys."""
    domain = 'halvorsen-robotics.test'
    identity = {'now': '2026-03-01T09:00:00Z', 'users': [
        {'id': 'upgrade-user', 'email': 'upgrade@example.com', 'password': 'correct horse', 'display_name': 'Upgrade'}]}
    with httpx.Client(base_url=frozen_deployment['app'], timeout=10, trust_env=False) as old, \
         httpx.Client(base_url=frozen_deployment['mock'], headers=ADMIN, timeout=10, trust_env=False) as old_mock, \
         httpx.Client(base_url=deployment['app'], timeout=10, trust_env=False) as new, \
         httpx.Client(base_url=deployment['mock'], headers=ADMIN, timeout=10, trust_env=False) as new_mock:
        assert old_mock.post('/_mock/reset', json={'epoch': 0}).status_code == 204
        assert old.post('/_test/reset', json=identity).status_code == 204
        login = old.post('/auth/login', json={'email': 'upgrade@example.com', 'password': 'correct horse'})
        assert login.status_code == 200
        token = login.json()['token']
        headers = {'Authorization': 'Bearer ' + token, 'Idempotency-Key': 'upgrade-create'}
        creation = old.post('/dossiers', headers=headers, json={'domain': domain})
        assert creation.status_code == 202
        old_dossier = wait_ready(old, token, domain)
        assert old_dossier['state'] == 'ready'
        assert any(field['value'] is not None for field in old_dossier['fields'].values())
        snapshot = old.get('/_test/export', timeout=10)
        assert snapshot.status_code == 200

        assert new_mock.post('/_mock/reset', json={'epoch': 0}).status_code == 204
        assert new.post('/_test/reset', json={'now': '2026-03-01T09:00:00Z', 'users': []}).status_code == 204
        before = new_mock.get('/_mock/log').json()['calls']
        imported = new.post('/_test/import', json=snapshot.json(), timeout=10)
        assert imported.status_code == 204
        assert new_mock.get('/_mock/log').json()['calls'] == before, 'import must not call providers (RL59)'
        answer = new.get('/dossiers/' + domain, headers={'Authorization': 'Bearer ' + token})
        assert answer.status_code == 200, 'old token remains valid'
        restored = answer.json()
        assert restored['state'] == 'ready'
        for name, old_field in old_dossier['fields'].items():
            field = restored['fields'][name]
            assert_field(field)
            if old_field['value'] is None:
                assert field['candidates'] == []
                continue
            expected = {(c['url'], c['excerpt'], c['provider']) for c in old_field['citations']}
            actual = {(c['url'], c['excerpt'], c['provider']) for c in field['candidates']}
            assert actual == expected
            assert len(field['candidates']) == len(old_field['citations'])
            for candidate in field['candidates']:
                assert candidate['value'] == old_field['value']
                assert candidate['kind'] is None and candidate['published_at'] is None
                assert instant(candidate['retrieved_at']) == instant(old_dossier['researched_at'])
        replay = new.post('/dossiers', headers=headers, json={'domain': domain})
        assert replay.status_code == 200 and replay.json() == creation.json()
        assert new_mock.get('/_mock/log').json()['calls'] == before, 'idempotent replay must not start a build'
        assert new.post('/_test/clock', json={'now':'2026-03-02T09:00:00Z'}).status_code == 204
        assert new_mock.post('/_mock/epoch', json={'epoch':1}).status_code == 204
        refresh = new.post('/dossiers/' + domain + '/refresh', headers={
            'Authorization': 'Bearer ' + token, 'Idempotency-Key': 'after-import-refresh'})
        assert refresh.status_code == 202
        refreshed = wait_ready(new, token, domain)
        assert refreshed['state'] == 'ready'
        assert instant(refreshed['researched_at']) > instant(old_dossier['researched_at'])
        for field in refreshed['fields'].values():
            assert_field(field)
            for candidate in field['candidates']:
                assert instant(candidate['retrieved_at']) == instant(refreshed['researched_at'])


def test_R2_69_R2_93_R2_108_RL59_browser_session_survives_stage1_import(frozen_deployment, deployment, browser_factory):
    """A browser holding a real Stage 1 token keeps working after that export imports."""
    domain = 'halvorsen-robotics.test'
    identity = {'now':'2026-03-01T09:00:00Z', 'users':[
        {'id':'upgrade-user', 'email':'upgrade@example.com', 'password':'correct horse', 'display_name':'Upgrade'}]}
    with httpx.Client(base_url=frozen_deployment['app'], timeout=10, trust_env=False) as old, \
         httpx.Client(base_url=frozen_deployment['mock'], headers=ADMIN, timeout=10, trust_env=False) as old_mock, \
         httpx.Client(base_url=deployment['app'], timeout=10, trust_env=False) as new, \
         httpx.Client(base_url=deployment['mock'], headers=ADMIN, timeout=10, trust_env=False) as new_mock:
        assert old_mock.post('/_mock/reset', json={'epoch':0}).status_code == 204
        assert old.post('/_test/reset', json=identity).status_code == 204
        old_login = old.post('/auth/login', json={'email':'upgrade@example.com', 'password':'correct horse'})
        assert old_login.status_code == 200
        old_token = old_login.json()['token']
        assert old.post('/dossiers', json={'domain':domain}, headers={
            'Authorization':'Bearer ' + old_token, 'Idempotency-Key':'upgrade-browser'}).status_code == 202
        old_dossier = wait_ready(old, old_token, domain)
        assert old_dossier['state'] == 'ready'
        snapshot = old.get('/_test/export', timeout=10).json()
        assert new_mock.post('/_mock/reset', json={'epoch':0}).status_code == 204
        assert new.post('/_test/import', json=snapshot, timeout=10).status_code == 204
        page = browser_factory(deployment)
        seen, captured = threading.Event(), []
        def capture_login(event):
            if event['request']['method'] == 'POST' and urlsplit(event['request']['url']).path == '/auth/login' and event.get('responseStatusCode') == 200:
                body = page.call('Fetch.getResponseBody', {'requestId':event['requestId']})
                raw = base64.b64decode(body['body']) if body.get('base64Encoded') else body['body'].encode()
                captured.append(json.loads(raw)['token'])
                seen.set()
            page.call('Fetch.continueRequest', {'requestId':event['requestId']})
        page.on('Fetch.requestPaused', capture_login)
        page.call('Fetch.enable', {'patterns':[{'urlPattern':'*/auth/login', 'requestStage':'Response'}]})
        login(page, 'upgrade@example.com')
        assert seen.wait(5) and len(captured) == 1
        page.call('Fetch.disable')
        replaced = page.evaluate('''(() => { let count=0; for (let i=0;i<localStorage.length;i++) {
            const k=localStorage.key(i), v=localStorage.getItem(k);
            if (v && v.includes(%s)) { localStorage.setItem(k,v.replaceAll(%s,%s)); count++; }
        } return count; })()''' % (json.dumps(captured[0]), json.dumps(captured[0]), json.dumps(old_token)))
        assert replaced >= 1, 'login must retain its token in localStorage (RL63)'
        page.navigate('/dossiers/' + domain)
        page.wait(present('dossier-domain'))
        page.wait(present('current-user'))
        before = new_mock.get('/_mock/log').json()['calls']
        assert new.post('/_test/import', json=snapshot, timeout=10).status_code == 204
        assert new_mock.get('/_mock/log').json()['calls'] == before
        responses, done = [], threading.Event()
        def observe(event):
            response = event['response']
            if urlsplit(response['url']).path == '/dossiers/' + domain and response['mimeType'].startswith('application/json'):
                responses.append(response['status'])
                done.set()
        page.on('Network.responseReceived', observe)
        page.call('Network.enable')
        page.click('dossier-reload')
        assert done.wait(15) and responses[-1] == 200, 'existing browser token must authorize the reload'
        page.wait(present('current-user'))
        assert 'Upgrade' in page.evaluate(node('current-user') + '.innerText')
        assert page.evaluate(node('dossier-domain') + '.innerText.trim()') == domain
        page.call('Network.disable')


@pytest.mark.parametrize('operation', ['create', 'refresh'])
def test_R2_74_R2_79_R2_92_R2_106_R2_108_lost_stage1_write_retries_after_import(frozen_deployment, deployment, upgrade_browser, operation):
    """A live browser retries a lost Stage 1 create or refresh after Stage 2 import."""
    page, proxy = upgrade_browser
    domain = 'halvorsen-robotics.test'
    identity = {'now':'2026-03-01T09:00:00Z', 'users':[
        {'id':'upgrade-user', 'email':'upgrade@example.com', 'password':'correct horse', 'display_name':'Upgrade'}]}
    with httpx.Client(base_url=frozen_deployment['app'], timeout=10, trust_env=False) as old, \
         httpx.Client(base_url=frozen_deployment['mock'], headers=ADMIN, timeout=10, trust_env=False) as old_mock, \
         httpx.Client(base_url=deployment['app'], timeout=10, trust_env=False) as new, \
         httpx.Client(base_url=deployment['mock'], headers=ADMIN, timeout=10, trust_env=False) as new_mock, \
         httpx.Client(base_url=proxy, timeout=10, trust_env=False) as bridge:
        assert old_mock.post('/_mock/reset', json={'epoch':0}).status_code == 204
        assert new_mock.post('/_mock/reset', json={'epoch':0}).status_code == 204
        assert old.post('/_test/reset', json=identity).status_code == 204
        old_login = old.post('/auth/login', json={'email':'upgrade@example.com', 'password':'correct horse'})
        assert old_login.status_code == 200
        old_token = old_login.json()['token']
        if operation == 'refresh':
            assert old.post('/dossiers', json={'domain':domain}, headers={
                'Authorization':'Bearer ' + old_token, 'Idempotency-Key':'pre-upgrade-create'}).status_code == 202
            assert wait_ready(old, old_token, domain)['state'] == 'ready'
        login(page, 'upgrade@example.com')
        if operation == 'create':
            page.navigate('/')
            writes = records_after_commit(page, '/dossiers')
            page.fill('research-domain', domain)
            page.click('research-submit')
            page.wait(present('research-uncertain'), timeout=20)
            assert not page.evaluate(present('research-error'))
        else:
            page.navigate('/dossiers/' + domain)
            page.wait(present('dossier-refresh'))
            writes = records_after_commit(page, '/dossiers/' + domain + '/refresh')
            page.click('dossier-refresh')
            page.wait(present('refresh-uncertain'), timeout=20)
            assert not page.evaluate(present('refresh-error'))
        assert wait_ready(old, old_token, domain)['state'] == 'ready'
        snapshot = old.get('/_test/export', timeout=10).json()
        before = new_mock.get('/_mock/log').json()['calls']
        assert new.post('/_test/import', json=snapshot, timeout=10).status_code == 204
        assert bridge.post('/_probe/switch').status_code == 204
        if operation == 'create':
            page.click('research-submit')
            page.wait(present('dossier-domain'), timeout=30)
        else:
            page.click('dossier-refresh')
            page.wait('!' + present('refresh-uncertain'), timeout=30)
        assert_same_write(writes)
        assert page.evaluate(node('dossier-domain') + '.innerText.trim()') == domain
        page.wait(present('current-user'))
        assert 'Upgrade' in page.evaluate(node('current-user') + '.innerText')
        assert new_mock.get('/_mock/log').json()['calls'] == before, 'retry must not start another build'
        page.call('Fetch.disable')
