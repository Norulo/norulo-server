---
name: norulo-connect
description: Connect Norulo to ChatGPT or Codex using OAuth, verify account access, and resolve missing, expired, or revoked permissions. Use for account setup, sign-in, authorization, reconnection, or authentication failures.
---

# Connect Norulo with OAuth

Start account work with connection_status. Installation and tool discovery do not prove that Norulo authorization is healthy. Never request passwords, API keys, OAuth codes, access tokens or refresh tokens in chat, source files or screenshots.

## Connect the public OAuth MCP

Use the host's Connect or Reconnect action for Norulo when authentication is required. The user signs in to Norulo and returns to the host after approving; do not require a separate connection-status website as an intermediate step. The public server uses OAuth discovery at https://mcp.norulo.com/.well-known/oauth-authorization-server and a Norulo consent page on norulo.com. Sign in, select the intended ledger and projects, choose only needed scopes, and approve. OAuth does not require copying an API key. A working browser session alone does not establish the host's MCP grant.

After the user returns, call connection_status and getLedgerMe to confirm the actual granted ledger and scopes. Confirm the actual OAuth scopes and ledger returned by getLedgerMe; installation alone does not prove authorization succeeded.

Missing scope or target access is not empty data. Ask the user to reconnect and explicitly choose the required operation/project; never silently widen the grant, change ledgers, or create another plugin. A revoked or expired grant requires the user to reconnect through the host. When a tool returns an OAuth challenge for additional permissions, let the host request explicit consent; discovering a write tool does not authorize using it. Never bypass a denied project or role by requesting broader scopes. Access tokens expire after one hour; an OAuth client can refresh them within the grant's fixed 30-day lifetime. Never retry uncertain ledger writes because a refresh or network request failed; retain the original body/idempotency key and reconcile with reads.

Users disconnect using the host's app connection controls. They can also revoke the named OAuth delegated key in https://norulo.com/api-keys to stop backend access. Legacy API-key connections remain compatible; mention that manual option only when explicitly requested or diagnosing an existing legacy setup.

## Direct OAuth MCP clients

The independently hosted public OAuth MCP endpoint is https://mcp.norulo.com/mcp. Its authorization-server discovery is https://mcp.norulo.com/.well-known/oauth-authorization-server and protected-resource metadata is https://mcp.norulo.com/.well-known/oauth-protected-resource/mcp. Use the host's supported OAuth discovery and consent flow. Do not paste tokens into local configuration.

Keep the existing plugin identity. If tools are missing after installation, a new conversation with Norulo selected may be needed. Public directory submission and approval are separate from deployment or development-plugin installation.
