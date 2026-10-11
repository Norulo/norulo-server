# Norulo production operations

This runbook covers norulo.com and api.norulo.com only. Preview and Workers.dev
remain disabled. Dated records in [production readiness](validation/production-readiness-2026-10-10.md)
identify what was actually published/read back; source configuration or a local
test does not establish the deployed version.

## Free public use and remaining acceptance

The user has confirmed successful real GitHub sign-in, email verification-code
delivery/login and ordinary expense recording. Repository installation,
credential/session refresh, account linking, shared-team flows, a complete ledger
journey, live recurring financial execution and native Worker real-provider AI
HTTPS remain separately unverified. The completed 36-case direct HTTPS AI quality
journal must not be repeated to claim native Worker acceptance.

Real payments are deferred. With explicitly empty Creem products, the reviewed
/billing/plan implementation returns a public Free catalog without requiring a
provider price row. Free is priced at zero and uses actual configured allowances:
by default 3 projects, 100 expense records, 10 writes/minute, 1,000 writes/month
and a zero AI allowance. Pro/Max prices are null, their month/year products are
unconfigured, provider billing is disabled and checkout is unavailable. It does
not grant a paid identity or replace an existing account's payment facts/usage.

The disabled path does not call a provider or read/write the persisted paid
catalog. Personal cookie-account data/usage still require the authorization
snapshot; anonymous/API-key pricing does not disclose them. Malformed, duplicate
or invalid products fail closed instead of becoming deliberate Free-only mode.
Valid configured paths retain provider-price and signed webhook controls. The
checked source includes the Free-only behavior and logging policy; confirm
their deployed state in the subsequent dated release readback.

## Preserve on every upload

| Resource or control | Required preservation |
| --- | --- |
| Production D1 | norulo-ledger-production, c41a1ab7-dffa-4c5d-a213-25f1bb6c78c5; verified schema v12 |
| Email admission | EMAIL_ADMISSION / EmailAdmission, namespace 6588312f00f74840a37463e72a2d75eb |
| Recurrence | RECURRING_SCHEDULER / RecurringScheduler, namespace b3f41def1906481e9c72662debf4b505; existing Root/Owner scopes and journal state |
| System sender | EMAIL restricted to login@auth.norulo.com; authenticated sending domain and existing contact Email Routing retained |
| Worker Secrets | NORULO_GITHUB_CLIENT_SECRET, NORULO_GITHUB_TOKEN_KEY, NORULO_EMAIL_CODE_SECRET and TYPESAFE_API_KEY, inherited by name without reading values |
| Environment credential | Existing CLOUDFLARE_API_TOKEN network binding; never clear or duplicate its value |
| Activation | Runtime D1, email, both AI flags and recurrence enabled through all four reviewed activation overlays; checked-in five flags remain 0 |
| Limits and schedule | cpu_ms=300000, subrequests=9000; exactly one cron, 10 16 * * * UTC |
| Exposure | Exact production domains, preview URLs/Workers.dev disabled; no preview release |

