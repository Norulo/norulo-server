"""Shared filters for ledger detail and reports."""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Mapping
import csv
import io


EXPORT_COLUMNS = ("id", "target_kind", "project_id", "occurred_on", "amount_minor",
                  "currency", "category_id", "purpose", "note", "quantity_decimal", "unit")
EXPORT_HEADER = ("id", "target", "projectId", "occurredOn", "amountMinor", "currency",
                 "categoryId", "purpose", "note", "quantity", "unit")
EXPORT_PAGE_SIZE = 250

# Archived projects retain ordinary financial history. Removed projects retain
# their records only in the background and must not contribute to any public
# detail, report or CSV page, including requests without an explicit project.
VISIBLE_EXPENSE_TARGET_SQL = """AND (expenses.target_kind='shared' OR
    (expenses.target_kind='project' AND EXISTS(SELECT 1 FROM ledger_projects AS visible_project
        WHERE visible_project.owner_id=expenses.owner_id AND visible_project.id=expenses.project_id
            AND visible_project.deleted_at IS NULL)))"""


class CsvExport:
    """A page-at-a-time CSV body. The Worker turns chunks into a ReadableStream."""

    def __init__(self, first_rows, next_page):
        self.first_rows = first_rows
        self.next_page = next_page

    async def chunks(self):
        output = io.StringIO(newline="")
        csv.writer(output).writerow(EXPORT_HEADER)
        yield output.getvalue()
        rows = self.first_rows
        while rows:
            output = io.StringIO(newline="")
            writer = csv.writer(output)
            for row in rows:
                writer.writerow([_csv_cell(row[column]) for column in EXPORT_COLUMNS])
            yield output.getvalue()
            if len(rows) < EXPORT_PAGE_SIZE:
                break
            last = rows[-1]
            rows = await self.next_page(last["occurred_on"], last["id"])

from .cloudflare_ledger_api import _error, _page_inputs, _param, _valid_resource_id
from .cloudflare_ledger_auth import ledger_principal, target_allowed
from .cloudflare_ledger_filters import restriction_filters, merge_page
from .cloudflare_principal import PrincipalAuthError
from .ledger_money_totals import AGGREGATE_SQL, aggregate_minor, public_minor


def expense_filter(params: Mapping[str, object], *, paged: bool = False):
    target = _param(params, "target") or "all"
    project_id = _param(params, "projectId")
    category_id = _param(params, "categoryId")
    currency = _param(params, "currency")
    start, end = _param(params, "from"), _param(params, "to")
    if target not in {"all", "project", "shared"} or (project_id and target == "shared"):
        raise ValueError("target")
    if any(value and not _valid_resource_id(value) for value in (project_id, category_id)):
        raise ValueError("resource")
    if currency and not re.fullmatch(r"[A-Z]{3}", currency):
        raise ValueError("currency")
    for value in (start, end):
        if value and (not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value)
                      or date.fromisoformat(value).isoformat() != value):
            raise ValueError("date")
    if start and end and start >= end:
        raise ValueError("range")
    clauses, values = [VISIBLE_EXPENSE_TARGET_SQL], []
    if target != "all":
        clauses.append("AND target_kind=?")
        values.append(target)
    if project_id:
        clauses.append("AND project_id=?")
        values.append(project_id)
    if category_id:
        clauses.append("AND category_id=?")
        values.append(category_id)
    if start:
        clauses.append("AND occurred_on>=?")
        values.append(start)
    if end:
        clauses.append("AND occurred_on<?")
        values.append(end)
    if currency:
        clauses.append("AND currency=?")
        values.append(currency)
    if paged:
        limit, cursor = _page_inputs(params)
        return " ".join(clauses), values, limit, cursor
    return " ".join(clauses), values


def _csv_cell(value):
    text = "" if value is None else str(value)
    stripped = text.lstrip(" \t\r\n")
    return "'" + text if stripped.startswith(("=", "+", "-", "@")) else text


