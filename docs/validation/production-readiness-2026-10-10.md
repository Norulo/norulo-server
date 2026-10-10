# Production readiness — 2026-10-10

The user now authorizes production publication at api.norulo.com and norulo.com,
with no preview release. Source-service Cloudflare settings may be consulted as
reference; source databases, data, unconfirmed provider credentials and old
publication permissions are not production Norulo bindings. Keep the existing
environment CLOUDFLARE_API_TOKEN and every other configured secret intact.

This document describes readiness and required configuration as of the
2026-10-10 complete Python production deployment. The new Norulo
GitHub App's public identity and minimal permissions have been verified, and the
user has now confirmed successful real GitHub sign-in. Installation, credential
refresh and the complete ledger journey remain unverified. The Web Worker has now
been published, and api.norulo.com was first attached to the temporary paused
bootstrap. The user later resumed D1 setup and full production deployment.
The independent Norulo database is initialized and verified against schema v12;
the full Python application is published and its read-only health/transport checks passed.
The earlier D1 deferral is historical and no longer blocks this authorized work.
The normal application and all 2,553 reference tests already passed local
verification; the local native acceptance record remains separate from production.

## Required platform and application configuration

| Binding or setting | Required value and purpose | Effect when missing |
| --- | --- | --- |
| Cloudflare account ID | The actual account containing the Norulo zone and new Norulo resources | Deployment cannot select the intended account reliably |
| DB | Initialized norulo-ledger-production, c41a1ab7-dffa-4c5d-a213-25f1bb6c78c5; twelve canonical migrations and schema v12 verified | Ledger/authentication routes cannot read or write their tables without the correct binding |
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
active norulo.com zone. Its exact api.norulo.com Custom Domain is now attached to
the paused Worker, allowing Cloudflare to manage the API hostname. The production
config now selects the independently created and initialized Norulo database.
Earlier on 2026-10-10, a database create request was rejected with Authentication
error and created nothing. The user subsequently updated the token permissions;
D1 creation was retried with the updated token and still returned HTTP 401,
code 10000, Authentication error. Workers write access now works, but independent
database creation was not possible in that attempt. No database was created then.
The user initially deferred D1 while proceeding with the frontend/domain stage,
then explicitly resumed database setup and full production deployment. With the
updated D1 permission, the new database was created and initialized as recorded
below. Preserve the existing token binding; the earlier pause instruction is no
longer a restriction on the authorized production release.

The user subsequently requested creation of a paused norulo-server-production
Worker so its GitHub Client Secret could be entered securely. Its initial upload
was rejected with HTTP 403, "No access to the specified resource." After the
user updated the token permissions, creation succeeded at 2026-10-10 13:05:07 UTC.
This temporary JavaScript bootstrap only returns 503 SERVICE_SETUP_PENDING with
Cache-Control: no-store; it has no database or provider access. workers_dev and
preview_urls were explicitly disabled and read back as false. At that initial
Secret-setup stage no D1 binding or route was added. The full Python ledger
application was not published at that initial stage.
At that earlier stage on 2026-10-10, twelve public configuration variables were
set, including the verified App
Client ID, slug and intended OAuth callback. One fresh NORULO_GITHUB_TOKEN_KEY Secret
was generated and uploaded securely; only its name was read back. The user then
saved NORULO_GITHUB_CLIENT_SECRET securely in the Cloudflare Dashboard. A fresh
Secret-name query confirmed both required names. The public Client ID, slug,
OAuth callback, origins and production mode also matched the intended settings;
workers_dev and preview_urls remained false. These checks establish Secret
presence and public configuration consistency, not Client Secret validity or
successful live OAuth. No secret value belongs in release evidence.

## Earlier frontend and paused API stages

- The Web Worker norulo-web was published as version
  fb3dbf7c-8530-405a-bf01-a9d208136a83, for the production host norulo.com.
- Cloudflare accepted the api.norulo.com Custom Domain on
  norulo-server-production; readback confirms enabled=true and
  previews_enabled=false. workers_dev and preview_urls remain false.
- Earlier on 2026-10-10, the bootstrap settings contained all 18 public variables
  and the two GitHub secret_text bindings. The settings PATCH used the multipart
  part named settings, with name-only inherit bindings for both Secrets;
  Cloudflare returned success and readback confirmed they were retained.