Use the [deployment command](../cloudflare/server/README.md#production-recurring-release)
and preserve every overlay/Secret. Never replay applied migrations as a release
check. Verify actual bindings, limits, flags, schedules and versions through
finite read-only control-plane requests. Supported limits do not confirm Paid
billing subscription status.

## Daily scheduling and monitoring

Cron runs daily at 00:10 Asia/Shanghai, 16:10 UTC on the preceding date. The next
natural tick after this 2026-10-11 preparation is 2026-10-12 00:10 Asia/Shanghai /
2026-10-11 16:10 UTC. Do not invoke production cron manually for acceptance.
Per-rule timezone determines stored UTC due time; daily scanning retains the
original period date and may delay other timezones by nearly 24 hours. Existing
weekly/monthly/quarterly/yearly rule frequencies are unchanged.

Cloudflare Past Events success means the platform invocation completed. It does
not prove zero failed Owners, no backlog or complete D1 metrics. Inspect the safe
scheduler aggregate too: failedOwners, backlog, selectedOwners, ownerRpcs,
handled/result counts and metrics completeness, with rows_read/rows_written
where available. Missing/incomplete metrics are unknown, never successful zeros.
Bounded progress/backlog may require another natural scan; it does not authorize
retrying an uncertain posting.
The production scheduled entry now emits a fixed STARTED receipt and a bounded
terminal receipt around the existing single Root RPC. Partial Owner failures,
incomplete metrics and malformed success shapes emit FAILED without changing
the original return/exception or financial behavior. CANCELLED preserves the
original cancellation. BUSY/DISABLED Root responses emit NOT_COMPLETED and retain
the original rejected-result exception. A deduplicated skip emits COMPLETED with
healthy=false; it does not claim new work. Top-level disabled flags remain silent.
Use Cron Events and fixed-code receipts together. An absent receipt is an
unverified observation; it does not prove the schedule did not run.

The checked publication logging policy is limited:

| Service | Logging policy | Limits of the observation |
| --- | --- | --- |
| Server | 100% sampling of emitted safe scheduler aggregates; query strings redacted; invocation logs/traces disabled | Not a complete HTTP request log, raw financial audit or automatic alert delivery |
| Web | 1% sampling of fixed-code upstream/service transport diagnostics; query strings redacted; invocation logs/traces disabled | Not every HTTP error, raw provider response or outage occurrence is captured |

Never log cookies, authorization headers, OAuth codes/state, private emails,
expense text, raw provider responses or Secret values. Aggregate fields stay
bounded and omit Owner identifiers. Verify configuration acceptance after
publication before relying on log persistence.

The existing Cloudflare billing alert is retained. Three Custom Alert definitions
are prepared in [the alert validation record](validation/recurring-alert-rules-2026-10-11.json).
All three exact SQL hashes returned HTTP 200 and one numeric value in this
account; 43 UTC boundary scenarios passed independently offline. The queries
scope logs.workersLogs to this account and norulo-server-production, match only
fixed code keys and return COUNT results without GROUP BY, including empty input.

| Rule | Signal | Query interval | Repeat notification |
| --- | --- | --- | --- |
| Execution failure | FAILED, CANCELLED or NOT_COMPLETED in the previous hour | 10 minutes | 1 hour |
| Backlog or blocked rules | BACKLOG or BLOCKED in the previous day | 10 minutes | 24 hours |
| Completion receipt missing | No COMPLETED/FAILED/CANCELLED receipt since the latest 16:10 UTC slot, after 30 minutes of grace | 10 minutes | 6 hours |

The initial missing-receipt check arms at 2026-10-11 16:40 UTC, assuming this
logging release is live before that day's 16:10 slot. Later deployments must
move the first expected slot before enabling a new detector. Each new daily slot
resets its grace; previous-slot receipts do not resolve it. Busy/disabled receipts
are failures but do not stand in for completion. Failure/cancellation does resolve
the observation gap while its separate failure rule still reports the incident.
The warning is a historical 24-hour signal, not a live remaining-work count.

Cloudflare Custom Alerts use alert_type=custom_analytics, raw SQL in
filters.selectors, source=[sql_api], execution_interval=[10m], threshold > 0 and
top-level alert_interval for repeat delivery. Do not submit time_range_mode; it
is a dashboard-only field. A conditional if in a timestamp lower bound was
rejected by the actual API; the final query uses two bounded OR branches and a
typed toDate constant for the initial UTC cutoff. Dashboard eligibility and
offline SQLite semantics alone do not establish actual SQL acceptance.

No new notification policy is enabled yet: the recipient is awaiting explicit
user designation. Existing routing destinations and billing-alert recipients are
not inferred as authorization for operational email. After designation, create
these three policies with email=[{id:the-approved-address}], enabled=true; read
back every query/filter/interval/destination and preserve existing policies.
Do not send a test notification or manufacture a production failure for testing.
Account Notifications Edit is only a requirement if the actual write is denied;
the current successful metadata/query reads do not prove write permission.

This monitor adds no business Cron, D1 heartbeat or financial retry. The 30-minute
grace is operational buffering, not a log-delivery SLA. Adaptive sampling,
ingestion delay and disabled logging can also cause missing observations. A
missing alert must never authorize replaying an uncertain expense. Actual email
delivery and the first natural financial event remain separate acceptance items.

For the first natural tick, use this read-only checklist:

1. Confirm the one daily cron, expected version, bindings and strict limits.
2. Check platform status and scheduler aggregate together; record failedOwners,
   backlog, completeness and metered costs separately.
3. If a real rule was due, compare existing occurrence/expense/audit state through
   authorized reads. Do not create production test rules or expenses.
4. If no real rule was due, record idle acceptance only, without claiming financial
   posting or provider notification was exercised.
5. Mark missing receipts as unverified and inspect the platform event/code path;
   do not infer that no execution occurred. Treat an unknown financial outcome
   or unresolved Root stop as an incident, preserving state as described below.

## Financial incidents and recovery

Stop new financial work when outcomes are uncertain. For a global incident, use
a reviewed production pause of recurrence/new writes, retaining resources,
namespaces and Secrets; an affected Owner's durable stop remains intact. Capture
safe codes, timestamps, release/configuration identities and available metrics.
Inspect existing financial/audit/idempotency state through bounded authorized
reads before deciding any repair.

The two uncertainty boundaries differ. A known native financial uncertainty
permanently stops its Owner while others may continue. An RPC transport exception
advances only if read-only progress proves the exact chunk settled; otherwise
new launches stop, started siblings are awaited and Root retains a permanent
global unknown stop. Never automatically retry, refund an uncertain reservation,
reset scopes/stopped markers, reinterpret completed_hour as a day, replace a
namespace or add a general reset/quarantine endpoint.

D1 recovery does not rewind RecurringScheduler/EmailAdmission SQLite state,
issued email/session effects, external provider actions or payment facts. An
older D1 snapshot with a later DO journal can skip work; a reset journal with
committed data can duplicate work. Preserve evidence, reconcile those boundaries
and obtain a concrete reviewed recovery decision before restore/financial repair.
A code rollback also does not restore these stores.

## D1 recovery readiness and cost

Seven read-only metadata requests returned HTTP 200 during this preparation.
The production D1 Time Travel bookmark is available and retained only in a
private local file with mode 0600; its value is not in Git or this runbook. These
checks performed no SQL, writes, restore, manual cron or business mutation.
Bookmark availability proves access to that recovery reference, not a tested
restore or complete independent backup/reconciliation workflow.

[Cloudflare Time Travel](https://developers.cloudflare.com/d1/reference/time-travel/)
documents 7 days on Free and 30 days on Paid. Billing subscription status is
unconfirmed; plan conservatively around 7 days until actual retention is known.
Do not assume 30 days from supported limits, standard usage model or metadata
success. Do not run a production restore drill or print/copy a bookmark to public
evidence.

Development, regression, load fixtures and restore experimentation belong in
local D1/SQLite. Remote initialization is limited to necessary unapplied canonical
migrations, executed once with native metrics/progress recorded. No production
test writes, synthetic fixtures, repeated migration setup or automatic unknown
write retries are permitted. Do not invent a daily/monthly D1 writing allowance.
Whole local fixture/setup costs, scheduler-window costs and successful-operation
metadata are separate; missing metrics cannot form a claimed complete bill.

Before operational readiness is complete, enable the prepared detectors with
explicit recipients and verify their readback, then observe the natural event. Real scheduled financial posting,
provider notification, native Worker paid AI, shared-team flows and GitHub App
installation remain separate acceptance items. None requires real charges or
remote synthetic business writes to prepare safely.
