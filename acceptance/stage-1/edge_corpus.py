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
    ('nodomain', 'founded_year', 'Another company was founded in 2014.', None),
    ('casefold', 'founded_year', 'TRIALCASEFOLD was FOUNDED in 2014.', 2014),
    ('negformer', 'ceo', 'Trialnegformer former CEO: Anne Müller.', None),
    ('negnot', 'founded_year', 'Trialnegnot was not founded in 2014.', None),
    ('negplans', 'funding_total', 'Trialnegplans plans to expand after it raised $12M.', None),
    ('ceothree', 'ceo', 'Trialceothree chief executive officer: Anna Maria Müller.', 'Anna Maria Müller'),
    ('ceomultiple', 'ceo', 'Trialceomultiple CEO: Anna Müller and Clara Novak.', None),
    ('hyphencity', 'hq_city', 'Trialhyphencity is based in New-York.', 'New-York'),
    ('cityrun', 'hq_city', 'Trialcityrun has headquarters in New York.', 'New York'),
    ('staffone', 'headcount_range', 'Trialstaffone employs 1 person.', '1-10'),
    ('stafften', 'headcount_range', 'Trialstafften has 10 employees.', '1-10'),
    ('staffeleven', 'headcount_range', 'Trialstaffeleven has 11 employees.', '11-50'),
    ('staffmany', 'headcount_range', 'Trialstaffmany has 10,001 employees.', '10001+'),
    ('staffdecimal', 'headcount_range', 'Trialstaffdecimal has 12.5 employees.', None),
    ('staffamount', 'headcount_range', 'Trialstaffamount has funding of $120 and employs people.', None),
    ('moneywords', 'funding_total', 'Trialmoneywords raised 12 million dollars.', 12000000),
    ('moneyus', 'funding_total', 'Trialmoneyus raised 12,000,000 US dollars.', 12000000),
    ('moneybn', 'funding_total', 'Trialmoneybn raised USD 1.5 billion.', 1500000000),
    ('moneyconflict', 'funding_total', 'Trialmoneyconflict raised $12M and $13M.', None),
    ('yearamount', 'founded_year', 'Trialyearamount was founded with $2014 of funding.', None),
    ('badnumber', 'founded_year', 'Trialbadnumber was founded in 20,14.', None),
    ('legalcorp', 'legal_name', 'Triallegalcorp has legal name Triallegalcorp Corp. on file.', 'Triallegalcorp Corp.'),
    ('legalunicode', 'legal_name', 'Triallegalunicode has registered name Triallegalunicode Müller GmbH.', 'Triallegalunicode Müller GmbH'),
    ('suffixsentence', 'legal_name', 'Trialsuffixsentence has legal name Trialsuffixsentence Inc. in the register. More text follows.', 'Trialsuffixsentence Inc.'),
    ('twosentences', 'founded_year', 'Trialtwosentences sells products. Trialtwosentences was founded in 2014!', 2014),
]

EXCERPTS = {
    'suffixsentence': 'Trialsuffixsentence has legal name Trialsuffixsentence Inc. in the register.',
    'twosentences': 'Trialtwosentences was founded in 2014!',
}

NEGATIONS = ['in talks to', 'plans to', 'planning to', 'wants to', 'expects to',
             'hopes to', 'aims to', 'seeking', 'could', 'would', 'might',
             'reportedly', 'rumoured', 'former', 'formerly', 'will become', 'not']
STATEMENTS = {
    'legal_name': ['legal name', 'registered name', 'registered as', 'registered company', 'legal entity', 'name of record'],
    'hq_city': ['headquartered in', 'headquarters in', 'head office in', 'based in', 'registered office in', 'registered seat in'],
    'ceo': ['chief executive officer', 'chief executive', 'CEO'],
    'founded_year': ['founded', 'founding', 'established', 'incorporated'],
    'headcount_range': ['employs', 'employees', 'staff', 'people', 'headcount', 'workforce'],
    'funding_total': ['raised', 'funding', 'invested', 'investment'],
}
SUFFIXES = ['Inc.', 'Corp.', 'LLC', 'LLP', 'L.P.', 'Ltd', 'Limited', 'Pty Ltd', 'plc', 'PLC',
            'GmbH', 'AG', 'KG', 'SE', 'AS', 'A/S', 'ASA', 'AB', 'Oy', 'Oyj', 'B.V.', 'N.V.',
            'S.A.', 'S.A.S.', 'S.L.', 'S.r.l.', 'S.p.A.', 's.r.o.', 'a.s.', 'K.K.']


