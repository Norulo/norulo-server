"""Long project grants must preserve permission, global cursors and exact money."""
import asyncio
import csv
import io
from contextlib import closing

import pytest

from test_ledger_recurring import app, api_auth, draft, NoGitHub
from norulo_server.cloudflare_ledger_api import handle_ledger_request
from norulo_server.cloudflare_ledger_reports import EXPORT_HEADER
from norulo_server.cloudflare_principal import PrincipalAuthError
from norulo_server.ledger_money_totals import public_minor


PATHS = ['/api/v1/projects', '/api/v1/expenses', '/api/v1/expense-recurring-rules',
    '/api/v1/reports/summary', '/api/v1/reports/timeseries', '/api/v1/reports/categories',
    '/api/v1/expenses/export']


@pytest.fixture
def ledger(app):
    with app.store._immediate() as db:
        for identifier, removed in [('prj_a', False), ('prj_z', False), ('prj_hidden', False), ('prj_removed', True)]:
            db.execute('''INSERT INTO ledger_projects(id,owner_id,name,description,status,revision,
                created_at,updated_at,deleted_at) VALUES(?,'owner',?,'',?,1,'created','updated',?)''',
                (identifier, identifier, 'archived' if removed else 'active',
                 '2026-09-30T00:00:00Z' if removed else None))
        db.execute("INSERT INTO ledger_projects(id,owner_id,name,description,status,revision,created_at,updated_at) VALUES('prj_other','other','Other','','active',1,'created','updated')")
        db.execute("INSERT INTO expense_categories(id,owner_id,name,revision,created_at,updated_at) VALUES('cat_other','other','Other',1,'created','updated')")
        for number in range(310):
            project = ['prj_a', 'prj_z', 'prj_1', None][number % 4]
            amount = 9007199254740991 if number < 4 else number + 1
            db.execute('''INSERT INTO expenses(id,owner_id,target_kind,project_id,category_id,occurred_on,
                amount_minor,currency,purpose,created_at,updated_at) VALUES(?,'owner',?,?,'cat_1',?,?,?,?,'created','updated')''',
                (f'exp_{number:04d}', 'project' if project else 'shared', project,
                 '2026-09-27' if number % 3 else '2026-09-28', amount,
                 'USD' if number % 3 else 'CNY', '=Synthetic' if number == 1 else 'Hosting'))
        for identifier, project, owner in [('exp_hidden', 'prj_hidden', 'owner'),
                ('exp_removed', 'prj_removed', 'owner'), ('exp_other', 'prj_other', 'other')]:
            db.execute('''INSERT INTO expenses(id,owner_id,target_kind,project_id,category_id,occurred_on,
                amount_minor,currency,purpose,created_at,updated_at) VALUES(?,?,'project',?,?,
                '2026-09-27',123,'USD','Hidden','created','updated')''', (identifier, owner, project,
                    'cat_other' if owner == 'other' else 'cat_1'))
    for number, target in enumerate([{'kind': 'project', 'projectId': 'prj_z'},
            {'kind': 'project', 'projectId': 'prj_a'}, {'kind': 'project', 'projectId': 'prj_1'},
            {'kind': 'shared'}, {'kind': 'project', 'projectId': 'prj_hidden'}]):
        status, _ = app.call('POST', body=draft(target=target, start='2030-10-31'), key=f'rule-{number}')
        assert status == 201
    original_batch = app.raw.batch
    app.captured = []

    async def batch(statements):
        statements = list(statements)
        assert all(len(item.params) <= 100 for item in statements), 'D1 maximum bound parameters exceeded'
        app.captured.extend(statements)
        return await original_batch(statements)
    app.raw.batch = batch
    app.ids = ['prj_z'] + [f'prj_retained_{n}' for n in range(95)] + ['prj_a', 'prj_1', 'prj_other', 'prj_removed']
    return app


def key(ledger, *, count=100, shared=False):
    restriction = {'shared': shared}
    if count is not None:
        restriction['projectIds'] = ledger.ids[:count] if count != 1 else ['prj_a']
    return api_auth(ledger, scopes=['projects:read', 'expenses:read', 'reports:read'],
                    restrictions=restriction)


def request(ledger, path, headers, params=None):
    return asyncio.run(handle_ledger_request(binding=ledger.raw, gateway=NoGitHub(), method='GET',
        path=path, headers=headers, params=params or {}, body=None, now=1_791_460_800))


def state(ledger):
    with closing(ledger.store.connect()) as db:
        return list(db.iterdump())


def visible_expenses(ledger, count=100, shared=False, filtered=False):
    projects = None if count is None else set(ledger.ids[:count] if count != 1 else ['prj_a'])
    with closing(ledger.store.connect()) as db:
        rows = [dict(row) for row in db.execute('SELECT * FROM expenses WHERE owner_id="owner"')]
    return [row for row in rows if row['project_id'] != 'prj_removed' and (
        row['target_kind'] == 'shared' and shared or row['target_kind'] == 'project' and (
            projects is None or row['project_id'] in projects)) and (not filtered or (
            row['project_id'] == 'prj_a' and row['currency'] == 'USD' and row['occurred_on'] == '2026-09-27'))]


