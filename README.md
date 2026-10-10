# Norulo Server

Cloudflare Python Worker for Norulo, a project expense ledger for developers
and teams. It owns account identity, cookie/API-key authorization, shared ledgers,
projects, categories, exact money, recurring expenses, reports and conditional
AI assistance. Expenses remain separate from platform subscription payments,
and reports keep each currency separate.

This repository contains the complete imported source main history and a Norulo
rebrand. The current schema is version 12. Imported provider deployments and
validation records are historical; no remote Norulo service, database or provider
configuration has been migrated. See [migration status](docs/validation/migration-2026-10-10.md).
The user has subsequently authorized a production-only release. Current resource,
credential and feature readiness is recorded in
[production readiness](docs/validation/production-readiness-2026-10-10.md);
full application publication is pending verified new database resources and
configuration. A temporary paused norulo-server-production Worker now exists
only for secure GitHub Secret setup; it has no D1 binding or public route and
returns SERVICE_SETUP_PENDING. The earlier Worker permission rejection was
resolved after the user updated the token; D1 write permission has not been
retested.
The user has registered [Norulo's GitHub App](https://github.com/apps/norulo);
its public identity and Metadata-only permission were verified on 2026-10-10.
The current step configures the App and its Secrets without activating the
business service. A fresh token-encryption key is stored securely; the user only
needs to enter NORULO_GITHUB_CLIENT_SECRET in Cloudflare. Saved callbacks and
real login remain unverified; see the [registration checklist](docs/design/github-project-ledger/github-app-permissions.md).
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
Preview and production configs are paused, use unconfigured D1 and optional
provider placeholders and have no schedules or mail bindings. Production's public
GitHub Client ID and slug identify the verified Norulo App. Its two required
Secrets are declared by name for inheritance during the full upload; secret and
callback readiness are separate checks. The execution guard rejects
placeholders and the source service's resource IDs. Configure independent Norulo
resources and callbacks before a separately authorized release.

Credentials belong in secure environment settings or Cloudflare Secrets, never
in Git or chat. Existing CLOUDFLARE_API_TOKEN configuration is retained. Local
binding names appear in cloudflare/server/.dev.vars.example. Development does not
require real provider credentials while the corresponding features are disabled.
