"""Black-box Docker harness; never imports the service under test.

R1.7 R1.8 R1.12 R1.18 R1.20: run the built image alone with provider
environment variables on a network without external routes.
"""
import os
import json
import re
import socket
import subprocess
import time
import uuid
from pathlib import Path

import httpx
import pytest

WEB = Path('/home/ndivij/buildathon/sf-buildathon-2026/challenges/dossier/web')
CORPUS = WEB / 'corpus/sample'
ADMIN = {'X-Mock-Admin': 'prover-local-admin'}
RELAY = r'''
import select, socket, socketserver, sys, threading
class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        try:
            with socket.create_connection((self.server.destination, 8080), timeout=5) as upstream:
                upstream.settimeout(None)
                sockets = [self.request, upstream]
                while True:
                    ready, _, _ = select.select(sockets, [], [], 30)
                    if not ready: return
                    for src in ready:
                        data = src.recv(65536)
                        if not data: return
                        (upstream if src is self.request else self.request).sendall(data)
        except (OSError, TimeoutError):
            return
class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True
servers = []
for port, destination in [(int(sys.argv[1]), 'mock'), (int(sys.argv[2]), 'app')]:
    server = Server(('0.0.0.0', port), Handler)
    server.destination = destination
    servers.append(server)
    threading.Thread(target=server.serve_forever, daemon=True).start()
threading.Event().wait()
'''

# Chromium runs only on the internal Docker network.  The local test process
# connects to its DevTools socket through this container-local TCP bridge.
BROWSER_CDP = r'''
import select, shutil, socket, socketserver, subprocess
chromium = shutil.which('chromium-browser') or shutil.which('chromium')
if not chromium: raise RuntimeError('chromium is absent in the mock-web image')
process = subprocess.Popen([chromium, '--headless', '--no-sandbox', '--disable-gpu',
    '--disable-dev-shm-usage', '--disable-background-networking',
    '--remote-debugging-port=9223', '--remote-allow-origins=*',
    '--user-data-dir=/tmp/prover-browser', 'about:blank'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        try:
            with socket.create_connection(('127.0.0.1', 9223), timeout=10) as upstream:
                upstream.settimeout(None)
                sockets = [self.request, upstream]
                while True:
                    ready, _, _ = select.select(sockets, [], [], 60)
                    if not ready: return
                    for source in ready:
                        data = source.recv(65536)
                        if not data: return
                        (upstream if source is self.request else self.request).sendall(data)
        except OSError:
            return
class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True
Server(('0.0.0.0', 9222), Handler).serve_forever()
'''

# An HTTP proxy measures active extract requests without inspecting the service.
EXTRACT_MONITOR = r'''
import http.client, http.server, json, threading
lock = threading.Lock()
active = peak = total = 0
class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_GET(self):
        if self.path == '/_probe/metrics':
            with lock: payload = json.dumps({'active': active, 'peak': peak, 'total': total}).encode()
            self.send_response(200); self.send_header('Content-Length', str(len(payload))); self.end_headers(); self.wfile.write(payload)
        else: self.forward()
    def do_POST(self): self.forward()
    def forward(self):
        global active, peak, total
        extract = self.path in ('/nimble/v2/extract', '/tavily/extract')
        body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
        if extract:
            with lock:
                active += 1; total += 1; peak = max(peak, active)
        try:
            conn = http.client.HTTPConnection('mock', 8080, timeout=60)
            headers = {k: v for k, v in self.headers.items() if k.lower() not in ('host', 'connection')}
            conn.request(self.command, self.path, body, headers)
            response = conn.getresponse(); data = response.read()
            self.send_response(response.status)
            for key, value in response.getheaders():
                if key.lower() not in ('connection', 'transfer-encoding', 'content-length'):
                    self.send_header(key, value)
            self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
        finally:
            if extract:
                with lock: active -= 1
http.server.ThreadingHTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
'''

