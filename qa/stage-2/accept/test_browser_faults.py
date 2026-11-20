"""Browser retry and read ordering with provider and transport faults."""
import base64
import json
from pathlib import Path
import tempfile
import threading
import time
from urllib.parse import urlsplit

import pytest

from test_browser import login, node, present
from test_candidates import wait_ready


def records_after_commit(page, endpoint):
    """Drop the first committed write response, then pass the retry through."""
    requests = []
    lock = threading.Lock()
    def intercepted(event):
        request = event['request']
        if request['method'] == 'POST' and urlsplit(request['url']).path == endpoint:
            headers = {name.lower(): value for name, value in request.get('headers', {}).items()}
            body = request.get('postData', '')
            with lock:
                requests.append((headers.get('idempotency-key'), body, event.get('responseStatusCode')))
                first = len(requests) == 1
            if first:
                page.call('Fetch.failRequest', {'requestId': event['requestId'], 'errorReason': 'Failed'})
                return
        page.call('Fetch.continueRequest', {'requestId': event['requestId']})
    page.on('Fetch.requestPaused', intercepted)
    page.call('Fetch.enable', {'patterns': [{'urlPattern':'*dossiers*', 'requestStage':'Response'}]})
    return requests


def assert_same_write(requests):
    assert len(requests) >= 2
    assert requests[0][0] and requests[0][0] == requests[1][0], 'retry must reuse the idempotency key'
    assert requests[0][1] == requests[1][1], 'retry must reuse the request body'
    assert requests[0][2] in (200, 202) and requests[1][2] == 200, 'the committed write must replay'


def test_R2_71_R2_72_R2_79_R2_107_existing_dossier_created_by_another_client_does_not_rebuild(api, mock, seeded, browser_page):
    """A browser opens a dossier created after its list was loaded, without another build."""
    domain = 'halvorsen-robotics.test'
    login(browser_page)
    browser_page.navigate('/')
    browser_page.wait(present('empty-dossiers'))
    assert api.post('/dossiers', json={'domain':domain}, headers={
        'Authorization':'Bearer ' + seeded[1], 'Idempotency-Key':'other-client-create'}).status_code == 202
    assert wait_ready(api, seeded[1], domain)['state'] == 'ready'
    before = len(mock.get('/_mock/log').json()['calls'])
    browser_page.fill('research-domain', domain.upper())
    browser_page.click('research-submit')
    browser_page.wait(present('dossier-domain'))
    assert browser_page.evaluate(node('dossier-domain') + '.innerText.trim()') == domain
    assert mock.get('/_mock/log').json()['calls'][before:] == [], 'existing dossier must not rebuild'


def test_R2_71_R2_72_R2_73_R2_74_R2_79_R2_103_R2_106_research_lost_response_reuses_key(api, mock, seeded, browser_page):
    """A lost post-commit response is uncertain and an identical retry starts only one build."""
    domain = 'halvorsen-robotics.test'
    login(browser_page)
    browser_page.navigate('/')
    requests = records_after_commit(browser_page, '/dossiers')
    browser_page.fill('research-domain', domain)
    browser_page.click('research-submit')
    browser_page.wait(present('research-uncertain'), timeout=20)
    assert browser_page.evaluate(node('research-uncertain') + '.innerText.trim().length > 0')
    assert not browser_page.evaluate(present('research-error'))
    browser_page.screenshot(Path(tempfile.gettempdir()) / f'{browser_page.artifact_prefix}-stage2-research-uncertain.png')
    browser_page.click('research-submit')
    browser_page.wait(present('dossier-domain'), timeout=30)
    assert_same_write(requests)
    assert not browser_page.evaluate(present('research-uncertain'))
    assert not browser_page.evaluate(present('research-error'))
    assert wait_ready(api, seeded[0], domain)['state'] == 'ready'
    calls = mock.get('/_mock/log').json()['calls']
    assert sum(c['method'] == 'search' and c['query'] == domain and c['status'] == 200 for c in calls) == 1
    browser_page.call('Fetch.disable')


