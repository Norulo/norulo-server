"""Finite local SQLite evidence for CSV index/cursor traversal; no D1 writes."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import time
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from norulo_server.cloudflare_ledger_reports import (  # noqa: E402
    EXPORT_COLUMNS, EXPORT_PAGE_SIZE, VISIBLE_EXPENSE_TARGET_SQL,
)
from norulo_server.cloudflare_preview_schema import UPGRADE_V13_SQL, V12_SCHEMA_SQL  # noqa: E402


def traversal(db, mode):
    projection = "*" if mode == "v12_original" else ",".join(EXPORT_COLUMNS)
    hint = " INDEXED BY expenses_owner_export_date" if mode == "v13_tuple_seek" else ""
    base = f"SELECT {projection} FROM expenses{hint} WHERE owner_id=? AND deleted_at IS NULL " + VISIBLE_EXPENSE_TARGET_SQL
    order = f" ORDER BY occurred_on,id LIMIT {EXPORT_PAGE_SIZE}"
    cursor = " AND (occurred_on,id)>(?,?)" if mode == "v13_tuple_seek" else " AND (occurred_on>? OR (occurred_on=? AND id>?))"
    first_sql, next_sql = base + order, base + cursor + order
    next_params = ("owner", "2026-10-02", "exp_00000500") if mode == "v13_tuple_seek" else (
        "owner", "2026-10-02", "2026-10-02", "exp_00000500")
    plans = {"first": [row[3] for row in db.execute("EXPLAIN QUERY PLAN " + first_sql, ("owner",))],
             "cursor": [row[3] for row in db.execute("EXPLAIN QUERY PLAN " + next_sql, next_params)]}
    steps = 0
    def progress():
        nonlocal steps
        steps += 1000
        return 0
    db.set_progress_handler(progress, 1000)
    start = time.perf_counter()
    pages, count, digest = 0, 0, hashlib.sha256()
    sql, params = first_sql, ("owner",)
    try:
        while True:
            rows = db.execute(sql, params).fetchall()
            pages += 1
            for row in rows:
                digest.update((row["occurred_on"] + ":" + row["id"] + "\n").encode())
            count += len(rows)
            if len(rows) < EXPORT_PAGE_SIZE: break
            last = rows[-1]
            sql = next_sql
            params = ("owner", last["occurred_on"], last["id"]) if mode == "v13_tuple_seek" else (
                "owner", last["occurred_on"], last["occurred_on"], last["id"])
    finally:
        db.set_progress_handler(None, 0)
    return {"mode": mode, "records": count, "pages": pages,
            "seconds": round(time.perf_counter() - start, 6), "sqliteVmStepsLowerBound": steps,
            "stepResolution": 1000, "sequenceSha256": digest.hexdigest(), "queryPlans": plans}


def measure(size):
    with closing(sqlite3.connect(":memory:")) as db:
        db.row_factory = sqlite3.Row
        for sql in V12_SCHEMA_SQL: db.execute(sql)
        db.execute("INSERT INTO expense_categories(id,owner_id,name,created_at,updated_at) VALUES('cat','owner','Hosting','now','now')")
        db.executemany("""INSERT INTO expenses(id,owner_id,target_kind,category_id,occurred_on,
            amount_minor,currency,purpose,created_at,updated_at)
            VALUES(?,'owner','shared','cat',?,100,'USD','Hosting','now','now')""",
            ((f"exp_{number:08d}", f"2026-10-{number % 7 + 1:02d}") for number in range(size)))
        original = traversal(db, "v12_original")
        for sql in UPGRADE_V13_SQL: db.execute(sql)
        residual = traversal(db, "v13_or_cursor")
        fixed = traversal(db, "v13_tuple_seek")
        assert len({item["sequenceSha256"] for item in (original, residual, fixed)}) == 1
        assert all(item["records"] == size for item in (original, residual, fixed))
        assert not any("TEMP B-TREE" in detail for detail in fixed["queryPlans"]["cursor"])
        assert any("(occurred_on,id)>(?,?)" in detail for detail in fixed["queryPlans"]["cursor"])
        return {"records": size, "identicalSequence": True, "measurements": [original, residual, fixed]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", type=int, nargs="+", default=[2000, 5000, 20000])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if any(not 1 <= size <= 100000 for size in args.sizes): parser.error("sizes must be between 1 and 100000")
    evidence = {"source": "local in-memory SQLite synthetic fixtures", "sqliteVersion": sqlite3.sqlite_version,
                "scope": "Complete CSV expense SELECT traversal including project visibility; principal batches and Worker FFI excluded",
                "limitations": "VM instructions and wall times are local observations, not native D1 rows_read or a production SLA; concurrent changes retain existing live-page behavior",
                "fixtures": [measure(size) for size in args.sizes]}
    output = json.dumps(evidence, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output)
    print(output)


if __name__ == "__main__": main()
