# Norulo Server migration — 2026-10-10

Imported the complete source main tree and history at commit `4bfbea95e5f57a7ac24c1cf264880de50037fd67` into
Norulo/norulo-server, retaining the target repository history, origin, and original
LICENSE. No source branches, application databases, deployed Workers, DNS records,
GitHub Apps, provider accounts or credentials were transferred.

The current source tree uses Norulo/norulo/NORULO consistently: norulo_server
package and imports, package/lock metadata, Worker and CI names, domains,
configuration variables, headers, cookies and token prefixes. API keys use nrk_,
invitations nri_, and cookies nr_session/nr_email_challenge. Web shares the exact
OpenAPI file. Branding within imported validation records is a mechanical copy,
not proof that those resources or results belong to Norulo. Historical JSON
records carry _migration_provenance; unmodified originals remain in Git history.
The original Norulo logo was subsequently downloaded from the shared source and
installed in norulo-web/public/norulo-logo.png. Its SHA256 is
`a9632acbd7a5ad48ad5ff25d6269f617c7655446365344c9db42d504213c710f`.
Derived icons and branding assets have been replaced and audited; no further
user asset upload is required.

At import, both remote configurations were paused with placeholder databases and
providers, and no scheduled jobs or email dispatch. The deployment checker rejects the source
service's database IDs, shared preview/production databases and execution with
unconfigured UUIDs. The inherited Builds plan contains no transferred trigger or
active approval. Historical AGENTS deployment permissions were replaced with
current Norulo authority and the implementation's financial/security invariants.
The existing environment CLOUDFLARE_API_TOKEN binding was preserved.

## Environment and integrity

Reference tests use Python 3.10.12, pytest 9.1.1, PyYAML 6.0.3 and tzdata 2026.5.
Worker packaging uses Python 3.14.2, workers-py 1.17.4, workers-runtime-sdk 1.9.0,
uv 0.12.3 and npm-locked Wrangler 4.136.3. Frozen uv/npm installation succeeded;
dependency integrity hashes and signatures were retained. uv pip check passed.

The migration 0008 SQL comment was rebranded. Its exact source-file manifest
SHA256 was regenerated as
`882a79e4d6135aa3af4d24b794c0d7417a64e1791fc2d26a236ee0ce3bcfd430`.
The schema semantics/fingerprint remain unchanged; all twelve canonical migration
hashes and compiled schema objects passed the offline checker.

The managed network supports HTTPS through its proxy. Workerd's Python bundle
loader initially attempted a direct connection. A supported Workerd disk-cache
option now uses the official bundle downloaded through the existing proxy from
https://pyodide-capnp-bin.edgeworker.net/pyodide_314.0.6_2026-08-17_6.capnp.bin.
Its 13,727,600 bytes matched the pre-existing pinned SHA256
`3c3fd5a4179230e21e018e28b0e735e7c4abd8fe8e4ff39d2fd6bb2ea3a2e260`.
No TLS or artifact verification was bypassed. The cache and wrapper live outside
the tracked repository. pywrangler sync populated ignored runtime packages
without changing dependency locks.

## Migration local acceptance

The complete Python suite passed: 2,553 tests and 66 subtests.
S01 static config/OpenAPI/canonical SQL checks, Worker mirror sync/check, shell
syntax checks and dependency compatibility checks passed. At migration time,
remote configs were unconfigured by design and the execution guard rejected them;
subsequent production setup is recorded below.

The [native local record](norulo-native-local-2026-10-10.json) covers 49 loopback
HTTP requests and 1,671 native statements: 3,921 metered rows read, 689 metered rows
written, and 2,695 separately counted read-only integrity-probe rows. It verifies
expense CRUD, integer money, CAS, idempotency, scoped keys, Origin protection,
recurring execution/revocation/member fences, project removal, invitation
approval/role/removal and shared/project activity scope. The original product
meter, native Python FFI, Durable Object SQLite and native D1 metadata execute;
the journal remains healthy and all accounting deltas match observed native
metadata. Local Miniflare omits total_attempts metadata; the checker reports that
absence and retains reservations instead of fabricating attempts. There were no
remote D1 operations, real provider requests, retries or deployments.

The imported native checker needed fixture repairs for current product behavior:
creation already records the historical start expense; the next scheduler period
requires advancing the synthetic clock. Its row bound accounts for those extra
recorded occurrences, and project removal now physically removes that local
fixture project. Existing installed tzdata is merged only after its full RECORD
integrity validation. These changes affect local acceptance fixtures only,
without changing application behavior. Earlier failed attempts remain in local
logs in separate fresh directories; no unknown remote outcome was retried.