def test_R2_90_R2_91_R2_92_R2_103_R2_106_refresh_lost_response_reuses_key(api, mock, seeded, browser_page):
    """A lost refresh response remains retryable without a duplicate build."""
    domain = 'halvorsen-robotics.test'
    headers = {'Authorization': 'Bearer ' + seeded[0], 'Idempotency-Key':'first-build'}
    assert api.post('/dossiers', headers=headers, json={'domain': domain}).status_code == 202
    assert wait_ready(api, seeded[0], domain)['state'] == 'ready'
    before = len(mock.get('/_mock/log').json()['calls'])
    login(browser_page)
    browser_page.navigate('/dossiers/' + domain)
    browser_page.wait(present('dossier-refresh'))
    requests = records_after_commit(browser_page, '/dossiers/' + domain + '/refresh')
    browser_page.click('dossier-refresh')
    browser_page.wait(present('refresh-uncertain'), timeout=20)
    assert browser_page.evaluate(node('refresh-uncertain') + '.innerText.trim().length > 0')
    assert not browser_page.evaluate(present('refresh-error'))
    browser_page.screenshot(Path(tempfile.gettempdir()) / f'{browser_page.artifact_prefix}-stage2-refresh-uncertain.png')
    browser_page.click('dossier-refresh')
    browser_page.wait('!' + present('refresh-uncertain'), timeout=30)
    assert_same_write(requests)
    assert not browser_page.evaluate(present('refresh-error'))
    assert wait_ready(api, seeded[0], domain)['state'] == 'ready'
    calls = mock.get('/_mock/log').json()['calls'][before:]
    assert sum(c['method'] == 'search' and c['query'] == domain and c['status'] == 200 for c in calls) == 1
    browser_page.call('Fetch.disable')


def test_R2_90_R2_91_confirmed_refresh_refusal_is_not_uncertain(api, seeded, browser_page):
    """A confirmed 4xx refresh response shows an error, not an unknown outcome."""
    domain = 'halvorsen-robotics.test'
    headers = {'Authorization':'Bearer ' + seeded[0], 'Idempotency-Key':'refusal-create'}
    assert api.post('/dossiers', headers=headers, json={'domain':domain}).status_code == 202
    assert wait_ready(api, seeded[0], domain)['state'] == 'ready'
    login(browser_page)
    browser_page.navigate('/dossiers/' + domain)
    browser_page.wait(present('dossier-refresh'))
    def refuse(event):
        if event['request']['method'] == 'POST' and urlsplit(event['request']['url']).path.endswith('/refresh'):
            body = json.dumps({'error':{'code':'idempotency_key_reuse', 'message':'The refresh was refused.'}}).encode()
            browser_page.call('Fetch.fulfillRequest', {'requestId':event['requestId'], 'responseCode':409,
                'responseHeaders':[{'name':'Content-Type', 'value':'application/json; charset=utf-8'}],
                'body':base64.b64encode(body).decode()})
        else:
            browser_page.call('Fetch.continueRequest', {'requestId':event['requestId']})
    browser_page.on('Fetch.requestPaused', refuse)
    browser_page.call('Fetch.enable', {'patterns':[{'urlPattern':'*/dossiers/*/refresh', 'requestStage':'Request'}]})
    browser_page.click('dossier-refresh')
    browser_page.wait(present('refresh-error'))
    assert not browser_page.evaluate(present('refresh-uncertain'))
    browser_page.call('Fetch.disable')


def test_R2_63_loading_state_screenshot_with_delayed_dossier_read(api, seeded, browser_page):
    """Capture a genuine in-flight read for visual review of the loading state."""
    domain = 'halvorsen-robotics.test'
    assert api.post('/dossiers', json={'domain':domain}, headers={
        'Authorization':'Bearer ' + seeded[0], 'Idempotency-Key':'loading-screenshot'}).status_code == 202
    assert wait_ready(api, seeded[0], domain)['state'] == 'ready'
    login(browser_page)
    held, release = threading.Event(), threading.Event()
    def delay(event):
        request = event['request']
        headers = {name.lower():value for name,value in request.get('headers',{}).items()}
        if (request['method'] == 'GET' and urlsplit(request['url']).path == '/dossiers/' + domain and
                'text/html' not in headers.get('accept','').lower() and not held.is_set()):
            held.set()
            assert release.wait(20), 'test did not release the loading read'
        browser_page.call('Fetch.continueRequest', {'requestId':event['requestId']})
    browser_page.on('Fetch.requestPaused', delay)
    browser_page.call('Fetch.enable', {'patterns':[{'urlPattern':'*/dossiers/*', 'requestStage':'Request'}]})
    try:
        browser_page.navigate('/dossiers/' + domain)
        assert held.wait(10), 'the browser must read the dossier through the API'
        browser_page.screenshot(Path(tempfile.gettempdir()) / f'{browser_page.artifact_prefix}-stage2-loading.png')
        release.set()
        browser_page.wait(present('dossier-domain'))
    finally:
        release.set()
        browser_page.call('Fetch.disable')


