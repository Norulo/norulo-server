# Norulo Python Worker

The source main branch has been imported and rebranded. The existing
wrangler.jsonc is explicitly local: no routes, remote=false, NORULO_MODE=local.
wrangler.preview.jsonc remains an undeployed offline reference.
wrangler.production.jsonc selects the initialized independent D1 database, with
its default access switch paused and account, domain, GitHub App and email settings described
below. Checked-in D1/email defaults stay 0; the published production runtime uses
both explicit activation overlays to set them to 1. Schema upgrades, scheduled
recurrence and AI provider dispatch stay disabled; preview remains undeployed.
The imported source's remote databases, providers, domain registrations and
historic publication approval have not been transferred. The user now authorizes
production-only publication with new Norulo resources. The production proposal
selects the verified account/zone and the exact api.norulo.com custom domain;
its DB is now norulo-ledger-production,
c41a1ab7-dffa-4c5d-a213-25f1bb6c78c5, initialized and schema-verified. The user has now
registered the real Norulo GitHub App: its public Client ID
Iv23li78ZPeUgSxJkLUj and slug norulo were verified with GitHub on 2026-10-10, with
only Metadata read permission and no events. The user has since confirmed real
GitHub sign-in; management options, installation and credential refresh remain
unverified. A temporary paused
norulo-server-production Worker was created earlier on 2026-10-10 after the user updated the token
permissions. At that earlier stage its handler returned 503 SERVICE_SETUP_PENDING,
and no D1 or Durable Object binding existed. The api.norulo.com Custom Domain is
bound with previews disabled; workers.dev and preview URLs remain disabled.
A fresh token-encryption key was
securely uploaded, and the user has now saved NORULO_GITHUB_CLIENT_SECRET in the
Cloudflare Dashboard. Both Secret names were read back without inspecting values.
Earlier on 2026-10-10, all 18 public production variables were applied, preserving
both GitHub Secrets through inherit bindings without reading their values.
The subsequent sender-preparation stage set NORULO_EMAIL_FROM=login@auth.norulo.com
and securely generated/uploaded NORULO_EMAIL_CODE_SECRET. The bootstrap then had
19 public variables and three Secrets, with the GitHub pair preserved.
The earlier domain API 403 was resolved after the token permission update.
auth.norulo.com is now enabled, with DNS status ready, no reported errors and
preview_enabled=false. Six new DNS records belong only to the auth subdomain;
the eight existing DNS records and two contact routing rules were preserved.
The Worker now has the EMAIL send binding restricted to login@auth.norulo.com,
with no recipient restriction; all 19 public variables and three Secrets were
retained. No actual email delivery was tested at the sender setup stage. Email
authentication and D1 were paused then; both are now enabled in production, and
the user has confirmed receipt of the verification code and successful email login.
The Web Worker has been published. The earlier user request to defer D1 was
superseded by explicit authorization to resume setup and full production deployment.
All twelve canonical migrations were applied once to the new empty Norulo
database, reporting 367 native rows written for initialization. Schema v12 and its
77 canonical objects were verified; at initialization app_state held only four
empty containers and the other 22 application tables were empty.
The complete Python Worker was first published as version
3ad0cffc-ecc3-47a4-ab5d-a53999528b8c. The email-feature version was
815a1216-4468-4591-be58-e339d4d2c154; the latest Cloudflare version after the user's
Secret update is ec33db03-2fd4-49a4-8430-9e1cb13fc340. Preflight retains
the intended DB, restricted EMAIL binding, independent EmailAdmission namespace
and all four now-configured Secrets. Nineteen public variables match the source
except the activation flags: D1/email 1, both AI flags 0 and recurrence 0. No cron
is installed. The earlier email upload retained three Secrets; AI preparation
added the fourth without changing that accepted application behavior. Both source defaults stay 0; recurring execution, AI
and public preview URLs remain disabled.
Finite read-only checks confirmed homepage HTTP 200, API and Web proxy health
HTTP 200, and their unauthenticated profile endpoints HTTP 401. No public check
set a cookie. This proves publication/transport and access enforcement. The user
subsequently reported successful real GitHub sign-in; installation, refresh and
the complete ledger journey remain unverified. The earlier unavailable email
sign-in preceded this enabled production release. The user has now confirmed
verification-code delivery and successful email login. Account linking, sign-out
and session refresh remain separately unverified. See
[production readiness](../../docs/validation/production-readiness-2026-10-10.md).

