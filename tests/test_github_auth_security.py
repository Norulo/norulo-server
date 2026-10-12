"""Browser binding, hashed credentials and native admission; local fixtures only."""
import asyncio
import json
import sqlite3
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest

from ledger_d1_fixture import D1ShapedSQLite, seed, seed_auth
from test_cloudflare_github_identity_http import (
    D1ShapedSQLite as IdentityD1, GitHubStub, call, seed as identity_seed,
)
from norulo_server.cloudflare_auth_admission import authorize_admission
from norulo_server.cloudflare_github_identity_http import _session_user
from norulo_server.cloudflare_ledger_api import _write_guard
from norulo_server.cloudflare_principal import PrincipalAuthError, _principal, _resource_auth_snapshot
from norulo_server.cloudflare_session_adapter import D1SessionTransactions, session_storage_id
from norulo_server.cloudflare_state_records import record_name


def authorize(binding, gateway, now, **params):
    status, payload, headers = call(binding, gateway, now, 'GET', '/auth/github/authorize', params)
    assert status in {200, 302}
    state = parse_qs(urlsplit(payload.get('url', payload.get('location'))).query)['state'][0]
    return state, headers['Set-Cookie'].split(';', 1)[0]


@pytest.mark.parametrize('response', ['', 'redirect'])
@pytest.mark.parametrize('browser', ['absent', 'other_flow', 'ambiguous', 'unicode'])
def test_login_callback_requires_original_browser_before_consumption_or_provider(tmp_path, response, browser):
    fixture, _, _ = identity_seed(tmp_path / 'binding.sqlite')
    binding = IdentityD1(fixture.store)
    class CountProvider(GitHubStub):
        calls = 0
        async def exchange(self, *args):
            self.calls += 1
            return await super().exchange(*args)
    gateway = CountProvider()
    state, cookie = authorize(binding, gateway, fixture.now, response=response)
    _, second_cookie = authorize(binding, gateway, fixture.now + 1)
    supplied = {'absent': '', 'other_flow': second_cookie,
                'ambiguous': cookie + '; ' + second_cookie,
                'unicode': 'nr_github_oauth=' + '中' * 64}[browser]
    with fixture.store.connect() as db:
        before = list(db.iterdump())
    result = call(binding, gateway, fixture.now + 2, 'GET', '/auth/github/callback',
                  {'state': state, 'code': 'synthetic-code'}, {'Cookie': supplied})
    assert result[0:2] == (400, {'error': {'code': 'OAUTH_STATE_INVALID'}})
    assert gateway.calls == 0 and 'Set-Cookie' not in result[2]
    with fixture.store.connect() as db:
        assert list(db.iterdump()) == before
    status, _, headers = call(binding, gateway, fixture.now + 3, 'GET', '/auth/github/callback',
                             {'state': state, 'code': 'synthetic-code'}, {'Cookie': cookie})
    assert status == 302 and gateway.calls == 1
    assert headers['Set-Cookie'][0].startswith('nr_session=ses-')
    assert headers['Set-Cookie'][1].startswith('nr_github_oauth=;')
    assert call(binding, gateway, fixture.now + 4, 'GET', '/auth/github/callback',
                {'state': state, 'code': 'synthetic-code'}, {'Cookie': cookie})[0] == 400
    assert gateway.calls == 1


def test_new_hashed_session_is_usable_revocable_and_fingerprint_is_not_a_credential(tmp_path):
    fixture, _, _ = seed(tmp_path / 'sessions.sqlite')
    raw = D1ShapedSQLite(fixture.store)
    params_seen = []
    prepare = raw.prepare
    def record_prepare(sql):
        statement = prepare(sql)
        bind = statement.bind
        def record_bind(*params):
            params_seen.extend(params)
            return bind(*params)
        statement.bind = record_bind
        return statement
    raw.prepare = record_prepare
    adapter = D1SessionTransactions(raw)
    token = 'ses-v2.synthetic-secret-bearer'
    identity = session_storage_id(token)
    asyncio.run(adapter.issue_session(owner_id='owner', session_id=token,
        now=fixture.now, expires_at=fixture.now + 3600))
    with fixture.store.connect() as db:
        dump = '\n'.join(db.iterdump())
        assert token not in dump and identity in dump
        session = json.loads(db.execute('SELECT payload FROM app_state WHERE name=?',
            (record_name('sessions', identity),)).fetchone()[0])
    assert session['id'] == identity
    headers = {'Cookie': 'nr_session=' + token}
    user, _ = asyncio.run(_principal(raw, headers, scope='profile:read', now=fixture.now))
    assert asyncio.run(_session_user(raw, headers, fixture.now))[0]['id'] == token
    proof = {}
    statements, validate = _resource_auth_snapshot(raw, headers, user, {}, fixture.now, 'profile:read', proof)
    validate([part.results for part in asyncio.run(raw.batch(statements))])
    assert proof['session_id'] == token and proof['session_record_id'] == identity
    for unauthorized in ({'Cookie': 'nr_session=' + identity}, {'Authorization': 'Bearer ' + identity}):
        with pytest.raises(PrincipalAuthError):
            asyncio.run(_principal(raw, unauthorized, scope='profile:read', now=fixture.now))
        assert asyncio.run(_session_user(raw, unauthorized, fixture.now)) == (None, None)
    assert asyncio.run(adapter.revoke_session(owner_id='owner', session_id=token, now=fixture.now)) is True
    with pytest.raises(sqlite3.IntegrityError):
        asyncio.run(raw.batch([_write_guard(raw, proof, 'owner', fixture.now),
                              raw.prepare('DELETE FROM d1_command_guard')]))
    with pytest.raises(PrincipalAuthError):
        asyncio.run(_principal(raw, headers, scope='profile:read', now=fixture.now))
    assert token not in json.dumps(params_seen)


