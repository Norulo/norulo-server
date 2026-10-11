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
The Root emits its custom summary on completed execution/result paths, but
disabled, busy, skipped and cancelled early paths can emit no summary. Use Cron
Events and fixed-code exceptions as complementary observations. An absent
summary is an unverified observation; it does not prove the schedule did not run.

The checked publication logging policy is limited:

| Service | Logging policy | Limits of the observation |
| --- | --- | --- |
| Server | 100% sampling of emitted safe scheduler aggregates; query strings redacted; invocation logs/traces disabled | Not a complete HTTP request log, raw financial audit or automatic alert delivery |
| Web | 1% sampling of fixed-code upstream/service transport diagnostics; query strings redacted; invocation logs/traces disabled | Not every HTTP error, raw provider response or outage occurrence is captured |

Never log cookies, authorization headers, OAuth codes/state, private emails,
expense text, raw provider responses or Secret values. Aggregate fields stay
bounded and omit Owner identifiers. Verify configuration acceptance after
publication before relying on log persistence.

The existing Cloudflare billing alert is retained. The account offers two
notification delivery types; this is not verified per-Worker alert eligibility:

- workers_observability_alert accepts only filters.status=[FIRING_FAILED]. It
  delivers an upstream rule's firing failure; it does not accept direct Worker,
  Cron, failed-Owner or backlog query filters.
- workers_observability_real_time_issue has no filters and requires Issues source
  enablement. That source has not been enabled as part of this preparation.

Only a disabled, recipient-ready draft is prepared. No upstream detection rule
or new notification policy was created and no test email sent. A concrete
upstream detector, user-approved recipients and the actual scope/eligibility
must be established before claiming automatic alerting. Manual inspection and
sampled logs do not establish it.

For the first natural tick, use this read-only checklist:

1. Confirm the one daily cron, expected version, bindings and strict limits.
2. Check platform status and scheduler aggregate together; record failedOwners,
   backlog, completeness and metered costs separately.
3. If a real rule was due, compare existing occurrence/expense/audit state through
   authorized reads. Do not create production test rules or expenses.
4. If no real rule was due, record idle acceptance only, without claiming financial
   posting or provider notification was exercised.
5. Mark missing summaries as unverified and inspect the platform event/code path;
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

Before operational readiness is complete, establish the reviewed upstream alert
detector/recipients/scope and observe the natural event. Real scheduled financial posting,
provider notification, native Worker paid AI, shared-team flows and GitHub App
installation remain separate acceptance items. None requires real charges or
remote synthetic business writes to prepare safely.
