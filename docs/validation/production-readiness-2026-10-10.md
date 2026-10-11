# Production readiness — 2026-10-10, updated 2026-10-11 (Asia/Shanghai)

The user now authorizes production publication at api.norulo.com and norulo.com,
with no preview release. Source-service Cloudflare settings may be consulted as
reference; source databases, data, unconfirmed provider credentials and old
publication permissions are not production Norulo bindings. Keep the existing
environment CLOUDFLARE_API_TOKEN and every other configured secret intact.

This document records the 2026-10-10 complete Python production deployment and
the subsequent AI quality stage recorded on 2026-10-11 in Asia/Shanghai. The new Norulo
GitHub App's public identity and minimal permissions have been verified, and the
user has now confirmed successful real GitHub sign-in. Installation, credential
refresh and the complete ledger journey remain unverified. The Web Worker has now
been published, and api.norulo.com was first attached to the temporary paused
bootstrap. The user later resumed D1 setup and full production deployment.
The independent Norulo database is initialized and verified against schema v12;
the full Python application is published and its read-only health/transport checks passed.
The email-enabled feature version was 815a1216-4468-4591-be58-e339d4d2c154, built
from main commit 96d6bee. The Secret-update revision
ec33db03-2fd4-49a4-8430-9e1cb13fc340 is an earlier checkpoint. Verified release A
on 2026-10-11 at 05:38:43 UTC is Server b5642a63-1643-418a-b494-bb7bcf427050
from main ebd11baf and Web 26697b80-76dc-405b-a0c0-c2ea7c0735f7 from main 3531f8a.
All five runtime D1/email/AI/recurrence flags are 1 through explicit overlays,
with one hourly UTC cron (0 * * * *) at that release A checkpoint.
Verified daily release B at 2026-10-11 06:38:08 UTC is Server
e2e4e02d-ac9a-4c20-852f-f6cbfe5b5ae4 from main ded49a46 and Web
0c63c81e-1f91-4b72-bf3b-f949b7840ad8 from main bef23ee7. It has exactly one
daily cron 10 16 * * * UTC (Beijing 00:10), strict cpu_ms=300000/subrequests=9000
and all five flags 1, with original resources and four Secret names retained.
See the [dated daily release record](production-daily-release-2026-10-11.json);
neither checkpoint guarantees future latest versions. Checked-in defaults remain
0/no cron. The user subsequently confirmed
receipt of the verification code and successful email login. Account linking,
sign-out and session refresh remain separately unverified. AI and recurrence
are enabled in this dated release; native real-provider HTTPS and live scheduled
financial execution remain untested. TYPESAFE_API_KEY is the fourth Worker
Secret, and runtime specification 11 confirms both network Secret bindings present
with the Cloudflare token retained. Fresh Norulo quality evidence completed 36
real CPython HTTPS calls once, with both review gates passing and no retry or D1/
application requests. Native Worker real-provider HTTPS remains untested. The earlier D1 deferral is historical and no longer blocks this
work. Initial migration checks passed 2,553 tests; the later email release gates
and native acceptance are recorded separately below.

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
active norulo.com zone. Its exact api.norulo.com Custom Domain was first attached
to the paused bootstrap and now serves the published Python Worker, allowing
Cloudflare to manage the API hostname. The production
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
schema verification. AI and scheduled recurrence were still disabled at this
earlier stage; release A below supersedes it. Payments remain unconfigured and
preview stays undeployed. The safe local stage
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
At initialization, app_state contained only its four empty containers; the other
22 application tables each had zero rows. The twelve journal entries establish migration
progress; they are metadata, not product fixtures.

The safe summary is [D1 production initialization](d1-production-init-2026-10-10.json).
Detailed local evidence is /workspace/.norulo-environment/d1-production-setup.json.
The first full Python Worker deployment succeeded, replacing the temporary
bootstrap, as version 3ad0cffc-ecc3-47a4-ab5d-a53999528b8c. At that stage, Cloudflare
settings readback confirmed Python compatibility, the intended DB and restricted
EMAIL binding, all three Secrets and 19 public variables. The activation overlay
set NORULO_D1_ACCESS_ENABLED=1; email auth was still 0. Its initialization JSON is a
historical snapshot, not the later email release state. The subsequent
email-enabled version 815a1216-4468-4591-be58-e339d4d2c154 retained those resources
and set both runtime activation flags to 1 as recorded below; AI/recurrence were
still disabled then. All source defaults remain 0 and Workers.dev/previews stay
disabled; release A later enabled runtime AI/recurrence with the hourly cron.

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
complete ledger journey. The user's earlier unavailable email sign-in matched the
then-disabled flag and pending production admission. The later enabled release
and user-confirmed email login are recorded below. The full schema was verified
independently before publication.

