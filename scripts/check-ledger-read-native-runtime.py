"""Run canonical Python reads and accounting over local Miniflare/workerd D1.

Only the loopback transport is adapted. SQL, parameters, results and native cost
metadata cross the real D1 JavaScript boundary. This is separate from a Python
Worker HTTP/FFI check and never accesses production or a real provider.
"""
import argparse
import asyncio
import csv
import io
import json
import sqlite3
from contextlib import closing
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
from test_ledger_read_parameter_limits import ledger as ledger_fixture, PATHS, FILTERS, visible_expenses, state
from test_ledger_recurring import app as app_fixture, api_auth, NoGitHub, NOW
from test_d1_validation_budget import LocalSql
from norulo_server.cloudflare_ledger_api import handle_ledger_request
from norulo_server.cloudflare_preview_budget import ProductMeteredD1, initial_data
from norulo_server.cloudflare_preview_schema import INDEX_COUNTS
from norulo_server.cloudflare_state_records import STATE_STORAGE_VERSION, USER_RECORD_BYTES
from norulo_server.cloudflare_validation_budget import BudgetJournal


class Prepared:
    def __init__(self, binding, sql):
        self.binding, self.sql, self.params = binding, sql, ()
    def bind(self, *params):
        self.params = params
        return self
    async def all(self):
        return (await self.binding.batch([self]))[0]
    async def first(self):
        rows = (await self.all()).results
        return rows[0] if rows else None


class NativeLocalD1:
    def __init__(self, port):
        self.url = f'http://127.0.0.1:{port}/batch'
        self.opener = build_opener(ProxyHandler({}))
        self.statements = self.read = self.written = self.maximum = 0
    def prepare(self, sql):
        return Prepared(self, sql)
    async def batch(self, statements):
        body = [{'sql': item.sql, 'params': item.params} for item in statements]
        assert len(body) <= 64 and all(len(item['params']) <= 100 for item in body)
        self.maximum = max(self.maximum, *(len(item['params']) for item in body))
        request = Request(self.url, method='POST', data=json.dumps(body).encode(),
                          headers={'Content-Type': 'application/json'})
        try:
            with self.opener.open(request, timeout=30) as response:
                results = json.load(response)
        except HTTPError as error:
            raise RuntimeError('Local synthetic D1: ' + error.read().decode()) from None
        self.statements += len(results)
        self.read += sum(item['meta']['rows_read'] for item in results)
        self.written += sum(item['meta']['rows_written'] for item in results)
        return [SimpleNamespace(**item) for item in results]


