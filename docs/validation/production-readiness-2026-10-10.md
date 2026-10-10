# Production readiness — 2026-10-10

The user now authorizes production publication at api.norulo.com and norulo.com,
with no preview release. Source-service Cloudflare settings may be consulted as
reference; source databases, data, unconfirmed provider credentials and old
publication permissions are not production Norulo bindings. Keep the existing
environment CLOUDFLARE_API_TOKEN and every other configured secret intact.

This document describes readiness and required configuration. The new Norulo
GitHub App's public identity and minimal permissions have now been verified;
this does not establish saved callbacks, secrets, real OAuth or a deployed Worker,
database or domain. The current step is GitHub App configuration only, with no
publication, database changes or application-secret operations.
The normal application and all 2,553 reference tests already passed local
verification; the local native acceptance record remains separate from production.

## Required platform and application configuration

| Binding or setting | Required value and purpose | Effect when missing |
| --- | --- | --- |
| Cloudflare account ID | The actual account containing the Norulo zone and new Norulo resources | Deployment cannot select the intended account reliably |
| DB | Independent norulo-ledger-production D1 database with the twelve canonical migrations, schema version 12 | Ledger/authentication routes cannot read or write their tables |
| NORULO_MODE | production | Invalid modes fail closed |
| NORULO_D1_ACCESS_ENABLED | 1 only after schema/resource validation; absent/0 remains paused | Every application request receives D1_ACCESS_PAUSED |
| NORULO_APP_URL | https://norulo.com | Trusted return destinations and app links are unavailable or invalid |
| NORULO_ALLOWED_ORIGINS | https://norulo.com | Browser writes fail trusted-Origin validation |
| NORULO_COOKIE_SAME_SITE | None with Secure/HttpOnly cookies | Must remain consistent with the reviewed browser/API transport |
| NORULO_GITHUB_CALLBACK_URL | https://norulo.com/api/auth/github/callback | OAuth exchanges/callback registration do not match |
| NORULO_GITHUB_CLIENT_ID | Iv23li78ZPeUgSxJkLUj, verified against the new Norulo GitHub App; not its numeric App ID | Empty yields GITHUB_NOT_CONFIGURED; a placeholder can redirect to an invalid OAuth client |
| NORULO_GITHUB_APP_SLUG | norulo, verified with the same App's Client ID | Installation flow yields GITHUB_APP_NOT_CONFIGURED or targets the wrong registration |
| NORULO_PLAN_LIMITS_JSON | Current checked-in canonical per-plan JSON policy | Invalid policy yields PLAN_POLICY_INVALID |
| Web NORULO_SERVER binding | norulo-server-production HTTP service binding | Web API transport cannot reach the intended Server |

The current proposal selects the independently verified Cloudflare account and
active norulo.com zone. Because there is no API DNS record, its exact
api.norulo.com custom-domain route lets Cloudflare manage the API hostname instead
of depending on an unconfigured zone-route origin. The D1 UUID remains a
placeholder: the current token can list databases, but its create request was
rejected with Authentication error. Publication needs an authorized new database
and effective D1 write permission; nothing was created by that failed request.