- The subsequent sender-preparation stage added
  NORULO_EMAIL_FROM=login@auth.norulo.com and a securely generated/uploaded
  NORULO_EMAIL_CODE_SECRET. The bootstrap then had 19 public variables and
  three Secrets, preserving both GitHub Secrets without reading their values.
  There was no EMAIL send binding at that stage. After the token permission
  update, the auth.norulo.com sending domain and restricted EMAIL binding were
  configured and verified. At that point it had no D1 or Durable Object binding;
  NORULO_D1_ACCESS_ENABLED and NORULO_EMAIL_AUTH_ENABLED were both 0.
- During these earlier stages, the JavaScript bootstrap had only the fixed
  503 SERVICE_SETUP_PENDING handler. No Python ledger upload, database/schema
  operation, live OAuth, provider acceptance or business activation occurred then.
- Initial requests with Python's default User-Agent returned 403. Finite requests
  using an ordinary browser User-Agent, without Authorization and with default
  TLS verification, then confirmed the homepage returns HTTP 200. Both
  api.norulo.com/health and norulo.com/api/health return the expected paused
  503 SERVICE_SETUP_PENDING with Cache-Control: no-store and no Set-Cookie.
  Six published branding assets matched their local hashes. No Cloudflare
  security setting was changed. This verifies frontend assets, the API domain
  and the Web-to-paused-API transport, not OAuth or ledger functionality.

The user deliberately postponed D1 during these earlier stages, then explicitly
resumed setup. The placeholder has now been replaced by the verified Norulo UUID.
The checked-in D1 default remains paused; explicit production activation follows
schema verification. Optional feature switches remain disabled and preview stays
undeployed. The safe local stage
record is /workspace/.norulo-environment/cloudflare-production-stage.json; it
contains public configuration, status booleans and Secret names, never values.
The subsequent local system-sender-plan.json records the sender setup. These
control-plane records do not establish actual delivery or email-login acceptance.

## D1 initialized; complete Python Worker published

The user resumed this step with an explicit requirement to minimize D1 Rows
Written. The independent norulo-ledger-production database,
c41a1ab7-dffa-4c5d-a213-25f1bb6c78c5, was created empty. Each of the twelve
unapplied canonical migration files was executed once, with its pinned Wrangler
migration-journal INSERT in the same request. No source database was accessed,
and no source data, remote test fixture or business acceptance write was inserted.

The 96 canonical statements, one journal CREATE and twelve journal INSERTs form
109 explicit initialization statements. Native metadata reports **367 rows
written for necessary initialization**. Successful API queries reported a total
of **4,097 rows read and 367 rows written**, including finite read-only checks.
These are reported successful-operation totals, not a claim of a complete bill
including rejected queries or later Worker/user traffic. DDL, indexes and
bookkeeping were not treated as free.

Two read-only checks using a 23-table compound UNION were rejected with HTTP 400,
code 7500, due to the compound-SELECT limit. No native row metrics were returned
for those checks. Verification was changed to bounded queries covering at most
five tables each; all passed and reported zero rows written. No migration was
replayed. Final schema verification matched all 77 canonical objects and
fingerprint d5f53c6229d5b5c318060c26e5e984052aa65cfcf7bc5564f9a52699ca41a77b.
app_state contains only its four empty containers; the other 22 application
tables each have zero rows. The twelve journal entries establish migration
progress; they are metadata, not product fixtures.

The safe summary is [D1 production initialization](d1-production-init-2026-10-10.json).
Detailed local evidence is /workspace/.norulo-environment/d1-production-setup.json.
The subsequent full Python Worker deployment succeeded, replacing the temporary
bootstrap. Published version: 3ad0cffc-ecc3-47a4-ab5d-a53999528b8c. Cloudflare
settings readback confirmed Python compatibility, the DB binding to the intended
Norulo UUID and the restricted EMAIL binding. All three Secrets were retained;
the 19 public variables matched production configuration except the explicit
activation overlay set NORULO_D1_ACCESS_ENABLED=1. The checked-in default remains
0. workers_dev and preview_urls remain false; email auth, recurring execution and
AI remain disabled.

Finite read-only public checks, all without Set-Cookie, confirmed:

- https://api.norulo.com/health and https://norulo.com/api/health: HTTP 200,
  with ok=true, service=norulo-server and database={type:d1, configured:true}.