def test_R2_93_R2_103_R2_104_latest_reload_wins_over_delayed_earlier_read(api, mock, seeded, browser_page):
    """A delayed response from an earlier reload cannot overwrite a later reload."""
    domain = 'halvorsen-robotics.test'
    headers = {'Authorization': 'Bearer ' + seeded[0], 'Idempotency-Key':'reload-create'}
    assert api.post('/dossiers', headers=headers, json={'domain': domain}).status_code == 202
    initial = wait_ready(api, seeded[0], domain)
    assert initial['state'] == 'ready'
    login(browser_page)
    browser_page.navigate('/dossiers/' + domain)
    browser_page.wait(present('dossier-reload'))
    held, release = threading.Event(), threading.Event()
    lock = threading.Lock()
    count = 0
    def delay_first(event):
        nonlocal count
        request = event['request']
        if request['method'] == 'GET' and urlsplit(request['url']).path == '/dossiers/' + domain:
            with lock:
                count += 1
                first = count == 1
            if first:
                held.set()
                assert release.wait(30), 'test did not release the delayed response'
        browser_page.call('Fetch.continueRequest', {'requestId':event['requestId']})
    browser_page.on('Fetch.requestPaused', delay_first)
    browser_page.call('Fetch.enable', {'patterns':[{'urlPattern':'*/dossiers/*', 'requestStage':'Response'}]})
    try:
        browser_page.click('dossier-reload')
        assert held.wait(10), 'first reload was not sent'
        assert mock.post('/_mock/epoch', json={'epoch': 1}).status_code == 204
        refreshed = api.post('/dossiers/' + domain + '/refresh',
                             headers={'Authorization':'Bearer ' + seeded[0], 'Idempotency-Key':'reload-refresh'})
        assert refreshed.status_code == 202
        newer = wait_ready(api, seeded[0], domain)
        old_ceo, new_ceo = initial['fields']['ceo']['value'], newer['fields']['ceo']['value']
        assert old_ceo != new_ceo, 'controlled epochs must give distinct CEOs'
        browser_page.click('dossier-reload')
        expected = json.dumps(str(new_ceo))
        browser_page.wait(present('field-value-ceo') + ' && ' + node('field-value-ceo') +
                          '.getAttribute("data-value") === ' + expected, timeout=20)
        release.set()
        time.sleep(.5)
        assert browser_page.evaluate(node('field-value-ceo') + '.getAttribute("data-value")') == str(new_ceo)
    finally:
        release.set()
        browser_page.call('Fetch.disable')


