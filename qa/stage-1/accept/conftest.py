"""Black-box Docker harness; never imports the service under test.

R1.7 R1.8 R1.12 R1.18 R1.20: run the built image alone with provider
environment variables on a network without external routes.
"""
import os
import json
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
import select, socket, socketserver, threading
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
for port, destination in [(18200, 'mock'), (18201, 'app')]:
    server = Server(('0.0.0.0', port), Handler)
    server.destination = destination
    servers.append(server)
    threading.Thread(target=server.serve_forever, daemon=True).start()
threading.Event().wait()
'''


def pytest_addoption(parser):
    parser.addoption('--service-root', default=os.environ.get('DOSSIER_ROOT'),
                     help='worktree containing stage-1/')
    parser.addoption('--corpus', default=str(CORPUS), help='mock web corpus directory')


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
    return [json.loads(path.read_text()) for path in sorted(corpus.glob('*.test.json'))]


@pytest.fixture(scope='session')
def all_pages(all_companies):
    return [page for company in all_companies for page in company['pages'] if 0 in page['epochs']]


def docker(*args, timeout=300, check=True):
    return subprocess.run(['docker', *map(str, args)], check=check, timeout=timeout,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def unused_ports(count):
    sockets = []
    try:
        for port in range(18200, 18300):
            sock = socket.socket()
            try:
                sock.bind(('127.0.0.1', port))
            except OSError:
                sock.close()
                continue
            sockets.append(sock)
            if len(sockets) == count:
                return [s.getsockname()[1] for s in sockets]
        raise RuntimeError('Not enough free ports in 18200–18299')
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


def launch_deployment(request, corpus):
    root = request.config.getoption('--service-root')
    if not root:
        pytest.fail('Set DOSSIER_ROOT or pass --service-root to a worktree containing stage-1')
    service = Path(root).resolve() / 'stage-1'
    corpus = Path(corpus).resolve()
    if not corpus.is_dir():
        pytest.fail(f'Corpus directory does not exist: {corpus}')
    if not (service / 'Dockerfile').is_file():
        pytest.fail(f'No Dockerfile in {service}')
    tag = 'prover-' + uuid.uuid4().hex[:12]
    network, front, relay, mock, app = tag + '-net', tag + '-front', tag + '-relay', tag + '-mock', tag + '-app'
    web_image, app_image = tag + '-web', tag + '-service'
    mock_port, app_port = unused_ports(2)
    try:
        docker('build', '-t', web_image, WEB, timeout=600)
        docker('build', '-t', app_image, service, timeout=600)
        docker('network', 'create', '--internal', network)
        docker('network', 'create', front)
        docker('run', '-d', '--name', relay, '--network', front,
               '-p', f'127.0.0.1:{mock_port}:18200', '-p', f'127.0.0.1:{app_port}:18201',
               '--entrypoint', 'python', web_image, '-u', '-c', RELAY)
        docker('network', 'connect', network, relay)
        docker('run', '-d', '--name', mock, '--network', network, '--network-alias', 'mock',
               '-e', 'MOCK_ADMIN_TOKEN=prover-local-admin',
               '-v', f'{corpus}:/data/corpus:ro', web_image)
        healthy(f'http://127.0.0.1:{mock_port}/_mock/health')
        docker('run', '-d', '--name', app, '--network', network, '--network-alias', 'app',
               '--cpus', '2', '--memory', '3g',
               '-e', 'PORT=8080', '-e', 'NIMBLE_API_KEY=local',
               '-e', f'NIMBLE_BASE_URL=http://{mock}:8080/nimble',
               '-e', 'TAVILY_API_KEY=local',
               '-e', f'TAVILY_BASE_URL=http://{mock}:8080/tavily', app_image)
        healthy(f'http://127.0.0.1:{app_port}/health')
        yield {'app': f'http://127.0.0.1:{app_port}', 'mock': f'http://127.0.0.1:{mock_port}',
               'container': app}
    finally:
        for name in (app, mock, relay):
            docker('rm', '-f', name, timeout=20, check=False)
        docker('network', 'rm', network, timeout=20, check=False)
        docker('network', 'rm', front, timeout=20, check=False)
        for image in (app_image, web_image):
            docker('image', 'rm', '-f', image, timeout=20, check=False)


@pytest.fixture(scope='session')
def deployment(request):
    yield from launch_deployment(request, request.config.getoption('--corpus'))


@pytest.fixture(scope='session')
def adversarial_deployment(request, tmp_path_factory):
    corpus = tmp_path_factory.mktemp('prover-corpus')
    for domain, sentence in (
        ('rumor-press.test', 'Rumor Press is rumoured to have raised $17M.'),
        ('scale-probe.test', 'Scale Probe has raised $23mn.'),
        ('adjacency-labs.test', 'Adjacency Labs raised $73widgets.'),
        ('exact-ledger.test', 'Exact Ledger raised $987654321098765432109876543210987654321.'),
        ('fraction-ledger.test', 'Fraction Ledger raised $0.00000007 million.'),
    ):
        page = {'url':f'https://{domain}/about', 'kind':'own', 'epochs':[0],
                'searchable':True, 'published_at':None, 'true_from':None,
                'title':domain, 'text':sentence, 'facts':{},
                'lineage':{'canonical':None, 'first_published_by':None, 'registrant':domain}}
        company = {'domain':domain, 'names':[domain.split('.')[0].replace('-', ' ')],
                   'pages':[page], 'research':{}}
        (corpus / (domain + '.json')).write_text(json.dumps(company))
    yield from launch_deployment(request, corpus)


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
