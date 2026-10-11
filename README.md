# Norulo Server

Cloudflare Python Worker for Norulo, a project expense ledger for developers
and teams. It owns account identity, cookie/API-key authorization, shared ledgers,
projects, categories, exact money, recurring expenses, reports and conditional
AI assistance. Expenses remain separate from platform subscription payments,
and reports keep each currency separate.

This repository contains the complete imported source main history and a Norulo
rebrand. The current schema is version 12. Imported provider deployments and
validation records are historical; source databases, data and provider deployments
have not been transferred to Norulo. See [migration status](docs/validation/migration-2026-10-10.md).
The user has subsequently authorized a production-only release. Current resource,
credential and feature readiness is recorded in
[production readiness](docs/validation/production-readiness-2026-10-10.md);
the Web Worker has been published, and api.norulo.com was first bound to the
temporary paused norulo-server-production bootstrap returning SERVICE_SETUP_PENDING.
The user then resumed D1 setup on 2026-10-10. The independent production database
now has all twelve canonical migrations and verified schema v12; native metadata
reports 367 rows written for necessary initialization. Only four empty app_state
containers were seeded; the other 22 application tables were empty at initialization. No remote
test fixtures, business acceptance writes or source data were inserted.
The complete Python Worker was first published as version
3ad0cffc-ecc3-47a4-ab5d-a53999528b8c. The email feature release was
815a1216-4468-4591-be58-e339d4d2c154. Verified release A on 2026-10-11 at
05:38:43 UTC is b5642a63-1643-418a-b494-bb7bcf427050, from server main ebd11baf.
It retains the initialized DB, EMAIL, EmailAdmission namespace and four Secrets,
sets all five D1/email/AI/recurrence flags to 1 through explicit overlays, and
has exactly one hourly UTC cron (0 * * * *). Web release A is
26697b80-76dc-405b-a0c0-c2ea7c0735f7 from main 3531f8a. The earlier Secret-update
revision ec33db03-2fd4-49a4-8430-9e1cb13fc340 is historical. See the dated
[release record](docs/validation/production-release-2026-10-11.json); it does not
assert that these version IDs remain the latest after later uploads. The earlier bootstrap and D1 deferral are historical.
Verified daily release B at 2026-10-11 06:38:08 UTC is Server
e2e4e02d-ac9a-4c20-852f-f6cbfe5b5ae4 from main ded49a46 and Web
0c63c81e-1f91-4b72-bf3b-f949b7840ad8 from main bef23ee7. Its dated
[daily release record](docs/validation/production-daily-release-2026-10-11.json)
verifies exactly one daily cron, 10 16 * * * UTC (Beijing 00:10), limits
cpu_ms=300000/subrequests=9000, all five flags 1 and preservation of the original
DB, both DO namespaces, EMAIL and four Secret names. Release A remains historical;
these read-only checks do not prove a live scheduled financial posting.
Finite read-only checks confirmed homepage HTTP 200, both API/Web proxy health
endpoints HTTP 200 and unauthenticated profile endpoints HTTP 401, with no
Set-Cookie. These checks verify publication and authenticated access enforcement;
the user subsequently confirmed successful real GitHub sign-in. Repository
installation, credential refresh and the complete ledger journey remain unverified.
The user has also confirmed ordinary expense recording. See the
[production operations runbook](docs/operations.md) for Free-only billing,
natural daily checks, alert status and financial recovery boundaries.
The user has registered [Norulo's GitHub App](https://github.com/apps/norulo);
its public identity and Metadata-only permission were verified on 2026-10-10.
The user has securely saved NORULO_GITHUB_CLIENT_SECRET, and
the fresh token-encryption key is also present. The subsequent sender-preparation
stage added NORULO_EMAIL_FROM=login@auth.norulo.com and securely generated/uploaded
NORULO_EMAIL_CODE_SECRET. The published Python Worker retains 19 public variables and three
Secrets at that release, with both GitHub Secrets retained. These checks establish
presence/settings consistency; actual login acceptance is reported separately
below. The later AI preparation added TYPESAFE_API_KEY as a fourth Worker Secret,
while both AI flags were still 0 at that preparation checkpoint.
The earlier sending-domain API 403 was resolved after the token permission update.
auth.norulo.com is now enabled with DNS status ready and sending previews disabled.
The Worker has an EMAIL send binding restricted to login@auth.norulo.com, with no
recipient restriction. Existing contact Email Routing DNS/rules were preserved.
No acceptance email was sent during sender setup. NORULO_D1_ACCESS_ENABLED and
NORULO_EMAIL_AUTH_ENABLED remain 0 in the checked-in configuration; production
activation uses the dual --activate-production / --activate-email-auth deployment
overlay. The independent production EmailAdmission SQLite Durable Object passed
native local acceptance and is published/enabled. The user subsequently confirmed
receipt of the verification code and successful email login, establishing
user-confirmed delivery, code verification and browser login acceptance. Account
linking, sign-out and session refresh remain separately unverified. No additional
mail-provider Secret is required for this native Cloudflare binding.
The user-confirmed login does not validate all App management options or the
installation flow; see the
[registration checklist](docs/design/github-project-ledger/github-app-permissions.md).
The current release targets norulo.com and api.norulo.com in production only.
Preview configuration remains an offline reference and is not a release target.
The original Norulo logo is installed in norulo-web/public/norulo-logo.png;
its derived icons and branding assets have been replaced and audited.

The Worker entry is cloudflare/server/src/entry.py. norulo_server/ owns its
modules; sync_server_modules.py generates the ignored Worker mirror. The
[OpenAPI contract](openapi/ledger-v1.yaml) is shared with norulo-web. Both clients
use NORULO_* bindings, X-Norulo-* headers, nr_session cookies, nrk_ API keys and
nri_ invitations.

## Development

Reference tests use Python 3.10.12. Worker tooling uses locked Python 3.14.2 and
Wrangler 4.136.3. Keep all dependency locks and integrity verification enabled.

```bash
uv sync --frozen --extra deployment --python 3.10.12
uv run --frozen --extra deployment --with pytest python -m pytest tests
uv run --frozen --extra deployment python scripts/check-ledger-s01.py --allow-placeholders
uv run --frozen --extra deployment python cloudflare/server/sync_server_modules.py
uv run --frozen --extra deployment python cloudflare/server/sync_server_modules.py --check
bash -n scripts/deploy-cloudflare.sh
cd cloudflare/server
npm ci
uv sync --frozen --python 3.14.2
uv run --frozen --python 3.14.2 pywrangler dev --local --config wrangler.jsonc --ip 127.0.0.1 --port 8080
```

Apply the checked-in SQL migrations only to the same local persistence directory
before exercising ledger routes. Synthetic local tests do not prove real OAuth,
email, payments, AI providers or remote Cloudflare behavior.

## Configuration

The [Worker guide](cloudflare/server/README.md) explains local and remote setup.
Preview remains paused and undeployed. The production config selects the initialized
independent D1 database, keeps its default access switch at 0, and has no schedules.
All five checked-in feature flags stay 0 and the source has no schedule. Verified
release B uses explicit overlays to enable D1/email/AI/recurrence and exactly one
daily cron, 10 16 * * * UTC (Beijing 00:10). Payments remain unconfigured.
The reviewed Free-only catalog supports public Free use without a payment
provider: actual allowances and zero price, unavailable Pro/Max prices and disabled
checkout. Malformed payment configuration still fails closed. Real payments
remain deferred; deployment evidence records when this change is live.
Production has the prepared EMAIL
send binding and independent admission namespace; email authentication is enabled
in the published runtime through the explicit overlay. Production's public
GitHub Client ID and slug identify the verified Norulo App. The two GitHub Secrets
and email-code Secret, plus the newly configured TYPESAFE_API_KEY, are declared
by name for inheritance during subsequent uploads; secret presence and actual
provider acceptance remain separate checks.
The execution guard rejects
placeholders and the source service's resource IDs. Configure independent Norulo
resources and callbacks before production activation.

With D1 and the complete Python Worker published, the core release still needs
verification of the remaining App options, session/sign-out/refresh behavior
and actual user ledger acceptance. Real GitHub sign-in is user-confirmed.
Development business-write regression
tests continue to use local D1 or SQLite.
The requested email-login feature is published/enabled with independent production
admission, and the user confirmed receipt of the code and successful login. Future
releases must preserve both activation overlays to retain runtime D1/email flags
of 1. Its sending domain and restricted EMAIL binding are verified.
AI quality capture is now complete: runtime specification 11 has both network
Secret bindings present, retaining the Cloudflare token. The single fixed journal
made 36 real CPython HTTPS requests once, with both quality gates passing, no
retry and no D1/application requests. The $0.0010017 usage estimate is not an
invoice; the full $0.099108 reservation is retained. Fresh results are recorded
for 2026-10-11 in Asia/Shanghai, separately from the earlier blocked snapshot and
imported source history.
The AI-stage local suite passed 2,777 tests after the activation-guard repair,
and the canonical native gateway passed five loopback fake-provider cases; these do not establish real model quality or native
provider HTTPS acceptance. Current Owner allowance is Pro $3 / Max $5 per UTC
calendar month under the configurable default policy, with no rollover; Free has
no AI allowance. Stored Owner entitlement/opt-in and monthly fences passed local
checks; native Worker real-provider HTTPS remains untested. The AI helper/guard
changes are published in verified release A, with both runtime AI flags 1.
The independent production RecurringScheduler is implemented and locally
reviewed: native 16-request/three-incarnation acceptance and the post-packaging-fix
full suite passed 2,942 tests in 106.73 seconds. Local D1 metadata totals were 234 statements, 805 rows read and 57
written, including setup/application/probes and excluding the separate CLI
migration setup. Verified daily release B has recurrence 1 and the exact daily UTC
cron; this control-plane verification does not prove a live financial posting.
The daily capacity revision is published with verified configuration. It uses
bounded parallel Owner chunks: 8 logical workers, at most 20 occurrences and
800 SQL statements per chunk, with 120-second Owner deadlines. Root stops new
launches after 600 seconds and awaits started work; daily engineering caps are
5,000 selected Owners, 10,000 handled occurrences and 8,192 child RPCs. Financial
quotas/atomic batches remain unchanged; these caps do not guarantee throughput
or allow development writes to remote D1. Rule frequencies, timezones and period
dates remain intact; other timezones can wait nearly 24 hours. Known financial
unknowns stop the affected Owner; unresolved transport uncertainty stops new
launches and ultimately Root, with no automatic retry. One user-requested
production capacity SELECT found total/active/due rules all zero, read 1/write 0,
with no fixtures. Final local load acceptance passed: 1,000 occurrences across
200 Owners completed in 33.985 seconds and 3,000 across 600 Owners in 107.635
seconds, both at peak concurrency 8. These local measurements are not a production
SLA. See the [compact capacity proof](docs/validation/production-recurring-load-native-local-2026-10-11.json)
for separate daily-window and whole-profile costs. Daily publication/readback
passed in dated release B; live financial execution remains untested.
The [earlier minimal daily proof](docs/validation/production-recurring-native-daily-local-2026-10-11.json)
is an immutable historical checkpoint, not evidence of the new load capacity.
The earlier 728-module release package omitted the
scheduler helper and was rejected by Cloudflare validation 10021. Three read-only
reconciliations confirmed that the live version and configuration stayed unchanged.
The repaired actual artifact contains 729 modules, with all 64 canonical modules
byte-equal to source; local fresh-start health/proxy checks passed. Creem payments
remain optional for the core release. See
[current AI quality evidence](docs/validation/ai-quality-2026-10-11-execution.json),
the unchanged [earlier local snapshot](docs/validation/ai-local-readiness-2026-10-10.json)
the [local recurring proof](docs/validation/production-recurring-native-local-2026-10-11.json)
and the [remaining release checklist](docs/validation/production-readiness-2026-10-10.md#remaining-release-checklist).

Development and regression tests must use local D1 or SQLite. Remote setup is
limited to necessary unapplied canonical migrations, executed once with native
row metrics recorded; production smoke checks are read-only. Never seed remote
fixtures, rebuild production for testing or blindly retry an unknown write.
See the [D1 initialization record](docs/validation/d1-production-init-2026-10-10.json)
for measured costs and the limits of rejected-query metadata.

Credentials belong in secure environment settings or Cloudflare Secrets, never
in Git or chat. Existing CLOUDFLARE_API_TOKEN configuration is retained. Local
binding names appear in cloudflare/server/.dev.vars.example. Development does not
require real provider credentials while the corresponding features are disabled.