def test_github_link_and_install_pending_records_only_keep_session_fingerprint(tmp_path):
    fixture, _, _ = identity_seed(tmp_path / 'pending.sqlite')
    binding, gateway = IdentityD1(fixture.store), GitHubStub()
    state, browser_cookie = authorize(binding, gateway, fixture.now)
    status, _, headers = call(binding, gateway, fixture.now + 1, 'GET', '/auth/github/callback',
        {'state': state, 'code': 'synthetic-code'}, {'Cookie': browser_cookie})
    assert status == 302
    cookie = headers['Set-Cookie'][0].split(';', 1)[0]
    token = cookie.split('=', 1)[1]
    auth_headers = {'Cookie': cookie, 'Origin': 'https://app.example.test'}
    for path, params in (('/auth/github/authorize', {'intent': 'link'}),
                         ('/integrations/github/authorize', {})):
        assert call(binding, gateway, fixture.now + 2, 'GET', path, params, auth_headers)[0] == 200
    with fixture.store.connect() as db:
        dump = '\n'.join(db.iterdump())
        assert token not in dump
        rows = db.execute("SELECT payload FROM app_state WHERE name GLOB 'record:githubStates:*'").fetchall()
    assert len(rows) == 2
    assert all(json.loads(row[0])['sessionId'] == session_storage_id(token) for row in rows)


def test_email_login_and_link_challenge_keep_no_new_bearer_in_sql_or_storage(tmp_path):
    import test_cloudflare_email_auth as email
    runtime = SimpleNamespace(binding=email.Binding(email.Store(tmp_path / 'email.sqlite')),
                              gateway=email.Gateway(), admit=email.Admission())
    issued = email.request(runtime)
    status, _, headers = email.verify(runtime, issued)
    assert status == 200
    cookie = headers['Set-Cookie'].split(';', 1)[0]
    token = cookie.split('=', 1)[1]
    assert token.startswith('ses-v2.')
    email.request(runtime, purpose='link', cookie=cookie, now=email.NOW + 62)
    with runtime.binding.store.connect() as db:
        dump = '\n'.join(db.iterdump())
    assert token not in dump
    assert email.records(runtime, 'emailChallenges')[0]['sessionId'] == session_storage_id(token)


def test_legacy_session_remains_read_only_compatible_and_expires_exclusively(tmp_path):
    fixture, _, _ = seed(tmp_path / 'legacy.sqlite')
    seed_auth(fixture, session_expires=fixture.now + 1)
    raw = D1ShapedSQLite(fixture.store)
    with fixture.store.connect() as db:
        before = list(db.iterdump())
    headers = {'Cookie': 'nr_session=session-local'}
    assert asyncio.run(_principal(raw, headers, scope='profile:read', now=fixture.now))[0]['id'] == 'owner'
    assert asyncio.run(_session_user(raw, headers, fixture.now))[0]['id'] == 'session-local'
    with pytest.raises(PrincipalAuthError):
        asyncio.run(_principal(raw, headers, scope='profile:read', now=fixture.now + 1))
    assert asyncio.run(_session_user(raw, headers, fixture.now + 1)) == (None, None)
    with fixture.store.connect() as db:
        assert list(db.iterdump()) == before


class NativeLimit:
    def __init__(self, result=True, failure=False):
        self.result, self.failure, self.keys = result, failure, []
    async def limit(self, options):
        self.keys.append(options['key'])
        if self.failure:
            raise RuntimeError('synthetic secret must not escape')
        return {'success': self.result}


@pytest.mark.parametrize('result,status', [(True, None), (False, 429), (None, 503), ('true', 503)])
def test_production_auth_native_admission_requires_definite_success(result, status):
    limit = NativeLimit(result)
    env = SimpleNamespace(NORULO_MODE='production', AUTH_RATE_LIMIT=limit)
    request = SimpleNamespace(headers={'cf-connecting-ip': '2001:db8:1234:5678::1'})
    decision = asyncio.run(authorize_admission(env, request))
    assert (decision[0] if decision else None) == status
    assert len(limit.keys) == 1 and len(limit.keys[0]) == 64


def test_native_admission_ipv6_prefix_and_fail_closed_missing_or_unknown_binding():
    limit = NativeLimit()
    env = SimpleNamespace(NORULO_MODE='production', AUTH_RATE_LIMIT=limit)
    for address in ('2001:db8:1234:5678::1', '2001:db8:1234:5678:ffff::2'):
        assert asyncio.run(authorize_admission(env, SimpleNamespace(headers={'cf-connecting-ip': address}))) is None
    assert limit.keys[0] == limit.keys[1]
    for unavailable in (SimpleNamespace(NORULO_MODE='production'),
                        SimpleNamespace(NORULO_MODE='production', AUTH_RATE_LIMIT=NativeLimit(failure=True))):
        assert asyncio.run(authorize_admission(unavailable, SimpleNamespace(headers={})))[0:2] == (
            503, {'error': {'code': 'AUTH_ADMISSION_UNAVAILABLE'}})
    assert asyncio.run(authorize_admission(SimpleNamespace(NORULO_MODE='local'), SimpleNamespace(headers={}))) is None