## Local runtime

From the repository root, install the Python 3.10.12 reference dependencies and
run all tests/offline checks from the root README. Then:

```bash
python cloudflare/server/sync_server_modules.py
cd cloudflare/server
npm ci
uv sync --frozen --python 3.14.2
node node_modules/wrangler/wrangler-dist/cli.js d1 migrations apply DB --local --config wrangler.jsonc --persist-to /workspace/.norulo-environment/server-state
uv run --frozen --python 3.14.2 pywrangler dev --local --config wrangler.jsonc --ip 127.0.0.1 --port 8080 --persist-to /workspace/.norulo-environment/server-state
```

The intended Web development server sends its API proxy to this local Worker.
Use fresh persistence directories for synthetic acceptance journeys. Never seed
local test identities, tokens or payment facts remotely. Loopback test clients
must disable system proxies and redirects.
Development, regression and browser fixtures must use local D1 or SQLite;
production smoke checks are read-only. Do not repeatedly run remote write-based
acceptance, seed fixtures or clear/rebuild production for testing. Record native
rows_read/rows_written for necessary bounded setup, and stop on unknown outcomes.

## Future remote configuration

Production is api.norulo.com with Web norulo.com. Preview is preview-api.norulo.com
with Web preview.norulo.com. Each environment needs its own reviewed D1 database
and GitHub App identity/callbacks, allowed origins, product IDs and secrets. The
GitHub Client ID, Secret and App slug must identify the same App; configure both
OAuth and installation setup callbacks through the Web API proxy. Web uses its
NORULO_SERVER HTTP service binding to the appropriate Server Worker.

NORULO_GITHUB_CLIENT_SECRET, NORULO_GITHUB_TOKEN_KEY, NORULO_CREEM_API_KEY,
NORULO_CREEM_WEBHOOK_SECRET and optional email/model credentials belong in Secrets.
NORULO_GITHUB_TOKEN_KEY is 32 cryptographically random bytes encoded as unpadded
base64url; the fresh Norulo key is already stored securely and must be retained.
Production secrets.required now lists the two GitHub Secret names,
NORULO_EMAIL_CODE_SECRET and TYPESAFE_API_KEY. Pinned Wrangler inherits all four
existing bindings and rejects a missing required Secret during real publication.
The email release retained the original three; later AI preparation added the
fourth Worker Secret without enabling AI. Keep all four through subsequent
uploads. A dry-run does not verify remote presence. Do not paste credentials into chat or saved instructions. Keep the existing environment
CLOUDFLARE_API_TOKEN binding intact.

NORULO_EMAIL_CODE_SECRET must be a securely generated string of at least 32
characters. It protects code/challenge hashes; it is not an SMTP password.
The prepared sender login@auth.norulo.com sends system verification codes and
recurring-failure notifications. Its auth.norulo.com sending domain is authenticated
and the send_email binding named EMAIL permits only this sender, without recipient
restrictions. No additional mail-provider Secret or SMTP credential is needed
for the native binding. Email Sending entitlement and domain status are enabled;
the user has confirmed verification-code receipt and successful email login.
Settings alone did not establish that acceptance. The independent production
path is published as EMAIL_ADMISSION / EmailAdmission, with SQLite DO
storage isolated from VALIDATION_BUDGET and D1. It stores hashed subjects, counters
and timing metadata, not addresses, raw IPs or codes. Atomic admission must succeed
before sending email or writing OTP state; ambiguous storage/RPC outcomes fail
closed with no automatic retry or refund. Native local acceptance passed; production publication
and its runtime flags/bindings are verified. User-confirmed delivery, code
verification and browser login passed; account linking, sign-out and refresh
remain separately unverified.
The existing OTP flow keeps its 600-second expiry, five-wrong-code limit, browser
challenge binding and single consumption. Its actual challenge/identity/session
writes still use D1 during ordinary real user operations; the limiter itself does
not write D1 or require a new D1 migration.

