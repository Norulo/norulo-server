"""CSV pages keep order, restrictions, visibility and live access checks."""
import asyncio
import csv
import io
from contextlib import closing

import pytest

from norulo_server.cloudflare_api_key_write import create_api_key
from norulo_server.cloudflare_ledger_reports import handle_report_request
from norulo_server.cloudflare_principal import PrincipalAuthError
from test_ledger_recurring import app, NOW


@pytest.fixture
def ledger(app):
    with closing(app.store.connect()) as db:
        db.execute("INSERT INTO expense_categories(id,owner_id,name,created_at,updated_at) VALUES('cat_2','owner','Tools','now','now')")
        db.execute("INSERT INTO ledger_projects(id,owner_id,name,status,created_at,updated_at,deleted_at) VALUES('prj_removed','owner','Removed','archived','now','now','2026-10-08T00:00:00Z')")
        db.execute("INSERT INTO expense_categories(id,owner_id,name,created_at,updated_at) VALUES('cat_other','other','Private','now','now')")
        rows = []
        for number in range(1200):
            target = "shared" if number % 2 else "project"
            rows.append((f"exp_{number:04d}", "owner", target, "prj_1" if target == "project" else None,
                         "cat_2" if number % 3 else "cat_1", f"2026-10-{number % 4 + 1:02d}",
                         "EUR" if number % 5 == 0 else "USD", "2026-10-08T00:00:00Z" if number % 17 == 0 else None))
        rows.extend((f"removed_{n:04d}", "owner", "project", "prj_removed", "cat_1", "2026-10-01", "USD", None) for n in range(31))
        rows.extend((f"other_{n:04d}", "other", "shared", None, "cat_other", "2026-10-01", "USD", None) for n in range(17))
        db.executemany("""INSERT INTO expenses(id,owner_id,target_kind,project_id,category_id,
            occurred_on,currency,deleted_at,amount_minor,purpose,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,100,'Hosting','now','now')""", rows)
        db.commit()
    return app, rows


def request(app, params=None, headers=None):
    return asyncio.run(handle_report_request(binding=app.raw, method="GET",
        path="/api/v1/expenses/export", headers=headers or {"Cookie": "nr_session=owner"},
        params=params or {}, now=NOW))


async def collect(export):
    return "".join([part async for part in export.chunks()])


@pytest.mark.parametrize("params", [{}, {"target": "project"}, {"target": "shared"},
    {"projectId": "prj_1"}, {"categoryId": "cat_2"}, {"currency": "USD"},
    {"from": "2026-10-02", "to": "2026-10-04"},
    {"target": "project", "categoryId": "cat_2", "currency": "USD"}])
def test_export_filters_and_same_date_cursor_match_expected_in_order(ledger, params):
    app, rows = ledger
    expected = [r for r in rows if r[1] == "owner" and r[3] != "prj_removed" and r[7] is None
                and (not params.get("target") or r[2] == params["target"])
                and (not params.get("projectId") or r[3] == params["projectId"])
                and (not params.get("categoryId") or r[4] == params["categoryId"])
                and (not params.get("currency") or r[6] == params["currency"])
                and (not params.get("from") or r[5] >= params["from"])
                and (not params.get("to") or r[5] < params["to"])]
    status, export = request(app, params)
    assert status == 200
    actual = list(csv.DictReader(io.StringIO(asyncio.run(collect(export)))))
    assert [(r["occurredOn"], r["id"]) for r in actual] == sorted((r[5], r[0]) for r in expected)


def test_restricted_api_key_never_exports_other_targets_or_shared_pool(ledger):
    app, rows = ledger
    status, key = asyncio.run(create_api_key(binding=app.raw,
        headers={"Cookie": "nr_session=owner", "Origin": "https://app.example.test"},
        body={"scopes": ["expenses:read"], "restrictions": {"projectIds": ["prj_1"], "shared": False}}, now=NOW))
    assert status == 201
    headers = {"Authorization": "Bearer " + key["key"]}
    status, export = request(app, headers=headers)
    assert status == 200
    actual = list(csv.DictReader(io.StringIO(asyncio.run(collect(export)))))
    assert [(r["occurredOn"], r["id"]) for r in actual] == sorted(
        (r[5], r[0]) for r in rows if r[1] == "owner" and r[3] == "prj_1" and r[7] is None)
    assert request(app, {"target": "shared"}, headers)[0] == 403
    assert request(app, {"projectId": "prj_removed"}, headers)[0] == 403


def test_next_page_rechecks_the_principal(ledger):
    app, _ = ledger
    status, export = request(app)
    assert status == 200
    with closing(app.store.connect()) as db:
        db.execute("DELETE FROM app_state WHERE name='record:sessions:owner'")
        db.commit()
    with pytest.raises(PrincipalAuthError): asyncio.run(collect(export))


@pytest.mark.parametrize("params", [
    {"target": "project", "categoryId": "cat_2", "currency": "USD"},
    {"from": "2026-10-01", "to": "2026-10-04"},
])
def test_cursor_plan_seeks_the_export_index_even_with_target_filters(ledger, params):
    app, _ = ledger
    sql_batches = []
    batch = app.raw.batch
    async def capture(statements):
        statements = list(statements)
        sql_batches.extend(statements)
        return await batch(statements)
    app.raw.batch = capture
    _, export = request(app, params)
    asyncio.run(collect(export))
    pages = [s for s in sql_batches if "INDEXED BY expenses_owner_export_date" in s.sql]
    assert len(pages) >= 2
    assert "(occurred_on,id)>(?,?)" in pages[1].sql
    with closing(app.store.connect()) as db:
        for page in pages:
            plan = [r[3] for r in db.execute("EXPLAIN QUERY PLAN " + page.sql, page.params)]
            assert any("expenses_owner_export_date" in detail for detail in plan)
            assert not any("TEMP B-TREE" in detail for detail in plan)
        later_plan = [r[3] for r in db.execute("EXPLAIN QUERY PLAN " + pages[1].sql, pages[1].params)]
        assert any("(occurred_on,id)>(?,?)" in detail for detail in later_plan)
