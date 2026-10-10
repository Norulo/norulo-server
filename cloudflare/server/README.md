# Norulo Python Worker

The source main branch has been imported and rebranded. The existing
wrangler.jsonc is explicitly local: no routes, remote=false, NORULO_MODE=local.
wrangler.preview.jsonc and wrangler.production.jsonc are unconfigured deployment
proposals. Both keep D1 access, schema upgrades, mail, scheduled recurrence and
AI provider dispatch disabled. Their database UUIDs and GitHub/provider settings
must be configured for independent Norulo resources before remote execution.
The imported source's remote databases, providers, domain registrations and
historic publication approval have not been transferred. The user now authorizes
production-only publication with new Norulo resources. The production proposal
selects the verified account/zone and the exact api.norulo.com custom domain;
its DB remains a placeholder until a new database is available. The user has now
registered the real Norulo GitHub App: its public Client ID
Iv23li78ZPeUgSxJkLUj and slug norulo were verified with GitHub on 2026-10-10, with
only Metadata read permission and no events. Saved callbacks, management options,
Client Secret validity and real login remain unverified. A temporary paused
norulo-server-production Worker was created after the user updated the token
permissions. Its handler returns 503 SERVICE_SETUP_PENDING; workers.dev and
preview URLs remain disabled. The api.norulo.com Custom Domain is now bound,
enabled with previews disabled, while no D1 or Durable Object binding exists.
A fresh token-encryption key was
securely uploaded, and the user has now saved NORULO_GITHUB_CLIENT_SECRET in the
Cloudflare Dashboard. Both Secret names were read back without inspecting values.
Earlier on 2026-10-10, all 18 public production variables were applied, preserving
both GitHub Secrets through inherit bindings without reading their values.
The subsequent sender-preparation stage set NORULO_EMAIL_FROM=login@auth.norulo.com
and securely generated/uploaded NORULO_EMAIL_CODE_SECRET. The bootstrap now has
19 public variables and three Secrets, with the GitHub pair preserved.
Sending-domain authentication is pending: the domain API returned 403, and the
user was asked to add Account → Email Sending → Edit to the existing token.
No EMAIL send binding exists; D1 access and email authentication remain disabled.
The Web Worker has been published, but the full Python application and business
service remain inactive. The user explicitly deferred D1 setup; do not request
immediate permission changes or retry database creation during this stage.
Finite ordinary browser User-Agent checks confirmed homepage HTTP 200 and both
api.norulo.com/health and the Web /api/health proxy returning the expected paused
503 response with no-store and no Set-Cookie. This verifies the current frontend
and paused transport, not login or ledger functions. See
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
Production secrets.required lists the two GitHub Secret names and
NORULO_EMAIL_CODE_SECRET, causing pinned Wrangler to inherit all three existing
bindings and reject a missing required Secret during real publication. The email
Secret is prepared while its feature remains disabled; keep it through later
uploads. A dry-run does not verify remote presence. Do not
paste credentials into chat or saved instructions. Keep the existing environment
CLOUDFLARE_API_TOKEN binding intact.

NORULO_EMAIL_CODE_SECRET must be a securely generated string of at least 32
characters. It protects code/challenge hashes; it is not an SMTP password.
The prepared sender login@auth.norulo.com sends system verification codes and
recurring-failure notifications. Before configuring the future send_email
binding named EMAIL, authenticate its sending domain and verify sending eligibility;
restrict allowed_sender_addresses to that one sender. Email Sending entitlement
is reported enabled; the actual onboarding response and delivery acceptance will
verify recipient eligibility. The current domain API permission error is the
confirmed infrastructure blocker. These steps do not enable production email login:
the current admission adapter depends on the preview-only VALIDATION_BUDGET
coordinator, which production must never reuse. Implement and test an independent
production admission path, then complete real delivery, code verification and
session acceptance before setting NORULO_EMAIL_AUTH_ENABLED=1. Keep the current
full-server bootstrap paused and do not deploy a placeholder DB binding.

The [remaining release checklist](../../docs/validation/production-readiness-2026-10-10.md#remaining-release-checklist)
separates the core GitHub/ledger release, the requested email-login feature and
optional payment, AI and background recurrence work.

The deployment checker validates explicit pause switches, host/origin isolation,
separate database identities, no source-service databases, provider separation,
and coordinated preview email/scheduling. The shell release command never
executes migrations. Dry-run allows placeholders for review; --execute rejects
them. A future remote release needs current user scope and verified configuration,
schema/accounting, callback, provider and end-to-end gates. Source historical
acceptance records do not satisfy Norulo gates.

The inherited preview singleton architecture retains bounded SQL/input/native
accounting, durable unknown-outcome stops and append-only journals. Do not reset
a journal, replay uncertain migrations, or enable recurring remote jobs as part
of ordinary environment startup.
