"""Browser checks use Chromium on the isolated Docker network and public routes only."""
import json
from pathlib import Path
import tempfile
import threading
import time

import pytest

from oracle import FIELDS, amounts
from test_candidates import wait_ready

def node(testid):
    return 'document.querySelector(' + json.dumps('[data-testid="' + testid + '"]') + ')'


def present(testid):
    return '!!' + node(testid)


def attribute(page, testid, name):
    page.wait(present(testid))
    return page.evaluate(node(testid) + '.getAttribute(' + json.dumps(name) + ')')


def text(page, testid):
    page.wait(present(testid))
    return page.evaluate(node(testid) + '.innerText')


def login(page, email='ada@example.com', password='correct horse'):
    page.navigate('/login')
    page.fill('login-email', email)
    page.fill('login-password', password)
    page.click('login-submit')
    page.wait(present('current-user'))


def test_R2_53_R2_55_R2_56_R2_57_R2_58_R2_59_R2_60_RL63_html_and_api_negotiation(api, mock):
    """Browser shells are public and the same dossier path serves authenticated JSON."""
    assert api.post('/_test/reset', json={'now':'2026-03-01T09:00:00Z', 'users':[]}).status_code == 204
    for path in ('/', '/signup', '/login', '/contested', '/dossiers/example.test',
                 '/dossiers/example.test/evidence'):
        answer = api.get(path, headers={'Accept':'text/html'})
        assert answer.status_code == 200, (path, answer.status_code)
        assert 'text/html' in answer.headers.get('content-type', '').lower()
    api_response = api.get('/dossiers/example.test', headers={'Accept':'application/json'})
    assert api_response.status_code == 401
    assert api_response.json()['error']['code'] == 'unauthenticated'


def test_R1_22_browser_reaches_health_on_isolated_network(browser_page):
    """A real browser can reach the service without outside network access."""
    browser_page.navigate('/health')
    assert json.loads(browser_page.evaluate('document.body.innerText'))['status'] == 'ok'


def test_R1_22_browser_can_intercept_a_response(browser_page):
    """The network interceptor can observe and release a real browser response."""
    seen = threading.Event()
    def resume(event):
        seen.set()
        browser_page.call('Fetch.continueRequest', {'requestId': event['requestId']})
    browser_page.on('Fetch.requestPaused', resume)
    browser_page.call('Fetch.enable', {'patterns': [{'urlPattern': '*health*', 'requestStage': 'Response'}]})
    browser_page.navigate('/health')
    assert seen.wait(5)
    assert json.loads(browser_page.evaluate('document.body.innerText'))['status'] == 'ok'
    browser_page.call('Fetch.disable')


def test_R1_22_browser_can_drop_a_committed_response(api, seeded, browser_page):
    """The test transport observes request identity before dropping a real response."""
    seen = []
    def drop(event):
        request = event['request']
        headers = {key.lower():value for key,value in request['headers'].items()}
        seen.append((headers.get('idempotency-key'), request.get('postData', '')))
        browser_page.call('Fetch.failRequest', {'requestId':event['requestId'], 'errorReason':'Failed'})
    browser_page.navigate('/health')
    browser_page.on('Fetch.requestPaused', drop)
    browser_page.call('Fetch.enable', {'patterns':[{'urlPattern':'*/auth/login', 'requestStage':'Response'}]})
    result = browser_page.evaluate('''fetch('/auth/login', {method:'POST', headers:{'Content-Type':'application/json',
        'Idempotency-Key':'browser-transport-check'}, body:JSON.stringify({email:'ada@example.com',
        password:'correct horse'})}).then(()=>'received').catch(()=>'failed')''')
    assert result == 'failed' and len(seen) == 1
    assert seen[0][0] == 'browser-transport-check' and json.loads(seen[0][1])['email'] == 'ada@example.com'
    browser_page.call('Fetch.disable')


