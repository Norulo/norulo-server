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
Icons await the user's assets.

Both remote configurations are paused with placeholder databases/providers and
no scheduled jobs or email dispatch. The deployment checker rejects the source
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

Before a separately authorized deployment, configure independent Norulo D1 and
Worker/DO resources, GitHub Apps and callbacks, verified domains/DNS, mail sender,
Creem products/secrets and optional AI transport/quality gates. Existing source
provider IDs and historical approvals are not Norulo requirements or permissions.
Database/provider acceptance, email delivery and real payment flows have not been
claimed as local setup results. Keep secret values in secure settings.
