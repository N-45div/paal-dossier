"""Controlled-corpus checks through the service and provider interfaces."""
import re
import copy

import httpx
import pytest

from conftest import ADMIN
from oracle import candidates, prose
from test_api import auth, create, done
from test_state_faults import fault


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


@pytest.mark.parametrize('domain', ['adjacency-labs.test', 'fraction-ledger.test'])
def test_R1_44_R1_149_R1_157_R1_164_invalid_amount_is_unknown(synthetic, domain):
    """R1.44 R1.149 R1.157 R1.164: adjacent letters and non-whole dollars yield no value."""
    api, mock, token = synthetic
    assert create(api, token, domain, 'invalid-amount').status_code == 202
    dossier = done(api, token, domain)
    assert dossier['state'] == 'ready'
    assert dossier['fields']['funding_total'] == {'value':None, 'status':'unknown', 'citations':[]}


def test_R1_44_R1_155_R1_164_large_amount_exact(synthetic):
    """R1.3 R1.43 R1.44 R1.155 R1.164: whole-dollar amounts and citations are exact."""
    api, mock, token = synthetic
    assert create(api, token, 'exact-ledger.test', 'large-amount').status_code == 202
    dossier = done(api, token, 'exact-ledger.test')
    assert dossier['state'] == 'ready'
    field = dossier['fields']['funding_total']
    assert field['status'] == 'known' and type(field['value']) is int
    assert field['value'] == 987654321098765432109876543210987654321
    assert field['citations']
    calls = mock.get('/_mock/log').json()['calls']
    for citation in field['citations']:
        assert candidates('exact-ledger.test', 'funding_total', citation['excerpt']) == {field['value']}
        excerpt = re.sub(r'\s+', ' ', citation['excerpt']).strip()
        assert any(call['provider'] == citation['provider'] and
                   any(page['url'] == citation['url'] and excerpt in re.sub(r'\s+', ' ', prose(page['text']))
                       for page in call.get('served', [])) for call in calls)


def test_R1_3_R1_43_R1_44_citation_length_limit(synthetic):
    """R1.3 R1.43 R1.44: cited excerpts cannot exceed 500 characters."""
    api, mock, token = synthetic
    assert create(api, token, 'length-probe.test', 'long').status_code == 202
    dossier = done(api, token, 'length-probe.test')
    assert dossier['state'] == 'ready'
    field = dossier['fields']['funding_total']
    assert field['status'] == 'known' and field['value'] == 19000000 and field['citations']
    calls = mock.get('/_mock/log').json()['calls']
    for citation in field['citations']:
        assert 1 <= len(citation['excerpt']) <= 500
        assert candidates('length-probe.test', 'funding_total', citation['excerpt']) == {19000000}
        excerpt = re.sub(r'\s+', ' ', citation['excerpt']).strip()
        assert any(call['provider'] == citation['provider'] and
                   any(page['url'] == citation['url'] and excerpt in re.sub(r'\s+', ' ', prose(page['text']))
                       for page in call.get('served', [])) for call in calls)


def test_R1_42_exact_domain_search_once(synthetic):
    """R1.42: each build has exactly one successful search of the normalized domain."""
    api, mock, token = synthetic
    assert create(api, token, 'scale-probe.test', 'domain').status_code == 202
    assert done(api, token, 'scale-probe.test')['state'] == 'ready'
    calls = mock.get('/_mock/log').json()['calls']
    assert sum(c['method'] == 'search' and c['query'] == 'scale-probe.test' and c['status'] == 200 for c in calls) == 1


def test_R1_42_R1_62_retry_refused_nimble_domain_search(synthetic):
    """R1.42 R1.62: retry an initially refused domain search when fallback fails."""
    api, mock, token = synthetic
    fault(mock, 'nimble', ['search'], 'throttle')
    fault(mock, 'tavily', ['search'], 'error')
    assert create(api, token, 'scale-probe.test', 'retry').status_code == 202
    assert done(api, token, 'scale-probe.test')['state'] == 'ready'
    calls = mock.get('/_mock/log').json()['calls']
    exact = [c for c in calls if c['provider'] == 'nimble' and c['method'] == 'search' and c['query'] == 'scale-probe.test']
    assert any(c['status'] == 429 and c['cost'] == 0 for c in exact)
    assert sum(c['status'] == 200 for c in exact) == 1