# A transparent provider proxy records request start and response times so
# retry spacing is measured outside the deliverable.
PROVIDER_MONITOR = r'''
import http.client, http.server, json, threading, time
lock = threading.Lock()
calls = []
class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_GET(self):
        if self.path == '/_probe/calls':
            with lock: data = json.dumps(calls).encode()
            self.send_response(200); self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
        else: self.forward()
    def do_POST(self): self.forward()
    def forward(self):
        start = time.monotonic()
        body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
        conn = http.client.HTTPConnection('mock', 8080, timeout=90)
        headers = {k:v for k,v in self.headers.items() if k.lower() not in ('host','connection')}
        conn.request(self.command, self.path, body, headers)
        response = conn.getresponse(); data = response.read()
        answered = time.monotonic()
        try: decoded = json.loads(body) if body else None
        except ValueError: decoded = None
        with lock: calls.append({'path':self.path, 'method':self.command, 'body':decoded,
                                 'start':start, 'answered':answered, 'status':response.status})
        self.send_response(response.status)
        for key, value in response.getheaders():
            if key.lower() not in ('connection','transfer-encoding','content-length'):
                self.send_header(key,value)
        self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
http.server.ThreadingHTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
'''

# For the upgrade test, HTML always comes from Stage 2 while API calls switch
# from the old service to the new service after an explicit test-only signal.
UPGRADE_PROXY = r'''
import http.client, http.server, threading
lock = threading.Lock()
target = 'oldapp'
class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_GET(self): self.forward()
    def do_POST(self):
        global target
        if self.path == '/_probe/switch':
            with lock: target = 'newapp'
            self.send_response(204); self.end_headers()
        else: self.forward()
    def forward(self):
        body = self.rfile.read(int(self.headers.get('Content-Length','0')))
        path = self.path.split('?',1)[0]
        is_api = (path == '/dossiers' or path.startswith('/dossiers/') or path.startswith('/auth/'))
        html = 'text/html' in self.headers.get('Accept','').lower()
        with lock: upstream = target if is_api and not html else 'newapp'
        conn = http.client.HTTPConnection(upstream,8080,timeout=60)
        headers = {k:v for k,v in self.headers.items() if k.lower() != 'connection'}
        conn.request(self.command,self.path,body,headers)
        response=conn.getresponse(); data=response.read()
        self.send_response(response.status)
        for key,value in response.getheaders():
            if key.lower() not in ('connection','transfer-encoding','content-length'):
                self.send_header(key,value)
        self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
http.server.ThreadingHTTPServer(('0.0.0.0',8080),Handler).serve_forever()
'''

# An independent provider endpoint serves different observed texts for one URL.
DUAL_PROVIDER_PROXY = r'''
import http.client, http.server, json, threading
lock = threading.Lock()
served = []
url = 'https://dual-witness.test/about'
texts = {'nimble': 'Dual Witness was founded in 2014.',
         'tavily': 'Dual Witness CEO Dana Ruiz.'}
class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_GET(self):
        if self.path == '/_probe/served':
            with lock: payload = json.dumps(served).encode()
            self.send_response(200); self.send_header('Content-Length', str(len(payload))); self.end_headers(); self.wfile.write(payload)
        else: self.forward()
    def do_POST(self): self.forward()
    def forward(self):
        body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
        request = json.loads(body) if body else {}
        if self.path == '/nimble/v2/search' and request.get('query') == 'dual-witness.test':
            data = b'{"error":{"message":"forced search refusal"}}'
            self.send_response(500); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
            return
        conn = http.client.HTTPConnection('mock', 8080, timeout=60)
        headers = {k:v for k,v in self.headers.items() if k.lower() not in ('host','connection')}
        conn.request(self.command, self.path, body, headers)
        response = conn.getresponse(); data = response.read()
        provider = 'nimble' if self.path.startswith('/nimble/') else 'tavily'
        if response.status == 200 and self.path in ('/nimble/v2/search','/tavily/search','/nimble/v2/extract','/tavily/extract'):
            payload = json.loads(data)
            records = []
            for item in payload.get('results', []):
                if item.get('url') != url: continue
                if self.path == '/nimble/v2/search':
                    item['description'] = texts[provider]; item['content'] = ''
                elif self.path == '/tavily/search':
                    item['content'] = texts[provider]; item['raw_content'] = None
                else:
                    item['raw_content'] = texts[provider]
                records.append({'provider':provider, 'url':url, 'text':texts[provider]})
            if self.path == '/nimble/v2/extract' and payload.get('url') == url and payload.get('status') == 'success':
                payload['data'] = {key:texts[provider] for key in payload['data']}
                records.append({'provider':provider, 'url':url, 'text':texts[provider]})
            with lock: served.extend(records)
            data = json.dumps(payload).encode()
        self.send_response(response.status)
        for key, value in response.getheaders():
            if key.lower() not in ('connection','transfer-encoding','content-length'):
                self.send_header(key,value)
        self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
http.server.ThreadingHTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
'''


