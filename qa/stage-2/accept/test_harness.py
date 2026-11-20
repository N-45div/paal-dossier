"""Validate controlled provider stimuli independently of the service."""
import httpx

from conftest import ADMIN


def test_R2_9_R2_10_R2_23_controlled_provider_serves_distinct_browser_text(selection_deployment):
    """The test corpus really differs before and after browser rendering."""
    url = 'https://selection-labs.test/about'
    with httpx.Client(base_url=selection_deployment['mock'], headers=ADMIN, timeout=10, trust_env=False) as mock:
        assert mock.post('/_mock/reset', json={'epoch':0}).status_code == 204
        for render in (False, True):
            assert mock.post('/nimble/v2/extract', json={
                'url':url, 'formats':['markdown'], 'render':render}).status_code == 200
        calls = mock.get('/_mock/log').json()['calls']
        assert len(calls) == 2
        assert calls[0]['cost'] == 1 and calls[1]['cost'] == 3
        static = next(page['text'] for page in calls[0]['served'] if page['url'] == url)
        browser = next(page['text'] for page in calls[1]['served'] if page['url'] == url)
        assert 'Phantom Smith' in static and 'Dana Ruiz' in browser
        assert 'Phantom Smith' not in browser


def test_R2_5_R2_6_R2_7_R2_8_RL66_controlled_provider_serves_metadata_variants(metadata_deployment):
    """The provider actually emits long fractions and malformed metadata for this corpus."""
    with httpx.Client(base_url=metadata_deployment['mock'], headers=ADMIN, timeout=10, trust_env=False) as mock:
        assert mock.post('/_mock/reset', json={'epoch':0}).status_code == 204
        for path in ('/z', '/invalid'):
            assert mock.post('/nimble/v2/extract', json={'url':'https://metadata-labs.test' + path,
                             'formats':['markdown'], 'render':True}).status_code == 200
        pages = {page['url']:page['text'] for call in mock.get('/_mock/log').json()['calls']
                 for page in call['served']}
        assert 'Published: 2025-01-01T00:00:00.12345678901234567891Z' in pages['https://metadata-labs.test/z']
        assert 'Kind: nonsense' in pages['https://metadata-labs.test/invalid']
        assert 'Published: 2025-02-30T00:00:00Z' in pages['https://metadata-labs.test/invalid']


def test_R2_108_upgrade_bridge_routes_api_before_and_after_switch(frozen_deployment, deployment, upgrade_browser):
    """The test bridge switches API traffic while the browser origin stays unchanged."""
    page, bridge_url = upgrade_browser
    def fixture(email):
        return {'now':'2026-03-01T09:00:00Z', 'users':[
            {'id':'u', 'email':email, 'password':'correct horse', 'display_name':'Test'}]}
    with httpx.Client(base_url=frozen_deployment['app'], timeout=10, trust_env=False) as old, \
         httpx.Client(base_url=deployment['app'], timeout=10, trust_env=False) as new, \
         httpx.Client(base_url=bridge_url, timeout=10, trust_env=False) as bridge:
        assert old.post('/_test/reset', json=fixture('old@example.com')).status_code == 204
        assert new.post('/_test/reset', json=fixture('new@example.com')).status_code == 204
        old_login = {'email':'old@example.com', 'password':'correct horse'}
        new_login = {'email':'new@example.com', 'password':'correct horse'}
        assert bridge.post('/auth/login', json=old_login).status_code == 200
        assert bridge.post('/auth/login', json=new_login).status_code == 401
        assert bridge.post('/_probe/switch').status_code == 204
        assert bridge.post('/auth/login', json=new_login).status_code == 200
        assert bridge.post('/auth/login', json=old_login).status_code == 401
