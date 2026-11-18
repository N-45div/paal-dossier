"""Create isolated, specification-derived evidence cases for the mock web."""
import json
import shutil
import sys
from pathlib import Path

# Each case has exactly one relevant page. The Facts header intentionally claims
# a value even where the page prose provides no support.
CASES = [
    ('yearlow', 'founded_year', 'Trialyearlow was founded in 1800.', 1800),
    ('yearhigh', 'founded_year', 'Trialyearhigh was founded in 2099.', 2099),
    ('yearbelow', 'founded_year', 'Trialyearbelow was founded in 1799.', None),
    ('yearabove', 'founded_year', 'Trialyearabove was founded in 2100.', None),
    ('yearconflict', 'founded_year', 'Trialyearconflict was founded in 2014 and incorporated in 2015.', None),
    ('staffsame', 'headcount_range', 'Trialstaffsame employs 51-200 people.', '51-200'),
    ('staffcross', 'headcount_range', 'Trialstaffcross employs 50-51 people.', None),
    ('staffzero', 'headcount_range', 'Trialstaffzero employs 0 people.', None),
    ('money', 'funding_total', 'Trialmoney raised US$12.5 million.', 12500000),
    ('fraction', 'funding_total', 'Trialfraction raised $0.1.', None),
    ('currency', 'funding_total', 'Trialcurrency raised €12 million.', None),
    ('negated', 'funding_total', 'Trialnegated reportedly raised $12M.', None),
    ('wrongphrase', 'hq_city', 'Trialwrongphrase opened a sales office in Porto.', None),
    ('city', 'hq_city', 'Trialcity is headquartered in Zürich.', 'Zürich'),
    ('person', 'ceo', 'Trialperson CEO: Anne Müller.', 'Anne Müller'),
    ('personfour', 'ceo', 'Trialpersonfour CEO: Anne Maria Clara Müller.', None),
    ('legal', 'legal_name', 'Triallegal has registered name Triallegal, Inc. in the register.', 'Triallegal, Inc.'),
    ('boundary', 'founded_year', 'XTrialboundary was founded in 2014.', None),
    ('headeronly', 'founded_year', 'Trialheaderonly sells products.', None),
    ('sameyear', 'founded_year', 'Trialsameyear was founded in 2014 and incorporated in 2014.', 2014),
]


def make_corpus(source, destination):
    shutil.copytree(source, destination)
    for suffix, field, prose, expected in CASES:
        domain = 'trial' + suffix + '.test'
        company = {'domain': domain, 'names': ['Trial' + suffix], 'pages': [{
            'url': 'https://' + domain + '/about', 'kind': 'own', 'epochs': [0, 1],
            'searchable': True, 'published_at': None, 'true_from': None,
            'title': domain, 'text': prose, 'facts': {field: expected if expected is not None else '2014'},
            'lineage': {'canonical': None, 'first_published_by': None, 'registrant': domain},
        }], 'research': {'nimble': {'0': [], '1': []}}}
        (destination / (domain + '.json')).write_text(json.dumps(company, ensure_ascii=False))


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('usage: python3 edge_corpus.py SAMPLE_CORPUS NEW_DESTINATION')
    make_corpus(Path(sys.argv[1]), Path(sys.argv[2]))
