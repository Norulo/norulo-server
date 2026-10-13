"""Edits advertise only future identities that can actually be generated."""
import json
import sqlite3
from datetime import datetime, timezone

import pytest

from norulo_server.cloudflare_ledger_recurring import MAX_SCHEDULE_SEARCH_OCCURRENCES
from norulo_server.cloudflare_state_records import encode_record, record_name
from norulo_server.ledger_recurrence_calendar import following_occurrence, next_occurrence, period_key
from test_ledger_recurring import app, draft
from test_recurring_occurrence_recovery import occupied


def create(app, schedule):
    body = draft(schedule={"timezone": "Asia/Shanghai", **schedule})
    status, rule = app.call("POST", body=body)
    assert status == 201, rule
    return body, rule


def financial_rows(app):
    return {name: app.rows(name) for name in (
        "expenses", "expense_events", "expense_recurring_occurrences", "expense_recurring_pending")}


def mark_consumed(app, rule, schedule, dates):
    with app.store._immediate() as db:
        for date in dates:
            db.execute("""INSERT INTO expense_recurring_occurrences(rule_id,owner_id,period_key,
                scheduled_on,expense_id,rule_revision,created_at) VALUES(?,'owner',?,?,NULL,1,'fixture')""",
                (rule["id"], period_key(schedule, date), date.isoformat()))


@pytest.mark.parametrize("paused", [False, True])
def test_october_fifth_initial_then_thirteenth_edit_and_resume_exclude_consumed_month(app, paused):
    body, rule = create(app, {"frequency": "monthly", "day": 5, "startOn": "2026-10-05"})
    before = financial_rows(app)
    assert before["expenses"][0]["occurred_on"] == "2026-10-05"
    if paused:
        status, rule = app.call("PATCH", rule["id"], {"status": "paused"}, revision=rule["revision"])
        assert status == 200
    edited = {**body, "schedule": {**body["schedule"], "day": 13, "startOn": "2026-10-13"}}
    status, rule = app.call("PATCH", rule["id"], edited, revision=rule["revision"])
    assert status == 200 and rule["nextOccurrenceOn"] == "2026-11-13"
    assert rule["status"] == ("paused" if paused else "active")
    if paused:
        status, rule = app.call("PATCH", rule["id"], {"status": "active"}, revision=rule["revision"])
        assert status == 200 and rule["nextOccurrenceOn"] == "2026-11-13"
    assert financial_rows(app) == before
    assert app.call("GET", rule["id"]) == (200, rule)
    assert app.call("GET", params={"target": "shared"})[1]["items"] == [rule]
    assert app.rows("expense_recurring_rules")[0]["next_period_key"] == "M2026-11"


def test_pending_period_keeps_frozen_values_on_edit_and_resume(app):
    occupied(app)
    body, rule = create(app, {"frequency": "monthly", "day": 5, "startOn": "2026-10-05"})
    before = financial_rows(app)
    assert before["expense_recurring_pending"][0]["period_key"] == "M2026-10"
    status, paused = app.call("PATCH", rule["id"], {"status": "paused"}, revision=1)
    assert status == 200
    # Model an existing paused rule whose old selector is now edited within
    # the occupied month; resume must independently make the same exclusion.
    edited = {**body, "amount": "200.00", "purpose": "Changed",
        "schedule": {**body["schedule"], "day": 13, "startOn": "2026-10-13"}}
    status, saved = app.call("PATCH", rule["id"], edited, revision=paused["revision"])
    assert status == 200 and saved["nextOccurrenceOn"] == "2026-11-13"
    with app.store._immediate() as db:
        db.execute("UPDATE expense_recurring_rules SET next_occurrence_on='2026-10-13',next_period_key='M2026-10' WHERE id=?", (rule["id"],))
    status, resumed = app.call("PATCH", rule["id"], {"status": "active"}, revision=saved["revision"])
    assert status == 200 and resumed["nextOccurrenceOn"] == "2026-11-13"
    assert resumed["pendingOccurrences"] == rule["pendingOccurrences"]
    assert financial_rows(app) == before


