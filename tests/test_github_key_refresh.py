"""Explicit delegated refresh: actor isolation, credential fences and no replay."""
import asyncio
import json

import pytest

from norulo_server.cloudflare_github_gateway import GitHubFailure
from norulo_server.cloudflare_state_records import encode_record, record_name
from test_github_token_refresh import (
    expiring_ledger, stored_user, database_snapshot, ROTATED_ACCESS, REFRESH, USER_ID,
)

PATH = '/api/v1/integrations/github/refresh'


def refresh(ledger, headers):
    return ledger.call('POST', PATH, {}, headers, gateway=ledger.gateway)


def stable_records(ledger):
    with ledger.store.connect() as db:
        return {table: [tuple(row) for row in db.execute('SELECT * FROM ' + table)]
            for table in ('ledger_projects', 'ledger_project_repositories', 'expenses',
                          'expense_events', 'ledger_plan_usage', 'api_keys', 'workspace_members')}


def test_key_refresh_uses_existing_claim_and_never_changes_financial_or_key_records(expiring_ledger):
    ledger, _, _, _, headers = expiring_ledger
    before = stable_records(ledger)
    status, page = ledger.call('GET', '/api/v1/repositories', headers=headers, gateway=ledger.gateway)
    assert status == 200 and page['githubRefreshRequired'] is True
    assert refresh(ledger, headers) == (200, {'ok': True, 'refreshed': True})
    assert stored_user(ledger.store)['githubAccessToken'] == 'sealed:' + ROTATED_ACCESS
    assert stable_records(ledger) == before
    assert refresh(ledger, headers) == (200, {'ok': True, 'refreshed': False})
    assert ledger.gateway.refresh_calls == [REFRESH]
    status, page = ledger.call('GET', '/api/v1/repositories', headers=headers, gateway=ledger.gateway)
    assert status == 200 and page['githubAccess'] == 'authorized'
    assert 'githubRefreshRequired' not in page


def test_delegated_cas_has_typed_record_and_credential_json_admission(expiring_ledger):
    from norulo_server.cloudflare_preview_budget import _input_bound, sql_write_bound
    ledger, _, _, _, headers = expiring_ledger
    original = ledger.binding.batch
    captured = []
    async def review(statements):
        for statement in statements:
            if statement.sql.lstrip().startswith('UPDATE app_state SET payload='):
                _input_bound(statement.params, sql=statement.sql)
                assert sql_write_bound(statement.sql) > 0
                captured.append(statement)
        return await original(statements)
    ledger.binding.batch = review
    assert refresh(ledger, headers)[0] == 200
    assert len(captured) == 2
    statement = captured[0]
    params = list(statement.params)
    params[7] = '{"unreviewed":true}'
    with pytest.raises(ValueError, match='delegated credential'):
        _input_bound(params, sql=statement.sql)
    params = list(statement.params)
    params[0] = '{"id":"somebody_else"}'
    with pytest.raises(ValueError, match='typed record'):
        _input_bound(params, sql=statement.sql)


@pytest.mark.parametrize('mutation', ['revoked', 'expired', 'scopes', 'restrictions'])
@pytest.mark.parametrize('phase', ['before_claim', 'before_publish'])
def test_key_changes_fence_exchange_and_publication(expiring_ledger, mutation, phase):
    ledger, _, _, _, headers = expiring_ledger
    async def change_key():
        with ledger.store.connect() as db:
            if mutation == 'revoked':
                db.execute('UPDATE api_keys SET revoked_at=?', (ledger.now,))
            elif mutation == 'expired':
                db.execute('UPDATE api_keys SET expires_at=?', (ledger.now - 1,))
            elif mutation == 'scopes':
                db.execute('UPDATE api_keys SET scopes=?', ('["profile:read"]',))
            else:
                db.execute('UPDATE api_keys SET restrictions=?', ('{"shared":true}',))
    if phase == 'before_claim':
        ledger.gateway.validate_refresh_configuration = change_key
    else:
        ledger.gateway.refresh_wait = change_key
    status, payload = refresh(ledger, headers)
    assert status == (409 if phase == 'before_claim' else 401)
    assert payload['error']['code'] == ('ACCOUNT_CHANGED' if phase == 'before_claim' else 'UNAUTHENTICATED')
    assert ledger.gateway.refresh_calls == ([] if phase == 'before_claim' else [REFRESH])
    user = stored_user(ledger.store)
    assert ('githubTokenRefresh' in user) == (phase == 'before_publish')
    assert user['githubAccessToken'] != 'sealed:' + ROTATED_ACCESS


