"""Foundation checks that do not require the later dossier routes."""
import time
import copy
import json
import socket
import threading
import http.client
from urllib.parse import urlsplit

import pytest

from test_api import auth, create, done, error


def test_R1_23_R1_48_R1_63_R1_66_seed_and_reset(api, seeded):
    'R1.23 R1.48 R1.63 R1.66'
    duplicate = {'now': '2026-03-02T00:00:00+00:00', 'users': [
        {'id': 'a', 'email': 'duplicate@example.com', 'password': 'correct horse', 'display_name': 'A'},
        {'id': 'b', 'email': 'DUPLICATE@example.com', 'password': 'correct horse', 'display_name': 'B'}]}
    error(api.post('/_test/reset', json=duplicate, timeout=10), 422, 'validation_failed')
    login = api.post('/auth/login', json={'email':'ADA@example.com', 'password':'correct horse'})
    assert login.status_code == 200 and login.json()['user_id'] == 'u_ada'
    assert api.post('/_test/reset', json={'now':'2026-03-02T00:00:00+00:00','users':[]}, timeout=10).status_code == 204
    error(api.post('/auth/login', json={'email':'ada@example.com', 'password':'correct horse'}), 401, 'unauthenticated')


def test_R1_24_R1_25_R1_27_R1_28_clock_public_and_monotonic(api, seeded):
    'R1.24 R1.25 R1.27 R1.28'
    assert api.post('/_test/clock', json={'now':'2026-03-01T09:00:00+00:00'}).status_code == 204
    assert api.post('/_test/clock', json={'now':'2026-03-01T10:00:00+00:00'}).status_code == 204
    error(api.post('/_test/clock', json={'now':'2026-03-01T09:59:59+00:00'}), 422, 'validation_failed')
    error(api.post('/_test/clock', json={'now':'2026-03-01T11:00:00'}), 422, 'validation_failed')
    error(api.post('/_test/clock', json={'now':1}), 400, 'malformed_request')
    assert api.post('/_test/clock', json={'now':'2026-03-01T11:00:00+01:00'}).status_code == 204


def test_R1_70_R1_124_R1_125_R1_126_R1_127_foundation_snapshot(api, seeded):
    'R1.70 R1.124 R1.125 R1.126 R1.127'
    exported = api.get('/_test/export', timeout=10)
    assert exported.status_code == 200
    snapshot = exported.json()
    assert snapshot['track'] == 'dossier' and snapshot['format_version'] == 1 and isinstance(snapshot['state'], dict)
    assert 'correct horse' not in exported.text
    assert api.post('/_test/reset', json={'now':'2026-04-01T00:00:00+00:00','users':[]}, timeout=10).status_code == 204
    imported = api.post('/_test/import', json=snapshot, timeout=10)
    assert imported.status_code == 204
    login = api.post('/auth/login', json={'email':'ada@example.com','password':'correct horse'})
    assert login.status_code == 200 and login.json()['user_id'] == 'u_ada'
    assert api.post('/_test/import', json=snapshot, timeout=10).status_code == 204
    error(api.post('/_test/clock', json={'now':'2026-03-02T00:00:00+00:00'}), 422, 'validation_failed')


def test_R1_49_R1_50_R1_54_error_envelope_unknown_route(api, seeded):
    'R1.49 R1.50 R1.54'
    error(api.get('/no-such-route', headers=auth(seeded[0])), 404, 'not_found')