All twelve SQL migrations applied to the local development database. The normal
Worker reached /health and /auth/session at 127.0.0.1:8080. Central environment
startup scripts own the long-running development process after validation.

## Remaining remote prerequisites

The user subsequently registered the real Norulo GitHub App. On 2026-10-10,
GitHub's public API verified Client ID Iv23li78ZPeUgSxJkLUj, slug norulo, owner
Norulo and only Metadata read permission with no events. At that public-metadata
stage, saved callbacks, management options, Client Secret validity and real login
had not been verified; the user-confirmed login is recorded below. See the
[current App checklist](../design/github-project-ledger/github-app-permissions.md).
Earlier on 2026-10-10, the App and its Secrets were configured on a temporary paused Worker, with no D1
or Durable Object binding. Its api.norulo.com Custom Domain is enabled with
previews disabled. Earlier on 2026-10-10, all 18 public production variables were
applied while retaining the two GitHub Secrets by name-only inheritance.
A fresh token-encryption key was securely uploaded, and the user subsequently
saved NORULO_GITHUB_CLIENT_SECRET. Both Secret names were confirmed without
reading values; live OAuth remained unverified then. At that stage, the full ledger
application had not been published and no remote database changes had been made. The Web Worker
was published as version fb3dbf7c-8530-405a-bf01-a9d208136a83. A new D1 create
attempt after the token update returned HTTP 401 Authentication error; the user
subsequently deferred D1 while proceeding with the frontend and production
domains. That deferral applied to the earlier frontend stage and was later
superseded by explicit authorization to resume D1/full production setup.
Initial default Python User-Agent checks returned
403; finite ordinary browser User-Agent checks subsequently confirmed homepage
200 and the expected API/Web proxy 503 SERVICE_SETUP_PENDING, with no-store and
no Set-Cookie. Published branding assets matched local hashes. This establishes
the frontend and paused transport, not real OAuth or ledger acceptance. See the current
[production readiness record](production-readiness-2026-10-10.md).

The subsequent sender-preparation stage set NORULO_EMAIL_FROM=login@auth.norulo.com
and securely uploaded NORULO_EMAIL_CODE_SECRET. The bootstrap then had 19 public
variables and three Secrets, preserving both GitHub Secrets. At that earlier
stage, the sending-domain API returned 403 and no EMAIL binding existed.
After the token permission update, auth.norulo.com was enabled with DNS status
ready, no errors and preview_enabled=false. The Worker now has the EMAIL send
binding restricted to login@auth.norulo.com, without recipient restrictions.
Six added DNS records are confined to the auth subdomain; the existing eight DNS
records and two contact routing rules were preserved. The 19 public variables and
three Secrets were retained, and D1/email-auth flags were both 0 at that stage. No actual email
was sent for acceptance at that stage; production admission and real delivery/
code/session acceptance were still pending. Sender preparation did not activate
the full Server. The subsequent email release and user acceptance are recorded below.

The user subsequently resumed D1 setup with strict Rows Written cost discipline.
The independent norulo-ledger-production database,
c41a1ab7-dffa-4c5d-a213-25f1bb6c78c5, now has all twelve canonical migrations,
each applied once with its journal INSERT in the same request. Native metadata
reports 367 initialization rows written; successful API queries total 4,097 rows
read and 367 rows written. Two rejected read-only compound-SELECT checks returned
no native metrics, so those totals do not claim complete billing for rejected
requests. Bounded five-table checks subsequently passed with zero rows written;
no migration was replayed. All 77 schema objects/fingerprint match canonical v12,
at initialization app_state had only four empty containers and the other 22
application tables were empty. No source database access, remote fixture or business acceptance write
occurred. See the [safe initialization summary](d1-production-init-2026-10-10.json).
The complete Python Worker was subsequently published as version
3ad0cffc-ecc3-47a4-ab5d-a53999528b8c, with the intended DB binding and runtime
D1 access activated to 1 through the explicit overlay; the source default stays
0. All 19 variables and three Secrets, Python compatibility and the restricted
EMAIL binding were read back; workers.dev and preview URLs remain disabled.
Read-only public checks returned homepage 200, API/Web proxy health 200 and
unauthenticated profile 401, all without Set-Cookie. The checks did not perform
OAuth, send actual mail or make business acceptance writes. The user subsequently
reported successful real GitHub sign-in. Installation, credential refresh and
the complete ledger journey remain unverified. At that first full-release stage,
email sign-in was temporarily unavailable with its flag 0 and production admission
pending. The earlier bootstrap and D1 deferral are historical.

