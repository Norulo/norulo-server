# Norulo Server

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
- Jev reserves only the current UTC-month USD allowance atomically before
  dispatch: Free $0, Pro $3 and Max $5 under the current policy, with no rollover.
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
review and the final 2,923-test suite. Its runtime flag remains 0 and no cron is
installed pending publication. The fixed scope is norulo-production-recurring-v1,
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
production AI flags remain 0 pending the final reviewed release.
--activate-ai-suggestions requires production and both D1/email activation
overlays; the static guard cannot prove quality. Preserve all four Worker Secrets.
The reviewed --activate-recurring-expenses release requires production plus all
D1/email/AI activation overlays, creating one hourly UTC cron (0 * * * *) in a
fresh temporary config while source defaults stay 0 and source has no cron.
Core/native/final local gates are complete; do not claim live scheduling from
those checks. The new DO migration does not run D1 migrations. See
[local recurring proof](docs/validation/production-recurring-native-local-2026-10-11.json)
for finite costs and limitations. Preserve the user-confirmed email behavior and
all four Secrets through final AI/recurring publication.

## Verification and repository hygiene

Use Python 3.10.12 for reference tests and Python 3.14.2 for the locked Worker
builder. Discover every current test with python -m pytest tests; do not hide
failures behind an allowlist. SQLite fixtures prove application behavior, not
Cloudflare FFI/provider/remote transactions. Close fixture connections.

Required offline checks: python scripts/check-ledger-s01.py --allow-placeholders,
python cloudflare/server/sync_server_modules.py followed by --check, and
bash -n scripts/deploy-cloudflare.sh. Use the frozen uv/npm locks and pinned
Wrangler. Keep TLS and artifact checksum verification enabled. Local native
acceptance uses a fresh persistence directory and finite loopback requests.

Keep source/tests/contracts and durable docs in Git. Ignore generated mirrors,
node_modules, Python tooling, runtime databases, caches and local logs. Inspect
tracked and untracked changes before/after setup and undo only unintended
changes caused by setup commands. Imported docs/validation evidence is source
history, not Norulo acceptance; current results belong in migration-2026-10-10.md.