@pytest.mark.parametrize("original,edited,expected", [
    ({"frequency": "weekly", "weekday": 1, "startOn": "2026-10-05"},
     {"frequency": "weekly", "weekday": 7, "startOn": "2026-10-11"}, "2026-10-18"),
    ({"frequency": "monthly", "day": 5, "startOn": "2026-10-05"},
     {"frequency": "monthly", "day": 31, "startOn": "2026-10-31"}, "2026-11-30"),
    ({"frequency": "quarterly", "quarterMonth": 1, "day": 5, "startOn": "2026-10-05"},
     {"frequency": "quarterly", "quarterMonth": 3, "day": 13, "startOn": "2026-12-13"}, "2027-03-13"),
    ({"frequency": "yearly", "month": 10, "day": 5, "startOn": "2026-10-05"},
     {"frequency": "yearly", "month": 12, "day": 13, "startOn": "2026-12-13"}, "2027-12-13"),
    ({"frequency": "monthly", "day": 5, "startOn": "2026-10-05"},
     {"frequency": "weekly", "weekday": 7, "startOn": "2026-10-11"}, "2026-10-11"),
])
def test_calendar_selector_edits_preserve_period_namespaces_and_clamping(app, original, edited, expected):
    body, rule = create(app, original)
    before = financial_rows(app)
    status, saved = app.call("PATCH", rule["id"], {**body,
        "schedule": {"timezone": "Asia/Shanghai", **edited}}, revision=1)
    assert status == 200 and saved["nextOccurrenceOn"] == expected
    assert financial_rows(app) == before


def test_timezone_change_uses_new_local_day_but_keeps_consumed_month(app):
    body, rule = create(app, {"frequency": "monthly", "day": 8, "startOn": "2026-10-08"})
    before = financial_rows(app)
    edited = {**body, "schedule": {**body["schedule"], "timezone": "Pacific/Pago_Pago", "day": 9, "startOn": "2026-10-09"}}
    status, saved = app.call("PATCH", rule["id"], edited, revision=1)
    assert status == 200 and saved["nextOccurrenceOn"] == "2026-11-09"
    expected = int(datetime(2026, 11, 9, 11, tzinfo=timezone.utc).timestamp())
    assert saved["nextRunAt"] == expected
    assert financial_rows(app) == before


def test_weekly_edit_crosses_iso_week_year_without_reusing_consumed_week(app):
    now = int(datetime(2026, 12, 28, 12, tzinfo=timezone.utc).timestamp())
    with app.store._immediate() as db:
        db.execute("UPDATE app_state SET payload=? WHERE name=?", (
            encode_record("sessions", "owner", {"userId": "owner", "expiresAt": now + 1000}),
            record_name("sessions", "owner")))
    body = draft(schedule={"frequency": "weekly", "weekday": 1, "timezone": "UTC", "startOn": "2026-12-28"})
    status, rule = app.call("POST", body=body, now=now)
    assert status == 201
    assert app.rows("expense_recurring_occurrences")[0]["period_key"] == "W2026-53"
    status, saved = app.call("PATCH", rule["id"], {**body,
        "schedule": {**body["schedule"], "weekday": 7, "startOn": "2027-01-03"}}, revision=1, now=now)
    assert status == 200 and saved["nextOccurrenceOn"] == "2027-01-10"
    assert app.rows("expense_recurring_rules")[0]["next_period_key"] == "W2027-01"


@pytest.mark.parametrize("resuming", [False, True])
def test_excluding_last_eligible_consumed_period_completes_without_financial_writes(app, resuming):
    body, rule = create(app, {"frequency": "monthly", "day": 5, "startOn": "2026-10-05", "endOn": "2026-10-31"})
    edited = {**body, "schedule": {**body["schedule"], "day": 13, "startOn": "2026-10-13"}}
    before = financial_rows(app)
    if resuming:
        with app.store._immediate() as db:
            db.execute("UPDATE expense_recurring_rules SET status='paused',schedule_json=? WHERE id=?", (json.dumps(edited["schedule"]), rule["id"]))
        edited = {"status": "active"}
    status, saved = app.call("PATCH", rule["id"], edited, revision=1)
    assert status == 200 and saved["status"] == "completed"
    assert saved["nextOccurrenceOn"] is saved["nextRunAt"] is None
    assert financial_rows(app) == before


