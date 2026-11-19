import json
import re
import time

import pytest

from conftest import CORPUS
from oracle import FIELDS, candidates, corpus_candidates, prose, sentences
from test_api import auth, create, done


def normalized(text):
    return re.sub(r'\s+', ' ', text).strip()


@pytest.mark.parametrize('field,text,expected', [
    ('ceo', 'Dana Ruiz has led Acme Robotics as chief executive since 2021.', {'Dana Ruiz'}),
    ('ceo', 'Acme Robotics CEO: Sam Ortiz.', {'Sam Ortiz'}),
    ('founded_year', 'Acme Robotics was founded in 2014.', {2014}),
    ('headcount_range', 'Acme Robotics employs about 120 people.', {'51-200'}),
    ('funding_total', 'Acme Robotics is reportedly in talks to raise $40M.', set()),
    ('hq_city', 'Acme Robotics opened a sales office in Porto.', set()),
    ('funding_total', 'Acme Robotics has raised $12M.', {12000000}),
    ('funding_total', 'Acme Robotics has raised 12 million dollars.', {12000000}),
    ('funding_total', 'Acme Robotics raised $1.2.3 million.', set()),
    ('funding_total', 'Acme Robotics raised $0.001.', set()),
    ('funding_total', 'Acme Robotics raised US$12.5 million.', {12500000}),
    ('funding_total', 'Acme Robotics raised 1,200 US dollars.', {1200}),
    ('funding_total', 'Acme Robotics raised €1200.', set()),
    ('headcount_range', 'Acme Robotics has 51-200 employees.', {'51-200'}),
    ('headcount_range', 'Acme Robotics has 50-51 employees.', set()),
    ('legal_name', 'The registered name is Acme Robotics, Inc.', {'Acme Robotics, Inc.'}),
    ('legal_name', 'The registered name is Acme Robotics AB GmbH.', {'Acme Robotics AB'}),
    ('hq_city', 'Acme Robotics is headquartered in Zürich.', {'Zürich'}),
    ('hq_city', 'Acme Robotics is headquartered in New York.', {'New York'}),
    ('founded_year', 'Acme Robotics was founded in 1799.', set()),
    ('founded_year', 'Acme Robotics was founded in 2099.', {2099}),
    ('founded_year', 'Acme Robotics was founded in 2100.', set()),
    ('founded_year', 'Acme Robotics was founded in 2014 or 2015.', set()),
    ('ceo', 'Acme Robotics CEO Sam Ortiz and Dana Ruiz.', set()),
    ('ceo', 'Acme Robotics former CEO Sam Ortiz.', set()),
    ('ceo', 'Acme Robotics CEO María Müller.', {'María Müller'}),
    ('ceo', 'Acme Robotics CEO Ana María Laura Müller.', set()),
])
def test_R1_130_R1_132_R1_133_R1_134_R1_135_R1_136_R1_137_R1_138_R1_139_R1_140_R1_141_R1_142_R1_143_R1_144_R1_145_R1_146_R1_147_R1_148_R1_149_R1_150_R1_151_R1_152_R1_153_R1_154_R1_155_R1_156_R1_157_R1_158_R1_159_R1_160_R1_161_R1_162_R1_163_R1_164_oracle_examples(field, text, expected):
    assert candidates('acme-robotics.test', field, text) == expected


def test_R1_47_R1_131_sentence_boundaries_and_header():
    text = 'Kind: news\nFacts: {"ceo":"invented"}\n\nAcme Robotics, Inc. employs 10 people. Another line!\nAcme Robotics CEO: Sam Ortiz.'
    assert sentences(prose(text)) == [
        'Acme Robotics, Inc. employs 10 people.', 'Another line!', 'Acme Robotics CEO: Sam Ortiz.']
    assert prose('No header here.\nSecond line.') == 'No header here.\nSecond line.'


COMPANIES = sorted(p for p in CORPUS.glob('*.test.json'))


@pytest.mark.parametrize('path', COMPANIES, ids=lambda p: p.stem)
def test_R1_3_R1_4_R1_5_R1_37_R1_38_R1_39_R1_40_R1_41_R1_42_R1_43_R1_44_R1_45_R1_46_R1_47_R1_83_R1_85_R1_86_R1_87_R1_89_R1_95_R1_96_R1_97_R1_98_R1_99_R1_110_R1_121_R1_122_R1_123_evidence_and_cost(api, mock, seeded, path):
    company = json.loads(path.read_text())
    domain = company['domain']
    token = seeded[0]
    started = time.monotonic()
    response = create(api, token, domain, 'build-' + domain)
    assert response.status_code == 202
    assert response.json()['domain'] == domain and response.json()['state'] == 'building'
    dossier = done(api, token, domain)
    assert time.monotonic() - started <= 10
    assert dossier['state'] == 'ready'
    calls = mock.get('/_mock/log').json()['calls']
    assert sum(call['cost'] for call in calls) <= 80
    assert dossier['spent_units'] == sum(call['cost'] for call in calls)
    assert sum(call['method'] == 'search' and call['query'] == domain and call['status'] == 200 for call in calls) == 1
    price = {('nimble', 'lite'): 1, ('nimble', 'fast'): 5, ('nimble', 'deep'): 15,
             ('tavily', 'lite'): 8, ('tavily', 'fast'): 16, ('tavily', 'deep'): 16}
    for call in calls:
        if call['status'] >= 400 and call['method'] != 'extract':
            assert call['cost'] == 0
        elif call['method'] == 'search':
            assert call['cost'] == price[call['provider'], call['depth']]
        elif call['method'] == 'extract' and call['status'] < 400:
            assert call['cost'] == len(call['urls']) * {'nimble': 1, 'tavily': 2}[call['provider']]
        elif call['method'] == 'research':
            assert call['cost'] == 25
            assert domain in call['query']
            assert set(call['fields']) == set(FIELDS)
    assert set(dossier['fields']) == set(FIELDS)
    all_pages = [page for file in COMPANIES for page in json.loads(file.read_text())['pages']
                 if 0 in page['epochs']]
    supported = corpus_candidates(domain, [page for page in all_pages if page.get('searchable', True)])
    for claim in company.get('research', {}).get('nimble', {}).get('0', []):
        field, value, excerpt = claim['field'], claim['value'], claim['excerpt']
        if field in FIELDS and value in candidates(domain, field, excerpt) and any(
            page['url'] == claim['url'] and normalized(excerpt) in normalized(page['text'])
            for page in all_pages
        ):
            supported[field].add(value)
    for field, result in dossier['fields'].items():
        value = result['value']
        if supported[field]:
            assert result['status'] == 'known' and value in supported[field], (domain, field, value, supported[field])
            assert result['citations']
        else:
            assert result['status'] == 'unknown' and value is None and result['citations'] == [], (domain, field, value)
        for citation in result['citations']:
            excerpt = citation['excerpt']
            assert 1 <= len(excerpt) <= 500
            assert len(sentences(normalized(excerpt))) == 1
            assert value in candidates(domain, field, excerpt), (domain, field, value, excerpt)
            assert citation['provider'] in ('nimble', 'tavily')
            assert any(normalized(excerpt) in normalized(prose(served['text']))
                       for call in calls if call['provider'] == citation['provider']
                       for served in call.get('served', []) if served['url'] == citation['url']), citation
    before = mock.get('/_mock/log').json()['calls']
    assert api.get('/dossiers', headers=auth(token)).status_code == 200
    assert api.get('/dossiers/' + domain, headers=auth(token)).status_code == 200
    assert mock.get('/_mock/log').json()['calls'] == before