Development, regression, browser fixtures and load tests must use local D1 or
SQLite. Remote setup is limited to necessary unapplied canonical migrations on
the intended independent database, in bounded once-only batches. Production smoke
checks use read-only endpoints/SELECTs. Record native row metrics and progress;
stop on missing metadata, unexpected results or unknown write outcomes, inspect
schema/journal read-only, and never retry blindly. Do not seed or rebuild a remote
database for testing or invent an unspecified numeric/calendar writing budget.

## System sending domain and binding ready

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
  0 during that setup. The first Python release activated only D1; the current
  email-enabled release retains the binding and activates both D1 and email auth.

The native Cloudflare binding needs no additional mail-provider Secret or SMTP
credential. Email Sending entitlement was also reported enabled. This establishes
domain/DNS and binding readiness only: no acceptance email was sent during
sender setup. The JavaScript bootstrap then returned its fixed 503 response
without using EMAIL. The database and full Python application followed, and
email auth was activated in the later release below. The user subsequently
confirmed actual code delivery and successful email login; sender setup alone
did not establish that acceptance.

## Production email admission

The earlier production blocker was the inherited preview-only admission adapter.
An independent production implementation is now present in
[EmailAdmission](../../norulo_server/cloudflare_email_admission.py) and
[the entry point](../../cloudflare/server/src/entry.py), with guard/contract coverage.
Local reference/native gates and publication passed. The earlier email-enabled
feature release was version 815a1216-4468-4591-be58-e339d4d2c154, built from main
commit 96d6bee. The earlier core version 3ad0cffc-ecc3-47a4-ab5d-a53999528b8c had
email auth disabled. The user has now confirmed receipt of the verification code
and successful email login, establishing actual delivery/code/browser-login
acceptance. Account linking, sign-out, refresh and production abuse/security
scenarios have not been separately accepted by that report.

The published EMAIL_ADMISSION binding points only to the EmailAdmission class,
with namespace 6588312f00f74840a37463e72a2d75eb, SQLite class migration tag
norulo-email-admission-v1 and fixed scope
norulo-production-email-admission-v1. It never reuses ValidationBudget, a preview
journal or the production D1 database for limiter storage. The limiter stores
64-hex hashed subjects, counters and timing metadata, not email addresses, raw
IPs or codes. Bucket admission is transactional; malformed calls, missing
bindings and uncertain storage/RPC outcomes fail closed. An accepted reservation
is not refunded or automatically retried after a delivery/checking failure or
unknown outcome. Known SQLite transaction failures roll back. There is no public
reset, refund or diagnostic endpoint.

The existing OTP security remains unchanged: six-digit codes expire after 600
seconds, valid-browser wrong-code attempts are capped at five, resend has a
60-second cooldown, challenge cookies bind the request to the browser, and
successful verification consumes the challenge once with identity/session writes
in the same D1 batch. Linking also checks the original user/session. Only the
limiter is independent of D1: ordinary real-user challenges, identities and
sessions still perform necessary D1 authentication writes. This feature adds no
D1 schema migration or remote synthetic fixtures.

The release helper now has an explicit --activate-email-auth option, requiring
production plus --activate-production. It overlays runtime D1/email flags to 1
without changing either checked-in default of 0. With the local gates completed,
the reviewed production release command is:

```bash
./scripts/deploy-cloudflare.sh --environment production \
  --activate-production --activate-email-auth --execute --local-checks-passed
```

This command was used for the verified email-enabled release. Subsequent
releases must retain both overlays; otherwise the checked-in 0 defaults pause the
corresponding routes. It does not execute D1 migrations. Readback confirmed all
19 public variables and three Secrets preserved, the unchanged intended DB, the
EMAIL sender restricted to login@auth.norulo.com without recipient limits, and
the independent EMAIL_ADMISSION namespace. Runtime D1/email flags are 1/1;
workers_dev and preview_urls remain false. API/Web health returned 200 and
unauthenticated profile endpoints 401, with no Set-Cookie. The release performed
no D1 migration, remote fixture write or actual send. Sending-domain/account
resources were unchanged. Local safe evidence is
/workspace/.norulo-environment/email-production-activation-checks.json.

The subsequent user report confirmed receiving the code and successfully logging
in. Do not generalize that report to account linking, refresh or every email
security case. Preserve the DB and all four now-configured Secrets through
name-only inheritance, the restricted sender and disabled email-content previews.
Development/regression/native fixtures stay local; do not create remote fixtures
or send synthetic mail to repeat acceptance.

Local validation reported 2,629 CPython reference tests, with 118 focused tests
passing after the three additional overlay-contract cases, and 62 admission tests
plus 27 subtests in the feature check. S01 with both activation overlays, Worker
mirror check, shell syntax and the pinned 728-module packaging dry-run passed.
These overlapping checks are not additive test totals.