def test_R1_23_R1_34_R1_48_R1_66_fixture_values_and_import(api, seeded):
    'R1.23 R1.34 R1.48 R1.66'
    fixture = {'now':'2026-01-01T00:00:00+00:00', 'users': [
        {'id':'x'*64, 'email':'no-at-sign', 'password':'', 'display_name':''},
        {'id':'u2', 'email':'another invalid email', 'password':'abc', 'display_name':'N'*101}]}
    assert api.post('/_test/reset', json=fixture, timeout=10).status_code == 204
    for user in fixture['users']:
        login = api.post('/auth/login', json={'email':user['email'],'password':user['password']})
        assert login.status_code == 200 and login.json()['user_id'] == user['id']
        error(api.post('/auth/login', json={'email':user['email'],'password':user['password']+'wrong'}), 401, 'unauthenticated')
    snapshot = api.get('/_test/export', timeout=10).json()
    assert api.post('/_test/reset', json={'now':'2026-01-02T00:00:00+00:00','users':[]}, timeout=10).status_code == 204
    assert api.post('/_test/import', json=snapshot, timeout=10).status_code == 204
    for user in fixture['users']:
        login = api.post('/auth/login', json={'email':user['email'],'password':user['password']})
        assert login.status_code == 200 and login.json()['user_id'] == user['id']


@pytest.mark.parametrize('changes,status,code', [
    ({'id':''}, 422, 'validation_failed'),
    ({'id':'x'*65}, 422, 'validation_failed'),
    ({'id':7}, 400, 'malformed_request'),
    ({'email':None}, 400, 'malformed_request'),
    ({'password':[]}, 400, 'malformed_request'),
    ({'display_name':False}, 400, 'malformed_request'),
])
def test_R1_23_R1_33_R1_48_fixture_validation_atomic(api, seeded, changes, status, code):
    'R1.23 R1.33 R1.48'
    user = {'id':'test', 'email':'not-email', 'password':'', 'display_name':''}
    user.update(changes)
    error(api.post('/_test/reset', json={'now':'2026-01-01T00:00:00+00:00','users':[user]}, timeout=10), status, code)
    login = api.post('/auth/login', json={'email':'ada@example.com','password':'correct horse'})
    assert login.status_code == 200 and login.json()['user_id'] == 'u_ada'


@pytest.mark.parametrize('missing', ['id', 'email', 'password', 'display_name'])
def test_R1_23_R1_48_missing_fixture_field(api, seeded, missing):
    """R1.23 R1.48: missing fixture user fields yield 422 and preserve state."""
    user = {'id':'test', 'email':'fixture', 'password':'', 'display_name':''}
    del user[missing]
    error(api.post('/_test/reset', json={'now':'2026-01-01T00:00:00+00:00','users':[user]}, timeout=10), 422, 'validation_failed')
    assert api.post('/auth/login', json={'email':'ada@example.com','password':'correct horse'}).status_code == 200


def test_R1_23_R1_48_fixture_duplicate_ids_atomic(api, seeded):
    'R1.23 R1.48'
    first = {'id':'same', 'email':'first', 'password':'', 'display_name':''}
    second = {'id':'same', 'email':'second', 'password':'', 'display_name':''}
    error(api.post('/_test/reset', json={'now':'2026-01-01T00:00:00+00:00','users':[first,second]}, timeout=10), 422, 'validation_failed')
    assert api.post('/auth/login', json={'email':'ada@example.com','password':'correct horse'}).status_code == 200


def test_R1_23_R1_25_reset_can_move_clock_backwards(api, seeded):
    'R1.23 R1.25'
    assert api.post('/_test/clock', json={'now':'2026-04-01T00:00:00+00:00'}).status_code == 204
    assert api.post('/_test/reset', json={'now':'2020-01-01T00:00:00+00:00'}, timeout=10).status_code == 204
    assert api.post('/_test/clock', json={'now':'2020-01-02T00:00:00+00:00'}).status_code == 204


def test_R1_17_R1_23_R1_48_500_seeded_users(api, seeded):
    'R1.17 R1.23 R1.48'
    users = [{'id':f'u{i}', 'email':f'user{i}@fixture.test', 'password':'fixture password',
              'display_name':f'User {i}'} for i in range(500)]
    start = time.monotonic()
    result = api.post('/_test/reset', json={'now':'2026-03-01T00:00:00+00:00','users':users}, timeout=10)
    elapsed = time.monotonic() - start
    assert result.status_code == 204
    assert elapsed <= 5, f'500-user reset took {elapsed:.3f}s'
    print(f'MEASURE reset_500_users={elapsed:.3f}s')
    for user in (users[0], users[249], users[-1]):
        response = api.post('/auth/login', json={'email':user['email'],'password':user['password']})
        assert response.status_code == 200 and response.json()['user_id'] == user['id']


