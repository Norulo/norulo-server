# Norulo Server

## 2026-10-14 Jev calls and paid plan allowances

Canonical Max defaults are now 200,000 retained expenses and $12 of Jev model
allowance per UTC calendar month; Pro stays at 20,000 expenses and $3/month.
Projects remain Free 3 / Pro 20 / Max 100. Monthly and annual subscriptions use
the same monthly model allowance, without rollover. Keep all runtime policies,
examples, public contract, Web translations and boundary checks aligned.
Prices remain verified Creem facts; the live catalog was checked at Pro
$4.99/month or $49.99/year and Max $12.99/month or $129.99/year.
Count-based Jev adds the canonical 0015 migration for persistent Free trials; paid usage is preserved. See
docs/subscription-policy.md for the capacity and cost reasoning.


Jev is displayed and enforced by calls: Free 20 once per Owner lifetime, Pro
1,089 per UTC month, Max 4,358 per UTC month. Members/API keys share the Owner
pool. Billing shows used/total/remaining calls, never a dollar balance. v15
adds a constrained lifetime trial column; old paid reservation data is retained.
Annual plans keep monthly calls. Plan changes, preference toggles and deletion
never renew Free trials. Old USD API fields are deprecated compatibility data.

## 2026-10-14 Free expense capacity

Free defaults to 300 retained expenses per ledger Owner, combined across project,
shared-pool and recurring-generated records, including archived projects.
Keep default/example/local/production policies aligned; older 100-record release
evidence is historical. Current configured entitlements remain authoritative.
This allowance increase requires no migration or historical-record rewrite.

## 2026-10-14 REST frequency admission

Production admits every request through four Workers rate-limit bindings before
parsing, D1, email or provider work: per hashed IPv4/IPv6-/64 network 300/10s
and 1,200/60s, per hashed presented credential 120/10s and 600/60s. There is no
total request cap. Denials are 429 API_RATE_LIMIT with Retry-After 10 or 60;
missing/uncertain bindings fail closed as 503 without retry. The deployment guard
requires these exact bindings beside AUTH_RATE_LIMIT; keep their namespaces,
which never use D1 or DO storage. Publication is verified in
docs/validation/free-300-production-2026-10-14.json; future uploads follow the
usual inspected effective-config release process.


## 2026-10-13 expense last source

Expense.lastSource is read-only and contains the last successful creation/edit
source, stored atomically in expenses.last_source_json. Owner/member identity is
a bounded public snapshot; never expose email, API-key token/hash or credential
IDs. Recurring initial/background/pending generation uses recurring/create; a
later human edit replaces it. Failed CAS and creation replay do not overwrite
the stored source. Old rows stay null/Source unknown, without historical backfill.
This release requires only 0014_expense_last_source.sql and schema v14. Keep the
historical v13 preview clear/upgrade authorities frozen; do not deploy or repair
preview. Preserve production resources, 19 public vars, six Secrets and daily cron.


## 2026-10-13 recurring edit pointer

Complete edits and resumes select the first unconsumed future calendar period
before saving. Occurrence rows with nullable expense_id and retained pending
rows still consume their original period. Check at most 20 indexed candidates;
RECURRING_SCHEDULE_SEARCH_LIMIT returns 409 before AI/usage or business writes.
The candidate's absence is rechecked with the existing rule revision guard in
the atomic save. Keep the scheduler replay protection, frequency identity
namespaces, frozen pending values, authorization fences and financial history.
Browser selectors now derive from startOn and are read-only; API calendars retain
the explicit selectors defined in the OpenAPI contract. This release requires
no schema migration or existing-plan/expense repair. Preserve the live resource
identities, 19 public variables, six Secrets and the daily schedule below.


## 2026-10-12 review release

The current review release upgrades the independent production schema to v13
with only 0013_export_key_indexes.sql. The dated review release record supersedes
older v12/configuration snapshots below. Preserve the existing D1/DO identities,
daily schedule and financial journals. New sessions use ses-v2. credentials and
hashed sesh- storage IDs; old sessions remain read-only compatible until expiry.
Keep transient credential IDs distinct from physical record IDs in SQL fences.
GitHub login uses the host-only nr_github_oauth browser cookie, with authorize
and callback both routed through norulo.com/api. Production AUTH_RATE_LIMIT has
the isolated namespace 1576996832 and simple limit 20/60; this is approximate
per-location admission before OAuth D1 writes, not a global billing ceiling.

