"""Independent candidate selection and provenance through public HTTP interfaces."""
import re
import time
from urllib.parse import urlsplit

import httpx

from conftest import ADMIN
from oracle import FIELDS, candidates as supported, prose
from selection_oracle import assert_field, instant


def norm(value):
    return re.sub(r'\s+', ' ', value).strip()


def wait_ready(api, token, domain):
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        response = api.get('/dossiers/' + domain, headers={'Authorization': 'Bearer ' + token}, timeout=5)
        assert response.status_code == 200
        dossier = response.json()
        if dossier['state'] != 'building':
            return dossier
        time.sleep(.05)
    raise AssertionError('build did not finish')


def build_controlled(deployment):
    domain = 'selection-labs.test'
    with httpx.Client(base_url=deployment['app'], timeout=10, trust_env=False) as api, \
         httpx.Client(base_url=deployment['mock'], headers=ADMIN, timeout=10, trust_env=False) as mock:
        assert mock.post('/_mock/reset', json={'epoch': 0}).status_code == 204
        fixture = {'now': '2026-03-01T09:00:00Z', 'users': [
            {'id': 'u', 'email': 'test@example.com', 'password': 'correct horse', 'display_name': 'Test'}]}
        assert api.post('/_test/reset', json=fixture).status_code == 204
        login = api.post('/auth/login', json={'email': 'test@example.com', 'password': 'correct horse'})
        assert login.status_code == 200
        token = login.json()['token']
        response = api.post('/dossiers', json={'domain': domain},
                            headers={'Authorization': 'Bearer ' + token, 'Idempotency-Key': 'select-probe'})
        assert response.status_code == 202
        dossier = wait_ready(api, token, domain)
        calls = mock.get('/_mock/log').json()['calls']
        return dossier, calls


def test_R2_1_R2_3_stage1_auth_and_idempotency_remain(api, mock, seeded):
    """The upgrade retains auth precedence and exactly-once dossier creation."""
    assert api.post('/dossiers', json={'domain':'halvorsen-robotics.test'}).status_code == 401
    headers = {'Authorization':'Bearer ' + seeded[0], 'Idempotency-Key':'retained-key'}
    first = api.post('/dossiers', headers=headers, json={'domain':'halvorsen-robotics.test'})
    assert first.status_code == 202
    assert wait_ready(api, seeded[0], 'halvorsen-robotics.test')['state'] == 'ready'
    before = mock.get('/_mock/log').json()['calls']
    replay = api.post('/dossiers', headers=headers, json={'domain':'halvorsen-robotics.test'})
    assert replay.status_code == 200 and replay.json() == first.json()
    assert mock.get('/_mock/log').json()['calls'] == before


def test_R2_2_R2_4_R2_31_R2_32_R2_33_R2_35_R2_36_R2_37_R2_38_R2_39_R2_40_R2_41_R2_42_R2_43_R2_44_R2_45_R2_46_R2_47_R2_48_R2_49_R2_50_R2_51_selection_and_evidence(selection_deployment):
    """Candidates preserve every supported page value and select by the Stage 2 rule."""
    dossier, calls = build_controlled(selection_deployment)
    assert dossier['state'] == 'ready'
    assert dossier['spent_units'] == sum(call['cost'] for call in calls)
    assert dossier['spent_units'] <= 80
    assert sum(call['method'] == 'search' and
               call['query'] == 'selection-labs.test' and call['status'] == 200 for call in calls) == 1
    assert any(call['method'] == 'research' and any(p['url'].endswith('/hidden') for p in call['served'])
               for call in calls), 'test requires the unsupported research citation to name the hidden page'
    assert any(call['provider'] == 'nimble' and call['method'] == 'extract' and call['status'] == 200 and
               call['cost'] == 3 * len(call['urls']) and
               any(p['url'].endswith('/about') and 'Dana Ruiz' in p['text'] for p in call['served'])
               for call in calls), 'the visibly different page must be obtained with browser text'
    fields = dossier['fields']
    assert set(fields) == set(FIELDS)
    for name in FIELDS:
        assert_field(fields[name])
        unique = [(candidate['url'], type(candidate['value']),
                   candidate['value'].strip() if isinstance(candidate['value'], str) else candidate['value'])
                  for candidate in fields[name]['candidates']]
        assert len(unique) == len(set(unique)), 'one candidate per page and value'
        for candidate in fields[name]['candidates']:
            assert instant(candidate['retrieved_at']) == instant(dossier['researched_at'])
            assert len(candidate['excerpt']) <= 500
            assert candidate['value'] in supported('selection-labs.test', name, candidate['excerpt'])
            assert any(call['provider'] == candidate['provider'] and call['status'] == 200 and
                       any(page['url'] == candidate['url'] and norm(candidate['excerpt']) in norm(prose(page['text']))
                           for page in call['served']) for call in calls), (name, candidate['url'], candidate['provider'])

    ceo = fields['ceo']
    assert ceo['value'] == 'Mira Stone' and ceo['status'] == 'contested'
    assert [citation['url'] for citation in ceo['citations']] == [
        'https://filings.test/selection-labs', 'https://news.test/selection-labs']
    assert {'Mira Stone', 'Dana Ruiz', 'Sam Ortiz', 'Nora Mills', 'Eva Lane'} <= {
        candidate['value'] for candidate in ceo['candidates']}
    assert not {'Phantom Smith', 'Riley Moore'} & {candidate['value'] for candidate in ceo['candidates']}
    assert fields['founded_year']['value'] == 2014 and fields['founded_year']['status'] == 'contested'
    assert {2014, 2018} <= {candidate['value'] for candidate in fields['founded_year']['candidates']}
    assert fields['headcount_range']['value'] == '51-200'
    assert any(candidate['url'].endswith('/hidden') for candidate in fields['headcount_range']['candidates'])