Native acceptance used actual local Wrangler 4.136.3, workerd 1.20260921.1 and
Python 3.14/Workers SDK 1.9.0. Twenty-six bounded localhost POST requests checked
strict boolean RPC admission, send cooldown, the eleventh IP verification limit,
expiry cleanup, complete SQLite transaction rollback on injected SQL failure and
recovery. The fixture had no D1, EMAIL or provider binding; remote requests and
messages sent were both zero. Local evidence is
/workspace/.norulo-environment/email-admission-native-local-20261010/evidence.json.
This verifies native limiter behavior, not actual mail delivery.

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
The email release subsequently added NORULO_EMAIL_CODE_SECRET, matching the three
remote Secrets at that stage. Pinned Wrangler 4.136.3 generated inherit bindings
for those three during that full upload, retaining the configured values,
including the email-code Secret used by the enabled email feature. The later AI
preparation added TYPESAFE_API_KEY; the current config declares all four for
strict inheritance on subsequent uploads.
If a required binding is absent, strict inheritance rejects publication instead
of silently removing or substituting it. This declaration contains names only.
It does not use keep_vars or inherit unrelated Dashboard configuration, and it
does not establish secret validity or a successful OAuth exchange. A packaging
dry-run does not contact Cloudflare to check secret presence; verify names before
production activation.
Subsequent uploads must inherit all four. Declare any further provider Secrets
explicitly before uploads; never remove existing bindings as part of setup.

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
| Jev assistance | TYPESAFE_API_KEY is present as the fourth Worker Secret; runtime spec 11 has the network binding present | Both NORULO_JEV_SUGGESTIONS_ENABLED and NORULO_JEV_SUGGESTIONS_EVALUATED use the reviewed release overlay | Fresh 36-case direct HTTPS quality gates passed; release B runtime flags 1/1 verified; native real-provider HTTPS/user suggestions remain untested; manual entry remains available |
| Email verification | NORULO_EMAIL_CODE_SECRET, at least 32 characters; securely stored | Authenticated sender/domain/EMAIL and independent EMAIL_ADMISSION SQLite DO published with the dual D1/email overlay | Runtime flag 1; user-confirmed code receipt and successful email login; checked-in flag stays 0 |
| Scheduled recurring execution | No extra provider Secret | Independent RECURRING_SCHEDULER / RecurringScheduler SQLite DO, compatible legacy hourly journal plus daily Root/Owner checkpoint and reviewed cron overlay | Implementation/core/native/final-suite gates passed; release B runtime flag 1, exactly one daily UTC cron and strict limits verified; live financial/provider execution untested |

Creem IDs are public configuration, not prices or secrets. The JSON must be a
plain-text JSON string, for example
{"pro":{"month":"prod_pro_month","year":"prod_pro_year"},"max":{"month":"prod_max_month","year":"prod_max_year"}}.
Use actual distinct production IDs; omit unavailable cadences rather than
inventing products or promoting test IDs. The webhook destination is
https://api.norulo.com/webhooks/creem. Signed webhooks, not checkout responses,
control entitlements. No real charge or subscription modification is part of
basic deployment acceptance.

Email verification requires a callable durable admission adapter. The new
production path uses only its independent EMAIL_ADMISSION namespace; preview
retains its existing coordinator. Setting a sender, Secret and flag alone does
not establish successful delivery/login. Never bind production to the preview
validation journal or bypass fail-closed admission.
The gateway's email-auth flag also gates recurring-failure emails. The notification
path falls back to the application inbox and does not retry an unknown delivery;
do not interpret sender preparation as acceptance of those notifications.

The inherited preview path remains isolated under _recurring_enabled and
ValidationBudget. A separate production RecurringScheduler is now implemented and
locally verified; it never reuses that preview journal. Verified daily release B has
recurrence 1 and exactly one daily UTC cron. Control-plane publication/readback
and local implementation/packaging do not prove live background financial posting
or provider delivery; retain that distinction in later acceptance records.

## AI configuration and acceptance gates

The user provided TYPESAFE_API_KEY securely to the production Worker. Its name is
present as the fourth Secret, with the original GitHub pair and email-code Secret
retained; no value is recorded here. Earlier revision 8 lacked the cloud network
binding and real quality capture was blocked. Runtime specification 11 now
confirms both network Secret bindings present, retaining the Cloudflare token.
The existing single quality journal completed 36 real direct CPython HTTPS calls
once; both quality gates passed and independent review accepted this bounded
synthetic result. Native Worker real-provider HTTPS remains untested. Both
production AI flags are 1 in verified release B; actual customer suggestions
remain separate from direct HTTPS quality capture and configuration readback.

The local deployment helper now supports --activate-ai-suggestions. Its final
email-preservation guard repair requires production, --activate-production and
--activate-email-auth together; these AI helper/guard changes are published in
release A. It overlays both Jev flags to 1 while their checked-in defaults
remain 0. The static guard rejects mismatched or malformed flags, paused D1, placeholder/source/shared databases and a missing TYPESAFE_API_KEY declaration.
It does not consume quality artifacts or establish model/transport acceptance.
Actual quality review and release A publication/readback are complete. Preserve
the now-enabled recurrence too: the current release command uses all four
activation overlays:

```bash
./scripts/deploy-cloudflare.sh --environment production \
  --activate-production --activate-email-auth --activate-ai-suggestions \
  --activate-recurring-expenses --execute --local-checks-passed
```

Inherit all four Secrets so AI activation does not pause accepted email login or
discard credentials.

The current configurable default [Owner policy](../../norulo_server/ledger_plan_policy.py)
is Free $0, Pro $3 and Max $5 per UTC calendar month, with no rollover. Stored Owner paid
entitlement and opt-in apply across the ledger; collaborator plans do not replace
the Owner's budget. Each dispatch reserves 2,753 micro-USD atomically before model
work, preserving reservations on failure/unknown outcomes. Old daily rows remain
historical; there is no current daily request cap. These allowances/reservations
are operator policy, not provider settlement or invoice totals. Explicit valid
categories continue to support manual writes if AI is unavailable or exhausted.

The one reviewed journal at
/workspace/.norulo-environment/ai-quality-native-local-20261010 is complete, with
73 events: one session, 36 reservations and 36 completions. Strict offline replay
confirmed the session, fixture, six source hashes, per-case request hashes and
normalized results. Exactly 36 real responses were valid, with zero retries,
zero remote D1 operations and zero application requests. The capture used direct
CPython HTTPS through the configured proxy and verified CA. No native real-
provider Worker HTTPS request was made. Do not rerun this completed suite or
create another journal directory to bypass its 36-attempt scope.

| Language | Task | Clear labels correctly suggested | Uncertain labels withheld | False actionable hints |
| --- | --- | --- | --- | --- |
| English | Category | 16 / 16 | 2 / 2 | 0 |
| English | Project/shared target | 16 / 16 | 2 / 2 | 0 |
| Chinese | Category | 16 / 16 | 2 / 2 | 0 |
| Chinese | Project/shared target | 16 / 16 | 2 / 2 | 0 |

Each language has 18 cases. All six reversed-order pairs agreed; both
providerEvidenceComplete and eligibleForReview gates passed. This small,
agent-authored synthetic suite does not estimate customer-data error rates or
establish calibrated confidence. The full 99,108 micro-USD ($0.099108) reservation
is retained. Provider usage was 23,850 input / 4,144 output tokens, yielding a
$0.0010017 usage estimate, not an invoice or refund.

Fresh evidence recorded on 2026-10-11 in Asia/Shanghai:

- [Normalized actual responses](ai-quality-2026-10-11-results.jsonl).
- [Per-language/per-task aggregate](ai-quality-2026-10-11-aggregate.json).
- [Execution, journal/request pins, source hashes and costs](ai-quality-2026-10-11-execution.json).

The journal has no absolute timestamp; 2026-10-11 is the local recording date,
not an inferred precise execution timestamp. The earlier local/imported artifacts
are unchanged. Reproduce the current metrics offline:

```bash
python scripts/evaluate-ledger-suggestions.py \
  docs/validation/ai-quality-2026-10-11-results.jsonl
```

Local validation passed the complete 2,768-test reference suite before the final
email-preservation activation-guard repair. After that repair, the targeted suite
passed 177 tests and 28 subtests; S01 default and full production overlays, shell
syntax and diff checks passed. The final stable full suite subsequently passed
2,777 tests in 106.08 seconds, after the email-preservation guard and native-size
fixture repairs. Its local log is
/workspace/.norulo-environment/logs/ai-local-final-tests.log. These overlapping
runs are not additive totals and made no real model or remote D1 calls.
Native Python FFI exercised the canonical WorkerJevGateway in five loopback
fake-provider cases:
valid response, redirect rejection, oversized declared body, oversized streamed
body and deadline rejection. The revised size fixture is 65,537-byte valid JSON
that would pass validation without the cap; both size cases reported
JEV_RESPONSE_TOO_LARGE/ValueError. Each made one local attempt, with no retry, D1,
Durable Object or real provider request. No application gateway repair was needed.
This proves the bounded canonical local transport behavior, not model quality or
native production HTTPS. See the [safe local summary](ai-local-readiness-2026-10-10.json)
for source hashes and counters at the earlier blocked stage, when actual-model
acceptance was false. The fresh 2026-10-11 record above is the current quality
result. Stored Owner Pro/Max entitlement/opt-in and UTC-month $3/$5 reservation,
exhaustion and fallback fences passed local acceptance without remote fixtures. The
[imported TypeSafe review](typesafe-jev-review.md) contains historical source-service
results and obsolete Max-only/daily-limit text; it is not Norulo acceptance.

## Production recurring implementation and local acceptance

[RecurringScheduler](../../cloudflare/server/src/entry.py) and its
[coordination/observed-D1 module](../../norulo_server/cloudflare_recurring_scheduler.py)
retain the independent RECURRING_SCHEDULER SQLite namespace, class and migration
tag. The published daily capacity revision uses a Root coordinator and validated
permanent hash scopes for Owner DOs in that same namespace. Existing
completed_hour units and active/stopped state remain compatible, with an
additional daily epoch/checkpoint; no reset, namespace replacement, D1 migration
or public reconciliation endpoint is introduced. Daily publication/readback
passed in dated release B; release A remains the earlier hourly checkpoint.

