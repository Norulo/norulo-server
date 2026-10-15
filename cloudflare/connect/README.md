# Norulo OAuth MCP

Production resource: `https://mcp.norulo.com/mcp`.
Issuer: `https://mcp.norulo.com`.
Authorization page: `https://norulo.com/api/connect/authorize`.

The OAuth server uses the pinned Cloudflare OAuth Provider library for DCR,
CIMD, PKCE S256, audience validation, encrypted grant props, code replay
protection, expiring access tokens, rotating refresh tokens and RFC7009 revocation.
`OAUTH_KV` is independent of the ledger's D1 database. No production D1 schema
change is needed. Backend delegated API keys expire after 30 days; OAuth grants
also have a fixed 30-day refresh lifetime. Users revoke delegated keys from
Norulo's API Keys page; backend revocation, role changes and key restrictions
remain authoritative on every ledger operation.

`norulo-web` forwards only `/api/connect/authorize` through its private
`NORULO_CONNECT_AUTH` service binding to the named `Authorization` entrypoint.
Only this entrypoint sees the host-only Norulo session. The public MCP host
cannot invoke it. Existing Norulo login verifies identity; login continuation
accepts only the exact same-origin authorization path. The OAuth consent is
bound to browser, actor and selected ledger, and explicitly selects projects,
shared access and read/write scopes. New OAuth connections do not inherit any
previous API-key connection's permissions.

The backend API key is created only after explicit user consent and stored
inside library-encrypted props. Never log tokens, cookies, authorization codes,
request bodies or raw exception messages. Redirects to upstream API URLs are
never followed. Public client names and ledger content are escaped as data.

Run `npm ci`, `npm test`, `npm run build`. Tests use an in-memory KV, mocked
Norulo backend and a Node loader stub for the Workers base class. They validate
protocol behavior but do not establish a real browser login or host consent.
Deploy with the checked-in configuration after verifying the actual Cloudflare
account, retained namespace and service bindings. Keep invocation logs disabled
and query strings redacted. Publishing a service is distinct from submitting
or publishing the plugin in the public directory.
