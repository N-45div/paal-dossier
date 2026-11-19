"""Controlled-corpus checks through the service and provider interfaces."""
import re

import httpx
import pytest

from conftest import ADMIN
from test_api import auth, create, done


@pytest.fixture
def synthetic(adversarial_deployment):
    with httpx.Client(base_url=adversarial_deployment['app'], timeout=5, trust_env=False) as api, \
         httpx.Client(base_url=adversarial_deployment['mock'], headers=ADMIN, timeout=10, trust_env=False) as mock:
        assert mock.post('/_mock/reset', json={'epoch':0}).status_code == 204
        fixture = {'now':'2026-03-01T09:00:00+00:00', 'users':[
            {'id':'test-user', 'email':'test@example.com', 'password':'correct horse', 'display_name':'Test'}]}
        assert api.post('/_test/reset', json=fixture, timeout=10).status_code == 204
        login = api.post('/auth/login', json={'email':'test@example.com','password':'correct horse'})
        assert login.status_code == 200
        yield api, mock, login.json()['token']


def test_R1_44_R1_133_R1_147_rumoured_funding_is_unknown(synthetic):
    """R1.44 R1.133 R1.147: rumoured is a negating phrase."""
    api, mock, token = synthetic
    assert create(api, token, 'rumor-press.test', 'rumor').status_code == 202
    dossier = done(api, token, 'rumor-press.test')
    assert dossier['state'] == 'ready'
    assert dossier['fields']['funding_total'] == {'value':None, 'status':'unknown', 'citations':[]}
    log = mock.get('/_mock/log').json()['calls']
    assert any(c['method'] == 'search' and c['status'] == 200 and c['query'] == 'rumor-press.test' for c in log)


def test_R1_44_R1_155_R1_158_R1_164_mn_is_one_million(synthetic):
    """R1.44 R1.155 R1.158 R1.164: mn scales by one million."""
    api, mock, token = synthetic
    assert create(api, token, 'scale-probe.test', 'scale').status_code == 202
    dossier = done(api, token, 'scale-probe.test')
    assert dossier['state'] == 'ready'
    field = dossier['fields']['funding_total']
    assert field['status'] == 'known' and type(field['value']) is int and field['value'] == 23000000
    assert field['citations']
    log = mock.get('/_mock/log').json()['calls']
    for citation in field['citations']:
        excerpt = re.sub(r'\s+', ' ', citation['excerpt']).strip()
        assert excerpt in 'Scale Probe has raised $23mn.'
        assert any(call['provider'] == citation['provider'] and
                   any(page['url'] == citation['url'] and excerpt in re.sub(r'\s+', ' ', page['text'])
                       for page in call.get('served', [])) for call in log)