The subsequent email-enabled Python Worker release, built from main commit
96d6bee, is version 815a1216-4468-4591-be58-e339d4d2c154. Settings readback verified
all 19 public variables and three Secrets retained, the unchanged production DB,
the restricted EMAIL sender and the independent EMAIL_ADMISSION / EmailAdmission
namespace 6588312f00f74840a37463e72a2d75eb. Runtime D1/email flags are both 1 through
the dual overlay; checked-in defaults stay 0. workers.dev and preview URLs remain
disabled. Finite API/Web health checks returned 200 and unauthenticated profiles
401, without Set-Cookie. The release did not run D1 migrations, seed remote
fixtures or send acceptance mail. The user then confirmed receiving the
verification code and successfully logging in by email. This establishes
user-confirmed delivery/code/browser login acceptance, without claiming account
linking, sign-out, refresh or other email abuse/security scenarios were tested
against production. Existing local tests cover the separate security contracts.

The remaining core acceptance includes the other App/session behaviors and actual
authenticated ledger use; GitHub sign-in is user-confirmed and full Worker/DB
publication is complete. The requested
email login now has a published independent EmailAdmission SQLite DO, with native
acceptance passed and actual code delivery/login confirmed by the user. Its
limiter stores hashed subjects/counters, uses transactional fail-closed admission
and does not write D1. Later releases must retain both --activate-production and
--activate-email-auth overlays. Local reference tests reported 2,629 passes;
118 focused tests passed after three overlay cases were added, with a separate
62-test/27-subtest admission check. Twenty-six bounded native localhost POSTs
verified limiter behavior without D1/provider bindings, remote requests or mail;
the pinned 728-module packaging dry-run also passed. These overlapping runs are
not additive totals. The next requested steps then were to configure
TYPESAFE_API_KEY and verify actual AI quality, Owner entitlement and monthly
allowance, followed by production recurrence before cron. AI/recurrence were
still disabled at that checkpoint. Creem
products/secrets remain optional feature work.

The subsequent AI preparation securely added TYPESAFE_API_KEY as the fourth
Worker Secret, retaining the GitHub pair and email-code Secret. Both AI flags
were 0 at that preparation stage; the cloud network Secret binding was absent
and the inspected revision-8 runtime had only the Cloudflare token. Real quality
capture was blocked and real model calls were zero then. The complete local
reference suite then passed 2,768 tests before the final email-preservation activation-guard repair. Five
canonical native-gateway fake-provider cases passed without D1,
remote application requests or real provider calls. No gateway repair was needed;
native real-provider HTTPS remains unverified. The fixed 36-case quality journal
allocates at most 99,108 micro-USD in conservative reservations, stops on failed/
unknown outcomes and cannot be restarted elsewhere to retry. Current policy is
the configurable default Pro $3 / Max $5 per UTC calendar month, Free $0, no
rollover or daily request cap.
The explicit --activate-ai-suggestions overlay and static guard were implemented
locally at this checkpoint, before publication/production activation. Their
implementation did not itself establish real quality acceptance. After the guard repair, 177 targeted tests
and 28 subtests passed, alongside S01 and shell checks. The final stable full
reference suite passed 2,777 tests in 106.08 seconds after the guard/native-fixture
repairs. These overlapping checks are not additive totals. Future AI releases
must explicitly retain
--activate-production and --activate-email-auth alongside the AI overlay.
See the unchanged [AI local snapshot](ai-local-readiness-2026-10-10.json).

The next AI stage is recorded on 2026-10-11 in Asia/Shanghai. Runtime specification
11 has both network Secret bindings present, preserving the Cloudflare token.
The existing single quality journal then completed exactly 36 real CPython HTTPS
requests once: 73 events (one session, 36 reservations and 36 completions), 36
valid responses, no retries and no remote D1/application requests. Both quality
gates passed: English/Chinese each 18 cases, category and target each 32/32 clear
labels correct and 4/4 uncertain labels withheld, all six reversed-order pairs
consistent and no false actionable hints. Usage was 23,850 input / 4,144 output
tokens, estimated $0.0010017, not an invoice. The full 99,108 micro-USD reservation
remains retained. Fresh [results](ai-quality-2026-10-11-results.jsonl),
[aggregate](ai-quality-2026-10-11-aggregate.json) and
[execution/source envelope](ai-quality-2026-10-11-execution.json) are separate from
both imported records and the earlier blocked snapshot. They do not prove
customer error rates or native Worker real-provider HTTPS, which remains untested.
Stored Owner Pro/Max entitlement/opt-in and UTC-month allowance fences passed
local checks; production AI was 0/0 at that quality checkpoint. Production
recurring implementation was still pending at the AI-quality checkpoint, with
no cron active then. That snapshot remains unchanged.