FILTERS = {'target': 'project', 'projectId': 'prj_a', 'categoryId': 'cat_1',
           'currency': 'USD', 'from': '2026-09-27', 'to': '2026-09-28'}


@pytest.mark.parametrize('path', PATHS)
@pytest.mark.parametrize('count,shared', [(100, False), (100, True), (0, False), (0, True), (None, False), (None, True)])
def test_full_grants_and_empty_grants_read_without_writes(ledger, path, count, shared):
    auth = key(ledger, count=count, shared=shared)
    before = state(ledger)
    status, payload = request(ledger, path, auth, {'limit': '100'})
    assert status == 200
    if path.endswith('/export'):
        async def collect():
            return ''.join([part async for part in payload.chunks()])
        exported = list(csv.DictReader(io.StringIO(asyncio.run(collect()))))
        assert [row['id'] for row in exported] == [row['id'] for row in sorted(
            visible_expenses(ledger, count, shared), key=lambda row: (row['occurred_on'], row['id']))]
        assert len({row['id'] for row in exported}) == len(exported)
    elif path == '/api/v1/expenses':
        assert [row['id'] for row in payload['items']] == sorted(row['id'] for row in visible_expenses(
            ledger, count, shared))[:100]
    elif count == 0 and not shared:
        assert payload.get('items', payload.get('groups')) == []
    assert state(ledger) == before


@pytest.mark.parametrize('path', PATHS[:3])
@pytest.mark.parametrize('limit', [1, 2, 100])
def test_global_pagination_is_ordered_complete_and_unique_across_grant_chunks(ledger, path, limit):
    auth = key(ledger, shared=True)
    before = state(ledger)
    cursor, found = '', []
    while True:
        status, page = request(ledger, path, auth, {'limit': str(limit), 'cursor': cursor})
        assert status == 200
        found.extend(row['id'] for row in page['items'])
        cursor = page['nextCursor']
        if cursor is None:
            break
        assert cursor == found[-1]
    if path.endswith('/projects'):
        expected = ['prj_1', 'prj_a', 'prj_z']
    elif path.endswith('/expenses'):
        expected = sorted(row['id'] for row in visible_expenses(ledger, shared=True))
    else:
        with closing(ledger.store.connect()) as db:
            expected = [row[0] for row in db.execute("SELECT id FROM expense_recurring_rules WHERE project_id IS NULL OR project_id!='prj_hidden' ORDER BY id")]
    assert found == expected and len(found) == len(set(found))
    assert state(ledger) == before


@pytest.mark.parametrize('name', ['summary', 'timeseries', 'categories'])
@pytest.mark.parametrize('filtered', [False, True])
def test_report_money_and_dimensions_are_exact_across_chunks(ledger, name, filtered):
    auth = key(ledger, shared=True)
    status, report = request(ledger, '/api/v1/reports/' + name, auth, FILTERS if filtered else {})
    assert status == 200
    expected = {}
    for row in visible_expenses(ledger, shared=True, filtered=filtered):
        dimensions = (row['target_kind'], row['project_id'], row['category_id'] if name == 'categories' else None,
                      row['occurred_on'] if name == 'timeseries' else None, row['currency'])
        keys = [dimensions]
        if name == 'summary':
            keys += [('account', None, None, None, row['currency'])]
            if row['target_kind'] == 'project':
                keys += [('project', None, None, None, row['currency'])]
        for dimensions in keys:
            expected[dimensions] = expected.get(dimensions, 0) + row['amount_minor']
    actual = {(row['target'], row['projectId'], row['categoryId'], row['bucket'], row['currency']): row['amountMinor']
              for row in report['groups']}
    assert actual == {dimensions: public_minor(amount) for dimensions, amount in expected.items()}


@pytest.mark.parametrize('count', [0, 1, 49, 50, 51, 91, 92, 97, 98, 99, 100])
@pytest.mark.parametrize('shared', [False, True])
def test_csv_crosses_page_and_chunk_boundaries_without_loss_or_duplicates(ledger, count, shared):
    auth = key(ledger, count=count, shared=shared)
    status, export = request(ledger, '/api/v1/expenses/export', auth)
    assert status == 200
    async def collect():
        return ''.join([part async for part in export.chunks()])
    rows = list(csv.reader(io.StringIO(asyncio.run(collect()))))
    assert rows[0] == list(EXPORT_HEADER)
    expected = sorted(visible_expenses(ledger, count, shared), key=lambda row: (row['occurred_on'], row['id']))
    assert [row[0] for row in rows[1:]] == [row['id'] for row in expected]
    assert len(rows) == len(expected) + 1
    if count == 100:
        assert any(row[7] == "'=Synthetic" for row in rows[1:])


