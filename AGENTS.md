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
  dispatch; preserve historical daily rows without daily-cap reads/writes.
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
manifest. Keep preview disabled. Do not silently claim production email login
or recurring background execution: both still use preview-only infrastructure.

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