def test_unknown_provider_outcome_keeps_claim_and_is_not_retried(expiring_ledger):
    ledger, _, _, _, headers = expiring_ledger
    ledger.gateway.refresh_failure = GitHubFailure('GITHUB_UNAVAILABLE')
    assert refresh(ledger, headers) == (503, {'error': {'code': 'GITHUB_UNAVAILABLE'}})
    assert refresh(ledger, headers) == (409, {'error': {'code': 'GITHUB_REFRESH_PENDING'}})
    ledger.now += 61
    assert refresh(ledger, headers) == (403, {'error': {'code': 'GITHUB_REAUTHORIZATION_REQUIRED'}})
    assert ledger.gateway.refresh_calls == [REFRESH]


def test_cookie_and_key_refresh_share_one_durable_claim(expiring_ledger):
    from test_github_token_refresh import async_refresh_request
    ledger, _, _, _, headers = expiring_ledger
    async def run():
        started, release = asyncio.Event(), asyncio.Event()
        async def wait():
            started.set()
            await release.wait()
        ledger.gateway.refresh_wait = wait
        from norulo_server.cloudflare_github_refresh import handle_key_github_refresh
        task = asyncio.create_task(handle_key_github_refresh(binding=ledger.binding,
            gateway=ledger.gateway, method='POST', headers=headers, body={}, now=ledger.now + 3))
        await started.wait()
        result = await async_refresh_request(ledger.binding, ledger.gateway, ledger.now + 3,
                                             ledger.headers['Cookie'])
        assert result[0] == 409 and result[1]['error']['code'] == 'GITHUB_REFRESH_PENDING'
        release.set()
        assert await task == (200, {'ok': True, 'refreshed': True})
    asyncio.run(run())
    assert ledger.gateway.refresh_calls == [REFRESH]


@pytest.mark.parametrize('remove_membership', [False, True])
def test_shared_ledger_refresh_uses_only_actor_credentials_and_current_membership(expiring_ledger, remove_membership):
    ledger, _, _, _, headers = expiring_ledger
    actor = stored_user(ledger.store)
    owner_id = 'usr_github_other_owner'
    owner = {**actor, 'id': owner_id, 'githubId': '12345', 'githubAccessToken': 'sealed:owner-access',
             'githubRefreshToken': 'sealed:owner-refresh'}
    owner_json = encode_record('users', owner_id, owner)
    restrictions = {'workspaceId': owner_id, 'workspaceMemberRevision': 1, 'shared': False}
    with ledger.store.connect() as db:
        db.execute('INSERT INTO app_state VALUES(?,?,?)',
                   (record_name('users', owner_id), owner_json, ledger.now))
        db.execute("INSERT INTO workspace_members VALUES(?,?,'viewer',1,'joined','updated',NULL,?)",
                   (owner_id, USER_ID, owner_id))
        db.execute('UPDATE api_keys SET restrictions=?', (json.dumps(restrictions),))
    if remove_membership:
        async def remove():
            with ledger.store.connect() as db:
                db.execute("UPDATE workspace_members SET removed_at='removed'")
        ledger.gateway.validate_refresh_configuration = remove
    status, payload = refresh(ledger, headers)
    assert status == (409 if remove_membership else 200), payload
    assert ledger.gateway.refresh_calls == ([] if remove_membership else [REFRESH])
    with ledger.store.connect() as db:
        assert db.execute('SELECT payload FROM app_state WHERE name=?',
                          (record_name('users', owner_id),)).fetchone()[0] == owner_json


@pytest.mark.parametrize('method,body,headers_kind,status', [
    ('GET', None, 'key', 405), ('POST', {'actorId': 'other'}, 'key', 422),
    ('POST', {}, 'cookie', 401), ('POST', {}, 'none', 401),
])
def test_refresh_rejects_invalid_or_non_delegated_requests_without_writes(expiring_ledger, method, body, headers_kind, status):
    ledger, _, _, _, key = expiring_ledger
    headers = key if headers_kind == 'key' else ledger.headers if headers_kind == 'cookie' else {'Authorization': 'Bearer invalid'}
    before = database_snapshot(ledger.store)
    result = ledger.call(method, PATH, body, headers, gateway=ledger.gateway)
    assert result[0] == status
    assert database_snapshot(ledger.store) == before and not ledger.gateway.refresh_calls
