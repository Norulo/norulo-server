"""Monthly, quarterly and annual project expense summaries."""
import pytest

import test_ledger_routes as route_fixture
from norulo_server.cloudflare_api_key_write import create_api_key
from norulo_server.cloudflare_ledger_reports import project_period


MAX_MINOR = 9007199254740991


@pytest.fixture
def ledger():
    routes = route_fixture.LedgerRoutesTests()
    routes.setUp()
    try:
        yield routes
    finally:
        routes.tearDown()


def seed(ledger, rows, *, project_id):
    _, category = ledger.call("POST", "/api/v1/categories", {"name": "Period"})
    with ledger.store.connect() as db:
        owner = db.execute("SELECT owner_id FROM expense_categories WHERE id=?",
            (category["id"],)).fetchone()[0]
        db.executemany("""INSERT INTO expenses(id,owner_id,target_kind,project_id,category_id,
            occurred_on,amount_minor,currency,purpose,created_at,updated_at,deleted_at)
            VALUES(?,?,?,?,?,?,?,?,'Period',?,?,?)""",
            [(expense_id, owner, "shared" if target is None else "project",
              project_id if target is True else target, category["id"], occurred_on,
              minor, currency, "2026-10-01T00:00:00Z", "2026-10-01T00:00:00Z", deleted)
             for expense_id, target, occurred_on, minor, currency, deleted in rows])
    return owner


def project(ledger, name=None):
    body = {"name": name} if name else {"githubRepoId": 202}
    status, created = ledger.call("POST", "/api/v1/projects", body)
    assert status == 201
    return created


def report(ledger, project_id, kind, params, headers=None):
    return ledger.call("GET", f"/api/v1/reports/projects/{project_id}/{kind}",
                       params=params, headers=headers)


@pytest.mark.parametrize(("granularity", "params", "start", "end"), [
    ("month", {"year": "2026", "month": "10"}, "2026-10-01", "2026-10-31"),
    ("month", {"year": "2024", "month": "02"}, "2024-02-01", "2024-02-29"),
    ("month", {"year": "2023", "month": "2"}, "2023-02-01", "2023-02-28"),
    ("month", {"year": "2026", "month": "12"}, "2026-12-01", "2026-12-31"),
    ("quarter", {"year": "2026", "quarter": "1"}, "2026-01-01", "2026-03-31"),
    ("quarter", {"year": "2026", "quarter": "4"}, "2026-10-01", "2026-12-31"),
    ("year", {"year": "2026"}, "2026-01-01", "2026-12-31"),
    ("year", {"year": "9999"}, "9999-01-01", "9999-12-31"),
    ("year", {"year": "0001"}, "0001-01-01", "0001-12-31"),
])
def test_periods_are_exact_inclusive_calendar_dates(granularity, params, start, end):
    period = project_period(granularity, params)
    assert (period["startOn"], period["endOn"]) == (start, end)


@pytest.mark.parametrize(("granularity", "params"), [
    ("month", {"year": "2026"}), ("month", {"year": "2026", "month": "13"}),
    ("month", {"year": "2026", "month": "0"}), ("month", {"year": "2026", "month": "+1"}),
    ("month", {"year": "2026", "month": "010"}), ("quarter", {"year": "2026", "quarter": "5"}),
    ("quarter", {"year": "2026", "quarter": "0"}), ("year", {"year": "0000"}),
    ("year", {"year": "26"}), ("year", {"year": "20260"}), ("year", {}),
])
def test_invalid_periods_are_rejected(granularity, params):
    with pytest.raises(ValueError):
        project_period(granularity, params)