def test_R2_5_R2_6_R2_7_R2_8_R2_9_R2_31_R2_34_R2_35_rendered_text_and_metadata(selection_deployment):
    """Page metadata and citation text come from what a browser actually sees."""
    dossier, calls = build_controlled(selection_deployment)
    pages = {c['url'] for f in dossier['fields'].values() for c in f['candidates']}
    with httpx.Client(base_url=selection_deployment['mock'], headers=ADMIN, timeout=10, trust_env=False) as mock:
        before = len(mock.get('/_mock/log').json()['calls'])
        for url in pages:
            response = mock.post('/nimble/v2/extract', json={'url': url, 'formats': ['markdown'], 'render': True})
            assert response.status_code == 200
        observed = mock.get('/_mock/log').json()['calls'][before:]
    rendered = {page['url']: page['text'] for call in observed for page in call['served']}
    assert pages <= rendered.keys()
    for name, field in dossier['fields'].items():
        for candidate in field['candidates']:
            text = rendered[candidate['url']]
            assert norm(candidate['excerpt']) in norm(prose(text)), (name, candidate['url'])
            header = text.split('\n\n', 1)[0].splitlines()
            metadata = dict(line.split(': ', 1) for line in header if ': ' in line)
            kind = metadata.get('Kind')
            if kind not in ('own', 'filing', 'news', 'aggregator'):
                kind = 'own' if urlsplit(candidate['url']).hostname == 'selection-labs.test' else 'aggregator'
            assert candidate['kind'] == kind
            published = metadata.get('Published')
            if published is None:
                assert candidate['published_at'] is None
            else:
                try:
                    instant(published)
                except ValueError:
                    assert candidate['published_at'] is None
                else:
                    assert candidate['published_at'] == published


def test_R2_11_R2_12_R2_13_R2_14_R2_15_R2_16_R2_17_R2_18_R2_19_R2_24_R2_25_R2_26_R2_27_optional_browser_vendor_costs(selection_deployment):
    """Optional vendors may be unused; if called, their provider logs define cost."""
    dossier, calls = build_controlled(selection_deployment)
    assert dossier['state'] == 'ready'
    assert dossier['spent_units'] == sum(call['cost'] for call in calls)
    for call in calls:
        if call['provider'] not in ('kernel', 'browserbase'):
            continue
        if call['status'] >= 400:
            assert call['cost'] == 0
        elif call['method'] == 'session':
            assert call['cost'] == (0 if call['provider'] == 'kernel' else 2)
        elif call['method'] == 'load':
            assert call['cost'] == 1
        elif call['method'] == 'browse':
            assert call['provider'] == 'browserbase' and call['cost'] in (0, 4)


def test_R2_6_R2_7_R2_8_R2_41_R2_42_R2_43_RL66_fraction_offset_and_default_kind(metadata_deployment):
    """Fractions compare exactly, equivalent offsets tie by URL, and invalid headers default."""
    domain = 'metadata-labs.test'
    with httpx.Client(base_url=metadata_deployment['app'], timeout=10, trust_env=False) as api, \
         httpx.Client(base_url=metadata_deployment['mock'], headers=ADMIN, timeout=10, trust_env=False) as mock:
        assert mock.post('/_mock/reset', json={'epoch':0}).status_code == 204
        fixture = {'now':'2026-03-01T09:00:00Z', 'users':[
            {'id':'u', 'email':'test@example.com', 'password':'correct horse', 'display_name':'Test'}]}
        assert api.post('/_test/reset', json=fixture).status_code == 204
        login = api.post('/auth/login', json={'email':'test@example.com', 'password':'correct horse'})
        assert login.status_code == 200
        token = login.json()['token']
        assert api.post('/dossiers', json={'domain':domain}, headers={
            'Authorization':'Bearer ' + token, 'Idempotency-Key':'metadata'}).status_code == 202
        dossier = wait_ready(api, token, domain)
        assert dossier['state'] == 'ready'
        field = dossier['fields']['ceo']
        assert_field(field)
        assert field['value'] == 'Bianca Hart' and field['status'] == 'contested'
        by_value = {c['value']:c for c in field['candidates']}
        assert {'Alex Brown', 'Bianca Hart', 'Casey Reed', 'Dina West', 'Elena Stone', 'Frances Green'} <= by_value.keys()
        assert by_value['Bianca Hart']['published_at'] == '2025-01-01T00:00:00.12345678901234567891Z'
        assert by_value['Casey Reed']['published_at'] == '2024-01-01T01:00:00+01:00'
        values = [c['value'] for c in field['candidates']]
        assert values.index('Bianca Hart') < values.index('Alex Brown')
        assert values.index('Casey Reed') < values.index('Dina West')
        assert by_value['Elena Stone']['kind'] == 'own' and by_value['Elena Stone']['published_at'] is None
        assert by_value['Frances Green']['kind'] == 'aggregator' and by_value['Frances Green']['published_at'] is None