async def handle_report_request(*, binding, method, path, headers, params, now):
    is_export = path == "/api/v1/expenses/export"
    name = path.removeprefix("/api/v1/reports/")
    if name.startswith("projects/"):
        parts = name.split("/")
        if len(parts) != 3:
            return _error(404, "NOT_FOUND")
        return await handle_project_period_report(binding=binding, method=method,
            project_id=parts[1], report=parts[2], headers=headers, params=params, now=now)
    if not is_export and name not in {"summary", "timeseries", "categories"}:
        return None
    if method != "GET":
        return _error(405, "METHOD_NOT_ALLOWED")
    try:
        where, values = expense_filter(params)
        bucket = _param(params, "bucket") or "day"
        if name == "timeseries" and bucket not in {"day", "month"}:
            raise ValueError("bucket")
    except ValueError:
        return _error(422, "INVALID_INPUT")
    scope = "expenses:read" if is_export else "reports:read"
    try:
        user, restrictions, auth, validate = await ledger_principal(
            binding=binding, headers=headers, scope=scope, now=now)
        if (_param(params, "target") == "shared" and not restrictions.get("shared")) or (
                _param(params, "projectId") and not target_allowed(
                    restrictions, "project", _param(params, "projectId"))):
            return _error(403, "TARGET_FORBIDDEN")
        filters = restriction_filters(restrictions)
        if is_export:
            # Keep every page on the owner/date/id index. More selective filter
            # indexes can require a full sort again for every page, whereas this
            # traversal visits each remaining owner row at most once in an
            # unchanged ledger, including restricted and filtered exports.
            export_sql = ("SELECT " + ",".join(EXPORT_COLUMNS) +
                          " FROM expenses INDEXED BY expenses_owner_export_date "
                          "WHERE owner_id=? AND deleted_at IS NULL ")
            suffix = f" ORDER BY occurred_on,id LIMIT {EXPORT_PAGE_SIZE}"
            base_sql = export_sql + where
        else:
            bucket_sql = "substr(occurred_on,1,7)" if bucket == "month" else "occurred_on"
            if name == "summary":
                dimensions = "target_kind,project_id,currency"
                projection = "target_kind,project_id,NULL AS category_id,NULL AS bucket,currency"
            elif name == "timeseries":
                dimensions = f"target_kind,project_id,{bucket_sql},currency"
                projection = f"target_kind,project_id,NULL AS category_id,{bucket_sql} AS bucket,currency"
            else:
                dimensions = "target_kind,project_id,category_id,currency"
                projection = "target_kind,project_id,category_id,NULL AS bucket,currency"
            base_sql = (f"SELECT {projection},{AGGREGATE_SQL} FROM expenses "
                        "WHERE owner_id=? AND deleted_at IS NULL " + where)
            suffix = f" GROUP BY {dimensions}"
        # Each chunk shares the same credential/owner/member snapshot. Empty
        # grants still validate auth, without an impossible indexed CSV SELECT.
        parts = await binding.batch([*auth, *[binding.prepare(base_sql + restricted + suffix).bind(
            user["id"], *values, *restricted_values) for restricted, restricted_values in filters]])
        validate([part.results for part in parts[:len(auth)]])
        rows = (merge_page(parts[len(auth):], EXPORT_PAGE_SIZE, columns=("occurred_on", "id")) if is_export
                else [row for part in parts[len(auth):] for row in part.results])
    except PrincipalAuthError as exc:
        return _error(exc.status, exc.code)
    if is_export:
        async def next_page(after_date, after_id):
            # A tuple comparison seeks directly past the previous index key;
            # the equivalent OR predicate can rescan its prefix on every page.
            # Place the cursor before any optional date lower bound so SQLite
            # chooses the cursor as its seek bound even for a dated export.
            page_sql = export_sql + " AND (occurred_on,id)>(?,?) " + where
            commands = [*auth, *[binding.prepare(page_sql + restricted + suffix).bind(user["id"], after_date,
                after_id, *values, *restricted_values) for restricted, restricted_values in filters]]
            page = await binding.batch(commands)
            validate([part.results for part in page[:len(auth)]])
            return merge_page(page[len(auth):], EXPORT_PAGE_SIZE, columns=("occurred_on", "id"))
        return 200, CsvExport(rows, next_page)
    groups = {}
    for row in rows:
        target = row["target_kind"]
        project_id = row["project_id"] if target == "project" else None
        if name == "summary":
            keys = [(target, project_id, None, None, row["currency"]),
                    ("account", None, None, None, row["currency"])]
            if target == "project":
                keys.append(("project", None, None, None, row["currency"]))
        elif name == "timeseries":
            time_bucket = row["bucket"]
            keys = [(target, project_id, None, time_bucket, row["currency"])]
        else:
            keys = [(target, project_id, row["category_id"], None, row["currency"])]
        for key in keys:
            groups[key] = groups.get(key, 0) + aggregate_minor(row)
    return 200, {"groups": [{"target": target, "projectId": project_id,
        "categoryId": category_id, "bucket": time_bucket, "currency": currency,
        "amountMinor": public_minor(amount)} for (target, project_id, category_id, time_bucket, currency), amount
        in sorted(groups.items(), key=lambda item: tuple(part or "" for part in item[0]))]}


PERIOD_REPORTS = {"monthly": "month", "quarterly": "quarter", "annual": "year"}
_PERIOD_CURSOR = re.compile(r"([0-9]{4}-[0-9]{2}-[0-9]{2})_([A-Za-z0-9_-]{1,120})")


