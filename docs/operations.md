# Rounded Jev call allowances, 2026-10-14

Production is verified at 100% traffic. Server source
`2fc9b48265e6cd4afff8f2b26457ddceb888af60` is Worker version
`45411608-40ae-4dee-a389-80d3200f2a5e`; Web source
`fdc1b012d3419f628e8d475bbb24025b203d9202` is Worker version
`cfc1a4a5-fc60-4c25-882e-5f6bde9edbcc`. Subsequent release-evidence commits do not
change application code.

Pro now has 1,000 Jev calls per UTC month; Max has 4,000. Annual plans get
the same monthly calls without rollover. Free retains 20 lifetime trials per
Owner, shared with members and API keys. Prices, expense capacities and project
capacities are unchanged. Billing displays used/total/remaining calls and all
six-language guides and API artifacts describe the rounded limits.

`jevMonthlyCalls` explicitly controls entitlements and atomic admission. Internal
$3/$12 funding safeguards can only lower it; unused funding grants no extra
calls. Prior paid usage and Free trial use are retained. Usage above the new
limit permits ordinary manual writes but no further model dispatch. The local
boundary tests cover the final permitted call, denial of the next attempt,
existing usage and annual entitlements. No migration is required.

The full Server run passed 3,293 tests and 107 subtests, with one
local HTTP transport test denied by the initial process network sandbox. With
loopback networking enabled, that test passed. All 3,294 Server cases are covered;
the full Web run passed 1,929 with one cold Members-route DOM timeout.
After adding a bounded ten-second asynchronous DOM wait, all 69 App tests passed
with assertions retained. Together these cover all 1,930 Web cases. Lint, build, Worker configuration,
OpenAPI synchronization and the 65-module upload audit passed. Chromium Billing
verification passed 84 layout states in 24 contexts across six languages.
All 32 public checks passed, including 14 byte-identical deployed assets.
Direct and proxied catalogs confirm Free 20, Pro 1,000 and Max 4,000 with the
unchanged verified prices. Fresh settings readback confirms only the intended
plan-call policy changed among the 19 public variables; all six Secret names,
resource bindings, limits and daily `10 16 * * *` cron are preserved.

No authenticated production business mutation, provider model evaluation,
email send, manual scheduler invocation or SQL verification request was used.
Ordinary catalog cache refresh row metrics are not exposed and are not claimed
as zero. Details are in [release evidence](validation/jev-rounded-calls-production-2026-10-14.json).

# Jev call allowance production release, 2026-10-14

Production publication is verified at 100% traffic. Server source
`ad63c4d790215cabb41911faaffc06d73ee864e8` is version
`f6e778ff-9f9e-4d98-99c9-27a7f210df73`; Web source
`9621562f617231bd42eff9de92f19dc064b1d129` is version
`de8d4cce-9057-4db3-87d6-499959931513`. Later evidence or test-only
commits do not change production application code.

Free has 20 lifetime Jev trials per Owner, shared with members and API keys.
Pro has 1,089 calls per UTC month; Max has 4,358. Annual plans get the same
monthly calls without rollover. Plan changes, preference toggles and deletion
never renew trials. Paid historical reservations are retained; the additive
0015 migration alone advances production D1 to canonical v15. Billing,
pricing, Settings, review, six-language guides and policy disclosures show
calls. Old USD API fields remain deprecated compatibility metadata.

Direct/proxied catalogs confirm all counts and unchanged prices/capacities.
All 31 public checks passed, including 14 byte-identical deployed assets.
The six Secret names, 19 public variables, D1/DO/rate-limit bindings, worker
limits and daily `10 16 * * *` cron are preserved. No production customer
write, provider evaluation, email send or manual scheduler invocation was used.

The full Server suite passed 3,285 tests and 107 subtests. All Web cases were
covered: the final full run passed 1,929 with one cold lazy-route DOM timeout;
the corrected bounded wait then passed all 69 App tests with assertions retained.
Six-language Billing checks passed 84 Chromium layout states in 24 contexts.
Isolated native D1 proved the 20th/21st boundary, stale-guard rollback and
lifetime persistence. Migration CLI row totals were not exposed and are unknown;
the six captured schema/journal SELECTs read 529 rows and wrote zero. Those
SELECT totals do not include migration bookkeeping or normal catalog cache
refreshes. Full details are in
[release evidence](validation/jev-calls-production-2026-10-14.json).

# Norulo production operations