- https://api.norulo.com/api/v1/me and
  https://norulo.com/api/api/v1/me: HTTP 401, UNAUTHENTICATED.
- https://norulo.com: HTTP 200.

These checks establish actual publication, DB health, Web-to-Server transport and
unauthenticated access enforcement. The checks did not perform OAuth, send mail or
make business acceptance writes. The user subsequently reported successful real
GitHub sign-in, establishing user-confirmed login acceptance. This does not prove
repository installation, credential refresh, every cookie/session behavior or the
complete ledger journey. The user's temporarily unavailable email sign-in matches
the disabled flag and pending production admission; actual mail remains untested.
The full schema was verified independently before publication.

Development, regression, browser fixtures and load tests must use local D1 or
SQLite. Remote setup is limited to necessary unapplied canonical migrations on
the intended independent database, in bounded once-only batches. Production smoke
checks use read-only endpoints/SELECTs. Record native row metrics and progress;
stop on missing metadata, unexpected results or unknown write outcomes, inspect
schema/journal read-only, and never retry blindly. Do not seed or rebuild a remote
database for testing or invent an unspecified numeric/calendar writing budget.

## System sending domain and binding ready; email login remains disabled

The user requested login@auth.norulo.com for system authentication emails.
NORULO_EMAIL_FROM is set to that address, and NORULO_EMAIL_CODE_SECRET is stored
securely. The Secret is a random string of at least 32 characters used to protect
code/challenge hashes; it is not an SMTP credential. Its value is not included in
this document or local evidence. The same gateway also uses this From address
for recurring-failure notifications; the code defines no separate Reply-To.
Server system emails do not require a receiving mailbox for this address.

Earlier on 2026-10-10, the sending-domain API returned HTTP 403. The user updated
the existing token's permissions, retaining its other permissions and binding;
the subsequent onboarding succeeded. Cloudflare now reports:

- auth.norulo.com, tag 3b648a34d60f4327b0c407c4b71b6984, enabled=true and
  preview_enabled=false. DNS/status readback is ready with errors=[]. The sending
  domain's email-content previews are disabled.
- Six newly generated DNS records are confined to the auth subdomain. All eight
  existing DNS records retained their IDs, types, names, contents, priorities,
  TTLs and proxy settings; both contact Email Routing rules are unchanged.
  Four public Cloudflare DNS-over-HTTPS queries for MX, SPF, DKIM and DMARC
  returned DNS status 0 and matched the generated records, including all three MX
  records. This verifies public DNS, not message delivery.
- The EMAIL send binding was prepared on the paused Worker, with
  allowed_sender_addresses=["login@auth.norulo.com"] and no recipient restriction.
  The settings PATCH succeeded, and readback confirmed that the 19 public
  variables and three Secrets were retained without reading Secret values.
  workers_dev and preview_urls remained false; D1 access and email auth were both
  0 during that setup. The published Python Worker retains this binding, with only
  D1 subsequently activated; email auth remains disabled.

The native Cloudflare binding needs no additional mail-provider Secret or SMTP
credential. Email Sending entitlement was also reported enabled. This establishes
domain/DNS and binding readiness only: no acceptance email was sent, and actual
delivery to user recipients, code verification and login have not been tested.
At the sender setup stage, the JavaScript bootstrap returned its fixed 503 response
without using the EMAIL binding. The database was initialized subsequently;
the complete Python application was then published. Neither stage
establishes email login.

The remaining email work does not require repeating the completed onboarding:

1. Retain the restricted EMAIL binding, disabled email-content previews and all
   three Secret bindings through explicit name-only inheritance on later uploads.
2. Implement an independent production durable IP/email admission path and its
   deployment guard/tests. Never attach production to the preview budget,
   namespace or validation journal merely to make the current adapter callable.
3. After the initialized database is bound to the complete Python application, verify
   actual delivery, code expiry/single use, resend and abuse limits, trusted
   Origin, and the browser challenge/session cookies through the Web proxy.
   Enable NORULO_EMAIL_AUTH_ENABLED only with the reviewed production path and
   these acceptance checks. Keep email auth at 0 during the core release; D1 access
   uses the separately reviewed production activation overlay.