def pytest_addoption(parser):
    parser.addoption('--service-root', default=os.environ.get('DOSSIER_ROOT'),
                     help='worktree containing stage-2/')
    parser.addoption('--corpus', default=str(CORPUS), help='mock web corpus directory')
    parser.addoption('--name-prefix', default='prover', help='Docker name prefix for this seat')
    parser.addoption('--port-start', type=int, default=18200, help='first allowed host port')
    parser.addoption('--port-end', type=int, default=18299, help='last allowed host port')
    parser.addoption('--stage1-root', default=None, help='worktree containing the frozen stage-1/')


def pytest_generate_tests(metafunc):
    if 'company_path' in metafunc.fixturenames:
        corpus = Path(metafunc.config.getoption('--corpus')).resolve()
        if not corpus.is_dir():
            raise pytest.UsageError(f'Corpus directory does not exist: {corpus}')
        companies = sorted(corpus.glob('*.test.json'))
        if not companies:
            raise pytest.UsageError(f'No company files in corpus: {corpus}')
        metafunc.parametrize('company_path', companies, ids=lambda p: p.stem)


@pytest.fixture(scope='session')
def all_companies(request):
    corpus = Path(request.config.getoption('--corpus')).resolve()
    result = []
    for path in sorted(corpus.glob('*.test.json')):
        source = json.loads(path.read_text())
        result.append({'domain': source['domain'], 'research': source.get('research', {}),
                       'pages': [{key: page[key] for key in ('url', 'epochs', 'searchable') if key in page}
                                 for page in source['pages']]})
    return result


@pytest.fixture(scope='session')
def served_companies(all_companies, deployment):
    """RL25: obtain page text from the provider, not corpus text variants."""
    with httpx.Client(base_url=deployment['mock'], headers=ADMIN, timeout=10, trust_env=False) as client:
        assert client.post('/_mock/reset', json={'epoch': 0}).status_code == 204
        pages = [page for company in all_companies for page in company['pages'] if 0 in page['epochs']]
        for url in dict.fromkeys(page['url'] for page in pages):
            response = client.post('/nimble/v2/extract', json={'url': url, 'formats': ['markdown']})
            assert response.status_code == 200, (url, response.status_code)
        calls = client.get('/_mock/log').json()['calls']
        texts = {item['url']: item['text'] for call in calls for item in call.get('served', [])}
        assert all(page['url'] in texts for page in pages)
        for page in pages:
            page['text'] = texts[page['url']]
        assert client.post('/_mock/reset', json={'epoch': 0}).status_code == 204
    return all_companies


@pytest.fixture(scope='session')
def all_pages(served_companies):
    return [page for company in served_companies for page in company['pages'] if 0 in page['epochs']]


