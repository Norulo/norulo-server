"""Last-writer attribution follows financial CAS, not timestamps or rolling logs."""
import asyncio
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from norulo_server.cloudflare_ledger_api import handle_ledger_request
from norulo_server.cloudflare_plan_limits import PlanLimitedD1
from norulo_server.cloudflare_state_records import encode_record, record_name
from norulo_server.cloudflare_preview_schema import SCHEMA_OBJECTS, SCHEMA_SQL, SCHEMA_FINGERPRINT
from test_ledger_recurring import app, NOW, draft


def expense(app, method, body=None, *, actor="owner", item=None, revision=None, key="expense-one", headers=None, now=NOW):
    auth = {"Cookie": "nr_session=" + actor, "Origin": "https://app.example.test",
            "X-Norulo-Workspace": "owner", "Idempotency-Key": key}
    if revision is not None:
        auth["If-Match"] = f'"{revision}"'
    auth.update(headers or {})
    if "Authorization" in auth:
        auth.pop("Cookie")
    return asyncio.run(handle_ledger_request(binding=PlanLimitedD1(app.raw, policy=app.policy, now=now),
        gateway=None, method=method, path="/api/v1/expenses" + ("/" + item if item else ""),
        headers=auth, params={} if item else {"target": "shared"}, body=body, now=now))


def ordinary():
    return {"target": {"kind": "shared"}, "amount": "12.34", "currency": "USD",
            "categoryId": "cat_1", "purpose": "Hosting", "occurredOn": "2026-10-08"}


def name(app, actor, value):
    with app.store._immediate() as db:
        key = record_name("users", actor)
        user = json.loads(db.execute("SELECT payload FROM app_state WHERE name=?", (key,)).fetchone()[0])
        user.update(name=value, email="private@example.test")
        db.execute("UPDATE app_state SET payload=? WHERE name=?", (encode_record("users", actor, user), key))


def test_owner_then_member_same_second_and_stale_save_replay_keep_latest(app):
    name(app, "owner", "Owner name")
    name(app, "editor", "Member name")
    status, created = expense(app, "POST", ordinary())
    assert status == 201
    assert created["lastSource"] == {"kind": "owner", "action": "create", "userId": "owner",
        "name": "Owner name", "githubLogin": None, "via": "web"}
    changed = {**ordinary(), "note": "Member edit"}
    status, updated = expense(app, "PATCH", changed, actor="editor", item=created["id"], revision=1)
    assert status == 200 and updated["revision"] == 2
    assert updated["lastSource"]["kind"] == "member" and updated["lastSource"]["name"] == "Member name"
    assert updated["lastSource"]["action"] == "update"
    before = app.rows("expenses")
    assert expense(app, "PATCH", ordinary(), item=created["id"], revision=1)[0] == 412
    assert expense(app, "POST", ordinary())[1] == created  # Immutable creation replay.
    assert app.rows("expenses") == before
    # Source remains available after the rolling log expires and the member renames.
    with app.store._immediate() as db:
        db.execute("DELETE FROM ledger_activity_events")
    name(app, "editor", "Renamed member")
    status, loaded = expense(app, "GET", item=created["id"], actor="viewer")
    assert status == 200 and loaded["lastSource"] == updated["lastSource"]
    assert "private@example.test" not in json.dumps(loaded)
    assert expense(app, "GET")[1]["items"][0]["lastSource"] == updated["lastSource"]
    assert expense(app, "PATCH", {**ordinary(), "lastSource": created["lastSource"]},
        actor="editor", item=created["id"], revision=2)[0] == 422
    status, final = expense(app, "PATCH", ordinary(), item=created["id"], revision=2)
    assert status == 200 and final["lastSource"]["kind"] == "owner"
    assert final["lastSource"]["action"] == "update"