def test_monthly_totals_group_by_currency_and_exclude_other_months(ledger):
    target = project(ledger)
    other = project(ledger, "Other")
    seed(ledger, [
        ("exp_sep_last", True, "2026-09-30", 100000, "USD", None),
        ("exp_oct_first", True, "2026-10-01", 1250, "USD", None),
        ("exp_oct_mid", True, "2026-10-15", 750, "USD", None),
        ("exp_oct_eur", True, "2026-10-20", 999, "EUR", None),
        ("exp_oct_jpy", True, "2026-10-31", 5000, "JPY", None),
        ("exp_nov_first", True, "2026-11-01", 200000, "USD", None),
        ("exp_oct_deleted", True, "2026-10-10", 7, "USD", "2026-10-11T00:00:00Z"),
        ("exp_oct_shared", None, "2026-10-10", 8, "USD", None),
        ("exp_oct_other", other["id"], "2026-10-10", 9, "USD", None),
        ("exp_2025_oct", True, "2025-10-10", 10, "USD", None),
    ], project_id=target["id"])
    status, payload = report(ledger, target["id"], "monthly", {"year": "2026", "month": "10"})
    assert status == 200
    assert payload["project"]["id"] == target["id"]
    assert payload["period"] == {"granularity": "month", "year": 2026, "month": 10,
                                 "startOn": "2026-10-01", "endOn": "2026-10-31"}
    assert payload["totals"] == [
        {"currency": "EUR", "amount": "9.99", "amountMinor": 999, "expenseCount": 1},
        {"currency": "JPY", "amount": "5000", "amountMinor": 5000, "expenseCount": 1},
        {"currency": "USD", "amount": "20.00", "amountMinor": 2000, "expenseCount": 2},
    ]
    assert [item["id"] for item in payload["items"]] == [
        "exp_oct_first", "exp_oct_mid", "exp_oct_eur", "exp_oct_jpy"]
    assert payload["items"][0]["target"] == {"kind": "project", "projectId": target["id"]}
    assert payload["nextCursor"] is None


def test_quarterly_and_annual_bounds(ledger):
    target = project(ledger)
    seed(ledger, [
        ("exp_2025_last", True, "2025-12-31", 1, "USD", None),
        ("exp_q1_first", True, "2026-01-01", 10, "USD", None),
        ("exp_q1_last", True, "2026-03-31", 20, "USD", None),
        ("exp_q2_first", True, "2026-04-01", 40, "USD", None),
        ("exp_q4_last", True, "2026-12-31", 80, "GBP", None),
        ("exp_2027_first", True, "2027-01-01", 160, "USD", None),
    ], project_id=target["id"])
    status, quarter = report(ledger, target["id"], "quarterly", {"year": "2026", "quarter": "1"})
    assert status == 200
    assert quarter["period"]["quarter"] == 1
    assert quarter["totals"] == [{"currency": "USD", "amount": "0.30", "amountMinor": 30, "expenseCount": 2}]
    assert [item["id"] for item in quarter["items"]] == ["exp_q1_first", "exp_q1_last"]
    status, annual = report(ledger, target["id"], "annual", {"year": "2026"})
    assert status == 200
    assert annual["period"] == {"granularity": "year", "year": 2026,
                                "startOn": "2026-01-01", "endOn": "2026-12-31"}
    assert {total["currency"]: total["amountMinor"] for total in annual["totals"]} == {"GBP": 80, "USD": 70}
    assert [item["id"] for item in annual["items"]] == [
        "exp_q1_first", "exp_q1_last", "exp_q2_first", "exp_q4_last"]


def test_totals_cover_the_whole_period_on_every_page(ledger):
    target = project(ledger)
    seed(ledger, [(f"exp_page_{index:02d}", True, f"2026-10-{index % 3 + 1:02d}", 100, "USD", None)
                  for index in range(5)], project_id=target["id"])
    seen, cursor = [], None
    while True:
        params = {"year": "2026", "month": "10", "limit": "2", **({"cursor": cursor} if cursor else {})}
        status, page = report(ledger, target["id"], "monthly", params)
        assert status == 200
        assert page["totals"] == [{"currency": "USD", "amount": "5.00", "amountMinor": 500, "expenseCount": 5}]
        assert len(page["items"]) <= 2
        seen += [(item["occurredOn"], item["id"]) for item in page["items"]]
        cursor = page["nextCursor"]
        if cursor is None:
            break
    assert seen == sorted(seen) and len(set(seen)) == 5