def docker(*args, timeout=300, check=True):
    return subprocess.run(['docker', *map(str, args)], check=check, timeout=timeout,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def unused_ports(count, first, last):
    sockets = []
    try:
        for port in range(first, last + 1):
            sock = socket.socket()
            try:
                sock.bind(('127.0.0.1', port))
            except OSError:
                sock.close()
                continue
            sockets.append(sock)
            if len(sockets) == count:
                return [s.getsockname()[1] for s in sockets]
        raise RuntimeError(f'Not enough free ports in {first}–{last}')
    finally:
        for sock in sockets:
            sock.close()


def healthy(url, seconds=60):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            if httpx.get(url, timeout=1, trust_env=False).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(.1)
    raise AssertionError(f'health endpoint did not become ready in {seconds}s: {url}')


def launch_deployment(request, corpus, monitor_extracts=False, dual_provider=False, monitor_requests=False,
                      stage='stage-2', root=None):
    root = root or request.config.getoption('--service-root')
    if not root:
        pytest.fail('Set DOSSIER_ROOT or pass --service-root to a worktree containing stage-2')
    service = Path(root).resolve() / stage
    corpus = Path(corpus).resolve()
    if not corpus.is_dir():
        pytest.fail(f'Corpus directory does not exist: {corpus}')
    if not (service / 'Dockerfile').is_file():
        pytest.fail(f'No Dockerfile in {service}')
    prefix = request.config.getoption('--name-prefix')
    first, last = request.config.getoption('--port-start'), request.config.getoption('--port-end')
    if not re.fullmatch(r'[a-z0-9][a-z0-9_.-]{0,39}', prefix):
        pytest.fail('Docker name prefix must be 1–40 lowercase letters, digits, dots, underscores or hyphens')
    if not 1 <= first < last <= 65535:
        pytest.fail('Port range must contain at least two valid TCP ports')
    tag = prefix + '-' + uuid.uuid4().hex[:12]
    network, front, relay, mock, app = tag + '-net', tag + '-front', tag + '-relay', tag + '-mock', tag + '-app'
    web_image, app_image = tag + '-web', tag + '-service'
    monitor = tag + '-monitor'
    mock_port, app_port = unused_ports(2, first, last)
    try:
        docker('build', '-t', web_image, WEB, timeout=600)
        docker('build', '-t', app_image, service, timeout=600)
        docker('network', 'create', '--internal', network)
        docker('network', 'create', front)
        docker('run', '-d', '--name', relay, '--network', front,
               '-p', f'127.0.0.1:{mock_port}:{mock_port}', '-p', f'127.0.0.1:{app_port}:{app_port}',
               '--entrypoint', 'python', web_image, '-u', '-c', RELAY, str(mock_port), str(app_port))
        docker('network', 'connect', network, relay)
        docker('run', '-d', '--name', mock, '--network', network, '--network-alias', 'mock',
               '-e', 'MOCK_ADMIN_TOKEN=prover-local-admin',
               '-e', 'XDG_CONFIG_HOME=/tmp', '-e', 'XDG_CACHE_HOME=/tmp',
               '-v', f'{corpus}:/data/corpus:ro', web_image)
        healthy(f'http://127.0.0.1:{mock_port}/_mock/health')
        upstream = mock
        if monitor_extracts or dual_provider or monitor_requests:
            docker('run', '-d', '--name', monitor, '--network', network,
                   '--entrypoint', 'python', web_image, '-u', '-c',
                   DUAL_PROVIDER_PROXY if dual_provider else PROVIDER_MONITOR if monitor_requests else EXTRACT_MONITOR)
            upstream = monitor
        docker('run', '-d', '--name', app, '--network', network, '--network-alias', 'app',
               '--network-alias', 'dossier.internal',
               '--cpus', '2', '--memory', '3g',
               '-e', 'PORT=8080', '-e', 'NIMBLE_API_KEY=local',
               '-e', f'NIMBLE_BASE_URL=http://{upstream}:8080/nimble',
               '-e', 'TAVILY_API_KEY=local',
               '-e', f'TAVILY_BASE_URL=http://{upstream}:8080/tavily',
               '-e', 'KERNEL_API_KEY=local', '-e', f'KERNEL_BASE_URL=http://{upstream}:8080/kernel',
               '-e', 'BROWSERBASE_API_KEY=local', '-e', f'BROWSERBASE_BASE_URL=http://{upstream}:8080/browserbase',
               app_image)
        healthy(f'http://127.0.0.1:{app_port}/health')
        yield {'app': f'http://127.0.0.1:{app_port}', 'mock': f'http://127.0.0.1:{mock_port}',
               'container': app, 'network': network, 'web_image': web_image, 'prefix': prefix,
               'monitor': monitor if monitor_extracts or dual_provider or monitor_requests else None}
    finally:
        for name in (app, monitor, mock, relay):
            docker('rm', '-f', name, timeout=20, check=False)
        docker('network', 'rm', network, timeout=20, check=False)
        docker('network', 'rm', front, timeout=20, check=False)
        for image in (app_image, web_image):
            docker('image', 'rm', '-f', image, timeout=20, check=False)


@pytest.fixture(scope='session')
def deployment(request):
    yield from launch_deployment(request, request.config.getoption('--corpus'))


@pytest.fixture(scope='session')
def frozen_deployment(request):
    root = request.config.getoption('--stage1-root') or request.config.getoption('--service-root')
    yield from launch_deployment(request, request.config.getoption('--corpus'), stage='stage-1', root=root)


@pytest.fixture(scope='session')
def selection_deployment(request, tmp_path_factory):
    """A small controlled corpus with disagreements and an unsearchable research page."""
    corpus = tmp_path_factory.mktemp('prover-selection-corpus')
    domain = 'selection-labs.test'
    definitions = [
        (f'https://{domain}/about', 'own', '2025-01-01T00:00:00Z', True,
         'Selection Labs CEO Dana Ruiz.\nSelection Labs was founded in 2014.\nSelection Labs was founded in 2018.',
         'Selection Labs CEO Phantom Smith.'),
        ('https://filings.test/selection-labs', 'filing', '2025-03-01T01:00:00+01:00', True,
         'Selection Labs CEO Mira Stone.', None),
        ('https://news.test/selection-labs', 'news', '2027-01-01T00:00:00Z', True,
         'Selection Labs CEO Sam Ortiz.\nSelection Labs CEO Mira Stone.', None),
        ('https://aggregator.test/selection-labs', 'aggregator', '2028-01-01T00:00:00Z', True,
         'Selection Labs CEO Nora Mills.', None),
        (f'https://{domain}/undated', None, None, True, 'Selection Labs CEO Eva Lane.', None),
        (f'https://{domain}/hidden', 'own', None, False, 'Selection Labs employs 120 people.', None),
    ]
    pages = []
    for url, kind, published, searchable, text, static in definitions:
        page = {'url': url, 'kind': kind, 'published_at': published, 'epochs': [0],
                'searchable': searchable, 'title': 'Selection Labs company profile', 'text': text,
                'facts': {}, 'lineage': {'canonical': None, 'first_published_by': None,
                                         'registrant': url.split('/')[2]}}
        if static is not None:
            page['static_text'] = static
        pages.append(page)
    claims = [
        ('ceo', 'Riley Moore', 5, 'Selection Labs employs 120 people.'),
        ('founded_year', 2014, 0, 'Selection Labs was founded in 2014.'),
        ('legal_name', 'Selection Labs Inc.', 2, 'Selection Labs CEO Sam Ortiz.'),
        ('hq_city', 'Paris', 3, 'Selection Labs CEO Nora Mills.'),
        ('headcount_range', '51-200', 1, 'Selection Labs CEO Mira Stone.'),
        ('funding_total', 5, 4, 'Selection Labs CEO Eva Lane.'),
    ]
    company = {'domain': domain, 'names': ['Selection Labs'], 'pages': pages,
               'research': {'nimble': {'0': [{'field':field, 'value':value, 'url':pages[i]['url'], 'excerpt':excerpt}
                                               for field,value,i,excerpt in claims]}}}
    (corpus / (domain + '.json')).write_text(json.dumps(company))
    yield from launch_deployment(request, corpus)


@pytest.fixture(scope='session')
def timed_deployment(request):
    yield from launch_deployment(request, request.config.getoption('--corpus'), monitor_requests=True)


@pytest.fixture(scope='session')
def metadata_deployment(request, tmp_path_factory):
    corpus = tmp_path_factory.mktemp('prover-metadata-corpus')
    domain = 'metadata-labs.test'
    definitions = [
        (f'https://{domain}/a', 'own', '2025-01-01T00:00:00.12345678901234567890Z', 'Alex Brown'),
        (f'https://{domain}/z', 'own', '2025-01-01T00:00:00.12345678901234567891Z', 'Bianca Hart'),
        (f'https://{domain}/offset-a', 'filing', '2024-01-01T01:00:00+01:00', 'Casey Reed'),
        (f'https://{domain}/offset-b', 'own', '2024-01-01T00:00:00Z', 'Dina West'),
        (f'https://{domain}/invalid', 'nonsense', '2025-02-30T00:00:00Z', 'Elena Stone'),
        ('https://outside.test/metadata-labs', None, None, 'Frances Green'),
        (f'https://{domain}/leap-invalid', 'filing', '2025-01-01T12:30:60Z', 'Invalid Leap'),
        (f'https://{domain}/leap-valid', 'news', '2025-01-01T18:59:60-05:00', 'Valid Leap'),
    ]
    pages = [{'url':url, 'kind':kind, 'published_at':published, 'epochs':[0], 'searchable':True,
              'title':'Metadata Labs company', 'text':f'Metadata Labs CEO {ceo}.', 'facts':{},
              'lineage':{'canonical':None, 'first_published_by':None, 'registrant':url.split('/')[2]}}
             for url,kind,published,ceo in definitions]
    fields = [('ceo', 'Alex Brown'), ('legal_name', 'Metadata Labs Inc.'), ('hq_city', 'Paris'),
              ('founded_year', 2014), ('headcount_range', '51-200'), ('funding_total', 5)]
    claims = [{'field':field, 'value':value, 'url':pages[i]['url'],
               'excerpt':f'Metadata Labs CEO {definitions[i][3]}.'}
              for i,(field,value) in enumerate(fields)]
    claims.extend({'field':'ceo', 'value':name, 'url':pages[i]['url'],
                   'excerpt':f'Metadata Labs CEO {name}.'}
                  for i,name in ((6, 'Invalid Leap'), (7, 'Valid Leap')))
    (corpus / (domain + '.json')).write_text(json.dumps({'domain':domain, 'names':['Metadata Labs'],
                      'pages':pages, 'research':{'nimble':{'0':claims}}}))
    yield from launch_deployment(request, corpus)


@pytest.fixture(scope='session')
def adversarial_deployment(request, tmp_path_factory):
    corpus = tmp_path_factory.mktemp('prover-corpus')
    long_prefix = 'Length Probe ' + ('background ' * 28) + 'raised $19M '
    long_sentence = long_prefix + 'x' * (500 - len(long_prefix)) + '.'
    assert len(long_sentence) == 501
    for domain, sentence in (
        ('rumor-press.test', 'Rumor Press is rumoured to have raised $17M.'),
        ('scale-probe.test', 'Scale Probe has raised $23mn.'),
        ('adjacency-labs.test', 'Adjacency Labs raised $73widgets.'),
        ('exact-ledger.test', 'Exact Ledger raised $987654321098765432109876543210987654321.'),
        ('fraction-ledger.test', 'Fraction Ledger raised $0.00000007 million.'),
        ('length-probe.test', long_sentence),
        ('extract-probe.test', 'Extract Probe publishes an annual review.'),
        ('hidden-record.test', 'Hidden Record was incorporated in 2008.\nHidden Record employs 120 people.'),
        ('zero-research.test', 'Zero Research has raised $0.'),
        ('variant-probe.test', 'Variant Probe has raised $19M.'),
        ('long-witness.test', 'Long Witness was incorporated in 2012 ' + 'and ' * 200 + 'today.'),
        ('late-negation.test', 'Late Negation raised $19M ' + 'filler ' * 90 + 'not later.'),
        ('late-conflict.test', 'Late Conflict raised $19M ' + 'filler ' * 90 + 'or $23M.'),
        ('shape-probe.test', 'Shape Probe Inc. is the legal name of Shape Probe.\n'
         'Shape Probe is based in Lisbon.\nShape Probe CEO Mira Santos.\n'
         'Shape Probe was founded in 2014.\nShape Probe employs 120 people.\n'
         'Shape Probe has raised $23mn.'),
    ):
        page = {'url':f'https://{domain}/about', 'kind':'own', 'epochs':[0],
                'searchable':True, 'published_at':None, 'true_from':None,
                'title':domain, 'text':sentence, 'facts':{},
                'lineage':{'canonical':None, 'first_published_by':None, 'registrant':domain}}
        company = {'domain':domain, 'names':[domain.split('.')[0].replace('-', ' ')],
                   'pages':[page], 'research':{}}
        if domain == 'extract-probe.test':
            company['research'] = {'nimble': {'0': [{
                'field':'ceo', 'value':'Elena Vale', 'url':'https://extract-probe.test/missing',
                'excerpt':'Extract Probe CEO Elena Vale.'}]}}
        elif domain == 'hidden-record.test':
            page['searchable'] = False
            company['research'] = {'nimble': {'0': [{
                'field':'founded_year', 'value':2008, 'url':page['url'],
                'excerpt':'Hidden Record was incorporated in 2008.'}]}}
        elif domain == 'zero-research.test':
            page['searchable'] = False
            company['research'] = {'nimble': {'0': [{
                'field':'funding_total', 'value':0, 'url':page['url'],
                'excerpt':'Zero Research has raised $0.'}]}}
        elif domain == 'variant-probe.test':
            page['static_text'] = 'Variant Probe has raised $23M.'
        (corpus / (domain + '.json')).write_text(json.dumps(company))
    yield from launch_deployment(request, corpus)


@pytest.fixture(scope='session')
def concurrency_deployment(request, tmp_path_factory):
    corpus = tmp_path_factory.mktemp('prover-concurrency-corpus')
    domain = 'concurrency-probe.test'
    pages = []
    for index in range(30):
        pages.append({'url': f'https://{domain}/page-{index:02d}', 'kind': 'own', 'epochs': [0],
                      'searchable': True, 'published_at': None, 'true_from': None,
                      'title': f'Concurrency Probe report {index}',
                      'text': 'Concurrency Probe publishes reports. ' + ('Additional details. ' * 40),
                      'facts': {}, 'lineage': {'canonical': None, 'first_published_by': None, 'registrant': domain}})
    company = {'domain': domain, 'names': ['Concurrency Probe'], 'pages': pages, 'research': {}}
    (corpus / (domain + '.json')).write_text(json.dumps(company))
    yield from launch_deployment(request, corpus, monitor_extracts=True)


@pytest.fixture(scope='session')
def dual_provider_deployment(request, tmp_path_factory):
    corpus = tmp_path_factory.mktemp('prover-dual-provider')
    domain = 'dual-witness.test'
    page = {'url':f'https://{domain}/about', 'kind':'own', 'epochs':[0], 'searchable':True,
            'published_at':None, 'true_from':None, 'title':'Dual Witness company',
            'text':'Dual Witness was founded in 2014.', 'facts':{},
            'lineage':{'canonical':None, 'first_published_by':None, 'registrant':domain}}
    company = {'domain':domain, 'names':['Dual Witness'], 'pages':[page], 'research':{}}
    (corpus / (domain + '.json')).write_text(json.dumps(company))
    yield from launch_deployment(request, corpus, dual_provider=True)


@pytest.fixture
def api(deployment):
    with httpx.Client(base_url=deployment['app'], timeout=5, trust_env=False) as client:
        yield client


@pytest.fixture
def direct_api(deployment):
    # A server can reject Content-Length before consuming the upload. A direct
    # connection observes that response without the relay closing mid-upload.
    address = docker('inspect', '--format', '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}',
                     deployment['container'], timeout=10).stdout.strip()
    with httpx.Client(base_url=f'http://{address}:8080', timeout=10, trust_env=False) as client:
        yield client


@pytest.fixture
def browser_factory():
    from browser_client import BrowserPage
    running = []
    def launch(deployment, width=375, origin='http://dossier.internal:8080'):
        name = deployment['prefix'] + '-browser-' + uuid.uuid4().hex[:12]
        running.append((name, None))
        docker('run', '-d', '--name', name, '--network', deployment['network'],
               '--entrypoint', 'python', deployment['web_image'], '-u', '-c', BROWSER_CDP)
        address = docker('inspect', '--format', '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}',
                         name, timeout=10).stdout.strip()
        endpoint = f'http://{address}:9222/json/version'
        healthy(endpoint, seconds=30)
        target = httpx.put(f'http://{address}:9222/json/new?about:blank', timeout=10, trust_env=False).json()
        page = BrowserPage(address, 9222, target['id'], width=width, origin=origin)
        page.container_name = name
        page.artifact_prefix = deployment['prefix']
        running[-1] = (name, page)
        return page
    try:
        yield launch
    finally:
        for name, page in reversed(running):
            if page:
                page.close()
            docker('rm', '-f', name, timeout=20, check=False)


@pytest.fixture
def browser_page(browser_factory, deployment):
    return browser_factory(deployment)


@pytest.fixture
def upgrade_browser(frozen_deployment, deployment, browser_factory):
    tag = deployment['prefix'] + '-upgrade-' + uuid.uuid4().hex[:12]
    network, proxy = tag + '-net', tag + '-proxy'
    page = None
    try:
        docker('network', 'create', '--internal', network)
        docker('network', 'connect', '--alias', 'oldapp', network, frozen_deployment['container'])
        docker('network', 'connect', '--alias', 'newapp', network, deployment['container'])
        docker('run', '-d', '--name', proxy, '--network', network, '--network-alias', 'upgrade.internal',
               '--entrypoint', 'python', deployment['web_image'], '-u', '-c', UPGRADE_PROXY)
        address = docker('inspect', '--format', '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}',
                         proxy, timeout=10).stdout.strip()
        browser_deployment = dict(deployment, network=network)
        page = browser_factory(browser_deployment, origin='http://upgrade.internal:8080')
        yield page, f'http://{address}:8080'
    finally:
        if page:
            page.close()
            docker('rm', '-f', page.container_name, timeout=20, check=False)
        docker('rm', '-f', proxy, timeout=20, check=False)
        docker('network', 'disconnect', network, frozen_deployment['container'], timeout=20, check=False)
        docker('network', 'disconnect', network, deployment['container'], timeout=20, check=False)
        docker('network', 'rm', network, timeout=20, check=False)


@pytest.fixture
def mock(deployment):
    with httpx.Client(base_url=deployment['mock'], headers=ADMIN, timeout=10, trust_env=False) as client:
        assert client.post('/_mock/reset', json={'epoch': 0}).status_code == 204
        yield client


@pytest.fixture
def seeded(api, mock):
    fixture = {'now': '2026-03-01T09:00:00+00:00', 'users': [
        {'id': 'u_ada', 'email': 'ada@example.com', 'password': 'correct horse', 'display_name': 'Ada'},
        {'id': 'u_bob', 'email': 'bob@example.com', 'password': 'correct horse', 'display_name': 'Bob'}]}
    assert api.post('/_test/reset', json=fixture, timeout=10).status_code == 204
    tokens = []
    for user in fixture['users']:
        response = api.post('/auth/login', json={'email': user['email'], 'password': user['password']})
        assert response.status_code == 200, response.text
        tokens.append(response.json()['token'])
    yield tokens
    # Do not clear the provider log for the next test while this test's builds
    # are still producing calls. Tests that deliberately invalidate these tokens
    # (reset/import) already wait for their in-flight build explicitly.
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        response = api.get('/dossiers', headers={'Authorization': 'Bearer ' + tokens[0]})
        if response.status_code != 200 or all(
            item['state'] != 'building' for item in response.json().get('dossiers', [])
        ):
            break
        time.sleep(.05)