Production recurrence is now implemented locally through the independent
RECURRING_SCHEDULER / RecurringScheduler SQLite DO, fixed scope
norulo-production-recurring-v1. Core review and 168 focused / 82 related tests
passed; the pre-packaging-fix suite passed 2,923 tests in 106.75 seconds after the
localized D1 SQL-literal guard repair. The later packaging-fix suite passed 2,942
tests in 106.73 seconds, including 19 new import-closure regressions.
Native acceptance passed 16 bounded local
requests over three workerd incarnations, with 234 D1 statements / 805 rows read /
57 written for setup, application, scheduler and probes. Separate twelve-file
local CLI migration setup is excluded from those native totals. Exactly one
Free expense/audit/occurrence and record-quota increment were verified, alongside
idle/same-hour/cold-restart/future-hour gates. A manually parked durable active
marker remained stopped after cold restart; no native lost-response injection
was claimed. Independent review matched 83 source/dependency/migration hashes and
41 raw metadata groups. See the
[compact native proof](production-recurring-native-local-2026-10-11.json).

The earlier all-overlay frozen dry-run produced 728 modules (338.02 KiB gzip),
but it omitted norulo_server.cloudflare_recurring_scheduler. Cloudflare rejected
the attempted upload with validation 10021; the incomplete package never
activated. Three read-only reconciliations confirmed the unchanged live version
ec33db03-2fd4-49a4-8430-9e1cb13fc340, DB/EMAIL, EmailAdmission namespace and all four
Secrets, with D1/email 1, both AI flags 0, recurrence 0 and no installed cron.
The repaired actual artifact contains 729 modules (1649.12 KiB total, 340.66 KiB
gzip), with all 64 canonical modules byte-equal to source. Absolute/relative
entry imports and full module closure are now checked. Local fresh Worker/Vite
health checks returned 200/200 and protected profile 401; local migration
application found no unapplied files, without remote D1/provider requests.
The later verified release A is recorded below; live scheduling acceptance
remains separate. The new
DO migration is distinct from D1; no remote D1 migration/fixture/model request was
added by this local scheduler validation. Existing source
provider IDs and historical approvals are not Norulo requirements or permissions.
Database/provider acceptance, email delivery and real payment flows have not been
claimed as local setup results. Keep secret values in secure settings.
All development/regression/browser fixture tests stay on local D1 or SQLite;
remote smoke checks are read-only. Never seed or rebuild production for testing,
repeat remote write-based acceptance or blindly retry unknown migration outcomes.

## Verified production release A — 2026-10-11

At 05:38:43 UTC, finite read-only verification accepted Server version
b5642a63-1643-418a-b494-bb7bcf427050 from main ebd11baf and Web version
26697b80-76dc-405b-a0c0-c2ea7c0735f7 from main 3531f8a. All five runtime flags
are 1, with exactly one hourly UTC cron (0 * * * *), the original DB/EMAIL,
retained EmailAdmission namespace and four Secrets, and new RecurringScheduler
namespace b3f41def1906481e9c72662debf4b505. Workers.dev and preview URLs remain
disabled. The earlier ec33/no-cron and rejected-upload records above are history.

Seven Cloudflare GETs and finite public checks verified both health endpoints
200, both unauthenticated profile endpoints 401, homepage 200, no Set-Cookie,
original-logo hash and www redirect 308 preserving path/query. This verification
used zero remote D1 SQL, business mutations, model/email requests, manual cron
invocations or replayed migrations. The remote migration-tag field was absent;
namespace identity was verified while checked-in tag definitions were retained.

The [durable dated record](production-release-2026-10-11.json) binds full source
heads and the final 2,942 Server / 1,654 Web test checkpoints. It is release A,
not a guarantee that these version IDs remain latest after later uploads. Native
Worker real-provider HTTPS and live scheduled financial posting remain untested;
the prior direct HTTPS quality capture and local native proof remain unchanged.

## Earlier minimal daily preparation — 2026-10-11

After release A, the user requested once-daily polling and delegated the
recommended Beijing 00:10 schedule, 10 16 * * * UTC. That minimal daily revision was locally
prepared, not published; the capacity revision below supersedes it. Release A
remains the dated earlier hourly checkpoint; release B below later replaced it.
Weekly/monthly/quarterly/yearly rule frequencies and each rule's timezone/period
date remain unchanged. Stored UTC due times are scanned once per day; other
timezones can wait nearly 24 hours. Existing completed_hour journal semantics,
scope/class/tag/namespace and no-retry unknown stops were retained at that
checkpoint. Its then-existing 10-rule/10-handled/3-global-catch-up limits could leave a backlog
above 10 due rules. One user-requested production capacity SELECT found
total/active/due counts zero with native read 1/write 0, no fixtures or retries.