def test_R2_54_R2_57_R2_71_R2_72_R2_73_R2_78_R2_94_R2_102_empty_not_found_and_refused_research(api, seeded, browser_page):
    """Empty and missing data are distinct from a rejected domain submission."""
    login(browser_page)
    browser_page.navigate('/')
    browser_page.wait(present('empty-dossiers'))
    browser_page.fill('research-domain', 'not a valid domain')
    browser_page.click('research-submit')
    browser_page.wait(present('research-error'))
    assert not browser_page.evaluate(present('research-uncertain'))
    browser_page.screenshot(Path(tempfile.gettempdir()) / f'{browser_page.artifact_prefix}-stage2-refused.png')
    browser_page.navigate('/contested')
    browser_page.wait(present('empty-contested'))
    browser_page.navigate('/dossiers/missing.test')
    browser_page.wait(present('dossier-not-found'))
    assert not browser_page.evaluate(present('field-ceo'))
    browser_page.navigate('/dossiers/not%20a%20domain')
    browser_page.wait(present('dossier-not-found'))
    assert not browser_page.evaluate(present('field-ceo'))


def test_R2_55_R2_63_failed_dossier_has_a_distinct_state(api, mock, seeded, browser_page):
    """A fully refused build is visibly failed and remains inspectable."""
    for provider, methods in [('nimble',['search','extract','research']), ('tavily',['search','extract'])]:
        assert mock.post('/_mock/faults', json={'provider':provider, 'methods':methods, 'mode':'error'}).status_code == 204
    login(browser_page)
    browser_page.navigate('/')
    browser_page.fill('research-domain', 'halvorsen-robotics.test')
    browser_page.click('research-submit')
    browser_page.wait(present('dossier-state') + ' && ' + node('dossier-state') +
                      '.innerText.trim() === "failed"', timeout=30)
    browser_page.screenshot(Path(tempfile.gettempdir()) / f'{browser_page.artifact_prefix}-stage2-failed.png')


@pytest.mark.parametrize('width', [375, 1440])
def test_R2_53_R2_54_R2_58_R2_59_R2_64_R2_65_R2_66_R2_67_R2_68_R2_69_R2_70_auth_and_layout(deployment, mock, api, browser_factory, width):
    """Signup, logout and login work at mobile and desktop widths without horizontal scrolling."""
    assert api.post('/_test/reset', json={'now':'2026-03-01T09:00:00Z', 'users':[]}).status_code == 204
    page = browser_factory(deployment, width)
    page.navigate('/signup')
    assert page.evaluate('window.innerWidth') == width, 'the screen must use the requested CSS viewport width'
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    page.call('Input.dispatchKeyEvent', {'type':'keyDown', 'key':'Tab', 'code':'Tab', 'windowsVirtualKeyCode':9})
    page.call('Input.dispatchKeyEvent', {'type':'keyUp', 'key':'Tab', 'code':'Tab', 'windowsVirtualKeyCode':9})
    assert page.evaluate('document.activeElement !== document.body')
    page.screenshot(Path(tempfile.gettempdir()) / f'{page.artifact_prefix}-stage2-signup-{width}.png')
    page.fill('signup-email', 'browser@example.com')
    page.fill('signup-password', 'correct horse')
    page.fill('signup-display-name', 'Browser User')
    page.click('signup-submit')
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if api.post('/auth/login', json={'email':'browser@example.com', 'password':'correct horse'}).status_code == 200:
            break
        time.sleep(.05)
    else:
        raise AssertionError('signup did not create the user')
    if page.evaluate(present('current-user')):
        assert 'Browser User' in text(page, 'current-user')
        page.click('logout-button')
        page.wait('!' + present('current-user'))
    page.navigate('/login')
    assert page.evaluate('window.innerWidth') == width
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    page.screenshot(Path(tempfile.gettempdir()) / f'{page.artifact_prefix}-stage2-login-{width}.png')
    page.fill('login-email', 'browser@example.com')
    page.fill('login-password', 'wrong password')
    page.click('login-submit')
    page.wait(present('auth-error'))
    page.fill('login-password', 'correct horse')
    page.click('login-submit')
    page.wait(present('current-user'))
    assert 'Browser User' in page.evaluate(node('current-user') + '.innerText')
    assert not page.evaluate(present('auth-error'))
    for path in ('/', '/contested'):
        page.navigate(path)
        page.wait(present('current-user'))
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    page.screenshot(Path(tempfile.gettempdir()) / f'{page.artifact_prefix}-stage2-list-{width}.png')
    page.click('logout-button')
    page.wait('!' + present('current-user'))


