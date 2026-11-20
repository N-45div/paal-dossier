"""Sample-corpus evidence and cost are measured from the provider's records."""
import json
import re
import time

from oracle import FIELDS, contains, corpus_candidates, candidates as supported, prose
from selection_oracle import assert_field, instant
from test_candidates import wait_ready


def normalized(text):
    return re.sub(r'\s+', ' ', text).strip()


def test_R2_2_R2_4_R2_9_R2_22_R2_23_R2_31_R2_34_R2_35_R2_36_R2_37_R2_38_R2_40_R2_45_R2_47_sample_evidence_and_cost(company_path, direct_api, mock, seeded):
    """Every value on the pages providers actually served becomes a ranked candidate."""
    domain = json.loads(company_path.read_text())['domain']
    headers = {'Authorization':'Bearer ' + seeded[0], 'Idempotency-Key':'sample-' + domain}
    started = time.monotonic()
    assert direct_api.post('/dossiers', headers=headers, json={'domain':domain}).status_code == 202
    dossier = wait_ready(direct_api, seeded[0], domain)
    elapsed = time.monotonic() - started
    assert dossier['state'] == 'ready'
    calls = mock.get('/_mock/log').json()['calls']
    assert dossier['spent_units'] == sum(call['cost'] for call in calls) <= 80
    assert sum(call['method'] == 'search' and call['query'] == domain and call['status'] == 200
               for call in calls) == 1
    company = domain.split('.')[0].replace('-', ' ')
    assert all(contains(call['query'], (domain, company)) for call in calls
               if call['method'] == 'search' and call['status'] == 200)
    if not any(call['status'] == 429 for call in calls):
        assert elapsed <= 10.5, ('direct HTTP elapsed seconds', elapsed)

    evidence_urls = {page['url'] for call in calls if call['status'] == 200 and
                     call['method'] in ('search', 'research')
                     for page in call.get('served', []) if page.get('url')}
    for url in sorted(evidence_urls):
        result = mock.post('/nimble/v2/extract', json={'url':url, 'formats':['markdown'], 'render':True})
        assert result.status_code == 200
    observed = mock.get('/_mock/log').json()['calls'][len(calls):]
    pages = {page['url']:page['text'] for call in observed for page in call['served']}
    expected = set()
    for url, rendered in pages.items():
        for field, values in corpus_candidates(domain, [{'text':prose(rendered)}]).items():
            expected.update((field, url, value) for value in values)

    actual = set()
    for field in FIELDS:
        result = dossier['fields'][field]
        assert_field(result)
        for candidate in result['candidates']:
            actual.add((field, candidate['url'], candidate['value']))
            excerpt, url, provider = candidate['excerpt'], candidate['url'], candidate['provider']
            assert candidate['kind'] in ('own','filing','news','aggregator')
            assert instant(candidate['retrieved_at']) == instant(dossier['researched_at'])
            assert 1 <= len(excerpt) <= 500
            assert candidate['value'] in supported(domain, field, excerpt)
            assert url in pages and normalized(excerpt) in normalized(prose(pages[url]))
            assert any(call['provider'] == provider and call['status'] == 200 and
                       any(p['url'] == url and normalized(excerpt) in normalized(prose(p['text']))
                           for p in call['served']) for call in calls)
    assert len(actual) == sum(len(dossier['fields'][field]['candidates']) for field in FIELDS)
    assert actual == expected, ('missing', sorted(expected - actual, key=str),
                                'unexpected', sorted(actual - expected, key=str))