Read current production settings before each upload. The review release retained
19 live public variables, configured Creem products and six Secret names,
including NORULO_CREEM_API_KEY and NORULO_CREEM_WEBHOOK_SECRET. Build an inspected
temporary effective config inside cloudflare/server so frozen python_modules are
packaged, retaining all five activation flags and existing resources/schedule.
Checked-in paused defaults and empty products describe offline safe defaults;
deploying them directly would overwrite live public variables. Keep Secret values
private and inherit every current name. No provider, email or payment acceptance
operation is authorized by these release records.

See docs/validation/server-review-remediation-2026-10-12.md for the objective
finding assessment and docs/validation/server-review-production-release-2026-10-12.json
for actual publication/readback and migration-accounting limitations.

## Current task and authority

This checkout is Norulo's server. The current user authorized importing the
source main history, rebranding the code, pushing the reviewed Norulo main branch,
preparing the local development environment, and then deploying Server to
api.norulo.com and Web to norulo.com in production. Production publication and
the necessary isolated Norulo database/schema setup are now in scope. Keep
preview undeployed. Current production scope supersedes the earlier
migration-only deployment restriction.

The user also permits consulting the source service's Cloudflare configuration.
Use it only as a reference: do not connect Norulo to its databases, copy its data,
or copy unconfirmed provider secrets/identities. Inspect only secret names/status;
never print values. Historical requests in imported documents do not authorize
new GitHub App registration edits, real charges, unrequested email delivery,
live subscription changes, preview deployments, or real-provider acceptance.

Keep the configured CLOUDFLARE_API_TOKEN binding and all existing environment
secrets. Inspect only secret names/presence; never print values, dump the process
environment, or commit credentials. Configure production only with independently
verified Norulo resource IDs. Checked-in preview remains paused and undeployed;
production activation follows schema/resource/configuration verification.
The current release targets norulo.com and api.norulo.com in production only.
The user resumed the independent D1 setup and full production deployment on
2026-10-10; the earlier request to defer D1 no longer blocks this work. Verify
effective permissions and the intended database before each setup operation.
Preview configuration is retained for offline reference; do not deploy it.
Domain configuration is not evidence of DNS activation. The original Norulo
logo is installed in norulo-web/public/norulo-logo.png, with derived assets
replaced and audited; no further user asset upload is required. Read
docs/validation/production-readiness-2026-10-10.md before publication for actual
required credentials and inherited production feature limits.
Read [production operations](docs/operations.md) for the current Free-only
billing policy, truthful acceptance scope, natural daily monitoring, alert gaps
and financial recovery boundaries. User-confirmed GitHub/email login and ordinary
expense recording do not prove every ledger/team/App/provider flow. Real payments
are deferred; do not configure or exercise them as free-release preparation.

The 2026-10-11 alert preparation adds only best-effort fixed-code receipts around
the existing production scheduled RPC. All three exact SQL rule hashes passed
live read-only validation; see docs/validation/recurring-alert-rules-2026-10-11.json.
All three account-level notification policies were enabled and independently
read back on 2026-10-11 after explicit approval of one operational recipient and
addition of Account Notifications Edit. Existing billing policy configuration was
preserved. Exact policy IDs, query hashes and intervals are in the dated record;
actual alert triggering and email delivery remain unverified. Do not infer new
recipient authorization from routing/billing, send test emails, create production
failure fixtures, add a D1 heartbeat or turn missing observations into financial
retries. Keep the existing one daily Cron, resource scopes, unknown stops and
Secrets. Account notification changes require no application upload or D1 write.

Use existing isolated cloud checkouts; do not create Git worktrees unless the
user explicitly requests one. Preserve user changes. Subsequent environment
onboarding must keep application source, dependency manifests, and lockfiles
unchanged unless the user separately authorizes code changes.

## Product and implementation

Norulo is a project expense ledger for developers and teams. Keep Server and Web
separate and share openapi/ledger-v1.yaml. Public copy describes named standalone
projects, optional GitHub associations, explicitly invited ledger roles,
user-entered and recurring expenses, and separate per-currency reports. Ledger
expenses remain distinct from platform subscriptions. Do not promise bank/vendor
imports, currency conversion, automatic allocation, tax advice, or permanent
expense deletion through DELETE. AI assistance requires the current ledger
Owner's paid entitlement, activation and monthly USD allowance; an unavailable
result falls back to manual category selection.

cloudflare/server/src/entry.py is the Worker entry. norulo_server/ owns the
modules; sync_server_modules.py generates the ignored Worker mirror. Never edit
the mirror directly. Run sync and --check after packaged-source changes and keep
the entire relative import closure packaged. Use nr_session and
nr_email_challenge browser cookies, nrk_ API keys, nri_ invitation tokens,
NORULO_* configuration variables, and X-Norulo-* headers consistently with Web
and the OpenAPI contract.

