"""D1's 100-variable ceiling with full repository pages and restricted keys."""
import asyncio
import json

import pytest

import test_ledger_routes as fixtures
from test_cloudflare_github_identity_http import D1ShapedSQLite, GitHubStub
from norulo_server.cloudflare_api_key_write import create_api_key


class ManyRepositories(GitHubStub):
    async def repositories(self, token, installation_id):
        return [{'id': 202, 'full_name': 'alice/project'}] + [
            {'id': 1000 + value, 'full_name': f'alice/project-{value}'} for value in range(120)]


class D1ParameterCeiling(D1ShapedSQLite):
    async def batch(self, statements):
        for statement in statements:
            assert len(statement.params) <= 100, 'D1 maximum bound parameters exceeded'
        return await super().batch(statements)


@pytest.fixture
def ledger():
    fixture = fixtures.LedgerRoutesTests()
    fixture.setUp()
    fixture.binding = D1ParameterCeiling(fixture.store)
    fixture.gateway = ManyRepositories()
    try:
        yield fixture
    finally:
        fixture.tearDown()


@pytest.mark.parametrize('restriction_count', [None, 0, 1, 100])
def test_full_pages_preserve_cursor_binding_visibility_and_read_only_state(ledger, restriction_count):
    status, visible = ledger.call('POST', '/api/v1/projects', {'githubRepoId': 202})
    assert status == 201
    status, hidden = ledger.call('POST', '/api/v1/projects', {'githubRepoId': 1001}, gateway=ledger.gateway)
    assert status == 201
    status, key = asyncio.run(create_api_key(binding=ledger.binding, headers=ledger.headers,
        body={'name': 'Synthetic pagination', 'scopes': ['projects:read']}, now=ledger.now + 3))
    assert status == 201
    if restriction_count is not None:
        ids = ([visible['id']] + [f'prj_retained_{value}' for value in range(restriction_count - 1)]
               if restriction_count else [])
        with ledger.store.connect() as db:
            db.execute('UPDATE api_keys SET restrictions=? WHERE id=?',
                       (json.dumps({'projectIds': ids, 'shared': False}), key['id']))
    with ledger.store.connect() as db:
        before = list(db.iterdump())
    headers = {'Authorization': 'Bearer ' + key['key']}
    status, page = ledger.call('GET', '/api/v1/repositories', headers=headers,
                               params={'limit': '100'}, gateway=ledger.gateway)
    assert status == 200 and len(page['items']) == 100
    by_id = {item['githubRepoId']: item for item in page['items']}
    assert by_id[202]['isBound'] is (restriction_count != 0)
    assert by_id[1001]['isBound'] is (restriction_count is None)
    status, next_page = ledger.call('GET', '/api/v1/repositories', headers=headers,
        params={'limit': '100', 'cursor': page['nextCursor']}, gateway=ledger.gateway)
    assert status == 200 and len(next_page['items']) == 21 and next_page['nextCursor'] is None
    ids = [item['githubRepoId'] for item in page['items'] + next_page['items']]
    assert len(set(ids)) == 121 and ids == sorted(ids)
    with ledger.store.connect() as db:
        assert list(db.iterdump()) == before