@pytest.mark.parametrize('width', [375, 1440])
def test_R2_52_R2_54_R2_55_R2_56_R2_57_R2_61_R2_62_R2_63_R2_64_R2_75_R2_76_R2_77_R2_80_R2_81_R2_82_R2_83_R2_84_R2_85_R2_86_R2_87_R2_88_R2_89_R2_93_R2_95_R2_97_R2_98_R2_99_R2_100_R2_101_R2_102_dossier_evidence_and_contested(deployment, api, seeded, browser_factory, width):
    """Rendered dossier, evidence and contested views reflect the public API in order."""
    domain = 'halvorsen-robotics.test'
    token = seeded[0]
    headers = {'Authorization':'Bearer ' + token, 'Idempotency-Key':'browser-evidence'}
    assert api.post('/dossiers', headers=headers, json={'domain':domain}).status_code == 202
    dossier = wait_ready(api, token, domain)
    assert dossier['state'] == 'ready'
    other_domain = 'ashgrove-solar.test'
    assert api.post('/dossiers', headers={'Authorization':'Bearer ' + token, 'Idempotency-Key':'browser-other'},
                    json={'domain':other_domain}).status_code == 202
    other = wait_ready(api, token, other_domain)
    assert other['state'] == 'ready'
    page = browser_factory(deployment, width)
    login(page)
    page.navigate('/')
    page.wait(present('dossier-item-' + domain))
    page.wait(present('dossier-item-' + other_domain))
    list_ids = page.evaluate('Array.from(document.querySelectorAll("[data-testid^=dossier-item-]"), '
                             'x => x.getAttribute("data-testid"))')
    assert list_ids == ['dossier-item-' + other_domain, 'dossier-item-' + domain]
    assert attribute(page, 'dossier-item-' + domain, 'data-state') == 'ready'
    assert domain in text(page, 'dossier-item-' + domain)
    legal = dossier['fields']['legal_name']['value']
    if legal is not None:
        assert legal in text(page, 'dossier-item-' + domain)
    page.fill('dossier-search', 'no-such-company')
    page.wait(present('empty-dossiers'))
    page.fill('dossier-search', 'halvorsen')
    page.wait(present('dossier-item-' + domain))

    page.navigate('/dossiers/' + domain.upper())
    page.wait(present('dossier-domain') + ' && ' + node('dossier-domain') + '.innerText.trim() === ' + json.dumps(domain))
    page.wait(present('dossier-state') + ' && ' + node('dossier-state') + '.innerText.trim() === "ready"')
    page.wait(present('current-user'))
    assert page.evaluate('window.innerWidth') == width
    assert text(page, 'dossier-domain').strip() == domain
    assert text(page, 'dossier-state').strip() == 'ready'
    assert attribute(page, 'dossier-spent', 'data-units') == str(dossier['spent_units'])
    assert page.evaluate(present('dossier-researched-at')) == (dossier['researched_at'] is not None)
    for index, field in enumerate(FIELDS):
        actual = dossier['fields'][field]
        assert attribute(page, 'field-' + field, 'data-status') == actual['status']
        if index:
            ordering = node('field-' + FIELDS[index-1]) + '.compareDocumentPosition(' + node('field-' + field) + ') & 4'
            assert page.evaluate(ordering), 'fields must follow the specification order'
        assert page.evaluate(present('field-value-' + field)) == (actual['value'] is not None)
        if actual['value'] is not None:
            assert attribute(page, 'field-value-' + field, 'data-value') == str(actual['value'])
        assert page.evaluate(present('field-contested-' + field)) == (actual['status'] == 'contested')
        page.wait(present('field-citations-' + field))
        for n, citation in enumerate(actual['citations'], 1):
            testid = f'citation-{field}-{n}'
            assert citation['excerpt'] in text(page, testid)
            assert attribute(page, testid, 'data-provider') == citation['provider']
            assert page.evaluate(node(testid) + '.querySelector("a").getAttribute("href")') == citation['url']
    assert attribute(page, 'dossier-evidence-link', 'href').endswith('/dossiers/' + domain + '/evidence')
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    page.screenshot(Path(tempfile.gettempdir()) / f'{page.artifact_prefix}-stage2-dossier-{width}.png')

    page.navigate('/dossiers/' + domain + '/evidence')
    page.wait(present('current-user'))
    for field in FIELDS:
        candidates = dossier['fields'][field]['candidates']
        page.wait(present('evidence-' + field))
        assert page.evaluate(present('evidence-empty-' + field)) == (not candidates)
        for n, candidate in enumerate(candidates, 1):
            testid = f'candidate-{field}-{n}'
            rendered = text(page, testid)
            assert candidate['excerpt'] in rendered
            if isinstance(candidate['value'], str):
                assert candidate['value'] in rendered
            elif field == 'founded_year':
                assert str(candidate['value']) in rendered
            for name in ('value', 'provider', 'kind', 'url', 'published-at', 'selected'):
                key = name.replace('-', '_')
                value = candidate.get(key)
                expected = '' if value is None else (str(value).lower() if isinstance(value, bool) else str(value))
                assert attribute(page, testid, 'data-' + name) == expected
            if n > 1:
                ordering = node(f'candidate-{field}-{n-1}') + '.compareDocumentPosition(' + node(testid) + ') & 4'
                assert page.evaluate(ordering), 'candidates must retain API order'
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    page.screenshot(Path(tempfile.gettempdir()) / f'{page.artifact_prefix}-stage2-evidence-{width}.png')

    page.navigate('/contested')
    page.wait(present('current-user'))
    contested = [(item_domain, field, item) for item_domain, item in [(other_domain, other), (domain, dossier)]
                 for field in FIELDS if item['fields'][field]['status'] == 'contested']
    if not contested:
        page.wait(present('empty-contested'))
    else:
        page.wait(present('contested-list'))
        for item_domain, field, item in contested:
            testid = f'contested-item-{item_domain}-{field}'
            assert attribute(page, testid, 'data-value') == str(item['fields'][field]['value'])
            rendered = text(page, testid)
            assert item_domain in rendered
            labels = {'legal_name':('legal name','registered name'), 'hq_city':('hq city','headquarters','head office'),
                      'ceo':('ceo','chief executive'), 'founded_year':('founded','founding'),
                      'headcount_range':('headcount','employees','workforce'), 'funding_total':('funding','raised','investment')}
            assert any(label in rendered.lower().replace('_', ' ') for label in labels[field])
            for value in {candidate['value'] for candidate in item['fields'][field]['candidates']}:
                if isinstance(value, str):
                    assert value in rendered
                elif field == 'funding_total':
                    digits = ''.join(char for char in rendered if char.isdecimal())
                    assert value in {amount for _, amount in amounts(rendered)} or str(value) in digits
                else:
                    assert str(value) in rendered
            link = page.evaluate('(() => {const e=' + node(testid) +
                                 '; const a=e.matches("a") ? e : e.querySelector("a"); return a && a.getAttribute("href")})()')
            assert link.endswith('/dossiers/' + item_domain + '/evidence')
        ids = page.evaluate('Array.from(document.querySelectorAll("[data-testid^=contested-item-]"), '
                            'x => x.getAttribute("data-testid"))')
        assert ids == [f'contested-item-{item_domain}-{field}' for item_domain,field,_ in contested]
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    page.screenshot(Path(tempfile.gettempdir()) / f'{page.artifact_prefix}-stage2-contested-{width}.png')
