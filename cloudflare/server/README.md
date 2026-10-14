# Norulo Python Worker

The source main branch has been imported and rebranded. The existing
wrangler.jsonc is explicitly local: no routes, remote=false, NORULO_MODE=local.
wrangler.preview.jsonc remains an undeployed offline reference.
wrangler.production.jsonc selects the initialized independent D1 database, with
its default access switch paused and account, domain, GitHub App and email settings described
below. All five checked-in feature defaults stay 0 and source has no cron;
verified daily release B uses all activation overlays to set runtime D1/email/AI/
recurrence flags to 1 with one daily UTC cron. Preview and automatic schema
upgrades remain disabled.
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
815a1216-4468-4591-be58-e339d4d2c154. Verified release A on 2026-10-11 at
05:38:43 UTC is b5642a63-1643-418a-b494-bb7bcf427050 from server main ebd11baf.
Readback retained DB c41a1ab7-dffa-4c5d-a213-25f1bb6c78c5, the restricted EMAIL
sender, EmailAdmission namespace 6588312f00f74840a37463e72a2d75eb and four Secrets,
and verified RecurringScheduler namespace b3f41def1906481e9c72662debf4b505.
Nineteen public variables match the source with exactly five activation flags
overlaid to 1; one hourly UTC cron (0 * * * *) is installed. The Secret-update
revision ec33db03-2fd4-49a4-8430-9e1cb13fc340 is an earlier checkpoint. Checked-in
flags stay 0, source has no cron, and Workers.dev/public previews are disabled.
The [dated release record](../../docs/validation/production-release-2026-10-11.json)
records Web version 26697b80-76dc-405b-a0c0-c2ea7c0735f7 and the finite readback;
these IDs are not a guarantee of future latest versions.
Verified daily release B at 2026-10-11 06:38:08 UTC is Server
e2e4e02d-ac9a-4c20-852f-f6cbfe5b5ae4 from main ded49a46 and Web
0c63c81e-1f91-4b72-bf3b-f949b7840ad8 from main bef23ee7. The
[dated daily release record](../../docs/validation/production-daily-release-2026-10-11.json)
verifies exactly one cron 10 16 * * * UTC, limits cpu_ms=300000/subrequests=9000,
19 public variables with five flags 1 and retained DB, both DO namespaces, EMAIL
and four Secrets. Release A above remains an immutable hourly checkpoint.
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
Preserve both overlays plus the now-enabled AI/recurrence overlays on subsequent
releases; omitting an overlay restores its defaults to 0 and pauses that feature. The [readiness record](../../docs/validation/production-readiness-2026-10-10.md#production-email-admission)
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

The current Owner policy admits Pro and Max only, with $3 and $12 respectively per
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
future release preserves D1/email and the now-enabled recurrence together:

```bash
./scripts/deploy-cloudflare.sh --environment production \
  --activate-production --activate-email-auth --activate-ai-suggestions \
  --activate-recurring-expenses --execute --local-checks-passed
```

The AI helper/guard changes are published in verified release A. The final guard
repair requires the explicit email overlay as well, protecting accepted login.
Post-repair targeted validation passed 177 tests and 28 subtests, alongside S01
default/full-overlay and shell checks; these overlap the final full suite.
The static guard checks exact matching flags, D1/isolation and the declared Secret; it cannot verify quality.
Source AI flags remain 0; verified release A has both runtime AI flags 1. Stored
Owner Pro/Max entitlement/opt-in and UTC-month reservation/fallback fences passed
local checks. The independent production scheduler passed local/native/final
suite gates below, and verified release B has recurrence 1 and the exact daily
cron. Live scheduled posting and native real-provider HTTPS remain untested.
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
read-only reconciliations at that rejection checkpoint confirmed version
ec33db03-2fd4-49a4-8430-9e1cb13fc340,
DB/EMAIL, EmailAdmission namespace and all four Secrets unchanged, with D1/email
1, both AI flags 0, recurrence 0 and no cron.

The repaired frozen actual artifact contains 729 modules (1649.12 KiB total,
340.66 KiB gzip); all 64 canonical modules are byte-equal to source, including
the scheduler helper. Entry closure checks cover 26 imports and the complete
64-module package. Managed local stop/start with fresh Worker/Vite passed server
health 200, proxy health 200 and protected profile 401; local CLI migration
application found no unapplied migrations. These checks made no remote D1 or
provider requests. Source flags remain 0 and source has no cron.
The verified release command, also required to preserve activation on subsequent
uploads, creates a scoped temporary Worker-relative config and removes it after
execution. Verified release B selects one daily UTC cron, 10 16 * * *
(Beijing 00:10), replacing the earlier release A hourly schedule:

```bash
./scripts/deploy-cloudflare.sh --environment production \
  --activate-production --activate-email-auth --activate-ai-suggestions \
  --activate-recurring-expenses --execute --local-checks-passed
```

Verified release A used these activation overlays with the earlier hourly
schedule and passed seven read-only Cloudflare GETs,
health/profile transport checks and www path/query redirect checks. No D1
migration is run by it. Verification used zero remote D1 SQL, application
mutations, provider requests or manual cron invocations. Readback verified the
scheduler namespace, not a remote migration tag: that API field was absent.
The checked-in DO tag definitions are retained. Installed cron does not prove
actual scheduled financial/provider execution; do not add remote fixtures or
repeated financial acceptance writes to claim it.

The published daily capacity revision retains weekly/monthly/quarterly/yearly
rule frequencies. Each rule's timezone determines stored UTC next_run_at; the
daily poll scans due values <= server time and preserves the original period
date. Another timezone can be delayed by nearly 24 hours. Daily publication and
configuration readback passed in dated release B; live financial behavior is untested.

The existing binding/class/namespace now hosts Root coordination and permanent,
validated hash scopes for Owner DOs. Legacy completed_hour units and active/
stopped journal state remain compatible, without reset/reinitialization. An
additional daily epoch/checkpoint bounds scanning and progress. Root pages and
deferred carry hold at most 64 Owners; daily caps are 5,000 selected Owners,
10,000 handled occurrences and 8,192 total child RPCs including status/progress.
Eight logical Owner workers process chunks of at most 20 occurrences. The
800-native-SQL-statement chunk cap and 200-statement occurrence reserve are
engineering bounds, not an official D1 quota interpretation or writing budget.
Each posting retains its original independent atomic financial batch and actual
Owner, actor/member/key, CAS, idempotency and quota fences. Known pre-dispatch
minute-quota denial defers to the next minute and releases the worker slot,
without a D1 heartbeat or permanent rule block.

Owner hard deadline is 120 seconds including schema/execution. Root's 600-second
soft deadline stops new launches, then awaits started Owners within their
remaining 120-second bound; Cron's official wall limit is 900 seconds. Known
native financial uncertainty permanently stops the affected Owner while others
continue. A transport exception is advanced only if read-only progress proves
that exact chunk completed. If it cannot prove settlement, stop new launches,
await siblings and retain the existing Root global permanent unknown stop. No
unknown retry, quarantine or reset endpoint is added. Completed same-chunk
replay is cached without D1; subsequent chunk identity is unique.

The production config strictly sets limits.cpu_ms=300000 and
limits.subrequests=9000. Release B publication/readback verified support; the account's
Paid billing subscription remains unconfirmed. See
[official limits provenance](../../docs/validation/cloudflare-scheduler-limits-2026-10-11.json)
for the CPU/wall distinction and unresolved D1 statement/dispatch/per-Owner
counting semantics. Frozen actual packaging passed 729 modules, 1675.10 KiB total
and 348.25 KiB gzip, with all 64 canonical modules byte-equal, blank initializer
and absolute/relative import closure verified; no remote D1/provider requests.

The earlier 16-request minimal daily proof is
[historical](../../docs/validation/production-recurring-native-daily-local-2026-10-11.json),
not load acceptance. The final full suite passed 3,009 tests in 115.01 seconds.
Final local capacity profiles passed; the
[compact load proof](../../docs/validation/production-recurring-load-native-local-2026-10-11.json)
pins producer/runtime/source hashes and the large raw captures outside Git.

| Local profile | Owners × rules | Daily-pass wall time | Peak Owner concurrency | Daily SQL / rows read / rows written | Whole-profile SQL / rows read / rows written |
| --- | --- | --- | --- | --- | --- |
| Overlap diagnostic | 8 × 1 | 1.621 s, including an injected 1,200 ms wait per Owner | 8 | 185 / 1,551 / 192 | 484 / 2,614 / 416 |
| Natural 1,000 occurrences | 200 × 5 | 33.985 s | 8 | 27,606 / 73,063 / 24,000 | 48,897 / 164,618 / 41,600 |
| Natural 3,000 occurrences | 600 × 5 | 107.635 s | 8 | 82,812 / 228,201 / 72,000 | 146,503 / 502,333 / 124,800 |

Every successful Owner's native metrics matched its RPC trace. Both natural
profiles had maximum Owner SQL 178; Root SQL maxima were 6 and 12. Same-epoch
and cold Root replay had zero D1 operations. Warm/cold manually parked Owner
and legacy Root unknown markers stayed fail-closed with zero D1; this was not
injected loss of a real financial commit or an RPC transport response. Known
minute-quota deferral is covered by reference tests, not these native profiles.
Whole-profile costs include local fixtures, rule creation, setup and integrity
probes; local CLI migrations and DO SQLite billing are excluded. The overlap
profile demonstrates concurrency only. Daily publication/readback passed in
dated release B; live financial/provider behavior remains untested. The load is
spread across independent Owners, not a same-Owner
throughput promise or Cloudflare SLA. One separate
user-requested production capacity SELECT found total/active/due rules all zero,
read 1/write 0, no fixtures or retries. Development/load tests remain on isolated
local D1; no daily remote writing allowance is invented.

The current bounded local checker is
[scripts/check-production-recurring-load-native-local.py](../../scripts/check-production-recurring-load-native-local.py).
The historical check-production-recurring-native-local.py rejects this Owner
architecture before creating a directory or executing SQL; do not use it as the
current acceptance command. Use a fresh isolated local run directory/output for
each profile, and do not rerun an accepted profile merely to reproduce timing:

```bash
python scripts/check-production-recurring-load-native-local.py \
  --occurrences 8 --overlap-delay-ms 1200 \
  --run-dir /workspace/.norulo-environment/recurring-overlap-new-local \
  --output /workspace/.norulo-environment/recurring-overlap-new-local/evidence.json
python scripts/check-production-recurring-load-native-local.py \
  --occurrences 1000 \
  --run-dir /workspace/.norulo-environment/recurring-1000-new-local \
  --output /workspace/.norulo-environment/recurring-1000-new-local/evidence.json
python scripts/check-production-recurring-load-native-local.py \
  --occurrences 3000 \
  --run-dir /workspace/.norulo-environment/recurring-3000-new-local \
  --output /workspace/.norulo-environment/recurring-3000-new-local/evidence.json
```

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
