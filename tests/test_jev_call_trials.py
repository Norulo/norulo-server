"""Lifetime trials share guarded admission and never renew on lifecycle changes."""
import asyncio
import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier

import pytest
from ledger_d1_fixture import D1ShapedSQLite, seed, seed_auth
from norulo_server.cloudflare_billing_read import read_billing
from norulo_server.cloudflare_plan_limits import PlanLimitedD1, PlanLimitError
from norulo_server.cloudflare_preview_schema import V14_SCHEMA_SQL, UPGRADE_V15_SQL, SCHEMA_OBJECTS, SCHEMA_FINGERPRINT
from test_ledger_plan_limits import account_plan, write


def test_free_get_is_read_only_and_returns_lifetime_counts(tmp_path):
    fixture, _, _ = seed(tmp_path/'free.db'); seed_auth(fixture)
    account_plan(fixture,'free')
    binding=PlanLimitedD1(D1ShapedSQLite(fixture.store),now=fixture.now)
    status, payload=asyncio.run(read_billing(binding=binding,headers={'Cookie':'nr_session=session-local'},now=fixture.now))
    assert status==200
    assert payload['ledgerUsage']['jev']=={'period':'lifetime','month':None,'usedCalls':0,'limitCalls':20,'remainingCalls':20,'currency':'USD','usedMicrousd':0,'limitMicrousd':0}
    with closing(fixture.store.connect()) as db:
        assert db.execute('SELECT COUNT(*) FROM ledger_plan_usage').fetchone()[0]==0


def test_trials_survive_paid_upgrade_downgrade_months_and_business_writes(tmp_path):
    fixture, _, _=seed(tmp_path/'lifecycle.db'); seed_auth(fixture)
    raw=D1ShapedSQLite(fixture.store); binding=PlanLimitedD1(raw,now=fixture.now)
    frozen=account_plan(fixture,'free')
    write(binding,frozen,fixture,1,kind='jev')
    frozen=account_plan(fixture,'max')
    write(binding,frozen,fixture,2,kind='jev')
    frozen=account_plan(fixture,'free')
    write(binding,frozen,fixture,3,kind='jev')
    with closing(fixture.store.connect()) as db:
        assert tuple(db.execute('SELECT jev_trial_calls,jev_reserved_microusd FROM ledger_plan_usage').fetchone())==(2,2753)
    later=fixture.now+40*86400
    write(binding,frozen,fixture,4,now=later)
    write(binding,frozen,fixture,5,kind='jev',now=later)
    with closing(fixture.store.connect()) as db:
        assert tuple(db.execute('SELECT jev_trial_calls,jev_reserved_microusd,writes FROM ledger_plan_usage').fetchone())==(3,0,1)
    from norulo_server.cloudflare_plan_limits import capacity_usage_statement, capacity_usage_payload
    row=asyncio.run(capacity_usage_statement(binding, "owner").first())
    payload=capacity_usage_payload(json.loads(frozen),[row],now=later)
    assert payload["jev"]["remainingCalls"]==17


def test_concurrent_last_trial_is_atomic_and_failed_guard_charges_nothing(tmp_path):
    fixture, _, _=seed(tmp_path/'race.db'); seed_auth(fixture)
    frozen=account_plan(fixture,'free'); binding=PlanLimitedD1(D1ShapedSQLite(fixture.store),now=fixture.now)
    write(binding,frozen,fixture,1,kind='jev')
    with fixture.store._immediate() as db: db.execute('UPDATE ledger_plan_usage SET jev_trial_calls=19')
    barrier=Barrier(2)
    class Racing(D1ShapedSQLite):
        async def batch(self, statements):
            barrier.wait(timeout=10)
            return await super().batch(statements)
    def attempt(n):
        try:
            write(PlanLimitedD1(Racing(fixture.store),now=fixture.now),frozen,fixture,n,kind='jev')
            return 'admitted'
        except PlanLimitError as e:
            assert e.code=='JEV_BUDGET_LIMIT'; return 'denied'
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt,[2,3]))==['admitted','denied']
    with fixture.store._immediate() as db:
        assert db.execute('SELECT jev_trial_calls FROM ledger_plan_usage').fetchone()[0]==20
        db.execute('UPDATE ledger_plan_usage SET jev_trial_calls=19')
    changed=account_plan(fixture,'free',currentPeriodEnd=fixture.now+3600)
    assert changed!=frozen
    with pytest.raises(Exception): write(binding,frozen,fixture,4,kind='jev')
    with closing(fixture.store.connect()) as db:
        assert db.execute('SELECT jev_trial_calls FROM ledger_plan_usage').fetchone()[0]==19
        assert db.execute('SELECT COUNT(*) FROM d1_command_guard').fetchone()[0]==0


def test_v15_additive_migration_preserves_paid_reservations_and_financial_rows():
    with closing(sqlite3.connect(':memory:')) as db:
        for sql in V14_SCHEMA_SQL: db.execute(sql)
        db.execute("INSERT INTO ledger_plan_usage VALUES('old',0,0,'2026-10',0,1,0,2753,3,300,10,1000,3000000,0,0,0,'2026-10',1)")
        before=db.execute('SELECT * FROM ledger_plan_usage').fetchone()
        for sql in UPGRADE_V15_SQL: db.execute(sql)
        after=db.execute('SELECT * FROM ledger_plan_usage').fetchone()
        assert after[:-1]==before and after[-1]==0
        objects=tuple((a,b,c,' '.join(d.split()) if d else None) for a,b,c,d in db.execute('SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name'))
        assert objects==SCHEMA_OBJECTS
        assert hashlib.sha256(json.dumps(objects,separators=(',',':')).encode()).hexdigest()==SCHEMA_FINGERPRINT
        for value in (-1,21,1.5,'bad'):
            with pytest.raises(sqlite3.IntegrityError): db.execute('UPDATE ledger_plan_usage SET jev_trial_calls=?',(value,))
