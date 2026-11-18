import json
import os
import time
from pathlib import Path
from common import Acceptance, FIELDS
from edge_corpus import CASES


def collapse(text):
    return ' '.join(text.split())


class Research(Acceptance):
    def test_R1_43_R1_46_R1_49_R1_50_R1_121_R1_122_R1_123_R1_124_R1_125_R1_126_R1_127_R1_128_R1_129_R1_130_R1_131_R1_132_R1_133_R1_134_R1_135_R1_136_R1_137_R1_138_R1_139_R1_140_support_boundaries(self):
        for suffix, field, prose, expected in CASES:
            domain = 'trial' + suffix + '.test'
            with self.subTest(domain=domain, field=field):
                self.assertEqual(self.mock('POST', '/_mock/reset', {'epoch': 0})[0], 204)
                self.assertEqual(self.create(domain, 'edge-' + domain)[0], 202)
                dossier = self.ready(domain)
                self.assertEqual(dossier['state'], 'ready')
                actual = dossier['fields'][field]
                self.assertEqual(actual['value'], expected, (prose, actual))
                if expected is not None:
                    self.assertTrue(actual['citations'])
                    self.assertTrue(all(c['excerpt'] == prose for c in actual['citations']), actual)
                else:
                    self.assertEqual(actual, {'value': None, 'status': 'unknown', 'citations': []})

    def test_R1_01a_R1_02_R1_06_R1_38_R1_39_R1_42_R1_44_R1_45_R1_47_R1_48_R1_82_R1_94_R1_141_R1_148_R1_149_sample_corpus(self):
        directory = os.environ.get('CORPUS_DIR')
        self.assertTrue(directory, 'Set CORPUS_DIR to the mock sample corpus')
        key = json.loads((Path(directory) / 'key.json').read_text())
        for domain, company in sorted(key.items()):
            with self.subTest(domain=domain):
                self.assertEqual(self.mock('POST', '/_mock/reset', {'epoch': 0})[0], 204)
                self.assertEqual(self.create(domain, 'sample-' + domain)[0], 202)
                dossier = self.ready(domain)
                self.assertEqual(dossier['state'], 'ready')
                log = self.log()
                cost = sum(c['cost'] for c in log)
                self.assertLessEqual(cost, 80, log)
                self.assertEqual(dossier['spent_units'], cost)
                searches = [c for c in log if c['method'] == 'search' and c['status'] < 400]
                self.assertEqual(sum(c['query'] == domain for c in searches), 1, log)
                research = [c for c in log if c['provider'] == 'nimble' and c['method'] == 'research' and c['status'] < 400]
                self.assertTrue(research, log)
                self.assertTrue(any(domain in c['query'] and set(c['fields'] or []) == FIELDS for c in research), log)
                expected = company['expected']['1']['0']
                labels = company.get('supports', [])
                fixture = json.loads((Path(directory) / (domain + '.json')).read_text())
                claims = fixture.get('research', {}).get('nimble', {}).get('0', [])
                for field in FIELDS:
                    value = dossier['fields'][field]['value']
                    allowed = expected[field] if isinstance(expected[field], list) else [expected[field]]
                    self.assertIn(value, allowed, (domain, field, dossier['fields'][field]))
                    for cite in dossier['fields'][field]['citations']:
                        self.assertIn(cite['provider'], ('nimble', 'tavily'))
                        self.assertTrue(1 <= len(cite['excerpt']) <= 500)
                        served = [s['text'] for c in log if c['provider'] == cite['provider'] for s in c.get('served', []) if s['url'] == cite['url']]
                        self.assertTrue(any(collapse(cite['excerpt']) in collapse(text) for text in served), (domain, field, cite))
                        # The sample labels are not exhaustive: research can cite a
                        # different valid excerpt absent from the labels. Require a
                        # labelled excerpt or a matching research claim and check
                        # values independently against the corpus key above.
                        self.assertTrue(any(x['field'] == field and x['value'] == value and x['url'] == cite['url'] and collapse(x['excerpt']) == collapse(cite['excerpt']) for x in labels + claims), (domain, field, cite))

    def test_R1_83_delay_bound(self):
        for provider in ('nimble', 'tavily'):
            self.assertEqual(self.mock('POST', '/_mock/faults', {'provider': provider, 'methods': ['search', 'extract', 'research'], 'mode': 'delay', 'seconds': 1})[0], 204)
        start = time.monotonic()
        self.assertEqual(self.create('halvorsen-robotics.test')[0], 202)
        self.ready('halvorsen-robotics.test', timeout=10)
        self.assertLess(time.monotonic() - start, 10)

    def test_R1_58_R1_81_R1_143_provider_errors(self):
        for provider in ('nimble', 'tavily'):
            self.assertEqual(self.mock('POST', '/_mock/faults', {'provider': provider, 'methods': ['search', 'extract', 'research'], 'mode': 'error'})[0], 204)
        self.assertEqual(self.create('halvorsen-robotics.test')[0], 202)
        item = self.ready('halvorsen-robotics.test')
        self.assertEqual(item['state'], 'failed')
        self.assertIsNone(item['researched_at'])
        self.assertTrue(all(f == {'value': None, 'status': 'unknown', 'citations': []} for f in item['fields'].values()))
        self.assertTrue(self.log())
        self.assertEqual(sum(c['cost'] for c in self.log()), 0)
        self.assertEqual(item['spent_units'], 0)

    def test_R1_23_R1_79_R1_80_R1_92_R1_106_R1_120_reset_cancels_inflight(self):
        self.assertEqual(self.mock('POST', '/_mock/faults', {'provider': 'nimble', 'methods': ['search', 'extract', 'research'], 'mode': 'delay', 'seconds': 1})[0], 204)
        self.assertEqual(self.create('halvorsen-robotics.test')[0], 202)
        item = self.get('halvorsen-robotics.test')[1]
        self.assertEqual(item['state'], 'building')
        self.assertTrue(all(f['status'] == 'unknown' for f in item['fields'].values()))
        snapshot = self.api('GET', '/_test/export')[1]
        self.assertEqual(self.api('POST', '/_test/import', snapshot, timeout=10)[0], 204)
        restored = self.get('halvorsen-robotics.test')[1]
        self.assertEqual(restored['state'], 'failed')
        self.assertEqual(restored['spent_units'], 0)
        self.assertIsNone(restored['researched_at'])
        time.sleep(2.5)
        self.assertEqual(self.get('halvorsen-robotics.test')[1], restored)
