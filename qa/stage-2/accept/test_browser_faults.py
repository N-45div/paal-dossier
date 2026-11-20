"""Browser retry and read ordering with provider and transport faults."""
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
                requests.append((headers.get('idempotency-key'), body))
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
    browser_page.screenshot(Path(tempfile.gettempdir()) / 'prover-stage2-research-uncertain.png')
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
    browser_page.screenshot(Path(tempfile.gettempdir()) / 'prover-stage2-refresh-uncertain.png')
    browser_page.click('dossier-refresh')
    browser_page.wait('!' + present('refresh-uncertain'), timeout=30)
    assert_same_write(requests)
    assert not browser_page.evaluate(present('refresh-error'))
    assert wait_ready(api, seeded[0], domain)['state'] == 'ready'
    calls = mock.get('/_mock/log').json()['calls'][before:]
    assert sum(c['method'] == 'search' and c['query'] == domain and c['status'] == 200 for c in calls) == 1
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
    browser_page.screenshot(Path(tempfile.gettempdir()) / 'prover-stage2-building.png')
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
