# GitHub access from delegated clients

Repository lists accept up to 100 items per page. The binding lookup splits
repository and project IDs into scalar SELECTs within one database batch, so
a full page with a restricted key does not exceed D1's 100 bound parameters
per statement. At most six SELECTs share the authorization snapshot. The cursor, actor's
GitHub visibility, selected ledger and binding visibility rules are unchanged.
Listing repositories and projects remains read-only.

When a repository or linked-project read returns `githubRefreshRequired: true`,
an API-key client may explicitly call:

```http
POST /api/v1/integrations/github/refresh
Authorization: Bearer <Norulo API key>
Content-Type: application/json

{}
```

This maintenance operation requires the key's existing `projects:read` scope,
its bound ledger and current membership. It only renews the actual actor's
existing GitHub grant; it cannot grant new permissions, refresh the ledger
owner's credentials on behalf of a member or return token material.

The MCP tool is `refreshLedgerGitHubAccess`. It advertises a write side effect
and is not automatically called by repository/project read tools. Hosts are
instructed to call it once when the read requests refresh and repeat that read
once after a successful renewal. The empty body accepts no actor, workspace,
provider credential or repository selectors. The ledger continues to come from
the authenticated key, subject to the existing workspace-header checks.

The browser keeps using its existing trusted-Origin, cookie-authenticated
`POST /integrations/github/refresh`. Both routes share one durable rotation
claim and one credential-generation check. Delegated writes recheck key hash,
actor, current scopes, restrictions, expiration/revocation and shared-ledger
membership before the provider exchange and before publishing new credentials.
They preserve business records, sessions, key permissions and account identity.

After `GITHUB_REFRESH_PENDING`, return the pending result without issuing a new
exchange. After an uncertain transport/provider/storage outcome, do not retry
the refresh token. Missing, revoked, expired or uncertain refresh credentials
require explicit GitHub reconnection through Norulo Web. Never replay a business
write automatically after renewal or reconnection.

Unexpected identity failures return an opaque `error.requestId`. Server logs
record `NORULO_IDENTITY_FAILURE` with the same ID, safe error code/type,
function/line and optional numeric provider status. Production responses omit
internal locations. Logs never stringify exceptions, provider bodies, request
headers, user records or credentials. This replaces the previous production
behavior that discarded unknown identity diagnostics. A request ID is diagnostic
correlation, not an authorization credential or evidence that a write succeeded.

No schema migration, GitHub App registration or new secret is required.
