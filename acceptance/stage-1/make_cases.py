"""Independent controlled prose, generated into a private copy of mock corpus."""
import json
import sys
from pathlib import Path

CASES = {
    'evidencealpha.test': ('Evidencealpha registered name Evidencealpha GmbH.\nEvidencealpha is headquartered in Zürich.\nEvidencealpha CEO: Dana Müller.\nEvidencealpha was founded in 1800.\nEvidencealpha employs 10 people.\nEvidencealpha has raised US$12.5 million.', {'legal_name':'Evidencealpha GmbH','hq_city':'Zürich','ceo':'Dana Müller','founded_year':1800,'headcount_range':'1-10','funding_total':12500000}),
    'evidencebeta.test': ('Evidencebeta registered name Evidencebeta Inc. Evidencebeta is based in New York.\nEvidencebeta was established in 2099.\nEvidencebeta staff: 11-50 employees.\nEvidencebeta raised 12 million dollars.', {'legal_name':'Evidencebeta Inc.','hq_city':'New York','founded_year':2099,'headcount_range':'11-50','funding_total':12000000}),
    'evidencegamma.test': ('Evidencegamma was founded in 1799.\nEvidencegamma was established in 2100.\nEvidencegamma has 0 employees.\nEvidencegamma raised €12 million.\nEvidencegamma opened a sales office in Porto.', {}),
    'evidencedelta.test': ('Evidencedelta was founded in 2014 and 2015.\nEvidencedelta employs 50-51 people.\nEvidencedelta funding was $1M or $2M.\nEvidencedelta CEO: Dana Ruiz or Sam Ortiz.', {}),
    'evidenceepsilon.test': ('Evidenceepsilon was founded in 2014.\nEvidenceepsilon employs 51-200 people.\nEvidenceepsilon raised $12,000,000.\nEvidenceepsilon chief executive Dana Ruiz leads the company.', {'founded_year':2014,'headcount_range':'51-200','funding_total':12000000,'ceo':'Dana Ruiz'}),
    'evidencezeta.test': ('Evidencezeta reportedly was founded in 2014.\nEvidencezeta formerly employed 100 people.\nEvidencezeta is not headquartered in London.\nEvidencezeta might raise $12M.\nEvidencezeta former CEO Dana Ruiz leads another company.', {}),
    'evidenceeta.test': ('Evidenceeta was founded in 20140.\nEvidenceeta employs 12.5 people.\nEvidenceeta raised $0.001.\nEvidenceeta has funding of 20 euros.', {}),
    'evidencetheta.test': ('Evidencetheta registered as Evidencetheta S.A.S.\nEvidencetheta is based in São-Paulo.\nEvidencetheta workforce: 10001 people.\nEvidencetheta has raised $1.5bn.', {'legal_name':'Evidencetheta S.A.S.','hq_city':'São-Paulo','headcount_range':'10001+','funding_total':1500000000}),
    'evidenceiota.test': ('Evidenceiota plans to be founded in 2014.\nEvidenceiota wants to employ 100 people.\nEvidenceiota could raise $12M.\nEvidenceiota will become headquartered in Lisbon.\nEvidenceiota is rumoured to have CEO Dana Ruiz.', {}),
    'evidencekappa.test': ('\n'.join('Evidencekappa ' + phrase + ' was founded in 2014.' for phrase in ('in talks to', 'plans to', 'planning to', 'wants to', 'expects to', 'hopes to', 'aims to', 'seeking', 'could', 'would', 'might', 'reportedly', 'rumoured', 'former', 'formerly', 'will become', 'not')), {}),
    'evidencelambda.test': ('Evidencelambda was refounded in 2014.\nEvidencelambda has funding of $1,23.\nEvidencelambda opened offices in Berlin.', {}),
    'evidencemu.test': ('Evidencemu was founded in 2014, a note states.', {'founded_year':2014}),
}

for n, count, expected in [('one', '1-10', '1-10'), ('two', '11-50', '11-50'),
                           ('three', '51-200', '51-200'), ('four', '201-500', '201-500'),
                           ('five', '501-1000', '501-1000'), ('six', '1001-5000', '1001-5000'),
                           ('seven', '5001-10000', '5001-10000'), ('eight', '10001', '10001+')]:
    domain = 'edge' + n + '.test'
    CASES[domain] = ('Edge' + n + ' employs ' + count + ' people.', {'headcount_range': expected})

if __name__ == '__main__':
    root = Path(sys.argv[1])
    for domain, (prose, _) in CASES.items():
        name = domain.split('.')[0].capitalize()
        page = {'url': 'https://' + domain + '/about', 'kind': 'own', 'epochs': [0, 1], 'searchable': True,
                'published_at': None, 'true_from': None, 'title': name, 'text': prose,
                'facts': {'ceo': 'Misleading Person', 'funding_total': '$999M'}, 'lineage': {'canonical': None, 'first_published_by': None, 'registrant': domain}}
        claims = []
        if domain == 'evidencezeta.test':
            claims.append({'field':'founded_year','value':2014,'url':page['url'],'excerpt':'Evidencezeta reportedly was founded in 2014.'})
        if domain == 'evidencealpha.test':
            claims.append({'field':'ceo','value':'Sam Ortiz','url':page['url'],'excerpt':'Evidencealpha CEO: Dana Müller.'})
        (root / (domain + '.json')).write_text(json.dumps({'domain': domain, 'names': [name], 'pages': [page], 'research': {'nimble': {'0': claims, '1': claims}}}))
    domain = 'multiproof.test'
    pages = []
    for path, text in [('a', 'Multiproof CEO: Dana Ruiz.'), ('b', 'Multiproof CEO: Dana Ruiz.'), ('c', '\n'.join(['Multiproof CEO: Sam Ortiz.'] * 5))]:
        pages.append({'url':'https://' + domain + '/' + path, 'kind':'own', 'epochs':[0,1], 'searchable':True,
                      'published_at':None, 'true_from':None, 'title':'Multiproof ' + path, 'text':text, 'facts':{},
                      'lineage':{'canonical':None,'first_published_by':None,'registrant':domain}})
    (root / (domain + '.json')).write_text(json.dumps({'domain':domain,'names':['Multiproof'],'pages':pages,'research':{'nimble':{'0':[],'1':[]}}}))