def test_R1_27_fractional_clock_precision(api, seeded):
    'R1.27'
    assert api.post('/_test/clock', json={'now':'2026-03-01T10:00:00.123456789+00:00'}).status_code == 204
    error(api.post('/_test/clock', json={'now':'2026-03-01T10:00:00.123456788+00:00'}), 422, 'validation_failed')
    assert api.post('/_test/clock', json={'now':'2026-03-01T10:00:00.123456790+00:00'}).status_code == 204


def test_R1_25_R1_27_RL26_leap_seconds(api, seeded):
    """R1.25 R1.27: leap seconds are accepted only at 23:59:60 UTC and ordered."""
    assert api.post('/_test/reset', json={'now':'2016-12-31T23:59:59Z', 'users':[]}, timeout=10).status_code == 204
    assert api.post('/_test/clock', json={'now':'2016-12-31T18:59:60-05:00'}).status_code == 204
    error(api.post('/_test/clock', json={'now':'2016-12-31T23:59:59.999999999Z'}), 422, 'validation_failed')
    assert api.post('/_test/clock', json={'now':'2017-01-01T00:00:00Z'}).status_code == 204
    assert api.post('/_test/reset', json={'now':'2016-12-31T23:59:60Z', 'users':[]}, timeout=10).status_code == 204
    for timestamp in ('2016-12-31T12:00:60Z', '2016-12-31T23:59:61Z'):
        error(api.post('/_test/clock', json={'now':timestamp}), 422, 'validation_failed')


def test_R1_25_R1_27_RL27_last_year_leap_second_is_out_of_range(api, mock):
    """R1.25 R1.27 RL27: the final year's leap second exceeds the UTC range."""
    fixture = {'now':'2026-03-01T09:00:00Z', 'users': [{'id':'u', 'email':'seed@example.com',
               'password':'correct horse', 'display_name':'Seed'}]}
    assert api.post('/_test/reset', json=fixture, timeout=10).status_code == 204
    response = api.post('/_test/reset', json={'now':'9999-12-31T23:59:60Z', 'users':[]}, timeout=10)
    error(response, 422, 'validation_failed')
    login = api.post('/auth/login', json={'email':'seed@example.com', 'password':'correct horse'})
    assert login.status_code == 200 and login.json()['user_id'] == 'u'


@pytest.mark.parametrize('digits', [10, 11, 30, 1000])
def test_R1_25_R1_27_RL18_fraction_comparison_exact_through_1000_digits(api, mock, digits):
    """R1.25 R1.27 RL18: compare full RFC3339 fractions without truncation."""
    prefix = '2026-03-01T10:00:00.' + ('1' * (digits - 1))
    assert api.post('/_test/reset', json={'now':prefix + '1Z', 'users':[]}, timeout=10).status_code == 204
    error(api.post('/_test/clock', json={'now':prefix + '0Z'}), 422, 'validation_failed')
    assert api.post('/_test/clock', json={'now':prefix + '2Z'}).status_code == 204


@pytest.mark.parametrize('timestamp', [
    '0001-01-02T00:00:00+23:59',
    '9999-12-30T23:59:59-23:59',
])
def test_R1_25_R1_27_R1_85_R1_96_RL27_boundary_offset_build_completes(api, mock, timestamp):
    """R1.25 R1.27 R1.85 R1.96 RL27: representable boundary offsets do not strand builds."""
    fixture = {'now': timestamp, 'users': [{'id':'u', 'email':'seed@example.com',
               'password':'correct horse', 'display_name':'Seed'}]}
    assert api.post('/_test/reset', json=fixture, timeout=10).status_code == 204
    login = api.post('/auth/login', json={'email':'seed@example.com', 'password':'correct horse'})
    assert login.status_code == 200
    token = login.json()['token']
    assert create(api, token, 'ashgrove-solar.test', 'boundary-clock').status_code == 202
    dossier = done(api, token, 'ashgrove-solar.test')
    assert dossier['state'] == 'ready' and dossier['researched_at'] is not None
    assert any(call['status'] == 200 for call in mock.get('/_mock/log').json()['calls'])