The paid allowance release was verified on 2026-10-14. Server main source
`704c2a14825446b820471e37a40b0638edd33043` is deployed as
`e04c7335-dd0d-4431-ab26-ffe5815ac955`; Web main source
`56d81c0bb2a35b9608448ef8b318ee86aba6a14d` is deployed as
`bed26335-f197-444f-8098-56fff3b0915b`, both at 100% traffic.
Direct and proxied public catalogs confirm Pro $4.99/month or $49.99/year with
20,000 expenses and $3/month Jev; Max $12.99/month or $129.99/year with
200,000 expenses and $12/month Jev. Projects remain 3/20/100. Annual subscriptions
retain the monthly UTC model allowance without rollover. No migration or usage
reset was needed; configured prices remain verified provider facts.

Local validation covered all 3,280 Server test cases and 107 subtests; the sole
sandbox-denied loopback test passed after the appropriate execution permission.
A final 27-test contract check plus 28 subtests passed. Web's initial timeout
failures were resolved by a single-worker, 15-second-timeout full recheck; its
remaining contract checksum failure occurred while regenerating that artifact.
All 239 final Billing/Docs/API/contract tests then passed against stable final
artifacts. Lint, build, contract sync, offline checks and 72 Chromium billing
layout states passed. All 731 Server upload files match the reviewed dry-run,
including the 65 canonical modules and checked import closure. Twenty-one bounded
public GET checks passed and final assets matched byte-for-byte. Existing bindings,
Secret names, public variables other than the requested Max policy, observability,
limits and daily cron were preserved. No business mutation, migration or SQL API
call was made. Catalog GETs can refresh an expired provider cache; native D1 row
metrics are unavailable for those HTTP reads, so zero total D1 writes is not
claimed. See the [actual allowance release readback](validation/subscription-allowances-production-2026-10-14.json).

Free expense capacity increased to 300 on 2026-10-14. Server main `90801f8`
is deployed as `645a2153-e946-4fe9-a733-eaa015c5e9f4`; Web main `98361a1`
is deployed as `89e91178-074d-4e76-be3e-e9b07e30fb38`, both at 100% traffic.
The anonymous catalog returns Free expenseRecords=300. No migration, existing
record rewrite, remote fixture or SQL API operation was needed. All existing
19 public variables except the intended Free record allowance, six Secret
names, D1/DO identities, activation flags and daily cron were preserved.
The latest main REST frequency admission also ships with its four declared
rate-limit bindings; the existing OAuth rate limiter is retained.
See the [Free 300 release record](validation/free-300-production-2026-10-14.json)
for local tests/native checks, 731 matching upload files and production readback.

The 2026-10-13 [expense source release](validation/expense-last-source-production-2026-10-13.json)
is verified on both production domains at 100% traffic. Schema v14 adds only
0014_expense_last_source.sql: a nullable latest-source snapshot on each expense.
Owner/member writes and all recurring generation paths update it in the original
atomic save. Old records stay unknown until edited; there is no backfill or new
history stream. Production resources, 19 public variables, six Secret names and
the daily schedule were preserved. Local suites and native source checks passed;
public production verification is read-only, not authenticated customer acceptance.


The 2026-10-13 [recurring controls release](validation/recurring-schedule-controls-production-2026-10-13.json)
preserves schema v13, all production resources and the daily schedule. Browser
creation/editing derives repeat dates from startOn; end-date Clear sends null.
Complete Server edits/resumes skip posted and retained pending period identities
before saving the next date. Historical expenses and frozen failures remain
intact; this release does not repair or regenerate existing financial records.


This runbook covers norulo.com and api.norulo.com only. Preview and Workers.dev
remain disabled. Dated records in [production readiness](validation/production-readiness-2026-10-10.md)
identify what was actually published/read back; source configuration or a local
test does not establish the deployed version.

## Catalog configuration and remaining acceptance

The 2026-10-12 review release retains the live configured Creem products and
six Secret names that were present before publication. See the
[review release record](validation/server-review-production-release-2026-10-12.json).
The empty-product Free catalog described below remains the supported deliberately
disabled billing path. This review performed no payment/provider/email acceptance
operation and made no changes to product IDs or provider identities.

The user has confirmed successful real GitHub sign-in, email verification-code
delivery/login and ordinary expense recording. Repository installation,
credential/session refresh, account linking, shared-team flows, a complete ledger
journey, live recurring financial execution and native Worker real-provider AI
HTTPS remain separately unverified. The completed 36-case direct HTTPS AI quality
journal must not be repeated to claim native Worker acceptance.