def test_R1_99_R1_121_refusals_cost_nothing(synthetic):
    """R1.99 R1.121: refused provider calls cost zero."""
    api, mock, token = synthetic
    fault(mock, 'nimble', ['search', 'extract', 'research'], 'error')
    fault(mock, 'tavily', ['search', 'extract'], 'error')
    assert create(api, token, 'scale-probe.test', 'refused').status_code == 202
    dossier = done(api, token, 'scale-probe.test')
    calls = mock.get('/_mock/log').json()['calls']
    assert calls and all(c['status'] >= 400 and c['cost'] == 0 for c in calls)
    assert dossier['state'] == 'failed' and dossier['spent_units'] == 0


def test_R1_99_R1_117_R1_118_missing_extract_is_charged(synthetic):
    """R1.99 R1.117 R1.118: extracting a missing URL still incurs its per-URL cost."""
    api, mock, token = synthetic
    assert create(api, token, 'extract-probe.test', 'missing').status_code == 202
    dossier = done(api, token, 'extract-probe.test')
    calls = mock.get('/_mock/log').json()['calls']
    extracts = [c for c in calls if c['method'] == 'extract' and 'https://extract-probe.test/missing' in c['urls']]
    assert extracts, 'research citation URL was not extracted'
    for call in extracts:
        assert call['cost'] == len(call['urls']) * {'nimble':1, 'tavily':2}[call['provider']]
        assert not any(p['url'] == 'https://extract-probe.test/missing' for p in call['served'])
    assert dossier['spent_units'] == sum(c['cost'] for c in calls)
    assert dossier['fields']['ceo'] == {'value':None, 'status':'unknown', 'citations':[]}


def test_R1_41_R1_45_R1_86_unsearchable_page_only_claimed_field(synthetic):
    """R1.41 R1.45 R1.86: unsearchable pages contribute only supported research claims."""
    api, mock, token = synthetic
    assert create(api, token, 'hidden-record.test', 'hidden').status_code == 202
    dossier = done(api, token, 'hidden-record.test')
    assert dossier['state'] == 'ready'
    year = dossier['fields']['founded_year']
    assert year['status'] == 'known' and year['value'] == 2008 and year['citations']
    assert dossier['fields']['headcount_range'] == {'value':None, 'status':'unknown', 'citations':[]}
    calls = mock.get('/_mock/log').json()['calls']
    assert not any(page['url'] == 'https://hidden-record.test/about'
                   for call in calls if call['method'] == 'search' for page in call.get('served', []))
    assert any(call['method'] == 'research' and call['status'] == 200 for call in calls)
    for citation in year['citations']:
        assert candidates('hidden-record.test', 'founded_year', citation['excerpt']) == {2008}
        excerpt = re.sub(r'\s+', ' ', citation['excerpt']).strip()
        assert any(call['method'] == 'extract' and call['provider'] == citation['provider'] and
                   any(page['url'] == citation['url'] and excerpt in re.sub(r'\s+', ' ', prose(page['text']))
                       for page in call.get('served', [])) for call in calls)


def test_R1_3_R1_43_R1_86_long_sentence_supporting_prefix(synthetic):
    """R1.3 R1.43 R1.86: a supporting prefix may cite an overlong sentence."""
    api, mock, token = synthetic
    assert create(api, token, 'long-witness.test', 'long-witness').status_code == 202
    dossier = done(api, token, 'long-witness.test')
    assert dossier['state'] == 'ready'
    field = dossier['fields']['founded_year']
    assert field['status'] == 'known' and field['value'] == 2012 and field['citations']
    calls = mock.get('/_mock/log').json()['calls']
    for citation in field['citations']:
        assert 1 <= len(citation['excerpt']) <= 500
        assert candidates('long-witness.test', 'founded_year', citation['excerpt']) == {2012}
        excerpt = re.sub(r'\s+', ' ', citation['excerpt']).strip()
        assert excerpt == 'Long Witness was incorporated in 2012'
        assert any(call['provider'] == citation['provider'] and
                   any(page['url'] == citation['url'] and excerpt in re.sub(r'\s+', ' ', prose(page['text']))
                       for page in call.get('served', [])) for call in calls)