@pytest.mark.parametrize('timestamp', [
    '0001-01-01T00:00:00+23:59',
    '9999-12-31T23:59:59-23:59',
])
def test_R1_25_R1_27_RL27_unrepresentable_utc_offset_rejected_atomically(api, mock, timestamp):
    """R1.25 R1.27 RL27: UTC-out-of-range instants are 422 and change nothing."""
    fixture = {'now':'2026-03-01T09:00:00Z', 'users': [{'id':'u_ada', 'email':'ada@example.com',
               'password':'correct horse', 'display_name':'Ada'}]}
    assert api.post('/_test/reset', json=fixture, timeout=10).status_code == 204
    response = api.post('/_test/reset', json={'now':timestamp, 'users':[]}, timeout=10)
    error(response, 422, 'validation_failed')
    login = api.post('/auth/login', json={'email':'ada@example.com', 'password':'correct horse'})
    assert login.status_code == 200 and login.json()['user_id'] == 'u_ada'


def test_R1_33_R1_125_R1_126_RL20_max_counter_export_after_signup_round_trips(api, mock):
    """R1.33 R1.125 R1.126: a valid max counter followed by signup exports importably."""
    assert api.post('/_test/reset', json={'now':'2026-03-01T09:00:00Z', 'users':[]}, timeout=10).status_code == 204
    snapshot = api.get('/_test/export', timeout=10).json()
    snapshot['state']['counters']['user'] = 10**12
    imported = api.post('/_test/import', json=snapshot, timeout=10)
    assert imported.status_code == 204
    signup = api.post('/auth/signup', json={'email':'rollover@example.com',
                      'password':'correct horse', 'display_name':'Rollover'})
    assert signup.status_code == 201 and len(signup.json()['user_id']) <= 64
    exported = api.get('/_test/export', timeout=10).json()
    imported = api.post('/_test/import', json=exported, timeout=10)
    assert imported.status_code == 204
    assert api.post('/auth/login', json={'email':'rollover@example.com',
                    'password':'correct horse'}).status_code == 200


@pytest.mark.parametrize('parameters', [(262144, 8, 16), (16384, 8, 1), (1024, 16, 1), (1024, 8, 2)])
def test_R1_17_R1_70_R1_126_RL27_import_rejects_other_scrypt_parameters(api, mock, parameters):
    """R1.17 R1.70 R1.126 RL27: import accepts only service-issued scrypt parameters."""
    fixture = {'now':'2026-03-01T09:00:00Z', 'users': [{'id':'u_ada', 'email':'ada@example.com',
               'password':'correct horse', 'display_name':'Ada'}]}
    assert api.post('/_test/reset', json=fixture, timeout=10).status_code == 204
    original = api.get('/_test/export', timeout=10).json()
    altered = copy.deepcopy(original)
    user = next(user for user in altered['state']['users'] if user['id'] == 'u_ada')
    parts = user['password_hash'].split('$')
    assert len(parts) == 6
    parts[1:4] = map(str, parameters)
    user['password_hash'] = '$'.join(parts)
    response = api.post('/_test/import', json=altered, timeout=10)
    error(response, 422, 'validation_failed')
    if api.get('/_test/export', timeout=10).json() != original:
        pytest.fail('invalid import changed the destination state')


@pytest.mark.parametrize('timestamp', [
    '2027-01-01T00:00:00+00:60', '2027-01-01T00:00:00+24:00',
    '2027-01-01T00:00:00-05:99', '2027-02-30T00:00:00+00:00'])