Shared PRODUCTION_RECURRING_CRON is 10 16 * * * UTC, Beijing 00:10. Scheduled
entry uses server time. Existing weekly/monthly/quarterly/yearly frequencies,
per-rule timezone and original period date are retained. The daily scan compares
stored UTC next_run_at <= server time; other timezones can be delayed by nearly
24 hours. RPC success requires strict boolean true. Actual Owner/actor/member/key,
CAS, integer-money, idempotency and quota fences remain in each independent
canonical financial batch. The observed D1 wrapper requires complete native
row metadata; a failed/unknown dispatch is not a harmless business denial.

## Earlier hourly local acceptance — historical

Core review and 168 focused / 82 related tests passed. A whole-suite checkpoint
had 2,918 passes and one failure because the existing D1 SQL-literal AST test
classified the new DO's SQLite table as D1; its localized test repair preserved
D1 checking and was followed by the successful pre-packaging-fix **2,923-test
suite in 106.75 seconds**. After the package-closure repair below, the final
**2,942-test suite passed in 106.73 seconds**, including 19 new package-import
regression tests. Final S01, Worker mirror, shell and diff checks passed.
Overlapping checks are not additive test totals.

Actual native workerd acceptance passed 16 bounded requests across three
incarnations, with one synthetic local Free Owner/session/rule. It verified one
expense, audit and occurrence, one record-quota increment, idle/same-hour/cold-
restart/future-hour gates and a durable unknown-marker stop. The unknown marker
was manually parked in local DO SQLite; this is not evidence of injected loss
of a real native D1 response. The fixture's local D1 totals were:

| Phase | Statements | Rows read | Rows written |
| --- | --- | --- | --- |
| Fixture setup | 7 | 3 | 16 |
| Application | 21 | 15 | 17 |
| Scheduler | 26 | 367 | 24 |
| Integrity probes | 180 | 420 | 0 |
| Total | 234 | 805 | 57 |

These totals include finite setup/application/probes and exclude separately
applied twelve-file local CLI migrations. The native attempt count was absent
and remains null, never fabricated. No remote D1/application operation or real
provider request occurred. Independent review verified 83 source/dependency/
migration hashes, 41 raw metadata groups and all aggregate deltas. The
[compact native proof](production-recurring-native-local-2026-10-11.json) pins
source-chain/artifact hashes, limited acceptance and current preflight state.

The earlier all-overlay frozen dry-run produced 728 modules (338.02 KiB gzip),
but its module list omitted norulo_server.cloudflare_recurring_scheduler and
the validator did not cover the entry's absolute import. Cloudflare rejected
the attempted upload with validation **10021** for that missing module. This
package was incomplete and never activated; the old dry-run does not establish
publication readiness. Three read-only GET reconciliations confirmed the live
version ec33db03-2fd4-49a4-8430-9e1cb13fc340 and configuration unchanged: D1/email 1,
both AI flags 0, recurrence 0, no cron, intended DB/EMAIL and EmailAdmission
namespace, and all four Secrets retained.

The repaired actual frozen artifact has **729 modules, 1649.12 KiB total and
340.66 KiB gzip**. All **64 canonical modules** are byte-equal to source, including
the missing helper; entry closure covers 26 imports plus the full module graph.
Nineteen new regression tests and independent packaging review passed. Managed
local helper stop/start with fresh Worker/Vite returned server health 200, proxy
health 200 and protected profile 401. Local CLI migration application found no
unapplied migrations. These checks made no remote D1 or provider requests.
The [compact proof](production-recurring-native-local-2026-10-11.json) records
this later packaging checkpoint separately from unchanged native acceptance.
Source flags remain 0 and source has no cron; the nineteen live public variables
still match the source except the activation flags.
The final reviewed publication command is:

```bash
./scripts/deploy-cloudflare.sh --environment production \
  --activate-production --activate-email-auth --activate-ai-suggestions \
  --activate-recurring-expenses --execute --local-checks-passed
```

The recurring overlay requires all preceding production/D1/email/AI overlays,
now materializes the daily cron 10 16 * * * in a fresh Worker-relative
temporary config and does not run D1 migrations. Release A publication/readback
below used the earlier hourly cron; the daily replacement passed release B
publication/readback recorded separately below.
Preserve the same activation overlays and inherited Secrets on later uploads;
do not create remote fixtures or make repeated financial acceptance writes to
claim live schedule/provider acceptance.

## Verified production release A — 2026-10-11