The reviewed release uses both --activate-production and
--activate-email-auth, overlaying runtime D1/email flags to 1 while their checked-in
defaults remain 0. Native/packaging checks passed and the current runtime is 1/1.
Use both overlays for subsequent releases; omitting them returns the defaults to
0 and pauses the corresponding routes. The [readiness record](../../docs/validation/production-readiness-2026-10-10.md#production-email-admission)
records actual publication and the subsequent user-confirmed delivery/login
acceptance separately from local checks.

The [remaining release checklist](../../docs/validation/production-readiness-2026-10-10.md#remaining-release-checklist)
separates the core GitHub/ledger release, the requested email-login feature and
optional payment, AI and background recurrence work.

## AI configuration and local gates

TYPESAFE_API_KEY is present as the fourth production Worker Secret. Earlier,
revision 8 lacked its cloud network binding. Runtime specification 11 now has
both network Secret bindings present, preserving the Cloudflare token. The fixed
journal has completed 36 real CPython HTTPS calls once, with both quality gates
passing and no retry or D1/application requests. This is fresh Norulo evidence,
recorded for 2026-10-11 in Asia/Shanghai; imported source results are unchanged. The AI-stage full local reference suite passed
2,777 tests after the email-preservation guard and native-fixture repairs. Five loopback fake-provider cases passed through the canonical native
WorkerJevGateway and Python FFI, covering success, redirects, oversized header/
stream and deadline rejection. The size cases use 65,537-byte valid JSON and
explicitly fail with JEV_RESPONSE_TOO_LARGE, rather than a schema error. This is
local transport evidence, not real
provider HTTPS or model-quality acceptance; no gateway source repair was needed.

The current Owner policy admits Pro and Max only, with $3 and $5 respectively per
UTC calendar month under the configurable default policy, no rollover and atomic
conservative reservation of 2,753 micro-USD before each dispatch. Free allowance is $0. Historical daily counters
are preserved but no daily request cap is used. Explicit opt-in and manual
category fallback remain required.

The fixed 36-case run is complete in its only reviewed journal directory,
/workspace/.norulo-environment/ai-quality-native-local-20261010. Its 73 events are
one session, 36 reservations and 36 completions. The full 99,108 micro-USD
($0.099108) reservation remains recorded; usage was 23,850 input and 4,144 output
tokens, yielding a $0.0010017 estimate rather than an invoice. English and Chinese
each had 18 cases; each task correctly suggested all 32 clear labels and withheld
all four uncertain labels, with six consistent order pairs and no false hints.
This small synthetic suite does not establish customer error rates or calibrated
confidence. Direct CPython HTTPS is separate from untested native real-provider
HTTPS. Do not repeat the completed run or start another directory to bypass it.
Recompute current normalized results offline:

```bash
python scripts/evaluate-ledger-suggestions.py \
  docs/validation/ai-quality-2026-10-11-results.jsonl
```

After this actual quality review, the final reviewed release uses
--activate-ai-suggestions to add both NORULO_JEV_SUGGESTIONS_ENABLED=1 and NORULO_JEV_SUGGESTIONS_EVALUATED=1. The required
future release preserves D1 and email activation together:

```bash
./scripts/deploy-cloudflare.sh --environment production \
  --activate-production --activate-email-auth --activate-ai-suggestions \
  --execute --local-checks-passed
```

The AI helper/guard changes are local and not yet published. The final guard
repair requires the explicit email overlay as well, protecting accepted login.
Post-repair targeted validation passed 177 tests and 28 subtests, alongside S01
default/full-overlay and shell checks; these overlap the final full suite.
The static guard checks exact matching flags, D1/isolation and the declared Secret; it cannot verify quality.
Both source/runtime AI flags remain 0 pending final publication. Stored Owner
Pro/Max entitlement/opt-in and UTC-month reservation/fallback fences passed local
checks. The independent production scheduler has now passed local/native/final
suite gates below; runtime recurrence remains 0 with no installed cron.
The fresh [quality execution record](../../docs/validation/ai-quality-2026-10-11-execution.json)
pins results, request/source hashes and journal counts. The unchanged
[2026-10-10 local snapshot](../../docs/validation/ai-local-readiness-2026-10-10.json)
records the earlier blocked stage, not the latest quality state.

## Production recurring release

The new RECURRING_SCHEDULER / RecurringScheduler SQLite DO uses fixed scope
norulo-production-recurring-v1 and migration tag norulo-recurring-scheduler-v1,
independent of preview ValidationBudget and its journal. It persists a completed
UTC hour and an in-flight marker before D1/provider work. Unknown outcomes stop
across cold starts, without automatic retry or a reset/reconciliation HTTP route.
The adapter records native D1 row metadata and does not write D1 heartbeats or
run idle retention cleanup. The existing financial calendar, Owner/quota,
permission and idempotency fences remain in the canonical application chain.
This adds no D1 migration or remote synthetic fixture.

Core checks passed 168 focused tests and 82 related tests; the pre-packaging-fix
full suite passed 2,923 tests in 106.75 seconds. The post-fix suite passed 2,942
tests in 106.73 seconds, including 19 new package-import regression tests.
Native acceptance passed 16 requests over
three actual workerd incarnations: one local Free expense/audit/occurrence and
record-quota increment; idle, same-hour, cold-restart, future-hour and durable
unknown-marker stops. The marker was manually parked in local DO SQLite; this
was not a native lost-D1-response injection. Reported local D1 totals were 234
statements, 805 rows read and 57 written, including setup/application/probes and
excluding separately applied local CLI migrations. The
[compact proof](../../docs/validation/production-recurring-native-local-2026-10-11.json)
pins 83 source/dependency/migration hashes and the raw evidence hash, with native
attempt metadata left null rather than fabricated. Real provider requests,
remote D1 and remote application operations were zero.

The earlier frozen dry-run produced 728 modules (338.02 KiB gzip) but missed
norulo_server.cloudflare_recurring_scheduler. Cloudflare rejected the attempted
upload with validation 10021; this incomplete package did not activate. Three
read-only reconciliations confirmed the live version ec33db03-2fd4-49a4-8430-9e1cb13fc340,
DB/EMAIL, EmailAdmission namespace and all four Secrets unchanged, with D1/email
1, both AI flags 0, recurrence 0 and no cron.

The repaired frozen actual artifact contains 729 modules (1649.12 KiB total,
340.66 KiB gzip); all 64 canonical modules are byte-equal to source, including
the scheduler helper. Entry closure checks cover 26 imports and the complete
64-module package. Managed local stop/start with fresh Worker/Vite passed server
health 200, proxy health 200 and protected profile 401; local CLI migration
application found no unapplied migrations. These checks made no remote D1 or
provider requests. Source flags remain 0 and source has no cron.
The reviewed future release command creates a scoped temporary Worker-relative
config with exactly one hourly UTC cron and removes it after execution:

```bash
./scripts/deploy-cloudflare.sh --environment production \
  --activate-production --activate-email-auth --activate-ai-suggestions \
  --activate-recurring-expenses --execute --local-checks-passed
```

This is a prepared release path, not evidence of live cron execution. No D1
migration is run by it. After actual publication, record the version, all runtime
flags, independent scheduler namespace, preserved DB/EMAIL/Secrets and exact
cron without remote fixtures or repeated financial acceptance writes.

The deployment checker validates explicit pause switches, host/origin isolation,
separate database identities, no source-service databases, provider separation,
independent production email admission and coordinated preview email/scheduling.
The shell release command never
executes migrations. Dry-run allows placeholders for review; --execute rejects
them. A future remote release needs current user scope and verified configuration,
schema/accounting, callback, provider and end-to-end gates. Source historical
acceptance records do not satisfy Norulo gates.

The inherited preview singleton architecture retains bounded SQL/input/native
accounting, durable unknown-outcome stops and append-only journals. Do not reset
a journal, replay uncertain migrations, or enable recurring remote jobs as part
of ordinary environment startup.