def test_api_key_attribution_exposes_user_without_credential_identifiers(app):
    token = "nrk_local_source_key"
    with app.store._immediate() as db:
        db.execute("INSERT INTO api_keys VALUES(?,?,?,?,?,?,?,?,?,?,?)", ("source-key", "editor", "Source",
            token[:16], hashlib.sha256(token.encode()).hexdigest(), '["expenses:write"]', None,
            '{"workspaceId":"owner","workspaceMemberRevision":1,"shared":true}', NOW, None, None))
    status, saved = expense(app, "POST", ordinary(), actor="editor", headers={"Authorization": "Bearer " + token})
    assert status == 201
    assert saved["lastSource"]["kind"] == "member" and saved["lastSource"]["via"] == "api_key"
    assert saved["lastSource"]["userId"] == "editor"
    assert token not in json.dumps(saved) and hashlib.sha256(token.encode()).hexdigest() not in json.dumps(saved)


@pytest.mark.parametrize("start,background", [("2026-10-08", False), ("2026-10-09", True)])
def test_recurring_creation_and_later_human_edit_replace_source(app, start, background):
    status, _ = app.call("POST", body=draft(start=start), actor="editor")
    assert status == 201
    if background:
        assert app.tick(now=NOW + 86400)["created"] == 1
        with app.store._immediate() as db:
            for actor in ("owner", "editor"):
                db.execute("UPDATE app_state SET payload=? WHERE name=?", (
                    encode_record("sessions", actor, {"userId": actor, "expiresAt": NOW+90000}), record_name("sessions", actor)))
    rows = app.rows("expenses")
    assert len(rows) == 1
    status, generated = expense(app, "GET", item=rows[0]["id"])
    assert status == 200
    assert generated["lastSource"] == {"kind": "recurring", "action": "create", "userId": None,
        "name": None, "githubLogin": None, "via": "schedule"}
    status, edited = expense(app, "PATCH", ordinary(), actor="editor", item=generated["id"], revision=1, now=NOW+86400 if background else NOW)
    assert status == 200 and edited["lastSource"]["kind"] == "member"
    assert edited["lastSource"]["action"] == "update"


def test_v14_schema_matches_canonical_and_old_rows_stay_unknown():
    from norulo_server.cloudflare_preview_schema import V14_SCHEMA_SQL as SCHEMA_SQL, V14_SCHEMA_OBJECTS as SCHEMA_OBJECTS, V14_SCHEMA_FINGERPRINT as SCHEMA_FINGERPRINT
    root = Path(__file__).resolve().parents[1]
    paths = sorted(p for p in (root / "cloudflare/server/migrations").glob("*.sql") if p.name <= "0014_expense_last_source.sql")
    with closing(sqlite3.connect(":memory:")) as db, closing(sqlite3.connect(":memory:")) as compiled:
        for path in paths[:-1]: db.executescript(path.read_text())
        db.execute("INSERT INTO expense_categories(id,owner_id,name,created_at,updated_at) VALUES('cat','old','Hosting','old','old')")
        db.execute("INSERT INTO expenses(id,owner_id,target_kind,category_id,occurred_on,amount_minor,currency,purpose,created_at,updated_at) VALUES('exp','old','shared','cat','2026-10-08',1234,'USD','Hosting','old','old')")
        before = db.execute("SELECT * FROM expenses").fetchone()
        db.executescript(paths[-1].read_text())
        after = db.execute("SELECT * FROM expenses").fetchone()
        assert after[:-1] == before and after[-1] is None
        for sql in SCHEMA_SQL: compiled.execute(sql)
        def objects(connection):
            return tuple((kind,name,table,' '.join(sql.split()) if sql else None)
                for kind,name,table,sql in connection.execute("SELECT type,name,tbl_name,sql FROM sqlite_schema WHERE name NOT GLOB 'sqlite_*' OR name GLOB 'sqlite_autoindex_*' ORDER BY type,name"))
        assert objects(db) == objects(compiled) == SCHEMA_OBJECTS
        assert hashlib.sha256(json.dumps(SCHEMA_OBJECTS, separators=(",", ":")).encode()).hexdigest() == SCHEMA_FINGERPRINT