def project_period(granularity: str, params: Mapping[str, object]):
    """Return the inclusive business-date bounds of one calendar period.

    occurred_on is a user-entered calendar date without a time or zone, so a
    period is bounded by dates alone. The inclusive last day keeps 9999-12-31
    reachable without an unrepresentable exclusive 10000-01-01 bound.
    """
    raw_year = _param(params, "year")
    if not re.fullmatch(r"[0-9]{4}", raw_year) or raw_year == "0000":
        raise ValueError("year")
    year = int(raw_year)
    period = {"granularity": granularity, "year": year}
    if granularity == "month":
        raw = _param(params, "month")
        if not re.fullmatch(r"[0-9]{1,2}", raw) or not 1 <= int(raw) <= 12:
            raise ValueError("month")
        first_month = last_month = period["month"] = int(raw)
    elif granularity == "quarter":
        raw = _param(params, "quarter")
        if not re.fullmatch(r"[1-4]", raw):
            raise ValueError("quarter")
        period["quarter"] = int(raw)
        first_month, last_month = 3 * int(raw) - 2, 3 * int(raw)
    else:
        first_month, last_month = 1, 12
    start = date(year, first_month, 1)
    end = date(year, 12, 31) if last_month == 12 else (
        date(year, last_month + 1, 1) - timedelta(days=1))
    period.update(startOn=start.isoformat(), endOn=end.isoformat())
    return period


def _period_page(params: Mapping[str, object]):
    raw_limit = _param(params, "limit")
    limit, _ = _page_inputs({"limit": raw_limit} if raw_limit else {})
    cursor = _param(params, "cursor")
    if not cursor:
        return limit, None
    match = _PERIOD_CURSOR.fullmatch(cursor)
    if match is None:
        raise ValueError("cursor")
    try:
        if date.fromisoformat(match.group(1)).isoformat() != match.group(1):
            raise ValueError("cursor")
    except ValueError:
        raise ValueError("cursor") from None
    return limit, (match.group(1), match.group(2))


async def handle_project_period_report(*, binding, method, project_id, report, headers, params, now):
    from .cloudflare_ledger_expenses import _decimal_amount, _dto
    if report not in PERIOD_REPORTS or not _valid_resource_id(project_id):
        return _error(404, "NOT_FOUND")
    if method != "GET":
        return _error(405, "METHOD_NOT_ALLOWED")
    try:
        period = project_period(PERIOD_REPORTS[report], params)
        limit, cursor = _period_page(params)
    except ValueError:
        return _error(422, "INVALID_INPUT")
    # Itemized expenses are returned beside the totals, so the read follows the
    # expenses:read scope that also governs CSV export of the same records.
    try:
        user, restrictions, auth, validate = await ledger_principal(
            binding=binding, headers=headers, scope="expenses:read", now=now)
        if not target_allowed(restrictions, "project", project_id):
            return _error(403, "TARGET_FORBIDDEN")
        # Both statements use the owner/target/project/date index. Totals cover
        # the whole period on every page; only the itemized list is paginated.
        scope_sql = ("FROM expenses WHERE owner_id=? AND deleted_at IS NULL AND target_kind='project' "
                     "AND project_id=? AND occurred_on>=? AND occurred_on<=?")
        bounds = (user["id"], project_id, period["startOn"], period["endOn"])
        seek_sql, seek_values = (" AND (occurred_on,id)>(?,?)", cursor) if cursor else ("", ())
        parts = await binding.batch([*auth,
            binding.prepare("""SELECT id,name,status FROM ledger_projects
                WHERE owner_id=? AND id=? AND deleted_at IS NULL""").bind(user["id"], project_id),
            binding.prepare(f"SELECT currency,COUNT(*) AS expense_count,{AGGREGATE_SQL} {scope_sql} "
                            "GROUP BY currency ORDER BY currency").bind(*bounds),
            binding.prepare(f"SELECT * {scope_sql}{seek_sql} ORDER BY occurred_on,id LIMIT ?").bind(
                *bounds, *seek_values, limit + 1)])
        validate([part.results for part in parts[:len(auth)]])
    except PrincipalAuthError as exc:
        return _error(exc.status, exc.code)
    projects, totals, items = (part.results for part in parts[len(auth):])
    if not projects:
        return _error(404, "NOT_FOUND")
    page = items[:limit]
    project = projects[0]
    return 200, {
        "project": {"id": project["id"], "name": project["name"], "status": project["status"]},
        "period": period,
        "totals": [{"currency": row["currency"],
                    "amount": _decimal_amount(aggregate_minor(row), row["currency"]),
                    "amountMinor": public_minor(aggregate_minor(row)),
                    "expenseCount": row["expense_count"]} for row in totals],
        "items": [_dto(row) for row in page],
        "nextCursor": page[-1]["occurred_on"] + "_" + page[-1]["id"] if len(items) > limit else None,
    }