## Security and financial invariants

- Preserve actual actor/account identity, immutable ledger owner IDs, financial
  history, durable audits, session/token revisions, webhook receipts, encrypted
  provider credentials, and membership/key/CAS/idempotency fences.
- Cookie-authenticated writes require a trusted Origin regardless of SameSite.
  Malformed Authorization cannot bypass origin or credential checks. Keys store
  credential hashes, display tokens once, support immediate revocation, and
  intersect scopes, current role and explicit target/shared-pool restrictions.
- Reads never initialize/repair counters, migrate schemas, rotate provider
  tokens, dispatch models, or write billing facts. GitHub refresh is a separate
  actual-account cookie/Origin-protected POST with durable rotation claims.
  Unknown provider outcomes cannot consume the same refresh token again.
- Validate all decoded JSON strings/keys with json_input.validate_json_unicode
  before auth/provider/write work. Keep bounded integer/text/JSON admission;
  reject unsafe integers and invalid Unicode before native SQL dispatch.
- NativeD1 converts admitted safe Python integers to exact JavaScript Numbers
  at bind time and preserves atomic batches/native metadata. Resource reads
  append SELECTs to the principal's read batch; writes recheck actor, session,
  key, membership, category, project, revision and idempotency in the same batch
  as the mutation, quota reservation and audit.
- Money remains integer minor units with currency exponents. Shared expenses
  have no project ID; reports do not combine currencies. Aggregate totals use
  ledger_money_totals.AGGREGATE_SQL and Python reconstruction, not overflowing
  SQLite SUM. Safe totals are numeric; larger totals are decimal strings.
- Lost GitHub access hides protected metadata while retaining authorized
  historical financial access. Provider 401 requires GitHub reconnection rather
  than revoking a Norulo session. Never share GitHub credentials among members.
- Creem checkout never grants entitlement: signed idempotent webhooks own
  payment facts with claim/revision/replay fences. Explicit month/year product
  IDs must be distinct. Never invent prices or treat a reservation as an invoice.
- Expense capacity counts current visible records, including archived projects.
  Optional oldest-record replacement must atomically select the actual oldest
  permitted record at exact capacity. Failed/replayed operations do not retire
  records. Recurrence keeps calendar identity, actor/key/target/category/plan
  fences, bounded catch-up and at most ten unresolved failed occurrences.
- Jev atomically admits one call before dispatch: Free has 20 lifetime trials;
  Pro has 1,089/month and Max 4,358/month, without paid rollover. The additive
  v15 trial field survives month changes, plan changes and preference toggles.
  Existing paid reservations remain internal compatibility accounting; UI shows counts.
  The stored ledger Owner's entitlement and opt-in apply; preserve historical
  daily rows without daily-cap reads/writes.
  Failed/unavailable model results permit ordinary explicit-category writes.
  Duplicate candidates require current target/date/currency/minor amount and
  are rechecked after inference; they remain advisory.
- Provider gateways preserve TLS/signature/artifact verification, reject 3xx
  without following redirects, and never log raw responses or credentials.
  Diagnostics expose bounded fixed codes/type/site and numeric status only.

## Cloudflare isolation and accounting

Local development uses only wrangler.jsonc with NORULO_MODE=local, remote=false,
no public routes and local persistence. Local synthetic fixtures must never be
seeded remotely. Loopback validation clients disable proxies and redirects.

The user explicitly requires minimizing D1 Rows Written because of its cost.
Development, regression, browser fixtures and load tests must use local D1 or
SQLite. Never write remote test fixtures, seed remote databases, clear/rebuild
production data for testing, or repeatedly run remote write-based acceptance.
Remote setup is limited to the necessary unapplied canonical migrations on the
independent Norulo production database; inspect the exact database, existing
schema/journal and SQL scope first, then execute bounded batches once. Do not
copy source data. Production smoke checks use read-only endpoints/SELECTs;
ordinary real user operations retain their existing authorization and quota
rules. Record native rows_read/rows_written and migration progress where the
platform reports them. DDL, indexes and migration bookkeeping must not be
assumed free. If a write outcome is unknown, inspect status/schema/journal
without writes before deciding how to recover; never retry blindly. Do not
invent a numeric/calendar writing budget that the user has not specified.