@pytest.mark.parametrize("occupied_count,finite_end,expected_status", [
    (MAX_SCHEDULE_SEARCH_OCCURRENCES - 1, False, 200),
    (MAX_SCHEDULE_SEARCH_OCCURRENCES, False, 409),
    (MAX_SCHEDULE_SEARCH_OCCURRENCES, True, 200),
])
def test_search_bound_checks_final_candidate_and_never_saves_an_unproven_pointer(app, monkeypatch, occupied_count, finite_end, expected_status):
    body, rule = create(app, {"frequency": "weekly", "weekday": 7, "startOn": "2026-10-11"})
    schedule = body["schedule"]
    date, dates = next_occurrence(schedule), []
    for _ in range(occupied_count):
        dates.append(date)
        date = following_occurrence(schedule, date)
    mark_consumed(app, rule, schedule, dates)
    edited = {**body, "categoryId": None}
    if finite_end:
        edited["schedule"] = {**schedule, "endOn": dates[-1].isoformat()}
    if expected_status == 409:
        async def forbidden_assistance(*args):
            pytest.fail("An exhausted read-only search must not reserve AI usage")
        monkeypatch.setattr("norulo_server.cloudflare_recurring_assistance.resolve_recurring_category", forbidden_assistance)
    else:
        edited["categoryId"] = "cat_1"
    before = {name: app.rows(name) for name in (
        "expense_recurring_rules", "ledger_activity_events", "ledger_plan_usage",
        "expense_suggestion_budget", "expense_suggestion_events")}
    status, saved = app.call("PATCH", rule["id"], edited, revision=1)
    assert status == expected_status
    if expected_status == 409:
        assert saved["error"]["code"] == "RECURRING_SCHEDULE_SEARCH_LIMIT"
        assert {name: app.rows(name) for name in before} == before
    elif finite_end:
        assert saved["status"] == "completed" and saved["nextOccurrenceOn"] is None
    else:
        assert saved["nextOccurrenceOn"] == date.isoformat()


@pytest.mark.parametrize("race", ["revision", "occurrence", "pending", "category"])
def test_candidate_occupancy_and_existing_authority_are_rechecked_in_same_edit_batch(app, race):
    body, rule = create(app, {"frequency": "monthly", "day": 13, "startOn": "2026-10-13"})
    before = {name: app.rows(name) for name in (
        "ledger_activity_events", "ledger_plan_usage", "expenses", "expense_events")}
    before_rule = app.rows("expense_recurring_rules")[0]
    original_batch = app.raw.batch
    async def raced_batch(statements):
        if any("UPDATE expense_recurring_rules SET actor_user_id=" in statement.sql for statement in statements):
            app.raw.batch = original_batch
            with app.store._immediate() as db:
                if race == "revision":
                    db.execute("UPDATE expense_recurring_rules SET revision=revision+1 WHERE id=?", (rule["id"],))
                elif race == "category":
                    db.execute("UPDATE expense_categories SET archived_at='archived'")
                elif race == "occurrence":
                    db.execute("""INSERT INTO expense_recurring_occurrences(rule_id,owner_id,period_key,
                        scheduled_on,expense_id,rule_revision,created_at) VALUES(?,'owner','M2026-10','2026-10-13',NULL,1,'race')""", (rule["id"],))
                else:
                    db.execute("""INSERT INTO expense_recurring_pending(rule_id,owner_id,period_key,scheduled_on,
                        template_json,rule_revision,failed_code,created_at,recipient_user_id,notification_state)
                        VALUES(?,'owner','M2026-10','2026-10-13',?,1,'RECORD_LIMIT','race','owner','inbox')""",
                        (rule["id"], before_rule["template_json"]))
        return await original_batch(statements)
    app.raw.batch = raced_batch
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        app.call("PATCH", rule["id"], {**body, "amount": "200.00"}, revision=1)
    assert {name: app.rows(name) for name in before} == before
    expected = {**before_rule, "revision": 2} if race == "revision" else before_rule
    assert app.rows("expense_recurring_rules")[0] == expected


def test_candidate_probe_queries_use_existing_unique_indexes(app):
    with app.store._immediate() as db:
        details = [row[3] for row in db.execute("""EXPLAIN QUERY PLAN SELECT
            EXISTS(SELECT 1 FROM expense_recurring_occurrences WHERE rule_id=? AND period_key=?)
            OR EXISTS(SELECT 1 FROM expense_recurring_pending WHERE rule_id=? AND period_key=?)
            AS occupied""", ("rule", "M2026-10", "rule", "M2026-10"))]
    assert any("sqlite_autoindex_expense_recurring_occurrences_" in line and "(rule_id=? AND period_key=?)" in line for line in details)
    assert any("sqlite_autoindex_expense_recurring_pending_1 (rule_id=? AND period_key=?)" in line for line in details)
    assert not any("SCAN expense_recurring_" in line for line in details)