The inherited implementation is blocked independently of sender configuration:
[WorkerEmailGateway](../../norulo_server/cloudflare_email_gateway.py) needs an
enabled flag, EMAIL binding and valid sender;
[email authentication](../../norulo_server/cloudflare_email_auth.py) additionally
requires the Secret and a callable admission adapter.
[The entry point](../../cloudflare/server/src/entry.py) currently obtains that
adapter only from VALIDATION_BUDGET, while
[the deployment guard](../../scripts/check-ledger-s01.py) permits enabled email
only under coordinated preview and rejects preview controls in active production.
These are implementation changes still to be made, not completed configuration.

## Required platform behavior for the full application

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
| NORULO_GITHUB_CLIENT_SECRET | Securely saved and its name verified without reading the value; the user subsequently confirmed successful real GitHub sign-in |
| NORULO_GITHUB_TOKEN_KEY | Exactly 32 cryptographically random bytes encoded as unpadded base64url, normally 43 characters; securely generated/uploaded for Norulo and its Secret name verified |

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
unverified at that earlier public-metadata stage. The user has now reported a
working GitHub sign-in; public metadata and health alone did not establish it.
Installation/management options and credential refresh remain unverified.

The fresh Norulo encryption key and the user's Client Secret are now stored
securely, with both Secret names confirmed. Retain the existing key;
do not regenerate it during ordinary setup or deployment. Once credentials are
stored, changing the key prevents decryption of
existing access/refresh tokens. Do not reuse an old service's database or presume
an old identity/key was authorized for Norulo. Check only presence, decoded key
length and readiness, and report booleans/errors without printing secret values.
Secrets embedded in a Worker cannot be recovered by listing their names.

At the earlier GitHub setup stage, secrets.required declared these two names.
The production config now also declares NORULO_EMAIL_CODE_SECRET, matching the
three prepared remote Secrets. Pinned Wrangler 4.136.3 generates inherit bindings
for all three during deployment, so the full Python upload retains the values
already configured on this Worker, including the email Secret while mail is disabled.
If a required binding is absent, strict inheritance rejects publication instead
of silently removing or substituting it. This declaration contains names only.
It does not use keep_vars or inherit unrelated Dashboard configuration, and it
does not establish secret validity or a successful OAuth exchange. A packaging
dry-run does not contact Cloudflare to check secret presence; verify names before
production activation.
Declare any additional provider Secrets explicitly before subsequent uploads;
the current precise inheritance covers the GitHub pair and email-code Secret.

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
App registration if automatic renewal is expected. User-authorized OAuth is
required for GitHub login; installation is additionally required for repository
associations. A successful Worker upload does not prove either flow.

## Provider secrets and feature requirements

Payments, AI and scheduled recurrence are optional for the core GitHub/free-ledger
release. Email login is also separate from that core path, but its requirements
below are mandatory for the email-login feature explicitly requested by the user.

| Feature | Secrets | Public settings/bindings | Current production behavior |
| --- | --- | --- | --- |
| Creem subscriptions | NORULO_CREEM_API_KEY and NORULO_CREEM_WEBHOOK_SECRET | NORULO_CREEM_API_BASE_URL=https://api.creem.io; NORULO_CREEM_PRODUCT_IDS_JSON maps pro/max to explicit month/year live product IDs | Core free ledger does not require payments; checkout/changes fail closed, and an unconfigured public price catalog is unavailable |
| Jev assistance | TYPESAFE_API_KEY | Both NORULO_JEV_SUGGESTIONS_ENABLED and NORULO_JEV_SUGGESTIONS_EVALUATED must be 1 after actual runtime/quality acceptance | Both flags remain 0; explicit-category manual expense entry remains available |
| Email verification | NORULO_EMAIL_CODE_SECRET, at least 32 characters; securely prepared | NORULO_EMAIL_FROM=login@auth.norulo.com, authenticated auth.norulo.com and restricted EMAIL send binding are configured; independent durable IP/email admission and acceptance must precede NORULO_EMAIL_AUTH_ENABLED=1 | Domain and binding ready; production admission and actual delivery/code/session acceptance remain pending; flag stays 0 |
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
admission implementation and tests are required before enabling it; never bind production
to the preview validation journal merely to satisfy this dependency.
The gateway's email-auth flag also gates recurring-failure emails. The notification
path falls back to the application inbox and does not retry an unknown delivery;
do not interpret sender preparation as acceptance of those notifications.