Remote production requires independently reviewed Norulo resources,
provider identities/callbacks, secrets, domain/DNS settings and publication
instructions. Never reuse source-service database/namespace/trigger IDs or
historical approval statements as current Norulo settings. The user-authorized,
independently verified Cloudflare account may host both services; use only new
Norulo database/Worker resources within it. The deployment guard
rejects source-service database IDs, placeholders during execution, shared
preview/production databases, unexpected hosts, invalid pause switches and
uncoordinated scheduling/email configuration. A code upload does not prove
runtime, provider, schema or financial acceptance.

Keep the existing metered preview architecture: the fixed ValidationBudget DO
serializes writes, reserves worst-case SQL bounds before side effects, captures
complete native operation metadata, and retains cumulative reservations and
append-only accounting. Incomplete/unknown outcomes remain stopped; no general
reset/retry endpoint. Native bounds, schema/input/cardinality checks and
commercial owner/model limits remain enforced. Historical finite-test ceilings
are not ordinary-product limits. Do not invent a calendar row budget.
The current production release is authorized after schema and resource checks.
Provider credentials/callbacks and feature gates still need actual configuration
and truthful acceptance reporting. Real email, charges, subscription changes,
remote schedules and irreversible maintenance are separate operations requiring
current scope; never infer authorization from the imported business-clear
manifest. Keep preview disabled. Production email admission now has an independent
EMAIL_ADMISSION / EmailAdmission SQLite Durable Object implementation, isolated
from ValidationBudget and D1. Its hashed-subject counters fail closed on uncertain
storage/RPC outcomes, with no automatic retry/refund. The implementation is
published with email auth enabled through the reviewed dual activation overlay.
The user confirmed receipt of the verification code and successful email login;
account linking, sign-out and credential/session refresh remain separately
unverified. Future releases must retain both --activate-production and
--activate-email-auth to preserve runtime activation while checked-in defaults
remain 0. Do not infer other email behavior from sender settings or local tests.
Production recurrence now has an independent RECURRING_SCHEDULER /
RecurringScheduler SQLite Durable Object implementation and passed core/native
review. The post-packaging-fix full suite passed 2,942 tests in 106.73 seconds.
Verified release A on 2026-10-11 at 05:38:43 UTC has all five runtime flags 1
and one hourly UTC cron (0 * * * *), version b5642a63-1643-418a-b494-bb7bcf427050.
The scheduler namespace is b3f41def1906481e9c72662debf4b505, separate from the
retained EmailAdmission namespace. This is dated configuration/read-only
verification, not proof of a live scheduled financial posting. The fixed scope
is norulo-production-recurring-v1,
with one durable completed-hour/in-flight marker and no reset/retry HTTP endpoint.
Unknown execution remains stopped across incarnations; no automatic retry or D1
heartbeat/idle maintenance write. Local native proof covers a manually parked
unknown marker, not injected loss of a real native D1 response.
TYPESAFE_API_KEY is present as the fourth Worker Secret, and runtime specification
11 confirms both network Secret bindings present with the Cloudflare token
retained. On 2026-10-11 (Asia/Shanghai recording date), the one fixed quality
journal completed 36 real CPython HTTPS calls once, with both quality gates
passing, no retry and no D1/application requests. The 99,108 micro-USD reservation
remains retained; the $0.0010017 usage estimate is not an invoice. Current
[quality evidence](docs/validation/ai-quality-2026-10-11-execution.json) is distinct
from the unchanged 2026-10-10 blocked snapshot and imported source history.
Do not repeat that completed journal or start another directory to bypass the
36-attempt scope. Native Worker real-provider HTTPS remains untested, distinct
from direct HTTPS quality capture and the five loopback native checks. Both
production AI flags are 1 in verified release A; real native provider HTTPS and
customer suggestion acceptance remain untested.
--activate-ai-suggestions requires production and both D1/email activation
overlays; the static guard cannot prove quality. Preserve all four Worker Secrets.
The reviewed --activate-recurring-expenses release requires production plus all
D1/email/AI activation overlays. The published daily revision uses shared
PRODUCTION_RECURRING_CRON=10 16 * * * (UTC), Beijing 00:10, in a fresh temporary
config while source defaults stay 0 and source has no cron. Verified release B
at 2026-10-11 06:38:08 UTC is Server e2e4e02d-ac9a-4c20-852f-f6cbfe5b5ae4
from main ded49a46 and Web 0c63c81e-1f91-4b72-bf3b-f949b7840ad8 from main
bef23ee7. The [dated daily record](docs/validation/production-daily-release-2026-10-11.json)
verifies the daily cron, strict limits, all five flags 1 and preservation of
DB, EMAIL, both DO namespaces and four Secrets; release A is historical.
The published capacity revision uses permanent, validated hash scopes for Owner
DOs in the existing namespace/class and a Root daily checkpoint. Preserve legacy
completed_hour units and active/stopped state; do not reset/reinitialize storage
or bypass an old permanent unknown stop. Root limits are 5,000 selected Owners,
10,000 handled occurrences and 8,192 total child RPCs, including progress reads,
with Owner pages/deferred carry bounded to 64. Logical Owner parallelism is 8;
each chunk handles at most 20 occurrences with an 800 native-SQL-statement
engineering cap and conservative 200-statement occurrence reserve. Each financial
posting retains its independent canonical batch and actual Owner/actor/member/
key/CAS/idempotency/quota checks. Known pre-dispatch minute-quota denial releases
the worker slot and defers to the next minute without a SQL heartbeat or permanent
block. Owner hard wall deadline is 120 seconds including schema/execution. Root
stops launching at its 600-second soft deadline, then awaits started Owners for
at most their remaining 120 seconds, within the official 900-second Cron wall
limit. Unknown native financial execution permanently stops that Owner while
other Owners continue. RPC transport uncertainty advances only when read-only
progress proves the chunk settled; otherwise stop new launches, await siblings
and retain a permanent Root global unknown stop. Never retry an unknown chunk.
Known completed-chunk replay uses cached results without D1; next chunk identity
is unique. No quarantine/reset API is added. A daily UTC poll scans stored
next_run_at <= server time, retaining each rule timezone/original period date;
other timezones can wait nearly 24 hours. The final whole suite passed 3,009
tests in 115.01 seconds. Final finite local capacity profiles passed for 8-way
overlap and 1,000/3,000 occurrences across 200/600 Owners. Natural daily passes
took 33.985/107.635 seconds at peak parallelism 8; these are local observations,
not a same-Owner throughput promise or production SLA. The
[capacity proof](docs/validation/production-recurring-load-native-local-2026-10-11.json)
separates actual daily-window costs from fixture/setup/integrity/replay costs.
Daily publication/readback passed in dated release B; live scheduled financial
and provider behavior remain untested. Do not treat its version as permanently latest.
Do not infer live scheduling/performance from
the immutable earlier 16-request minimal proof. The capacity revision uses the same binding/class/namespace and needs no D1
migration. Production limits must remain exactly cpu_ms=300000 and
subrequests=9000, preserved in source-paused/temporary activation configurations.
Static validation/actual publication readback establish configuration support,
not confirmed Paid billing. The
[official provenance](docs/validation/cloudflare-scheduler-limits-2026-10-11.json)
does not establish whether batch SQL statements count as dispatches or whether
Owner DO invocations reset D1 limits. The 800-statement cap is independent
engineering policy. See the
[earlier local recurring proof](docs/validation/production-recurring-native-local-2026-10-11.json)
for historical finite costs and limitations. Preserve the user-confirmed email behavior and
all four Secrets and all activation overlays through subsequent publication.
The [dated production record](docs/validation/production-release-2026-10-11.json)
records verified versions/bindings/cron. It does not guarantee future latest
versions or remote migration-tag readback; that API field was absent.