@pytest.mark.parametrize('path', PATHS[1:])
def test_full_filter_set_with_hundred_project_grant(ledger, path):
    auth = key(ledger)
    params = {k: v for k, v in FILTERS.items() if not path.endswith('rules') or k in {'target', 'projectId'}}
    status, payload = request(ledger, path, auth, params)
    assert status == 200
    if path.endswith('/export'):
        async def collect():
            return ''.join([part async for part in payload.chunks()])
        rows = list(csv.DictReader(io.StringIO(asyncio.run(collect()))))
        assert len(rows) == len(visible_expenses(ledger, filtered=True))


@pytest.mark.parametrize('path', PATHS)
def test_revoked_grant_is_rechecked_in_same_batch_even_for_empty_result(ledger, path):
    auth = key(ledger, count=0)
    def revoke():
        with ledger.store._immediate() as db:
            db.execute('UPDATE api_keys SET revoked_at=1')
    ledger.raw.before_batch = revoke
    status, _ = request(ledger, path, auth)
    assert status == 401


def test_export_rechecks_grant_on_next_page(ledger):
    auth = key(ledger, shared=True)
    status, export = request(ledger, '/api/v1/expenses/export', auth)
    assert status == 200
    async def consume_then_revoke():
        chunks = export.chunks()
        await chunks.__anext__()  # header
        await chunks.__anext__()  # first complete page
        with ledger.store._immediate() as db:
            db.execute('UPDATE api_keys SET revoked_at=1')
        with pytest.raises(PrincipalAuthError):
            await chunks.__anext__()
    asyncio.run(consume_then_revoke())


@pytest.mark.parametrize('path', PATHS)
@pytest.mark.parametrize('change', ['scope', 'grant', 'membership'])
def test_member_key_grant_and_membership_are_fenced_before_disclosure(ledger, path, change):
    auth = api_auth(ledger, actor='viewer', scopes=['projects:read', 'expenses:read', 'reports:read'],
                    restrictions={'projectIds': ledger.ids, 'shared': True})
    assert request(ledger, path, auth)[0] == 200
    def change_authority():
        with ledger.store._immediate() as db:
            if change == 'scope':
                db.execute("UPDATE api_keys SET scopes='[]'")
            elif change == 'grant':
                db.execute("UPDATE api_keys SET restrictions='{}'")
            else:
                db.execute("UPDATE workspace_members SET removed_at='removed',revision=revision+1 WHERE user_id='viewer'")
    ledger.raw.before_batch = change_authority
    status, _ = request(ledger, path, auth)
    assert status in {401, 403, 404}


def test_hundred_maximum_length_project_ids_stay_inside_scalar_input_envelopes(ledger):
    ids = ['prj_' + str(number).zfill(100) for number in range(100)]
    auth = api_auth(ledger, scopes=['projects:read', 'expenses:read', 'reports:read'],
                    restrictions={'projectIds': ids, 'shared': False})
    from norulo_server.cloudflare_preview_budget import _input_bound
    for path in PATHS:
        assert request(ledger, path, auth)[0] == 200
    for statement in ledger.captured:
        _input_bound(statement.params, sql=statement.sql)


def test_long_project_grant_preserves_repository_bindings_on_every_page():
    from test_ledger_routes import LedgerRoutesTests
    from test_repository_pagination_limits import D1ParameterCeiling, ManyRepositories
    from norulo_server.cloudflare_api_key_write import create_api_key
    fixture = LedgerRoutesTests()
    fixture.setUp()
    try:
        fixture.binding = D1ParameterCeiling(fixture.store)
        fixture.gateway = ManyRepositories()
        created = []
        for repo in [202, 1001]:
            status, project = fixture.call('POST', '/api/v1/projects', {'githubRepoId': repo}, gateway=fixture.gateway)
            assert status == 201
            created.append(project)
        status, token = asyncio.run(create_api_key(binding=fixture.binding, headers=fixture.headers,
            body={'scopes': ['projects:read'], 'restrictions': {'projectIds': [created[1]['id']] +
                ['prj_retained_' + str(n) for n in range(98)] + [created[0]['id']], 'shared': False}}, now=fixture.now + 3))
        assert status == 201
        headers = {'Authorization': 'Bearer ' + token['key']}
        pages, cursor = [], ''
        for _ in range(2):
            status, page = fixture.call('GET', '/api/v1/projects', headers=headers,
                params={'limit': '1', 'cursor': cursor}, gateway=fixture.gateway)
            assert status == 200 and len(page['items']) == 1
            pages.extend(page['items'])
            cursor = page['nextCursor']
        assert cursor is None
        assert [(row['id'], row['githubRepoIds'], row['githubAccess']) for row in pages] == [
            (row['id'], row['githubRepoIds'], 'authorized') for row in sorted(created, key=lambda row: row['id'])]
    finally:
        fixture.tearDown()