Fresh [daily native proof](production-recurring-native-daily-local-2026-10-11.json)
passed 16 local requests across three incarnations, 234 statements/read 805/
written 57, excluding distinct local CLI migration setup. Extra-hour ticks and
manual unknown markers are local fixture seams; no remote cron/provider
acceptance is claimed. All 83 current source/dependency/migration hashes and the
64-module mirror plus separate blank initializer matched. Final daily suite/
packaging and actual release/readback were still pending at that minimal
preparation checkpoint. The hourly proof, release
A JSON and completed real AI journal/source hashes remain immutable.

## Verified daily capacity revision — release B

The new source retains Beijing 00:10 (10 16 * * * UTC), per-rule timezone and
original period date, but replaces the small global tick bound with validated
hash-scoped Owner chunks in the existing DO binding/class/namespace. No D1
migration or journal reset is introduced. Legacy completed_hour units and
active/stopped states remain compatible, with an additional daily checkpoint.
Root caps selection at 5,000 Owners, handling at 10,000 occurrences, all child
RPCs (including read-only progress) at 8,192, and page/deferred carry at 64.
Eight logical workers handle chunks of at most 20 occurrences, 800 native SQL
statements and a conservative 200-statement occurrence reserve. Actual financial
quotas, independent atomic batches, actor/member/key/CAS/idempotency fences stay
enforced. Known pre-dispatch minute-quota denial defers to the next minute,
releasing the worker slot without a D1 heartbeat or permanent block.

Each Owner has a 120-second hard schema/execution deadline. Root stops new
launches at 600 seconds and awaits started Owners within their remaining bound,
below the official Cron wall limit of 900 seconds. Native financial uncertainty
permanently stops its Owner while others continue. A transport exception can
advance only after read-only progress proves the exact chunk completed; otherwise
new launches stop, siblings settle and Root remains permanently globally stopped.
Same-chunk completed replay uses cached results with no D1; no unknown retries,
quarantine/reset API or reinterpretation of old hour state is added.

Strict production limits are cpu_ms=300000 and subrequests=9000. The
[official source record](cloudflare-scheduler-limits-2026-10-11.json) preserves
conditional plan limits and D1 counting ambiguities; supported configuration
readback does not confirm Paid billing. Frozen actual packaging has 729 modules,
1675.10 KiB total/348.25 KiB gzip, with all 64 canonical bytes and import closure
verified. The definitive final full suite passed 3,009 tests in 115.01 seconds.
The [final compact local capacity proof](production-recurring-load-native-local-2026-10-11.json)
records 8-way overlap and natural 1,000/3,000-occurrence profiles across 200/600
Free Owners. Natural daily passes took 33.985/107.635 seconds with peak 8 and
maximum Owner SQL 178. Actual daily-window totals were respectively
27,606/73,063/24,000 and 82,812/228,201/72,000 SQL/read/write; whole-profile
fixture/setup/integrity totals are recorded separately. Warm/cold manual unknown
markers remained stopped without D1; no real lost-response injection or production
SLA is claimed. Daily publication/readback passed in dated release B; live
financial execution remains untested. Earlier hourly/release A/minimal
daily records and all completed real AI quality evidence remain unchanged.

At 2026-10-11 06:38:08 UTC, daily release B was published and verified from
Server main ded49a46b06f5f79e2996f58d773d66acaddc0a0, version
e2e4e02d-ac9a-4c20-852f-f6cbfe5b5ae4, and Web main
bef23ee7cca378614cdf1e7cdcc8494601c86648, version
0c63c81e-1f91-4b72-bf3b-f949b7840ad8. Seven Cloudflare GETs and seven public
checks verified exactly one daily cron, strict CPU/subrequest limits, all five
flags 1, unchanged DB/two DO identities, EMAIL/four Secrets, disabled previews,
health 200, protected profiles 401, homepage 200, original logo and www redirect.
No D1 SQL, application mutation, manual cron, provider call or migration replay
was performed by these checks. Web's later production-guide correction passed
15 focused tests in 3.84 seconds, lint and production build; its prior 1,654-test
whole-suite checkpoint remains historical. The
[dated daily release record](production-daily-release-2026-10-11.json) preserves
the exact readback/hash without claiming future latest versions or live
financial/provider execution.