Real payments are deferred. With explicitly empty Creem products, the reviewed
/billing/plan implementation returns a public Free catalog without requiring a
provider price row. Free is priced at zero and uses actual configured allowances:
by default 3 projects, 300 expense records, 10 writes/minute, 1,000 writes/month
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
| Production D1 | norulo-ledger-production, c41a1ab7-dffa-4c5d-a213-25f1bb6c78c5; verified schema v14; additive 0014 latest-source column, no backfill |
| Email admission | EMAIL_ADMISSION / EmailAdmission, namespace 6588312f00f74840a37463e72a2d75eb |
| Recurrence | RECURRING_SCHEDULER / RecurringScheduler, namespace b3f41def1906481e9c72662debf4b505; existing Root/Owner scopes and journal state |
| System sender | EMAIL restricted to login@auth.norulo.com; authenticated sending domain and existing contact Email Routing retained |
| Worker Secrets | NORULO_GITHUB_CLIENT_SECRET, NORULO_GITHUB_TOKEN_KEY, NORULO_EMAIL_CODE_SECRET, TYPESAFE_API_KEY, NORULO_CREEM_API_KEY and NORULO_CREEM_WEBHOOK_SECRET, inherited by name without reading values |
| OAuth admission | AUTH_RATE_LIMIT, isolated namespace 1576996832, 20/60 per location; preserve browser-bound single-use state |
| REST frequency admission | API_IP_BURST_RATE_LIMIT 1744429548 (300/10), API_IP_RATE_LIMIT 1820219268 (1,200/60), API_CREDENTIAL_BURST_RATE_LIMIT 1012765925 (120/10), API_CREDENTIAL_RATE_LIMIT 1009527699 (600/60); all four required once the admission source is published |
| Environment credential | Existing CLOUDFLARE_API_TOKEN network binding; never clear or duplicate its value |
| Activation | Runtime D1, email, both AI flags and recurrence enabled through all four reviewed activation overlays; checked-in five flags remain 0 |
| Limits and schedule | cpu_ms=300000, subrequests=9000; exactly one cron, 10 16 * * * UTC |
| Exposure | Exact production domains, preview URLs/Workers.dev disabled; no preview release |

Use the [deployment command](../cloudflare/server/README.md#production-recurring-release)
with an inspected effective configuration preserving current live public variables
and every overlay/Secret. Source paused/empty-product defaults require this live
configuration overlay. Keep a temporary config inside the Worker directory so
the frozen Python dependencies are included. Never replay applied migrations as a release
check. Verify actual bindings, limits, flags, schedules and versions through
finite read-only control-plane requests. Supported limits do not confirm Paid
billing subscription status.

## REST request frequency

Every production request, including authentication, billing and webhook paths,
passes Workers rate-limit admission before URL/body parsing, D1, email or
provider work. Keys are SHA-256 digests of the client IPv4 address or IPv6 /64
(from Cloudflare's CF-Connecting-IP, which Web forwards across its service
binding) and of the first presented session/API-key credential. A 10-second
burst window and a 60-second sustained window per subject behave like a token
bucket: 300/10s and 1,200/min per network, 120/10s and 600/min per credential.
There is no hourly, monthly or total request cap; ledger-owner write allowances,
email admission and AUTH_RATE_LIMIT still apply separately.

Denials return 429 API_RATE_LIMIT with Retry-After 10 or 60. A missing binding
or uncertain native result fails closed as 503 API_ADMISSION_UNAVAILABLE without
retry. Counters are approximate per Cloudflare location, not a strict global
ceiling, and need no D1 or Durable Object storage writes. Changing a threshold
means updating wrangler.production.jsonc, the deployment guard and the OpenAPI
description together. Local and preview modes do not consult these bindings.

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

The existing Cloudflare billing alert is retained. Three Custom Alert policies
are enabled and read back in [the alert validation record](validation/recurring-alert-rules-2026-10-11.json).
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

On 2026-10-11 at 14:23 UTC, all three policies were created with HTTP 201 and
enabled=true for the one explicitly approved operational email recipient. Each
policy was independently read back with HTTP 200: exact query, filters, intervals
and email mechanism matched the submitted configuration. The existing billing
policy's complete configuration fingerprint was unchanged. Policy IDs are in the
dated validation record; the recipient address is kept in Cloudflare settings.
The initial POST was denied with HTTP 403/code 10000. After the user added Account
Notifications Edit to the existing token, creation succeeded; no broad Account
Settings permission was requested. Historical failure evidence is retained.
Do not send a test notification or manufacture a production failure for testing.
Actual triggering and mailbox delivery remain unverified until a natural event.
These account-level policies take effect without a new Worker upload, application
environment variable, additional business Cron or D1 operation.

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

The three operational detectors are enabled with the approved recipient and
verified readback. Observe the next natural event without synthetic production
writes or test notifications. Real scheduled financial posting,
provider notification, native Worker paid AI, shared-team flows and GitHub App
installation remain separate acceptance items. None requires real charges or
remote synthetic business writes to prepare safely.