def test_R1_27_invalid_rfc3339_offsets(api, seeded, timestamp):
    'R1.27'
    error(api.post('/_test/clock', json={'now':timestamp}), 422, 'validation_failed')


def test_R1_25_R1_27_long_fractional_timestamp(api, seeded):
    'R1.25 R1.27'
    assert api.post('/_test/reset', json={'now':'2026-03-01T10:00:00.12345678901+00:00','users':[]}, timeout=10).status_code == 204
    error(api.post('/_test/clock', json={'now':'2026-03-01T10:00:00.12345678900+00:00'}), 422, 'validation_failed')


def test_R1_17_R1_23_R1_31_body_size_boundary(api, direct_api, seeded):
    'R1.17 R1.23 R1.31'
    limit = 16 * 1024 * 1024
    prefix = b'{"now":"2026-03-01T09:00:00+00:00","ignored":"'
    suffix = b'","users":[]}'
    payload = prefix + b'x' * (limit - len(prefix) - len(suffix)) + suffix
    assert len(payload) == limit
    accepted = direct_api.post('/_test/reset', content=payload, headers={'Content-Type':'application/json'}, timeout=10)
    assert accepted.status_code == 204
    assert api.post('/auth/signup', json={'email':'after@example.com', 'password':'correct horse',
                                        'display_name':'After'}).status_code == 201
    rejected = direct_api.post('/_test/reset', content=payload[:-len(suffix)] + b'x' + suffix,
                               headers={'Content-Type':'application/json'}, timeout=10)
    error(rejected, 413, 'payload_too_large')
    assert api.post('/auth/login', json={'email':'after@example.com','password':'correct horse'}).status_code == 200


