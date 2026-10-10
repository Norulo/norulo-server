# Norulo Python Worker

The source main branch has been imported and rebranded. The existing
wrangler.jsonc is explicitly local: no routes, remote=false, NORULO_MODE=local.
wrangler.preview.jsonc and wrangler.production.jsonc are unconfigured deployment
proposals. Both keep D1 access, schema upgrades, mail, scheduled recurrence and
AI provider dispatch disabled. Their database UUIDs and GitHub/provider settings
must be configured for independent Norulo resources before remote execution.
The imported source's remote databases, providers, domain registrations and
historic publication approval have not been transferred.

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
base64url; an existing data migration must preserve its encryption key. Do not
paste credentials into chat or saved instructions. Keep the existing environment
CLOUDFLARE_API_TOKEN binding intact.

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
