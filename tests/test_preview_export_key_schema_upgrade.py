"""The index-only v13 upgrade preserves facts and reserves its whole build."""
import asyncio
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from norulo_server.cloudflare_preview_budget import (
    _upgrade_v13_plan, sql_write_bound, upgrade_product_schema_v12,
    upgrade_product_schema_v13, upgrade_product_schema_v11,
)
from norulo_server.cloudflare_preview_schema import (
    V13_INDEX_COUNTS as INDEX_COUNTS, V13_MIGRATIONS as MIGRATIONS, V13_SCHEMA_FINGERPRINT as SCHEMA_FINGERPRINT, V13_SCHEMA_OBJECTS as SCHEMA_OBJECTS, V13_SCHEMA_SQL as SCHEMA_SQL,
    V13_SCHEMA_VERSION as SCHEMA_VERSION, UPGRADE_V13_SQL, V12_INDEX_COUNTS, V12_SCHEMA_OBJECTS,
)
from norulo_server.cloudflare_validation_budget import BudgetError, BudgetJournal
from test_d1_validation_budget import LocalSql
from test_preview_business_erasure_schema_upgrade import facts, objects
from test_preview_recurring_pending_schema_upgrade import old as v11_old
from test_preview_schema_upgrade import SQLiteD1


@pytest.fixture
def previous(v11_old):
    db, storage, journal = v11_old
    asyncio.run(upgrade_product_schema_v12(SQLiteD1(db, journal), journal, clock=lambda: 12))
    return db, storage, journal


def upgrade(raw, journal):
    asyncio.run(upgrade_product_schema_v13(raw, journal, clock=lambda: 13))


def test_index_build_preserves_all_business_facts_and_journal_once(previous):
    db, storage, journal = previous
    columns = {table: [row[1] for row in db.execute("PRAGMA table_info(" + table + ")")]
               for table in V12_INDEX_COUNTS}
    original, before = facts(db, columns), journal.snapshot()
    raw = SQLiteD1(db, journal, attempts=None)
    asyncio.run(upgrade_product_schema_v11(raw, journal, clock=lambda: 13))
    assert raw.calls == 0 and journal.snapshot() == before
    plan = _upgrade_v13_plan(before)
    assert plan.rows_written == 256 + before["product_data"]["rows"]["expenses"] + before["product_data"]["rows"]["api_keys"]
    upgrade(raw, journal)
    after = journal.snapshot()
    assert facts(db, columns) == original and objects(db) == SCHEMA_OBJECTS
    assert after["schema_version"] == 13 and after["schema_fingerprint"] == SCHEMA_FINGERPRINT
    assert after["product_data"] == before["product_data"]
    for key in ("scope", "state_storage_version", "state_record_migration",
                "state_record_integrity_version", "state_record_integrity_request",
                "schema_upgrade", *("schema_upgrade_v" + str(n) for n in range(6, 13))):
        assert after[key] == before[key]
    assert after["requests"] == before["requests"] + 1
    assert after["reserved_written"] == before["reserved_written"] + plan.rows_written
    assert after["reserved_read"] == before["reserved_read"] + plan.rows_read
    assert after["evidence"][:len(before["evidence"])] == before["evidence"]
    assert after["schema_upgrade_v13"]["complete"] is True
    assert after["schema_upgrade_v13"]["write_execution"]["native_attempts"] == [None, None]
    assert after["active"] is None and after["stopped"] is None and raw.calls == 4
    restarted = BudgetJournal(LocalSql(storage), preview_product=True, product_operations=True)
    upgrade(raw, restarted)
    assert raw.calls == 4 and restarted.snapshot() == after


@pytest.mark.parametrize("change", ["fingerprint", "unverified", "incomplete_v12", "used",
                                   "guard", "unknown_table", "legacy_storage", "stopped"])
def test_unreviewed_index_build_does_not_dispatch(change, previous):
    db, _, journal = previous
    saved = journal.snapshot()
    if change == "fingerprint": saved["schema_fingerprint"] = "unreviewed"
    elif change == "unverified": saved["product_data_verified"] = False
    elif change == "incomplete_v12": saved["schema_upgrade_v12"] = {"complete": False}
    elif change == "used": saved["cases"]["product-schema-v12-to-v13"] = 1
    elif change == "guard": saved["product_data"]["rows"]["d1_command_guard"] = 1
    elif change == "unknown_table": saved["product_data"]["rows"]["unreviewed"] = 0
    elif change == "legacy_storage": saved["state_storage_version"] = 0
    elif change == "stopped": saved["stopped"] = "D1_OUTCOME_UNKNOWN"
    journal._save(saved)
    raw = SQLiteD1(db, journal)
    with pytest.raises(BudgetError): upgrade(raw, journal)
    assert raw.calls == 0 and journal.snapshot() == saved


@pytest.mark.parametrize("fault", ["write_timeout", "write_metadata", "readback_timeout", "native_retry"])
def test_unknown_index_build_retains_reservation_and_never_retries(fault, previous):
    db, storage, journal = previous
    before = journal.snapshot()
    options = {"write_timeout": {"fail_call": 3}, "write_metadata": {"missing_meta": 3},
               "readback_timeout": {"fail_call": 4}, "native_retry": {"attempts_by_call": {3: 2}}}[fault]
    raw = SQLiteD1(db, journal, **options)
    with pytest.raises((BudgetError, TimeoutError)): upgrade(raw, journal)
    stopped = journal.snapshot()
    assert stopped["schema_version"] == 12 and stopped["schema_upgrade_v13"]["complete"] is False
    assert stopped["stopped"] is not None
    assert stopped["reserved_written"] == before["reserved_written"] + _upgrade_v13_plan(before).rows_written
    calls = raw.calls
    restarted = BudgetJournal(LocalSql(storage), preview_product=True, product_operations=True)
    with pytest.raises(BudgetError): upgrade(raw, restarted)
    assert raw.calls == calls and restarted.snapshot() == stopped


def test_fresh_v13_matches_all_canonical_migrations_and_accounts_for_both_indexes():
    root = Path(__file__).resolve().parents[1]
    paths = [p for p in sorted((root / "cloudflare/server/migrations").glob("*.sql")) if p.name <= "0013_export_key_indexes.sql"]
    assert paths[-1].name == "0013_export_key_indexes.sql" and SCHEMA_VERSION == 13
    assert len(SCHEMA_SQL) == 56 <= 64 and len(UPGRADE_V13_SQL) == 2
    assert {item["name"]: item["sha256"] for item in MIGRATIONS} == {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    with closing(sqlite3.connect(":memory:")) as canonical, closing(sqlite3.connect(":memory:")) as compiled:
        for path in paths: canonical.executescript(path.read_text())
        for sql in SCHEMA_SQL: compiled.execute(sql)
        assert objects(canonical) == objects(compiled) == SCHEMA_OBJECTS
    assert hashlib.sha256(json.dumps(SCHEMA_OBJECTS, separators=(",", ":")).encode()).hexdigest() == SCHEMA_FINGERPRINT
    assert set(V12_SCHEMA_OBJECTS) < set(SCHEMA_OBJECTS)
    assert INDEX_COUNTS == {**V12_INDEX_COUNTS, "expenses": 5, "api_keys": 4}
    assert sql_write_bound("INSERT INTO expenses(id) VALUES(?)") == 6
    assert sql_write_bound("UPDATE expenses SET purpose=? WHERE owner_id=? AND id=?") == 11
    assert sql_write_bound("INSERT INTO api_keys(id) VALUES(?)") == 5
    assert sql_write_bound("UPDATE api_keys SET revoked_at=? WHERE id=? AND user_id=?") == 9