@pytest.mark.parametrize('route', ['/_test/reset', '/auth/signup', '/dossiers', '/_test/import'])
@pytest.mark.parametrize('framing', ['length', 'chunked'])
def test_R1_31_R1_49_RL28_oversize_body_has_413_envelope(direct_api, seeded, route, framing):
    """R1.31 R1.49 RL28: each POST route delivers a 413 for oversized streamed bodies."""
    limit = 16 * 1024 * 1024
    def payload():
        for _ in range(limit // 65536):
            yield b'x' * 65536
        yield b'x'
    headers = {'Content-Type':'application/json', **auth(seeded[0], 'oversize')}
    if framing == 'length':
        headers['Content-Length'] = str(limit + 1)
    response = direct_api.post(route, content=payload(), headers=headers, timeout=15)
    error(response, 413, 'payload_too_large')


def test_R1_31_RL28_small_chunked_body_is_parsed(direct_api, mock):
    """R1.31 RL28: a valid chunked reset is parsed under the size limit."""
    chunks = iter([b'{"now":"2026-03-01T09:00:00Z",', b'"users":[]}'])
    response = direct_api.post('/_test/reset', content=chunks, headers={'Content-Type':'application/json'}, timeout=10)
    assert response.status_code == 204


def chunked_socket_request(direct_api, body):
    endpoint = urlsplit(str(direct_api.base_url))
    with socket.create_connection((endpoint.hostname, endpoint.port), timeout=10) as conn:
        conn.settimeout(10)
        conn.sendall(b'POST /_test/reset HTTP/1.1\r\nHost: localhost\r\n'
                     b'Content-Type: application/json\r\nTransfer-Encoding: chunked\r\n'
                     b'Connection: close\r\n\r\n' + body)
        conn.shutdown(socket.SHUT_WR)
        response = http.client.HTTPResponse(conn)
        response.begin()
        return response.status, response.read()


@pytest.mark.parametrize('body', [
    b'+1\r\nx\r\n0\r\n\r\n',
    b'0x1\r\nx\r\n0\r\n\r\n',
    b'1_0\r\n' + b'x' * 16 + b'\r\n0\r\n\r\n',
    b'1\r\nx!!0\r\n\r\n',
    b'0',
    b'0\r\n',
    b'0\r\ninvalid-trailer\r\n\r\n',
], ids=['plus', 'hex-prefix', 'underscore', 'bad-data-crlf', 'eof-after-zero',
        'missing-final-crlf', 'invalid-trailer'])
def test_R1_31_R1_49_RL49_malformed_chunk_framing_is_atomic(api, direct_api, seeded, body):
    """R1.31 R1.49 RL49: malformed chunk frames are 400 and leave state unchanged."""
    snapshot = api.get('/_test/export', timeout=10).json()
    status, payload = chunked_socket_request(direct_api, body)
    assert status == 400
    envelope = json.loads(payload)
    assert envelope['error']['code'] == 'malformed_request'
    assert isinstance(envelope['error']['message'], str)
    if api.get('/_test/export', timeout=10).json() != snapshot:
        pytest.fail('malformed chunk changed the destination state')
    assert direct_api.get('/health').status_code == 200


def test_R1_31_RL49_chunk_extension_and_trailer_are_parsed(direct_api, mock):
    """R1.31 RL49: valid chunk extensions and trailers are accepted."""
    body = b'{"now":"2026-03-01T09:00:00Z","users":[]}'
    framed = f'{len(body):x};probe=ok\r\n'.encode() + body + b'\r\n0\r\nX-Probe: accepted\r\n\r\n'
    status, _ = chunked_socket_request(direct_api, framed)
    assert status == 204
    assert direct_api.get('/health').status_code == 200


def test_R1_31_R1_49_RL42_unframed_request_has_no_body_and_service_stays_healthy(direct_api, mock):
    """R1.31 R1.49 RL42: without framing headers there is no body and no server error."""
    endpoint = urlsplit(str(direct_api.base_url))
    with socket.create_connection((endpoint.hostname, endpoint.port), timeout=15) as conn:
        conn.settimeout(15)
        conn.sendall(b'POST /_test/reset HTTP/1.0\r\nHost: localhost\r\nContent-Type: application/json\r\n\r\n')
        sent = []
        def upload():
            count = 0
            try:
                for _ in range(256):
                    conn.sendall(b'x' * 65536)
                    count += 65536
                conn.sendall(b'x')
                count += 1
                conn.shutdown(socket.SHUT_WR)
            except OSError:
                pass
            sent.append(count)
        writer = threading.Thread(target=upload, daemon=True)
        writer.start()
        response = http.client.HTTPResponse(conn)
        response.begin()
        body = response.read()
        writer.join(timeout=15)
        assert not writer.is_alive()
        assert response.status in (400, 422)
        assert json.loads(body)['error']['code'] in ('malformed_request', 'validation_failed')
    assert direct_api.get('/health').status_code == 200


def test_R1_31_R1_49_RL30_keepalive_recovers_after_oversize(direct_api, mock):
    """R1.31 R1.49 RL30: reuse a client after a 413, reconnecting if the server closes."""
    endpoint = urlsplit(str(direct_api.base_url))
    conn = http.client.HTTPConnection(endpoint.hostname, endpoint.port, timeout=15)
    try:
        for _ in range(2):
            conn.request('GET', '/health')
            response = conn.getresponse()
            assert response.status == 200
            response.read()
        conn.request('POST', '/_test/reset', body=b'x' * (16 * 1024 * 1024 + 1),
                     headers={'Content-Type':'application/json'})
        response = conn.getresponse()
        assert response.status == 413
        assert json.loads(response.read())['error']['code'] == 'payload_too_large'
        try:
            conn.request('GET', '/health')
            response = conn.getresponse()
        except (http.client.RemoteDisconnected, BrokenPipeError, ConnectionResetError):
            # RL30 expressly permits the server to close after the 413.
            conn.close()
            conn.request('GET', '/health')
            response = conn.getresponse()
        assert response.status == 200
        response.read()
    finally:
        conn.close()


def test_R1_31_R1_62_R1_64_R1_127_surrogate_round_trip(api, seeded):
    'R1.31 R1.62 R1.64 R1.127'
    display = '\ud800'
    body = json.dumps({'email':'surrogate@example.com','password':'correct horse','display_name':display}, ensure_ascii=True).encode('ascii')
    response = api.post('/auth/signup', content=body, headers={'Content-Type':'application/json'})
    assert response.status_code == 201 and response.json()['display_name'] == display
    snapshot = api.get('/_test/export', timeout=10).json()
    assert api.post('/_test/reset', json={'now':'2026-03-02T00:00:00+00:00','users':[]}, timeout=10).status_code == 204
    encoded = json.dumps(snapshot, ensure_ascii=True).encode('ascii')
    assert api.post('/_test/import', content=encoded, headers={'Content-Type':'application/json'}, timeout=10).status_code == 204
    login = api.post('/auth/login', json={'email':'surrogate@example.com','password':'correct horse'})
    assert login.status_code == 200 and login.json()['display_name'] == display


def test_R1_62_R1_107_surrogate_query_does_not_fail(api, seeded):
    'R1.62 R1.107'
    response = api.get('/dossiers?q=%ED%A0%80', headers=auth(seeded[0]))
    assert response.status_code == 200 and isinstance(response.json()['dossiers'], list)


def test_R1_126_missing_export_sections_rejected_atomically(api, seeded):
    'R1.126'
    exported = api.get('/_test/export', timeout=10).json()
    assert isinstance(exported['state'], dict) and exported['state']
    for section in exported['state']:
        modified = copy.deepcopy(exported)
        del modified['state'][section]
        response = api.post('/_test/import', json=modified, timeout=10)
        assert response.status_code == 422, f'missing state section {section!r}: {response.status_code}'
        error(response, 422, 'validation_failed')
        login = api.post('/auth/login', json={'email':'ada@example.com','password':'correct horse'})
        assert login.status_code == 200 and login.json()['user_id'] == 'u_ada'
    error(api.post('/_test/import', json=[]), 400, 'malformed_request')


@pytest.mark.parametrize('corruption', ['token_reference', 'counter_high', 'counter_low', 'password_record', 'duplicate_ids'])
def test_R1_70_R1_126_R1_127_invalid_snapshot_entries_are_atomic(api, seeded, corruption):
    """R1.70 R1.126 R1.127: reject malformed entries without replacing credentials."""
    if corruption in ('counter_high', 'counter_low'):
        response = api.post('/auth/signup', json={'email':'counter@example.com', 'password':'correct horse', 'display_name':'Counter'})
        assert response.status_code == 201
    snapshot = api.get('/_test/export', timeout=10).json()
    state = snapshot['state']
    if corruption == 'token_reference':
        entries = state['tokens']
        assert isinstance(entries, list) and entries and isinstance(entries[0], dict) and 'user_id' in entries[0]
        entries[0]['user_id'] = 'nonexistent-prover-user'
    elif corruption in ('counter_high', 'counter_low'):
        counters = state['counters']
        assert isinstance(counters, dict)
        numeric_keys = [key for key, value in counters.items() if type(value) is int and value > 0]
        assert numeric_keys
        counters[numeric_keys[0]] = 10**40 if corruption == 'counter_high' else 0
    elif corruption == 'password_record':
        users = state['users']
        assert isinstance(users, list) and users and isinstance(users[0], dict) and 'password_hash' in users[0]
        users[0]['password_hash'] = 'malformed-scrypt-record'
    else:
        users = state['users']
        assert isinstance(users, list) and users
        duplicate = copy.deepcopy(users[0])
        duplicate['email'] = 'distinct-duplicate@example.com'
        users.append(duplicate)
    error(api.post('/_test/import', json=snapshot, timeout=10), 422, 'validation_failed')
    login = api.post('/auth/login', json={'email':'ada@example.com','password':'correct horse'})
    assert login.status_code == 200 and login.json()['user_id'] == 'u_ada'
    assert api.get('/dossiers', headers=auth(seeded[0])).status_code == 200
