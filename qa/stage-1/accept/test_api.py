import concurrent.futures
import datetime
import threading
import time

import httpx
import pytest

from conftest import docker


def auth(token, key=None):
    headers = {'Authorization': 'Bearer ' + token}
    if key is not None:
        headers['Idempotency-Key'] = key
    return headers


def error(response, status, code):
    assert response.status_code == status, (response.request.method, str(response.request.url), response.status_code, response.text)
    body = response.json()
    assert body['error']['code'] == code
    assert isinstance(body['error']['message'], str)


def done(api, token, domain, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r = api.get('/dossiers/' + domain, headers=auth(token))
        assert r.status_code == 200, r.text
        if r.json()['state'] != 'building':
            return r.json()
        time.sleep(.05)
    pytest.fail(f'{domain} was still building after {timeout}s')


def create(api, token, domain, key):
    return api.post('/dossiers', headers=auth(token, key), json={'domain': domain})


def test_R1_15_R1_21_R1_22_R1_49_health(api, mock):
    'R1.7 R1.8 R1.12 R1.15 R1.18 R1.20 R1.21 R1.22 R1.49'
    response = api.get('/health')
    assert response.status_code == 200 and response.json() == {'status': 'ok'}
    assert mock.get('/_mock/log').json()['calls'] == []


def test_R1_29_R1_30_json_and_timestamp(api, seeded):
    'R1.29 R1.30'
    token = seeded[0]
    response = api.get('/health')
    assert response.headers['content-type'].lower().replace(' ', '') == 'application/json;charset=utf-8'
    assert create(api, token, 'ashgrove-solar.test', 'json-format').status_code == 202
    stamp = done(api, token, 'ashgrove-solar.test')['researched_at']
    assert datetime.datetime.fromisoformat(stamp.replace('Z', '+00:00')).utcoffset() is not None


def test_R1_90_R1_91_R1_104_R1_106_dossier_contract(api, seeded):
    'R1.90 R1.91 R1.104 R1.106'
    token = seeded[0]
    error(api.post('/dossiers', headers=auth(token), json={'domain':'x.test'}), 400, 'missing_idempotency_key')
    error(api.post('/dossiers/missing.test/refresh', headers=auth(token, 'x')), 404, 'not_found')
    created = create(api, token, 'ashgrove-solar.test', 'contract')
    assert created.status_code == 202
    assert set(created.json()) == {'dossier_id', 'domain', 'state'}
    item = done(api, token, 'ashgrove-solar.test')
    listing = api.get('/dossiers', headers=auth(token)).json()['dossiers']
    assert listing[0]['legal_name'] == item['fields']['legal_name']['value']


def test_R1_23_R1_48_R1_63_R1_65_R1_66_R1_69_auth_reset(api, seeded):
    'R1.23 R1.48 R1.63 R1.65 R1.66 R1.69'
    ada, bob = seeded
    response = api.post('/auth/login', json={'email': 'ADA@example.com', 'password': 'correct horse'})
    assert response.status_code == 200 and response.json()['user_id'] == 'u_ada'
    assert api.get('/dossiers', headers=auth(ada)).status_code == 200
    assert api.get('/dossiers', headers=auth(response.json()['token'])).status_code == 200
    error(api.post('/auth/login', json={'email': 'ada@example.com', 'password': 'wrong password'}), 401, 'unauthenticated')
    error(api.post('/auth/signup', json={'email': 'ADA@example.com', 'password': '12345678', 'display_name': 'A'}), 409, 'email_taken')
    fixture = {'now': '2026-03-02T00:00:00+00:00', 'users': [
        {'id': 'one', 'email': 'x@example.com', 'password': '12345678', 'display_name': 'X'},
        {'id': 'two', 'email': 'X@example.com', 'password': '12345678', 'display_name': 'Y'}]}
    error(api.post('/_test/reset', json=fixture), 422, 'validation_failed')
    assert api.get('/dossiers', headers=auth(bob)).status_code == 200


@pytest.mark.parametrize('body,status,code', [
    ({'email': 'bad', 'password': '12345678', 'display_name': 'A'}, 422, 'validation_failed'),
    ({'email': 'a@b', 'password': '1234567', 'display_name': 'A'}, 422, 'validation_failed'),
    ({'email': 'a@b', 'password': '12345678', 'display_name': ''}, 422, 'validation_failed'),
    ({'email': 'a@b', 'password': '12345678', 'display_name': 'X'*101}, 422, 'validation_failed'),
    ({'email': 5, 'password': '12345678', 'display_name': 'X'}, 400, 'malformed_request'),
    ({'password': '12345678', 'display_name': 'X'}, 422, 'validation_failed'),
])
def test_R1_49_R1_50_R1_51_R1_56_R1_57_R1_64_R1_65_signup_validation(api, seeded, body, status, code):
    'R1.49 R1.50 R1.51 R1.56 R1.57 R1.64 R1.65'
    error(api.post('/auth/signup', json=body), status, code)


def test_R1_31_R1_33_R1_64_signup_extra_fields(api, seeded):
    'R1.31 R1.33 R1.64'
    response = api.post('/auth/signup', json={'email': 'new@example.com', 'password': '12345678', 'display_name': 'New', 'extra': True})
    assert response.status_code == 201
    assert len(response.json()['user_id']) <= 64
    assert response.json()['display_name'] == 'New'


@pytest.mark.parametrize('header', [None, '', 'Basic x', 'Bearer unknown', 'Bearer'])
def test_R1_53_R1_67_R1_68_auth_precedes_key(api, seeded, header):
    'R1.53 R1.67 R1.68'
    headers = {} if header is None else {'Authorization': header}
    error(api.post('/dossiers', headers=headers, json={'domain': 'foo.test'}), 401, 'unauthenticated')


@pytest.mark.parametrize('method,path', [
    ('GET', '/dossiers'), ('GET', '/dossiers/missing.test'),
    ('POST', '/dossiers'), ('POST', '/dossiers/missing.test/refresh')])
def test_R1_53_R1_67_missing_auth_all_routes(api, seeded, method, path):
    'R1.53 R1.67'
    error(api.request(method, path), 401, 'unauthenticated')


def test_R1_49_R1_51_R1_56_malformed_body_types(api, seeded):
    'R1.49 R1.51 R1.56'
    error(api.post('/auth/login', content=b'{', headers={'Content-Type': 'application/json'}), 400, 'malformed_request')
    error(api.post('/auth/login', json={'email': 'ada@example.com', 'password': 7}), 400, 'malformed_request')
    error(api.post('/auth/login', json={'email': 'ada@example.com'}), 422, 'validation_failed')
    error(api.post('/dossiers', headers=auth(seeded[0], 'array'), json=[]), 400, 'malformed_request')


def test_R1_24_R1_25_R1_26_R1_27_R1_28_clock(api, seeded):
    'R1.24 R1.25 R1.26 R1.27 R1.28'
    t = seeded[0]
    assert api.post('/_test/clock', json={'now': '2026-03-01T10:00:00+00:00'}).status_code == 204
    error(api.post('/_test/clock', json={'now': '2026-03-01T09:59:59+00:00'}), 422, 'validation_failed')
    error(api.post('/_test/clock', json={'now': '2026-03-01T10:01:00'}), 422, 'validation_failed')
    error(api.post('/_test/clock', json={'now': 42}), 400, 'malformed_request')
    assert api.post('/_test/clock', json={'now': '2026-03-01T11:00:00+01:00'}).status_code == 204
    assert create(api, t, 'clock-one.test', 'clock1').status_code == 202
    assert datetime.datetime.fromisoformat(done(api, t, 'clock-one.test')['researched_at']) == datetime.datetime.fromisoformat('2026-03-01T10:00:00+00:00')
    assert create(api, t, 'clock-two.test', 'clock2').status_code == 202
    assert datetime.datetime.fromisoformat(done(api, t, 'clock-two.test')['researched_at']) == datetime.datetime.fromisoformat('2026-03-01T10:00:00+00:00')


@pytest.mark.parametrize('domain', ['localhost', '-a.test', 'a-.test', 'a..test', 'https://a.test', 'a.test/path', 'a_b.test', 'a'*64+'.test', 'a.test..'])
def test_R1_35_R1_51_R1_57_R1_94_invalid_domains(api, seeded, domain):
    'R1.35 R1.51 R1.57 R1.94'
    error(create(api, seeded[0], domain, 'domain'), 422, 'validation_failed')


def test_R1_31_R1_35_R1_36_R1_92_R1_100_normalisation(api, seeded):
    'R1.31 R1.35 R1.36 R1.92 R1.100'
    token = seeded[0]
    first = create(api, token, '  WWW.Acme-Robotics.TEST.  ', 'norm1')
    assert first.status_code == 202 and first.json()['domain'] == 'acme-robotics.test'
    same = create(api, token, 'acme-robotics.test', 'norm2')
    assert same.status_code == 200 and same.json()['dossier_id'] == first.json()['dossier_id']
    assert api.get('/dossiers/WWW.Acme-Robotics.TEST.', headers=auth(token)).json()['domain'] == 'acme-robotics.test'
    error(api.get('/dossiers/missing.test', headers=auth(token)), 404, 'not_found')
    error(api.post('/dossiers', headers=auth(token, 'missing'), json={}), 422, 'validation_failed')
    error(api.post('/dossiers', headers=auth(token, 'wrongtype'), json={'domain': 1}), 400, 'malformed_request')


def test_R1_52_R1_54_R1_55_R1_59_R1_60_R1_71_R1_72_R1_73_R1_74_R1_75_R1_76_R1_77_R1_78_R1_79_R1_81_R1_82_idempotency(api, seeded):
    'R1.52 R1.54 R1.55 R1.59 R1.60 R1.71 R1.72 R1.73 R1.74 R1.75 R1.76 R1.77 R1.78 R1.79 R1.81 R1.82'
    ada, bob = seeded
    error(api.post('/dossiers', headers=auth(ada), content=b'{'), 400, 'missing_idempotency_key')
    error(api.post('/dossiers', headers=auth(ada, 'x'*256), json={'domain':'foo.test'}), 422, 'validation_failed')
    error(api.post('/dossiers', headers=auth(ada, 'invalid'), content=b'{'), 400, 'malformed_request')
    error(create(api, ada, 'bad', 'reusable'), 422, 'validation_failed')
    assert create(api, ada, 'first.test', 'reusable').status_code == 202
    first = create(api, ada, 'Case.test', 'key')
    assert first.status_code == 202
    replay = api.post('/dossiers', headers=auth(ada, 'key'), json={'ignored': 1, 'domain': 'Case.test'})
    assert replay.status_code == 200 and replay.json() == first.json()
    error(create(api, ada, 'case.test', 'key'), 409, 'idempotency_key_reuse')
    error(api.post('/dossiers', headers=auth(ada, 'key'), json={'domain': 3}), 409, 'idempotency_key_reuse')
    assert create(api, bob, 'other.test', 'key').status_code == 202
    refreshed = api.post('/dossiers/case.test/refresh', headers=auth(ada, 'key'), content=b'not json')
    assert refreshed.status_code == 202
    repeat = api.post('/dossiers/case.test/refresh', headers=auth(ada, 'key'), content=b'any body')
    assert repeat.status_code == 200 and repeat.json() == refreshed.json()
    error(api.post('/dossiers/absent.test/refresh', headers=auth(ada, 'absent')), 404, 'not_found')
    assert create(api, ada, 'case.test', 'key').status_code == 409


@pytest.mark.parametrize('parameter,value', [('limit','0'), ('limit','201'), ('limit','1e9'), ('limit','4.0'), ('limit','+4'), ('offset','-1'), ('offset','1e9')])
def test_R1_58_R1_61_R1_109_pagination_invalid(api, seeded, parameter, value):
    'R1.58 R1.61 R1.109'
    error(api.get('/dossiers', headers=auth(seeded[0]), params={parameter:value}), 422, 'validation_failed')


def test_R1_32_R1_34_R1_105_R1_107_R1_108_R1_109_order_and_pagination(api, seeded):
    'R1.32 R1.34 R1.105 R1.107 R1.108 R1.109'
    ada, bob = seeded
    for domain in ('zebra.test', 'alpha.test', 'middle.test'):
        assert create(api, ada, domain, domain).status_code == 202
    page = api.get('/dossiers', headers=auth(bob), params={'limit':2, 'offset':0, 'ignored':'yes'}).json()
    assert [x['domain'] for x in page['dossiers']] == ['alpha.test','middle.test']
    assert page['has_more'] is True
    page = api.get('/dossiers', headers=auth(bob), params={'limit':2,'offset':2}).json()
    assert [x['domain'] for x in page['dossiers']] == ['zebra.test'] and page['has_more'] is False
    page = api.get('/dossiers', headers=auth(bob), params={'q':'PHA'}).json()
    assert [x['domain'] for x in page['dossiers']] == ['alpha.test']
    empty = api.get('/dossiers', headers=auth(bob), params={'limit':'200', 'offset':'9'*100})
    assert empty.status_code == 200 and empty.json()['dossiers'] == [] and not empty.json()['has_more']
    assert api.get('/dossiers', headers=auth(bob), params={'limit':'001', 'offset':'000'}).status_code == 200


@pytest.mark.parametrize('offset,expected', [('0'*5000, 'first.test'), ('9'*5000, None)])
def test_R1_58_R1_61_R1_62_extreme_decimal_offset(api, seeded, offset, expected):
    """R1.58 R1.61 R1.62: arbitrarily large decimal offsets remain valid."""
    token = seeded[0]
    assert create(api, token, 'first.test', 'offset').status_code == 202
    response = api.get('/dossiers', headers=auth(token), params={'offset':offset})
    assert response.status_code == 200
    domains = [item['domain'] for item in response.json()['dossiers']]
    assert domains == ([] if expected is None else [expected])


@pytest.mark.parametrize('limit,valid', [
    ('0'*5000 + '1', True), ('0'*5000 + '200', True),
    ('0'*5000 + '201', False), ('9'*5000, False),
])
def test_R1_58_R1_61_R1_62_extreme_decimal_limit(api, seeded, limit, valid):
    """R1.58 R1.61 R1.62: arbitrarily long limits honor numeric bounds."""
    response = api.get('/dossiers', headers=auth(seeded[0]), params={'limit':limit})
    if valid:
        assert response.status_code == 200
    else:
        error(response, 422, 'validation_failed')


def test_R1_59_R1_60_R1_78_key_boundaries_and_failed_refresh_reuse(api, seeded):
    'R1.59 R1.60 R1.78'
    token = seeded[0]
    error(api.post('/dossiers/new.test/refresh', headers=auth(token, 'same')), 404, 'not_found')
    assert create(api, token, 'new.test', 'x'*255).status_code == 202
    refreshed = api.post('/dossiers/new.test/refresh', headers=auth(token, 'same'))
    assert refreshed.status_code == 202
    replay = api.post('/dossiers/new.test/refresh', headers=auth(token, 'same'))
    assert replay.status_code == 200 and replay.json() == refreshed.json()


def test_R1_2_R1_16_R1_17_R1_62_R1_80_R1_93_R1_129_concurrent_identical(direct_api, seeded):
    'R1.2 R1.16 R1.17 R1.62 R1.80 R1.93 R1.129'
    token = seeded[0]
    barrier = threading.Barrier(50)
    def one(_):
        with httpx.Client(base_url=direct_api.base_url, timeout=5, trust_env=False) as client:
            barrier.wait(timeout=5)
            start = time.monotonic()
            r = client.post('/dossiers', headers=auth(token,'burst'), json={'domain':'burst.test'})
            return r.status_code, r.json(), time.monotonic()-start
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as pool:
        results = list(pool.map(one, range(50)))
    assert [status for status, _, _ in results].count(202) == 1
    assert [status for status, _, _ in results].count(200) == 49
    assert all(body == results[0][1] for _, body, _ in results)
    assert max(duration for _, _, duration in results) < 5
    print(f'MEASURE 50_identical_writes_max={max(duration for _, _, duration in results):.3f}s')


def test_R1_14_container_memory_limit(deployment, seeded):
    'R1.14'
    reading = docker('stats', '--no-stream', '--format', '{{.MemUsage}}', deployment['container'], timeout=10).stdout.strip()
    used = reading.split('/')[0].strip()
    print(f'MEASURE container_memory={used}')
    units = {'B': 1, 'KiB': 1024, 'MiB': 1024**2, 'GiB': 1024**3}
    for suffix in sorted(units, key=len, reverse=True):
        if used.endswith(suffix):
            assert float(used[:-len(suffix)]) * units[suffix] <= 3 * 1024**3
            break
    else:
        pytest.fail(f'Unrecognized Docker memory usage: {used}')


def test_R1_16_R1_55_R1_62_R1_77_R1_80_R1_129_concurrent_conflicting(direct_api, seeded):
    'R1.16 R1.55 R1.62 R1.77 R1.80 R1.129'
    barrier = threading.Barrier(50)
    def one(i):
        with httpx.Client(base_url=direct_api.base_url, timeout=5, trust_env=False) as client:
            barrier.wait(timeout=5)
            start = time.monotonic()
            domain = 'conflict-a.test' if i % 2 else 'conflict-b.test'
            response = client.post('/dossiers', headers=auth(seeded[0], 'conflict'), json={'domain': domain})
            return domain, response.status_code, response.json(), time.monotonic() - start
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as pool:
        rows = list(pool.map(one, range(50)))
    winners = [(domain, body) for domain, status, body, _ in rows if status == 202]
    assert len(winners) == 1
    winner, original = winners[0]
    assert all((status == 200 and body == original) if domain == winner else
               (status == 409 and body['error']['code'] == 'idempotency_key_reuse')
               for domain, status, body, _ in rows if status != 202)
    assert max(row[3] for row in rows) < 5


def test_R1_16_R1_17_R1_62_R1_65_R1_69_R1_129_concurrent_signup(direct_api, seeded):
    'R1.16 R1.17 R1.62 R1.65 R1.69 R1.129'
    barrier = threading.Barrier(50)
    def one(_):
        with httpx.Client(base_url=direct_api.base_url, timeout=5, trust_env=False) as client:
            barrier.wait(timeout=5)
            start = time.monotonic()
            response = client.post('/auth/signup', json={
                'email': 'parallel@example.com', 'password': 'correct horse', 'display_name': 'Parallel'})
            return response.status_code, response.json(), time.monotonic() - start
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as pool:
        rows = list(pool.map(one, range(50)))
    assert sum(status == 201 for status, _, _ in rows) == 1
    assert sum(status == 409 and body['error']['code'] == 'email_taken' for status, body, _ in rows) == 49
    assert max(duration for _, _, duration in rows) < 5


def test_R1_16_R1_17_R1_62_R1_69_concurrent_logins(direct_api, seeded):
    'R1.16 R1.17 R1.62 R1.69'
    barrier = threading.Barrier(50)
    def one(_):
        with httpx.Client(base_url=direct_api.base_url, timeout=5, trust_env=False) as client:
            barrier.wait(timeout=5)
            start = time.monotonic()
            response = client.post('/auth/login', json={'email': 'ada@example.com', 'password': 'correct horse'})
            return response.status_code, response.json(), time.monotonic() - start
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as pool:
        rows = list(pool.map(one, range(50)))
    assert all(status == 200 and body['user_id'] == 'u_ada' and body['token'] for status, body, _ in rows)
    assert max(duration for _, _, duration in rows) < 5
    print(f'MEASURE 50_logins_max={max(duration for _, _, duration in rows):.3f}s')


def test_R1_16_R1_62_R1_93_R1_129_concurrent_different_keys(direct_api, seeded):
    'R1.16 R1.62 R1.93 R1.129'
    barrier = threading.Barrier(50)
    def one(i):
        with httpx.Client(base_url=direct_api.base_url, timeout=5, trust_env=False) as client:
            barrier.wait(timeout=5)
            start = time.monotonic()
            response = client.post('/dossiers', headers=auth(seeded[0], 'distinct-' + str(i)), json={'domain': 'same.test'})
            return response.status_code, response.json(), time.monotonic() - start
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as pool:
        rows = list(pool.map(one, range(50)))
    assert sum(status == 202 for status, _, _ in rows) == 1
    assert sum(status == 200 for status, _, _ in rows) == 49
    assert len({body['dossier_id'] for _, body, _ in rows}) == 1
    assert max(duration for _, _, duration in rows) < 5


def test_R1_81_R1_89_R1_101_R1_102_R1_103_refresh_and_replay(api, mock, seeded):
    'R1.81 R1.89 R1.101 R1.102 R1.103'
    token = seeded[0]
    first = create(api, token, 'ashgrove-solar.test', 'create')
    assert first.status_code == 202
    previous = done(api, token, 'ashgrove-solar.test')
    old_calls = mock.get('/_mock/log').json()['calls']
    assert api.post('/_test/clock', json={'now': '2026-03-02T00:00:00+00:00'}).status_code == 204
    refreshed = api.post('/dossiers/ashgrove-solar.test/refresh', headers=auth(token, 'refresh'))
    assert refreshed.status_code == 202 and refreshed.json()['state'] == 'building'
    new = done(api, token, 'ashgrove-solar.test')
    calls = mock.get('/_mock/log').json()['calls']
    assert len(calls) > len(old_calls)
    assert new['spent_units'] == sum(c['cost'] for c in calls)
    assert new['spent_units'] >= previous['spent_units']
    assert datetime.datetime.fromisoformat(new['researched_at']) == datetime.datetime.fromisoformat('2026-03-02T00:00:00+00:00')
    replay = create(api, token, 'ashgrove-solar.test', 'create')
    assert replay.status_code == 200 and replay.json() == first.json()
    assert mock.get('/_mock/log').json()['calls'] == calls