The successful release used Server main
ebd11baf0da9d6aa83f8718b55e0c630e04108bd and Web main
3531f8ab23ac976f6e17caf1c2246dcbf5ea125c. At 05:38:43 UTC, seven read-only
Cloudflare GETs verified Server version b5642a63-1643-418a-b494-bb7bcf427050 and
Web version 26697b80-76dc-405b-a0c0-c2ea7c0735f7. This dated release A is a
checkpoint, not a guarantee of the latest versions after subsequent uploads.

- Nineteen Server public variables exactly match source with the five activation
  flags overlaid to 1. Exactly one cron, 0 * * * *, was created at 05:37:56 UTC.
- DB c41a1ab7-dffa-4c5d-a213-25f1bb6c78c5, EMAIL sender login@auth.norulo.com,
  EmailAdmission namespace 6588312f00f74840a37463e72a2d75eb and four Secret names
  were retained. RecurringScheduler namespace
  b3f41def1906481e9c72662debf4b505 is independently verified. Workers.dev and
  preview URLs are disabled for both services.
- The remote migration-tag field was absent/null. Namespace identity is verified
  and checked-in DO migration-tag definitions are retained; no remote tag
  readback is claimed.
- API and Web proxy health returned 200; both unauthenticated profile endpoints
  returned 401; homepage returned 200, with no Set-Cookie on these checks. The
  original logo hash matched and www returned 308 preserving path/query.

The final Server suite passed 2,942 tests in 106.73 seconds and Web passed 1,654
tests; fixed actual packaging contains 729 modules with all 64 canonical modules
byte-equal to source. This verification performed zero remote D1 SQL, application
mutations, provider/email requests, manual cron invocations or migration replays.
It did not repeat completed model-quality calls or native financial fixtures.
Native Worker real-provider HTTPS and live scheduled financial posting remain
untested. User-confirmed GitHub sign-in and email code/login remain accepted.

The [durable release record](production-release-2026-10-11.json) preserves the
sanitized proof hash, exact source heads, configuration/readback and these
acceptance limits. Earlier ec33/no-cron and rejected-upload checkpoints above
remain historical; the local/native and real-quality source hashes are unchanged.

## Verified daily capacity revision — release B

The user requested support for thousands of same-day postings and bounded
parallelism, superseding the earlier minimal daily plan. That earlier
[16-request proof](production-recurring-native-daily-local-2026-10-11.json) remains
an immutable historical checkpoint; it is not the new capacity acceptance. The
earlier release A used hourly polling. Release B verified the daily replacement.
The recommended daily time stays Beijing 00:10, 10 16 * * * UTC. Per-rule timezones
and original period dates remain intact; one daily scan can delay other
timezones by nearly 24 hours. No daily rule frequency is added.

The final source uses these explicit engineering bounds:

| Scope | Bound | Behavior at the boundary |
| --- | --- | --- |
| Root selection | 5,000 Owners; pages of 64; deferred/carry at most 64 | Persist bounded progress/backlog rather than retaining an unbounded owner set |
| Root handling | 10,000 handled occurrences | Preserve remaining backlog; this is a safety cap, not a throughput guarantee or D1 writing allowance |
| Child calls | 8,192 total RPCs, including status/read-only progress | Stop launching when the budget is reached |
| Owner concurrency | 8 logical workers | Each Owner's financial work remains serial and isolated in its validated hash scope |
| Owner chunk | At most 20 occurrences; 800 native SQL statements; 200-statement occurrence reserve | Stop before exceeding the conservative engineering reservation; actual native metrics remain distinct |
| Owner wall time | 120 seconds hard, including schema validation and execution | Bound the started Owner operation; uncertain financial work is not retried |
| Root wall time | Stop new launches at 600 seconds, then await started Owners within their remaining 120 seconds | Drain launched work under the official 900-second Cron wall ceiling |

Each posting retains its original independent atomic financial batch and actual
Owner/actor/member/key/CAS/idempotency/quota checks. A known pre-dispatch
minute-quota rejection defers to the next minute and releases the logical worker
slot. It does not write a SQL heartbeat, permanently block the rule, refund an
unknown operation or replay a completed posting. An Owner's completed same-chunk
replay returns cached metadata without D1; the next chunk has a unique identity.

Failure scopes are deliberately different. Native financial uncertainty leaves
that Owner permanently stopped while other Owners continue. An RPC transport
exception is advanced only when one read-only progress check proves the exact
chunk settled. If settlement cannot be proved, stop new launches, await started
siblings, then retain the existing Root global permanent unknown stop. There is
no automatic retry of unknown chunks, quarantine/reset API or journal
reinitialization. Legacy completed_hour storage remains an hour bucket, with
old active/stopped compatibility and an additional daily checkpoint.

