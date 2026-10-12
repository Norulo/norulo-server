"""Sessions expire at expiresAt for reads, writes and final SQL authority fences."""
import asyncio
import sqlite3
from contextlib import closing

import pytest

from test_ledger_recurring import NOW, app
from norulo_server.cloudflare_github_identity_http import _session_user
from norulo_server.cloudflare_ledger_api import _write_guard, handle_ledger_request
from norulo_server.cloudflare_plan_limits import PlanLimitedD1
from norulo_server.cloudflare_principal import PrincipalAuthError, _principal, _resource_auth_snapshot
from norulo_server.cloudflare_state_records import encode_record, record_name


HEADERS = {"Cookie": "nr_session=owner", "Origin": "https://app.example.test"}


def set_expiry(app, expires):
    with closing(app.store.connect()) as db:
        db.execute("UPDATE app_state SET payload=? WHERE name=?", (
            encode_record("sessions", "owner", {"userId": "owner", "expiresAt": expires}),
            record_name("sessions", "owner")))
        db.commit()


def snapshot(app):
    return {table: app.rows(table) for table in (
        "app_state", "expense_categories", "api_keys", "ledger_plan_usage", "d1_command_guard")}


@pytest.mark.parametrize("offset,authenticated", [(-1, False), (0, False), (1, True)])
def test_identity_and_ledger_reads_use_same_exclusive_expiry(app, offset, authenticated):
    set_expiry(app, NOW + offset)
    before = snapshot(app)
    assert (asyncio.run(_session_user(app.raw, HEADERS, NOW))[1] is not None) is authenticated
    result = asyncio.run(handle_ledger_request(
        binding=PlanLimitedD1(app.raw, policy=app.policy, now=NOW), gateway=None,
        method="GET", path="/api/v1/categories", params={}, headers=HEADERS, body=None, now=NOW))
    assert result[0] == (200 if authenticated else 401)
    assert snapshot(app) == before


@pytest.mark.parametrize("path,body", [
    ("/api/v1/categories", {"name": "Should not be created"}),
    ("/api/v1/account/jev", {"enabled": False}),
    ("/api/v1/account/expense-retention", {"autoRemoveOldestExpense": True}),
])
def test_exactly_expired_session_cannot_authorize_resource_read_or_write(app, path, body):
    set_expiry(app, NOW)
    before, batches = snapshot(app), app.raw.batch_count
    result = asyncio.run(handle_ledger_request(
        binding=PlanLimitedD1(app.raw, policy=app.policy, now=NOW), gateway=None,
        method="POST" if path.endswith("/categories") else "PATCH", path=path, params={},
        headers={**HEADERS, "If-Match": '"1"'}, body=body, now=NOW))
    assert result == (401, {"error": {"code": "UNAUTHENTICATED"}})
    # Authentication may look up a credential, but no resource batch is admitted.
    assert app.raw.batch_count == batches and snapshot(app) == before


def test_read_snapshot_rechecks_exclusive_expiry_without_resource_acceptance(app):
    set_expiry(app, NOW)
    user, _ = asyncio.run(_principal(app.raw, HEADERS, scope="profile:read", now=NOW - 1))
    proof = {}
    auth, validate = _resource_auth_snapshot(app.raw, HEADERS, user, {}, NOW, "profile:read", proof)
    parts = asyncio.run(app.raw.batch(auth))
    with pytest.raises(PrincipalAuthError) as failure:
        validate([part.results for part in parts])
    assert failure.value.status == 401 and proof == {}


def test_atomic_write_guard_rejects_expiry_even_with_a_previously_valid_proof(app):
    set_expiry(app, NOW)
    user, _ = asyncio.run(_principal(app.raw, HEADERS, scope="profile:read", now=NOW - 1))
    proof = {}
    auth, validate = _resource_auth_snapshot(app.raw, HEADERS, user, {}, NOW - 1, "profile:read", proof)
    parts = asyncio.run(app.raw.batch(auth))
    validate([part.results for part in parts])
    before = snapshot(app)
    with pytest.raises(sqlite3.IntegrityError):
        asyncio.run(app.raw.batch([
            _write_guard(app.raw, proof, user["id"], NOW),
            app.raw.prepare("UPDATE expense_categories SET name='Expired mutation' WHERE id='cat_1'"),
            app.raw.prepare("DELETE FROM d1_command_guard")]))
    assert snapshot(app) == before
