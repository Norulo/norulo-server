# Norulo Python Worker

The source main branch has been imported and rebranded. The existing
wrangler.jsonc is explicitly local: no routes, remote=false, NORULO_MODE=local.
wrangler.preview.jsonc remains an undeployed offline reference.
wrangler.production.jsonc selects the initialized independent D1 database, with
its default access switch paused and account, domain, GitHub App and email settings described
below. Both keep schema upgrades, email authentication, scheduled recurrence and
AI provider dispatch disabled. Production D1 activation uses the explicit deploy
overlay after schema verification; preview stays undeployed.
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
retained. No actual email delivery was tested; email authentication remains
disabled. D1 was paused during that sender setup stage.
The Web Worker has been published. The earlier user request to defer D1 was
superseded by explicit authorization to resume setup and full production deployment.
All twelve canonical migrations were applied once to the new empty Norulo
database, reporting 367 native rows written for initialization. Schema v12 and its
77 canonical objects were verified; at initialization app_state held only four
empty containers and the other 22 application tables were empty.
The complete Python Worker is now published as version
3ad0cffc-ecc3-47a4-ab5d-a53999528b8c. Readback confirms Python compatibility,
the intended DB and restricted EMAIL bindings, all three Secrets, and all 19
public variables with only the D1 flag activated to 1. The source default stays 0;
email auth, recurring execution and AI remain disabled, as do public preview URLs.
Finite read-only checks confirmed homepage HTTP 200, API and Web proxy health
HTTP 200, and their unauthenticated profile endpoints HTTP 401. No public check
set a cookie. This proves publication/transport and access enforcement. The user
subsequently reported successful real GitHub sign-in; installation, refresh and
the complete ledger journey remain unverified. Email sign-in is temporarily
unavailable while its flag remains 0 and production admission is pending; no
actual email delivery was tested. See
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
recurring-failure notifications. Its auth.norulo.com sending domain is authenticated
and the send_email binding named EMAIL permits only this sender, without recipient
restrictions. No additional mail-provider Secret or SMTP credential is needed
for the native binding. Email Sending entitlement and domain status are enabled;
actual delivery to user recipients has not been tested. These settings do not
enable production email login:
the current admission adapter depends on the preview-only VALIDATION_BUDGET
coordinator, which production must never reuse. Implement and test an independent
production admission path, then complete real delivery, code verification and
session acceptance before setting NORULO_EMAIL_AUTH_ENABLED=1. Keep email auth
disabled during the authorized core production release; database initialization
does not remove the separate production admission dependency.

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