def code(i):
    return chr(ord('a') + i // 26) + chr(ord('a') + i % 26)


def table_cases():
    negations, statements, suffixes = [], [], []
    for i, phrase in enumerate(NEGATIONS):
        suffix = 'negation' + code(i)
        name = 'Trial' + suffix
        negations.append((suffix, 'founded_year', f'{name} {phrase} founded in 2014.', None, phrase))
    i = 0
    for field, phrases in STATEMENTS.items():
        for phrase in phrases:
            suffix = 'statement' + code(i)
            name = 'Trial' + suffix
            if field == 'legal_name':
                prose, value = f'{name} has {phrase} {name}, Inc.', f'{name}, Inc.'
            elif field == 'hq_city':
                prose, value = f'{name} is {phrase} Zürich.', 'Zürich'
            elif field == 'ceo':
                prose, value = f'{name} {phrase}: Anna Müller.', 'Anna Müller'
            elif field == 'founded_year':
                prose, value = f'{name} {phrase} in 2014.', 2014
            elif field == 'headcount_range':
                prose, value = f'{name} {phrase}: 120.', '51-200'
            else:
                prose, value = f'{name} {phrase}: $12M.', 12000000
            statements.append((suffix, field, prose, value, phrase))
            i += 1
    for i, form in enumerate(SUFFIXES):
        suffix = 'form' + code(i)
        name = 'Trial' + suffix
        suffixes.append((suffix, 'legal_name', f'{name} has legal name {name}, {form} in the register.', f'{name}, {form}', form))
    return negations, statements, suffixes


def make_corpus(destination):
    destination.mkdir(parents=True, exist_ok=True)
    table = [case[:4] for group in table_cases() for case in group]
    for suffix, field, prose, expected in CASES + table:
        domain = 'trial' + suffix + '.test'
        company = {'domain': domain, 'names': ['Trial' + suffix], 'pages': [{
            'url': 'https://' + domain + '/about', 'kind': 'own', 'epochs': [0, 1],
            'searchable': True, 'published_at': None, 'true_from': None,
            'title': domain, 'text': prose, 'facts': {field: expected if expected is not None else '2014'},
            'lineage': {'canonical': None, 'first_published_by': None, 'registrant': domain},
        }], 'research': {'nimble': {'0': [], '1': []}}}
        (destination / (domain + '.json')).write_text(json.dumps(company, ensure_ascii=False))

    # The domain search is crowded out by decoys matching the domain. A search
    # for the company's name finds the only page with a headquarters statement.
    domain = 'trialnamequery.test'
    def page(url, title, text):
        return {'url': url, 'kind': 'own', 'epochs': [0, 1], 'searchable': True,
                'published_at': None, 'true_from': None, 'title': title, 'text': text,
                'facts': {}, 'lineage': {'canonical': None, 'first_published_by': None, 'registrant': domain}}
    pages = [page('https://' + domain + '/decoy%02d' % i,
                  (domain + ' ') * 12, (domain + ' sells products. ') * 12) for i in range(12)]
    pages.append(page('https://' + domain + '/hq', 'Trialnamequery headquarters',
                      'Trialnamequery is headquartered in Zürich. ' * 12))
    company = {'domain': domain, 'names': ['Trialnamequery'], 'pages': pages,
               'research': {'nimble': {'0': [], '1': []}}}
    (destination / (domain + '.json')).write_text(json.dumps(company, ensure_ascii=False))


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('usage: python3 edge_corpus.py SAMPLE_CORPUS NEW_DESTINATION')
    source, destination = Path(sys.argv[1]), Path(sys.argv[2])
    shutil.copytree(source, destination)
    custom = Path(__file__).parent / 'corpus'
    for path in custom.glob('*.json'):
        shutil.copy2(path, destination / path.name)