The Server production hostname is api.norulo.com; the Web host removes the first
/api path prefix before forwarding. The Server receives /api/v1/* for browser
requests to /api/api/v1/*. OAuth callbacks run through the same Web proxy.
An exact zone route requires an existing correctly proxied API DNS record; an
exact custom domain is another supported route shape. Verify zone/account
ownership and selected DNS behavior before publication.

The checked-in deploy script's explicit --activate-production option overlays
NORULO_D1_ACCESS_ENABLED=1 while leaving the source default paused. It never runs
migrations. The guard requires a real database UUID, independent environment
resources, expected production hosts/callback/live Creem origin, and no preview
coordinator. It rejects source-service database IDs and placeholders on execution.
Its static checks do not prove provider secrets, registered callbacks or actual
OAuth success; the operator must verify those separately.

## Required secrets for GitHub sign-in

| Secret name | Requirement |
| --- | --- |
| NORULO_GITHUB_CLIENT_SECRET | Secret belonging to the same intended GitHub App as Client ID and slug |
| NORULO_GITHUB_TOKEN_KEY | Exactly 32 cryptographically random bytes encoded as unpadded base64url, normally 43 characters; imported into WebCrypto AES-GCM |

These are the minimum application secrets for a working GitHub login on a fresh
production ledger. The platform CLOUDFLARE_API_TOKEN authorizes setup/deployment;
it is not an application Secret and should not be copied into the Worker.
The user has registered [Norulo](https://github.com/apps/norulo). On 2026-10-10,
GitHub GET /apps/norulo confirmed owner Norulo, name Norulo, slug norulo, Client ID
Iv23li78ZPeUgSxJkLUj, only metadata read permission and no events. These public
values replace the earlier blank App configuration. A prior local check proved
that a blank Client ID fails closed with GITHUB_NOT_CONFIGURED; that check did
not validate this App. Its saved callbacks, options and Client Secret cannot be
verified from the public App response, and real login/installation remains
unverified. Health and unauthenticated session acceptance do not establish a
working login.

Generate a new encryption key securely for the new empty Norulo database. Once
credentials are stored, retain that same key: changing it prevents decryption of
existing access/refresh tokens. Do not reuse an old service's database or presume
an old identity/key was authorized for Norulo. Check only presence, decoded key
length and readiness, and report booleans/errors without printing secret values.
Secrets embedded in a Worker cannot be recovered by listing their names.

The App management page must be checked for:

- Homepage: https://norulo.com.
- OAuth callback: https://norulo.com/api/auth/github/callback.
- Installation Setup URL: https://norulo.com/api/integrations/github/callback.
- Repository Metadata read permission; installation/repository grants belong to
  each actual user. No organization/account permission or private key is required
  by this user-token gateway.
- Expire user authorization tokens enabled; Request user authorization during
  installation, Redirect on update, Device Flow and Webhook Active disabled.
- Any account installation scope for users outside the registration account.

The complete registration checklist and the distinction between verified public
metadata and unverified management settings are recorded in
[GitHub App permissions](../design/github-project-ledger/github-app-permissions.md).
The current implementation does not need a numeric App ID or App private key.

The Client ID/Secret/slug must identify a GitHub App because repository discovery
uses /user/installations and App user access tokens. An ordinary OAuth App or a
numeric App ID is insufficient. Current code persists provider access/refresh
credentials and their lifetimes; provider refresh must be enabled by the intended
App registration if automatic renewal is expected. User-authorized OAuth and
installation are prerequisites; a successful Worker upload does not prove them.

## Optional provider secrets and feature requirements

| Feature | Secrets | Public settings/bindings | Current production behavior |
| --- | --- | --- | --- |
| Creem subscriptions | NORULO_CREEM_API_KEY and NORULO_CREEM_WEBHOOK_SECRET | NORULO_CREEM_API_BASE_URL=https://api.creem.io; NORULO_CREEM_PRODUCT_IDS_JSON maps pro/max to explicit month/year live product IDs | Core ledger works without payment configuration; checkout/changes fail closed with BILLING_NOT_CONFIGURED or BILLING_UNAVAILABLE |
| Jev assistance | TYPESAFE_API_KEY | Both NORULO_JEV_SUGGESTIONS_ENABLED and NORULO_JEV_SUGGESTIONS_EVALUATED must be 1 after actual runtime/quality acceptance | Both flags remain 0; explicit-category manual expense entry remains available |
| Email verification | NORULO_EMAIL_CODE_SECRET, at least 32 characters | NORULO_EMAIL_AUTH_ENABLED=1; EMAIL send binding; verified NORULO_EMAIL_FROM such as login@auth.norulo.com; durable IP/email admission | Not production-ready in the inherited implementation; remains disabled |
| Scheduled recurring execution | No extra provider secret | Scheduler plus coordinated durable accounting | Not production-ready in the inherited implementation; no production cron |

Creem IDs are public configuration, not prices or secrets. The JSON must be a
plain-text JSON string, for example
{"pro":{"month":"prod_pro_month","year":"prod_pro_year"},"max":{"month":"prod_max_month","year":"prod_max_year"}}.
Use actual distinct production IDs; omit unavailable cadences rather than
inventing products or promoting test IDs. The webhook destination is
https://api.norulo.com/webhooks/creem. Signed webhooks, not checkout responses,
control entitlements. No real charge or subscription modification is part of
basic deployment acceptance.

Email verification currently requires a callable durable admission adapter. The
normal production config has no VALIDATION_BUDGET binding, the static guard only
permits enabled mail under coordinated preview, and the runtime's current
admission class belongs to that preview coordinator. Setting a sender, Secret and
flag alone does not make production email login work. A separate production
admission design and tests are required before enabling it; never bind production
to the preview validation journal merely to satisfy this dependency.

The recurring scheduler's _recurring_enabled guard requires preview mode and the
preview product coordinator. Adding production cron/flags alone does not execute
future occurrences. Creating a rule can record its historical start expense, but
future background posting is unavailable in production until a distinct reviewed
production scheduler/coordinator is implemented. Keep the flag disabled and no
production triggers; communicate this release limit without claiming full
background recurrence acceptance.

## Publication sequence and validation

1. Verify the account and Norulo zone, select independent resources and record
   database/account IDs without modifying or querying source-service databases.
2. Apply the twelve canonical migrations to the new Norulo production database
   only; verify schema version/objects. Preserve dependency and TLS verification.
3. Configure the actual Norulo public App settings and required secrets securely,
   or explicitly report that real GitHub sign-in remains blocked.
4. Run static production checks and the pinned packaging dry-run. Publish the
   reviewed production Worker, then Web with its matching service binding.
5. Use finite ordinary health/unauthenticated session and Web-to-Server transport
   checks. Real user OAuth, provider emails/models and payment flows are separate
   from these checks and must be reported accurately.

Do not deploy preview, copy source sessions/payment facts, send synthetic remote
users, reset validation journals, poll D1, or retry an unknown migration/payment/
provider outcome. Keep release evidence distinct from imported historical records.

## Checks completed for this proposal

The production deployment/configuration/runtime tests passed: 36 tests and 18
subtests. S01 production validation with --allow-placeholders, including the
--activate-production overlay, and shell syntax checks passed. Frozen Python
3.14.2 pywrangler deploy --dry-run with the production config completed and
produced a package without remote publication. Those checks preserved the database
placeholder, the then-blank GitHub identity, unconfigured optional providers and
disabled optional features. The subsequent App public metadata verification does
not establish Cloudflare write permissions, saved callbacks, secret readiness or
live login acceptance.
