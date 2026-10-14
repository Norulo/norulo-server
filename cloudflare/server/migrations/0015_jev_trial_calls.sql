-- Persistent once-per-Owner Free trial. Paid monthly reservations remain unchanged.
-- One additional field in the existing atomic quota write; no GET writes or backfill.
ALTER TABLE ledger_plan_usage ADD COLUMN jev_trial_calls INTEGER NOT NULL DEFAULT 0
  CONSTRAINT plan_jev_trial_limit CHECK(typeof(jev_trial_calls)='integer' AND jev_trial_calls BETWEEN 0 AND 20);