def test_R2_90_R2_96_R2_103_R2_105_browser_follows_another_clients_refresh(api, mock, seeded, browser_page):
    """A browser joins an existing build and polls at least once every two seconds."""
    domain = 'halvorsen-robotics.test'
    auth = {'Authorization': 'Bearer ' + seeded[0]}
    assert api.post('/dossiers', headers={**auth, 'Idempotency-Key':'poll-create'},
                    json={'domain':domain}).status_code == 202
    assert wait_ready(api, seeded[0], domain)['state'] == 'ready'
    login(browser_page)
    browser_page.navigate('/dossiers/' + domain)
    browser_page.wait(present('dossier-refresh'))
    assert mock.post('/_mock/epoch', json={'epoch':1}).status_code == 204
    assert mock.post('/_mock/faults', json={'provider':'nimble', 'methods':['search','extract','research'],
                                            'mode':'delay', 'seconds':2}).status_code == 204
    before = len(mock.get('/_mock/log').json()['calls'])
    times = []
    lock = threading.Lock()
    def observed(event):
        request = event['request']
        if request['method'] == 'GET' and urlsplit(request['url']).path == '/dossiers/' + domain:
            with lock:
                times.append(event['timestamp'])
    browser_page.on('Network.requestWillBeSent', observed)
    browser_page.call('Network.enable')
    assert api.post('/dossiers/' + domain + '/refresh',
                    headers={**auth, 'Idempotency-Key':'other-client-refresh'}).status_code == 202
    browser_page.click('dossier-refresh')
    browser_page.wait(present('dossier-state') + ' && ' + node('dossier-state') +
                      '.innerText.trim() === "building"', timeout=15)
    browser_page.screenshot(Path(tempfile.gettempdir()) / f'{browser_page.artifact_prefix}-stage2-building.png')
    browser_page.wait(present('dossier-state') + ' && ' + node('dossier-state') +
                      '.innerText.trim() === "ready"', timeout=45)
    newest = wait_ready(api, seeded[0], domain)
    browser_page.wait(present('field-value-ceo') + ' && ' + node('field-value-ceo') +
                      '.getAttribute("data-value") === ' + json.dumps(str(newest['fields']['ceo']['value'])))
    with lock:
        observed_times = sorted(times)
    assert len(observed_times) >= 2, 'a sufficiently slow build must be polled'
    assert max(b-a for a, b in zip(observed_times, observed_times[1:])) <= 2.25
    calls = mock.get('/_mock/log').json()['calls'][before:]
    assert sum(c['method'] == 'search' and c['query'] == domain and c['status'] == 200 for c in calls) == 1
    browser_page.call('Network.disable')


def test_R2_93_R2_96_R2_104_stale_build_poll_cannot_overwrite_ready(api, mock, seeded, browser_page):
    """An earlier building response delayed in transit cannot replace a later ready read."""
    domain = 'halvorsen-robotics.test'
    login(browser_page)
    assert mock.post('/_mock/faults', json={'provider':'nimble', 'methods':['search','extract','research'],
                                            'mode':'delay', 'seconds':2}).status_code == 204
    assert api.post('/dossiers', json={'domain':domain}, headers={
        'Authorization':'Bearer ' + seeded[0], 'Idempotency-Key':'poll-order'}).status_code == 202
    browser_page.navigate('/dossiers/' + domain)
    browser_page.wait(present('dossier-state') + ' && ' + node('dossier-state') +
                      '.innerText.trim() === "building"')
    held, release = threading.Event(), threading.Event()
    lock = threading.Lock()
    def delay_building(event):
        request = event['request']
        if request['method'] == 'GET' and urlsplit(request['url']).path == '/dossiers/' + domain:
            body = browser_page.call('Fetch.getResponseBody', {'requestId':event['requestId']})
            raw = base64.b64decode(body['body']) if body.get('base64Encoded') else body['body'].encode()
            value = json.loads(raw)
            with lock:
                should_hold = value.get('state') == 'building' and not held.is_set()
                if should_hold:
                    held.set()
            if should_hold:
                assert release.wait(30), 'test did not release the delayed poll'
        browser_page.call('Fetch.continueRequest', {'requestId':event['requestId']})
    browser_page.on('Fetch.requestPaused', delay_building)
    browser_page.call('Fetch.enable', {'patterns':[{'urlPattern':'*/dossiers/*', 'requestStage':'Response'}]})
    try:
        assert held.wait(15), 'test requires a building poll to be delayed'
        newest = wait_ready(api, seeded[0], domain)
        assert newest['state'] == 'ready'
        browser_page.click('dossier-reload')
        browser_page.wait(present('dossier-state') + ' && ' + node('dossier-state') +
                          '.innerText.trim() === "ready"', timeout=20)
        release.set()
        time.sleep(.5)
        assert browser_page.evaluate(node('dossier-state') + '.innerText.trim()') == 'ready'
        if newest['fields']['ceo']['value'] is not None:
            assert browser_page.evaluate(node('field-value-ceo') + '.getAttribute("data-value")') == str(newest['fields']['ceo']['value'])
    finally:
        release.set()
        browser_page.call('Fetch.disable')