async def export_rows(export):
    return list(csv.DictReader(io.StringIO(''.join([chunk async for chunk in export.chunks()]))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    process = subprocess.Popen(['node', str(ROOT / 'scripts/check-ledger-read-native-runtime.cjs')],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=sys.stderr)
    evidence = {'passed': False, 'localOnly': True, 'remoteWrites': 0,
                'canonicalPythonHandlers': True, 'nativeD1': True, 'pythonWorkerHttpFFI': False}
    try:
        ready = json.loads(process.stdout.readline())
        raw = NativeLocalD1(ready['port'])
        with tempfile.TemporaryDirectory() as directory:
            fixture = ledger_fixture.__wrapped__(app_fixture.__wrapped__(Path(directory)))
            grants = [(100, False), (100, True), (0, False), (0, True), (None, False), (None, True)]
            credentials = [(count, shared, api_auth(fixture, scopes=['projects:read', 'expenses:read', 'reports:read'],
                restrictions={'shared': shared, **({'projectIds': fixture.ids[:count]} if count is not None else {})},
                suffix=str(number))) for number, (count, shared) in enumerate(grants)]
            with closing(fixture.store.connect()) as db:
                schema = [row[0] for row in db.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY rowid")]
                commands = [raw.prepare(sql) for sql in schema]
                remaining = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
                tables = []
                while remaining:
                    ready_tables = sorted(table for table in remaining if not {
                        row[2] for row in db.execute('PRAGMA foreign_key_list(' + table + ')')} & remaining)
                    assert ready_tables, 'fixture table dependencies must be acyclic'
                    tables.extend(ready_tables)
                    remaining.difference_update(ready_tables)
                for table in tables:
                    columns = [row[1] for row in db.execute('PRAGMA table_info(' + table + ')')]
                    for row in db.execute('SELECT * FROM ' + table):
                        commands.append(raw.prepare('INSERT INTO ' + table + '(' + ','.join(columns) + ') VALUES(' +
                            ','.join('?' for _ in columns) + ')').bind(*row))
                counts = {table: db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0] for table in INDEX_COUNTS}
            for offset in range(0, len(commands), 32):
                asyncio.run(raw.batch(commands[offset:offset + 32]))
            evidence['fixtureSetup'] = {'statements': raw.statements, 'rowsRead': raw.read, 'rowsWritten': raw.written}
            original_state = state(fixture)
            raw.read = raw.written = raw.statements = raw.maximum = 0
            cases = []
            for count, shared, auth in credentials:
                for path, filters in [(path, {}) for path in PATHS] + (
                        [(path, FILTERS) for path in PATHS[1:] if not path.endswith('rules')] if count == 100 else []):
                    with closing(sqlite3.connect(':memory:')) as journal_db:
                        journal = BudgetJournal(LocalSql(journal_db), preview_product=True, product_operations=True)
                        saved = journal.snapshot()
                        data = initial_data()
                        data['rows'].update(counts)
                        data['arrays'] = USER_RECORD_BYTES // 2
                        saved.update(product_data=data, product_data_verified=True, state_storage_version=STATE_STORAGE_VERSION,
                                     state_record_integrity_version=2)
                        journal._save(saved)
                        ticket = journal.begin_product(now=10)
                        binding = ProductMeteredD1(raw, journal, ticket, clock=lambda: 11)
                        status, payload = asyncio.run(handle_ledger_request(binding=binding, gateway=NoGitHub(),
                            method='GET', path=path, headers=auth, params={'limit': '100', **filters}, body=None, now=NOW))
                        assert status == 200, (path, count, shared, status)
                        size = len(payload.get('items', payload.get('groups', []))) if isinstance(payload, dict) else 0
                        if path.endswith('/export'):
                            rows = asyncio.run(export_rows(payload))
                            expected = sorted(visible_expenses(fixture, count, shared, bool(filters)),
                                              key=lambda row: (row['occurred_on'], row['id']))
                            assert [row['id'] for row in rows] == [row['id'] for row in expected]
                            assert [(row['amountMinor'], row['currency']) for row in rows] == [
                                (str(row['amount_minor']), row['currency']) for row in expected]
                            size = len(rows)
                        else:
                            expected_status, expected_payload = asyncio.run(handle_ledger_request(
                                binding=fixture.raw, gateway=NoGitHub(), method='GET', path=path,
                                headers=auth, params={'limit': '100', **filters}, body=None, now=NOW))
                            assert expected_status == status and expected_payload == payload
                        assert binding.accounted_outcome()
                        journal.finish(ticket, now=11)
                        saved = journal.snapshot()
                        assert saved['actual_written'] == 0 and saved['stopped'] is None
                        cases.append({'path': path, 'projectGrant': count, 'shared': shared, 'filtered': bool(filters),
                            'status': status, 'rows': size, 'nativeRowsRead': saved['actual_read'],
                            'nativeRowsWritten': saved['actual_written'], 'reservedRead': saved['reserved_read']})
            assert raw.written == 0 and state(fixture) == original_state
            evidence.update(passed=True, cases=cases, requests=len(cases), nativeStatements=raw.statements,
                            nativeRowsRead=raw.read, nativeRowsWritten=raw.written, maximumParameters=raw.maximum,
                            nativeAccountingCoveredEveryRead=True, completeResponsesMatchSQLite=True,
                            csvMoneyAndOrderMatchFixture=True)
    finally:
        process.terminate()
        process.wait(timeout=20)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, indent=2) + '\n')
        print(json.dumps({key: evidence.get(key) for key in ['passed', 'requests', 'nativeStatements',
            'nativeRowsRead', 'nativeRowsWritten', 'maximumParameters']}))


if __name__ == '__main__':
    main()