def test_large_totals_remain_exact(ledger):
    target = project(ledger)
    seed(ledger, [(f"exp_big_{index}", True, "2026-10-05", MAX_MINOR, "USD", None)
                  for index in range(3)], project_id=target["id"])
    status, payload = report(ledger, target["id"], "monthly", {"year": "2026", "month": "10", "limit": "1"})
    assert status == 200
    assert payload["totals"][0]["amountMinor"] == str(MAX_MINOR * 3)
    assert payload["totals"][0]["amount"] == "270215977642229.73"


def test_empty_period_returns_no_totals(ledger):
    target = project(ledger)
    status, payload = report(ledger, target["id"], "annual", {"year": "2020"})
    assert status == 200
    assert payload["totals"] == [] and payload["items"] == [] and payload["nextCursor"] is None


@pytest.mark.parametrize(("path", "params", "expected"), [
    ("monthly", {"year": "2026", "month": "13"}, 422),
    ("monthly", {"year": "2026"}, 422),
    ("quarterly", {"year": "2026", "quarter": "Q4"}, 422),
    ("annual", {"year": "2026", "cursor": "bad"}, 422),
    ("annual", {"year": "2026", "cursor": "2026-02-30_exp"}, 422),
    ("annual", {"year": "2026", "limit": "101"}, 422),
    ("weekly", {"year": "2026"}, 404),
])
def test_invalid_requests(ledger, path, params, expected):
    target = project(ledger)
    status, payload = report(ledger, target["id"], path, params)
    assert status == expected


def test_unknown_removed_and_malformed_projects_are_not_found(ledger):
    status, _ = report(ledger, "prj_missing", "annual", {"year": "2026"})
    assert status == 404
    status, _ = ledger.call("GET", "/api/v1/reports/projects/bad id/annual", params={"year": "2026"})
    assert status == 404
    status, _ = ledger.call("GET", "/api/v1/reports/projects/x/annual/extra", params={"year": "2026"})
    assert status == 404
    target = project(ledger)
    with ledger.store.connect() as db:
        db.execute("""UPDATE ledger_projects SET deleted_at='2026-10-09T00:00:00Z',status='archived',
            github_repo_id=NULL,github_full_name=NULL,github_organization_id=NULL WHERE id=?""",
            (target["id"],))
    status, _ = report(ledger, target["id"], "annual", {"year": "2026"})
    assert status == 404


def test_method_and_authentication(ledger):
    target = project(ledger)
    status, _ = ledger.call("POST", f"/api/v1/reports/projects/{target['id']}/annual",
                            params={"year": "2026"})
    assert status == 405
    status, _ = report(ledger, target["id"], "annual", {"year": "2026"}, headers={"Origin": "https://app.example.test"})
    assert status == 401


def _key(ledger, scopes, restrictions=None):
    import asyncio
    body = {"scopes": scopes, **({"restrictions": restrictions} if restrictions else {})}
    status, payload = asyncio.run(create_api_key(binding=ledger.binding, headers=ledger.headers,
        body=body, now=ledger.now + 3))
    assert status == 201, payload
    return {"Authorization": "Bearer " + payload["key"]}


def test_api_keys_need_expenses_read_and_project_grant(ledger):
    target = project(ledger)
    other = project(ledger, "Other")
    params = {"year": "2026"}
    status, _ = report(ledger, target["id"], "annual", params, _key(ledger, ["reports:read"]))
    assert status == 403
    status, _ = report(ledger, target["id"], "annual", params, _key(ledger, ["expenses:read"]))
    assert status == 200
    restricted = _key(ledger, ["expenses:read"], {"projectIds": [other["id"]]})
    status, payload = report(ledger, target["id"], "annual", params, restricted)
    assert (status, payload["error"]["code"]) == (403, "TARGET_FORBIDDEN")
    status, _ = report(ledger, other["id"], "annual", params, restricted)
    assert status == 200


def test_other_owner_project_is_hidden(ledger):
    with ledger.store.connect() as db:
        db.execute("""INSERT INTO ledger_projects(id,owner_id,github_repo_id,github_full_name,
            description,status,revision,created_at,updated_at)
            VALUES('prj_other','usr_other',999,'other/private','','active',1,'now','now')""")
    status, _ = report(ledger, "prj_other", "monthly", {"year": "2026", "month": "10"})
    assert status == 404
