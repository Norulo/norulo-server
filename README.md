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
The complete Python Worker is now published as version
3ad0cffc-ecc3-47a4-ab5d-a53999528b8c, with the initialized DB bound and runtime
NORULO_D1_ACCESS_ENABLED=1. The earlier bootstrap and D1 deferral are historical.
Finite read-only checks confirmed homepage HTTP 200, both API/Web proxy health
endpoints HTTP 200 and unauthenticated profile endpoints HTTP 401, with no
Set-Cookie. These checks verify publication and authenticated access enforcement;
the user subsequently confirmed successful real GitHub sign-in. Repository
installation, credential refresh and the complete ledger journey remain unverified.
The user has registered [Norulo's GitHub App](https://github.com/apps/norulo);
its public identity and Metadata-only permission were verified on 2026-10-10.
The user has securely saved NORULO_GITHUB_CLIENT_SECRET, and
the fresh token-encryption key is also present. The subsequent sender-preparation
stage added NORULO_EMAIL_FROM=login@auth.norulo.com and securely generated/uploaded
NORULO_EMAIL_CODE_SECRET. The published Python Worker retains 19 public variables and three
Secrets, with both GitHub Secrets retained. These checks establish presence and
settings consistency, not credential validity or email delivery.
The earlier sending-domain API 403 was resolved after the token permission update.
auth.norulo.com is now enabled with DNS status ready and sending previews disabled.
The Worker has an EMAIL send binding restricted to login@auth.norulo.com, with no
recipient restriction. Existing contact Email Routing DNS/rules were preserved.
No email has been sent for acceptance. NORULO_D1_ACCESS_ENABLED and
NORULO_EMAIL_AUTH_ENABLED remain 0 in the checked-in configuration; production D1
activation is a separate explicit deployment overlay. Production email login still needs an independent
durable admission implementation and actual delivery/code/session acceptance;
the prepared domain and binding do not enable it by themselves. No additional
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
Optional provider features remain disabled. Production has the prepared EMAIL
send binding while email authentication stays disabled. Production's public
GitHub Client ID and slug identify the verified Norulo App. The two GitHub Secrets
and the prepared email-code Secret are declared by name for inheritance during
the full upload; secret, callback and email readiness are separate checks.
The execution guard rejects
placeholders and the source service's resource IDs. Configure independent Norulo
resources and callbacks before production activation.

With D1 and the complete Python Worker published, the core release still needs
verification of the remaining App options, session/sign-out/refresh behavior
and actual user ledger acceptance. Real GitHub sign-in is user-confirmed.
Development business-write regression
tests continue to use local D1 or SQLite.
The requested email-login feature still needs independent production admission
and actual delivery/code/session acceptance. Its sending domain and restricted
EMAIL binding are prepared. Creem
payments, Jev AI assistance and scheduled recurring execution are optional;
production background recurrence requires implementation work before activation.
See the [remaining release checklist](docs/validation/production-readiness-2026-10-10.md#remaining-release-checklist).

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