The recurring scheduler's _recurring_enabled guard requires preview mode and the
preview product coordinator. Adding production cron/flags alone does not execute
future occurrences. Creating a rule can record its historical start expense, but
future background posting is unavailable in production until a distinct reviewed
production scheduler/coordinator is implemented. Keep the flag disabled and no
production triggers; communicate this release limit without claiming full
background recurrence acceptance.

## Remaining release checklist

Database initialization and complete Python publication are complete. The following
distinguishes remaining real-user acceptance from feature-specific work; none requires remote
synthetic business writes.

| Scope | Remaining work besides D1 | Acceptance required |
| --- | --- | --- |
| Core GitHub/free ledger — remaining acceptance | GitHub sign-in is user-confirmed; preserve the deployment/DB/Secrets and verify remaining App/session behaviors | Repository installation, credential refresh, sign-out/session details and the complete ledger journey remain unverified; business regression/isolation tests stay local |
| Requested email login — required for that feature | Retain the authenticated domain, restricted EMAIL binding and prepared Secret; implement independent production admission and guard/tests; keep flag 0 until ready | Actual mail delivery and six-digit code verification, expiry/single use, bounded resend/abuse handling and browser session through the Web proxy |
| GitHub repository associations — optional | A user's App installation and chosen repository grants; no numeric App ID/private key required | Actual installation Setup callback with server-issued state and authorized repository discovery/synchronization; standalone projects do not need installation |
| Paid plans — optional | Independent live Creem products for the available plan/cadence pairs, API/webhook Secrets and explicit inheritance, signed webhook registration | Accurate public prices and idempotent entitlement changes from verified webhooks; no charge or subscription mutation is part of core acceptance |
| Jev AI assistance — optional | TYPESAFE_API_KEY, reviewed model transport/quality and both feature gates | Owner's paid entitlement/monthly allowance, actual bounded suggestions and safe manual fallback |
| Future recurring posting — optional | Distinct production scheduler/coordinator implementation and tests; then reviewed triggers/flag | Finite scheduled execution with idempotency, permissions/quota fences, failures/inbox behavior and truthful delivery reporting |

Production domains, frontend assets, the published API/Web transport, system sending
domain/binding and the three prepared Secret names are already recorded above.
They do not need new secret
values from the user and do not establish live application behavior. No additional
receiving mailbox is required by the Server for its system sender.

## Publication sequence and validation

Frontend/domain, sending-domain/binding and D1 initialization are complete at the
control plane. Full Python publication and finite read-only health/transport
checks are also complete. The user resumed the full application sequence;
do not repeat completed migrations or redeploy merely to repeat acceptance.

1. Verify the account and Norulo zone, select independent resources and record
   database/account IDs without modifying or querying source-service databases.
2. For a genuinely new database only, apply necessary unapplied canonical migrations
   once and verify schema/objects. This production database is already initialized;
   preserve its journal and measured costs. Preserve dependency and TLS verification.
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

At the earlier GitHub setup stage on 2026-10-10, after adding the exact two GitHub
names to secrets.required, the pinned Wrangler
schema accepted the production config and the frozen Python packaging dry-run
passed again without contacting Cloudflare. The 36 existing deployment/config/
production-runtime tests and 18 subtests, and both paused/activation-overlay S01
checks, passed. An independent offline check exercised the actual pinned
inheritance helper and reviewed strict missing-binding error handling. These
Those earlier checks preserved the D1 placeholder and disabled optional features; they did not
verify Client Secret validity or D1 access. The subsequent name-only query
confirmed both required Secrets are present; the fresh D1 create attempt still
failed with Authentication error.

At the subsequent sender-preparation stage, S01 static production configuration
validation passed with the sender, three required Secret names and disabled
features. The existing email-auth/deployment-contract tests passed: 39 tests and
18 subtests. This is offline configuration/regression evidence, not authenticated
sending-domain setup, remote Secret-value validation, delivery or live email login.

After the sending-domain onboarding and EMAIL binding setup, S01 static
production validation and the 39 email-auth/deployment-contract tests plus 18
subtests passed again. Cloudflare readback established the domain,
DNS and binding state described above; no email was sent for acceptance and no
delivery, code or session success is claimed.
