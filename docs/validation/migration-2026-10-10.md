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

## Current local acceptance

The complete Python suite passed: 2,553 tests and 66 subtests.
S01 static config/OpenAPI/canonical SQL checks, Worker mirror sync/check, shell
syntax checks and dependency compatibility checks passed. Remote configs remain
unconfigured by design and the execution guard rejects them.

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
was sent for acceptance. Production email login still needs an independent
admission implementation and real delivery/code/session acceptance. This does
did not activate the full Server.

The user subsequently resumed D1 setup with strict Rows Written cost discipline.
The independent norulo-ledger-production database,
c41a1ab7-dffa-4c5d-a213-25f1bb6c78c5, now has all twelve canonical migrations,
each applied once with its journal INSERT in the same request. Native metadata
reports 367 initialization rows written; successful API queries total 4,097 rows
read and 367 rows written. Two rejected read-only compound-SELECT checks returned
no native metrics, so those totals do not claim complete billing for rejected
requests. Bounded five-table checks subsequently passed with zero rows written;
no migration was replayed. All 77 schema objects/fingerprint match canonical v12,
app_state has only four empty containers and the other 22 application tables are
empty. No source database access, remote fixture or business acceptance write
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
the complete ledger journey remain unverified; email sign-in is temporarily
unavailable while its flag is 0 and production admission remains pending.
The earlier bootstrap and D1 deferral are historical.

The remaining core acceptance includes the other App/session behaviors and actual
authenticated ledger use; GitHub sign-in is user-confirmed and full Worker/DB
publication is complete. The requested
email login additionally needs independent production admission and real
delivery/code/session acceptance; its sending domain and EMAIL binding are now
prepared. Creem products/secrets, AI transport/quality
gates and background recurrence are optional feature work. Existing source
provider IDs and historical approvals are not Norulo requirements or permissions.
Database/provider acceptance, email delivery and real payment flows have not been
claimed as local setup results. Keep secret values in secure settings.
All development/regression/browser fixture tests stay on local D1 or SQLite;
remote smoke checks are read-only. Never seed or rebuild production for testing,
repeat remote write-based acceptance or blindly retry unknown migration outcomes.