@pytest.mark.parametrize('domain', ['late-negation.test', 'late-conflict.test'])
def test_R1_43_R1_44_R1_86_long_sentence_full_context(synthetic, domain):
    """R1.43 R1.44 R1.86: late negation or conflicting values defeat a short prefix."""
    api, mock, token = synthetic
    assert create(api, token, domain, 'long-context').status_code == 202
    dossier = done(api, token, domain)
    assert dossier['state'] == 'ready'
    assert dossier['fields']['funding_total'] == {'value':None, 'status':'unknown', 'citations':[]}


@pytest.mark.parametrize('corruption', ['missing_field', 'known_without_citations', 'unknown_with_citations', 'wrong_value_type', 'empty_excerpt'])
def test_R1_40_R1_126_R1_127_invalid_dossier_snapshot_is_atomic(synthetic, corruption):
    """R1.40 R1.126 R1.127: reject incomplete or inconsistent dossier fields atomically."""
    api, mock, token = synthetic
    domain = 'scale-probe.test'
    assert create(api, token, domain, 'snapshot-dossier').status_code == 202
    original = done(api, token, domain)
    assert original['state'] == 'ready' and original['fields']['funding_total']['value'] == 23000000
    snapshot = api.get('/_test/export', timeout=10).json()
    dossiers = snapshot['state']['dossiers']
    assert isinstance(dossiers, list) and len(dossiers) == 1
    fields = dossiers[0]['fields']
    if corruption == 'missing_field':
        del fields['legal_name']
    elif corruption == 'known_without_citations':
        fields['funding_total']['citations'] = []
    elif corruption == 'unknown_with_citations':
        citation = copy.deepcopy(fields['funding_total']['citations'][0])
        assert fields['legal_name']['value'] is None
        fields['legal_name']['citations'] = [citation]
    elif corruption == 'wrong_value_type':
        fields['funding_total']['value'] = 'not-an-integer'
    else:
        fields['funding_total']['citations'][0]['excerpt'] = ''
    from test_api import error
    error(api.post('/_test/import', json=snapshot, timeout=10), 422, 'validation_failed')
    response = api.get('/dossiers/' + domain, headers=auth(token))
    assert response.status_code == 200 and response.json() == original


@pytest.mark.parametrize('field,bad_value', [
    ('founded_year', True), ('founded_year', 1799), ('founded_year', 2100),
    ('funding_total', True), ('funding_total', 0), ('funding_total', -1), ('funding_total', 1.5),
    ('headcount_range', '10-50'),
    ('legal_name', ''), ('legal_name', ' Shape Probe Inc.'),
    ('hq_city', ''), ('hq_city', 'Lisbon '),
    ('ceo', ''), ('ceo', ' Mira Santos'),
])
def test_R1_38_R1_40_R1_126_invalid_import_field_values(synthetic, field, bad_value):
    """R1.38 R1.40 R1.126: reject invalid field types, ranges and whitespace atomically."""
    from test_api import error
    api, mock, token = synthetic
    domain = 'shape-probe.test'
    assert create(api, token, domain, 'invalid-field').status_code == 202
    original = done(api, token, domain)
    assert original['state'] == 'ready' and original['fields'][field]['status'] == 'known'
    snapshot = api.get('/_test/export', timeout=10).json()
    snapshot['state']['dossiers'][0]['fields'][field]['value'] = bad_value
    error(api.post('/_test/import', json=snapshot, timeout=10), 422, 'validation_failed')
    response = api.get('/dossiers/' + domain, headers=auth(token))
    assert response.status_code == 200 and response.json() == original


@pytest.mark.parametrize('key,bad_value', [
    ('url', ''), ('url', None), ('excerpt', ''), ('excerpt', 'x'*501),
    ('excerpt', None), ('provider', 'other'), ('provider', None),
])
def test_R1_40_R1_43_R1_126_invalid_import_citation(synthetic, key, bad_value):
    """R1.40 R1.43 R1.126: reject invalid citation shape and bounds atomically."""
    from test_api import error
    api, mock, token = synthetic
    domain = 'shape-probe.test'
    assert create(api, token, domain, 'invalid-citation').status_code == 202
    original = done(api, token, domain)
    assert original['state'] == 'ready' and original['fields']['funding_total']['citations']
    snapshot = api.get('/_test/export', timeout=10).json()
    snapshot['state']['dossiers'][0]['fields']['funding_total']['citations'][0][key] = bad_value
    error(api.post('/_test/import', json=snapshot, timeout=10), 422, 'validation_failed')
    response = api.get('/dossiers/' + domain, headers=auth(token))
    assert response.status_code == 200 and response.json() == original