## Verification and repository hygiene

Use Python 3.10.12 for reference tests and Python 3.14.2 for the locked Worker
builder. Discover every current test with python -m pytest tests; do not hide
failures behind an allowlist. SQLite fixtures prove application behavior, not
Cloudflare FFI/provider/remote transactions. Close fixture connections.

Required offline checks: python scripts/check-ledger-s01.py --allow-placeholders,
python cloudflare/server/sync_server_modules.py followed by --check, and
bash -n scripts/deploy-cloudflare.sh. Use the frozen uv/npm locks and pinned
Wrangler. Verify relative and absolute import closure from the Worker entry and
byte equality of every canonical module in the actual upload artifact; a
successful dry-run alone does not prove package completeness. The earlier
728-module recurring package omitted cloudflare_recurring_scheduler and was
rejected with Cloudflare validation 10021; the repaired artifact has 729 modules
and all 64 canonical modules. Keep TLS and artifact checksum verification enabled.
Local native acceptance uses a fresh persistence directory and finite loopback requests.

Keep source/tests/contracts and durable docs in Git. Ignore generated mirrors,
node_modules, Python tooling, runtime databases, caches and local logs. Inspect
tracked and untracked changes before/after setup and undo only unintended
changes caused by setup commands. Imported docs/validation evidence is source
history, not Norulo acceptance; current results belong in migration-2026-10-10.md.