Production config limits are strictly cpu_ms=300000 and subrequests=9000,
preserved in source-paused and temporary activated configurations. These are CPU
and subrequest settings, not a 900-second DO CPU allowance. The
[official provenance](cloudflare-scheduler-limits-2026-10-11.json) documents
Cron's 900-second wall ceiling, conditional Paid CPU limits and DO's default
30/configurable 300 CPU seconds. Paid billing remains unconfirmed. The D1-specific
1,000/50 query table and newer generic subrequest table do not establish SQL
statement-versus-batch-dispatch counting or resets per Owner DO invocation;
800 statements is an independent conservative engineering bound. Actual
publication/readback must verify accepted settings without implying a billing
receipt or production throughput guarantee.

One separately user-requested real production capacity SELECT found total/active/
due rule counts all zero, native read 1/write 0, no fixtures or retries. This is
a dated capacity snapshot, not a daily writing budget. Development, failure
injection and scale fixtures remain on isolated local D1; no new remote SQL
migrations, synthetic fixtures or financial acceptance writes are required.

Frozen actual packaging passed 729 modules, 1675.10 KiB total/348.25 KiB gzip,
including the 29.06 KiB scheduler helper. All 64 canonical module bytes, the
separate blank initializer and absolute/relative entry import closure match.
The earlier capacity full-suite checkpoint passed 3,006 tests in 111.20 seconds
before three failure cases were added; the definitive final whole suite passed
**3,009 tests in 115.01 seconds**. The earlier Web whole-suite checkpoint passed
1,654 tests. The subsequent production API-guide URL/text correction across
three source files passed 15 focused tests in 3.84 seconds, lint and the
production build; these focused checks are not a replacement whole-suite run.

Final native capacity acceptance passed. The
[compact proof](production-recurring-load-native-local-2026-10-11.json) preserves
the producer/runtime/source chain, all 83 source/dependency/migration hashes,
raw capture hashes and precise phase totals without committing large raw
financial snapshots.

| Local profile | Owners × rules | Daily-pass wall time | Peak Owner concurrency | Daily SQL / rows read / rows written | Whole-profile SQL / rows read / rows written |
| --- | --- | --- | --- | --- | --- |
| Overlap diagnostic | 8 × 1 | 1.621 s, including an injected 1,200 ms wait per Owner | 8 | 185 / 1,551 / 192 | 484 / 2,614 / 416 |
| Natural 1,000 occurrences | 200 × 5 | 33.985 s | 8 | 27,606 / 73,063 / 24,000 | 48,897 / 164,618 / 41,600 |
| Natural 3,000 occurrences | 600 × 5 | 107.635 s | 8 | 82,812 / 228,201 / 72,000 | 146,503 / 502,333 / 124,800 |

The natural profiles' maximum per-Owner SQL was 178; Root SQL maxima were 6/12.
All Owner and daily-window metrics matched the underlying native statement
groups, including rows read/written. Same-epoch/cold Root replay and warm/cold
manually parked Owner/legacy Root unknown markers used zero D1. These markers
do not demonstrate native lost-commit or RPC transport fault injection; known
minute-quota deferral is covered by reference tests. Whole-profile totals
include fixtures, rule creation, setup and integrity probes; local CLI migrations
and DO SQLite billing are excluded. The overlap wait is diagnostic only. Natural
timings describe local workloads spread across Owners, not a same-Owner limit,
production SLA or a complete Cloudflare bill. Daily publication/readback passed
in dated release B; live scheduled financial/provider behavior remains untested.
The completed 36-call real AI journal and its six accepted source hashes remain
unchanged and must not be replayed.

## Verified production daily release B — 2026-10-11

At 06:38:08 UTC, seven read-only Cloudflare GETs and seven finite public checks
verified Server main ded49a46b06f5f79e2996f58d773d66acaddc0a0 as version
e2e4e02d-ac9a-4c20-852f-f6cbfe5b5ae4 and Web main
bef23ee7cca378614cdf1e7cdcc8494601c86648 as version
0c63c81e-1f91-4b72-bf3b-f949b7840ad8. This is dated release B, not a permanent
claim about the latest version after future uploads.

- Exactly one cron, 10 16 * * *, was created at 06:37:31 UTC. Limits read back
  exactly cpu_ms=300000/subrequests=9000. This demonstrates accepted configuration,
  not confirmed Paid billing, a production throughput SLA or official D1
  statement/batch-counting semantics.
- Nineteen public variables matched source with five activation flags 1. The
  original DB UUID, EmailAdmission and RecurringScheduler namespace identities,
  restricted EMAIL sender and all four Secret names were retained. Workers.dev
  and public previews remained disabled for both services. Remote migration-tag
  readback was absent/null; checked-in tag definitions were retained separately.
- API and Web proxy health returned 200, both unauthenticated profile endpoints
  returned 401 and homepage returned 200, without Set-Cookie. The original logo
  hash matched; www returned 308 preserving path/query.
- This verification used zero remote D1 SQL, application mutations, manual cron
  invocations, provider requests, acceptance emails or migration replays. It
  did not repeat completed quality calls or local financial fixtures. Live
  scheduled financial/provider execution and native Worker real-provider HTTPS
  remain untested; user-confirmed GitHub and email-code login are retained.

The [durable daily release record](production-daily-release-2026-10-11.json)
copies the sanitized readback with its SHA-256, exact deployed source heads,
local test/package references and limits of acceptance. Earlier release A,
minimal-daily and native-capacity records remain immutable dated evidence.

## Remaining release checklist

Database initialization and complete Python publication are complete. The following
distinguishes remaining real-user acceptance from feature-specific work; none requires remote
synthetic business writes.

| Scope | Remaining work besides D1 | Acceptance required |
| --- | --- | --- |
| Core GitHub/free ledger — remaining acceptance | GitHub sign-in is user-confirmed; preserve the deployment/DB/Secrets and verify remaining App/session behaviors | Repository installation, credential refresh, sign-out/session details and the complete ledger journey remain unverified; business regression/isolation tests stay local |
| Requested email login — published and user-confirmed | Preserve the independent admission, dual activation overlays, existing domain/EMAIL and all four now-configured Secrets | Code receipt and successful browser login are user-confirmed; account linking, sign-out/refresh and production abuse scenarios remain separate; local tests cover expiry/single use and bounded admission |
| GitHub repository associations — optional | A user's App installation and chosen repository grants; no numeric App ID/private key required | Actual installation Setup callback with server-issued state and authorized repository discovery/synchronization; standalone projects do not need installation |
| Paid plans — optional | Independent live Creem products for the available plan/cadence pairs, API/webhook Secrets and explicit inheritance, signed webhook registration | Accurate public prices and idempotent entitlement changes from verified webhooks; no charge or subscription mutation is part of core acceptance |
| Jev AI assistance — published/enabled, quality reviewed | Preserve all four Secrets and all D1/email/AI/recurrence activation overlays | Fixed real quality suite and local Owner/monthly fences passed; release B runtime flags verified; actual customer suggestions and native real-provider HTTPS remain untested |
| Recurring posting — daily release B published/verified | Preserve Root/Owner journals, existing namespace, four Secrets, strict CPU/subrequest limits and all overlays; daily cron 10 16 * * * (Beijing 00:10) | Final whole suite 3,009 passed; 8-way overlap and natural 1,000/3,000-occurrence native profiles passed; daily publication/readback verified; live financial/provider behavior untested; bounded progress/backlog remains possible |

Production domains, frontend assets, the published API/Web transport, system sending
domain/binding and the original three Secret names are already recorded above.
AI preparation subsequently added the fourth Secret as recorded separately.
They do not need new secret
values from the user and do not establish live application behavior. No additional
receiving mailbox is required by the Server for its system sender.

Email publication and user-confirmed code/login acceptance are complete. The AI
stage now has its Worker/network Secret bindings, independently reviewed fixed
real quality evidence and locally verified Owner/monthly allowance fences.
Verified release B has both runtime AI flags 1 and recurrence 1 with the daily
UTC cron, preserving D1 and accepted email login. The distinct production
scheduler/coordinator passed implementation, native/core review and the final
full suite. Publication/configuration readback does not establish actual native
provider HTTPS, customer suggestions or scheduled financial/provider behavior. Any new provider Secret must be explicitly inherited on later
uploads, retaining all four now configured. No remote fixture writes, real charge or
subscription modification is implied by this sequence.

## Publication sequence and validation

Frontend/domain, sending-domain/binding and D1 initialization are complete at the
control plane. Full Python publication and finite read-only health/transport
checks are also complete. The email-enabled release and user-confirmed GitHub/
email sign-in are complete. The user resumed the full application sequence;
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
inheritance helper and reviewed strict missing-binding error handling.
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
DNS and binding state described above; no email was sent for acceptance at that
stage. The later email-enabled release and actual user-confirmed code receipt /
login are recorded in the production email admission section.

## Subsequent Free public-use preparation, 2026-10-11

Real payments are deferred by the user. Explicitly empty product configuration
now returns a genuine Free catalog instead of a provider-price 503; paid prices
remain null and checkout disabled. Authenticated usage/entitlement retain their
actual authorization snapshot. Invalid product configuration still fails
closed. The user separately confirmed ordinary real expense recording succeeds;
live recurring financial posting and native paid-AI provider acceptance remain
unverified.

The subsequent local Server full suite passed 3,052 tests in 125.03 seconds. A
fresh actual dry-run package verified all 64 canonical modules, blank initializer
and absolute/relative import closure; it contains 729 uploaded modules. This
does not replace the earlier capacity evidence or require repeating load/model
acceptance calls. Mobile layout, Free billing and self-hosted-font privacy copy
are corrected in Web and verified separately.

The [production runbook](../operations.md) records the safe logging policy,
natural daily-run checks, alert-delivery limitations, private recovery bookmark
and coordinated D1/DO recovery boundaries. Metadata checks used no SQL, restore,
manual Cron or remote business writes. The new
[dated Free release](production-free-launch-2026-10-11.json) records exact checks
and production versions after publication; earlier release snapshots remain
historical.
