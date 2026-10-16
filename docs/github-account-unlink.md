# GitHub account unlinking

`DELETE /integrations/github` unlinks the actual signed-in account, independent
of the selected ledger or the provider used to create the account. It requires
a cookie session, a trusted Origin/Referer and a verified email login identity
whose exact `emailIdentities` record belongs to that account. A GitHub profile
email or billing contact email is insufficient. A bound login email cannot be
unlinked or replaced; the existing email-link flow enforces replacement rejection.

The response is the current `AccountSession`. The current browser session and
account ID remain valid. GitHub identity ownership, encrypted credentials,
refresh claims and repository grants are removed together. Projects and their
repository associations, expense history, memberships, API keys and billing
facts are retained. GitHub App installations are not uninstalled remotely.

The single D1 batch checks exact user, session, email identity and GitHub mapping
snapshots before publishing anything. A concurrent change rolls back the batch.
An already detached account returns the session without another write. There is
no schema migration, provider call, background task or automatic mutation retry.

Each unlink changes an account-local GitHub link revision. Login-link and
installation states capture this revision and callbacks recheck it, including
after provider awaits. Refresh publication already fences the saved account and
credential generation. Consequently, an old callback or refresh cannot restore
a removed connection, even after a subsequent explicit relink.

Standalone GitHub logins with a fresh owner ID claim their `githubIdentities`
mapping atomically. Unchanged legacy logins keep their deterministic identity
without an additional mapping write. Legacy `usr_github_<id>` accounts with their GitHub identity
removed keep their verified email and ledger. A later standalone GitHub login
creates a separate account and cannot reopen that retained account. The released
identity can instead be explicitly linked to an existing signed-in account;
accounts are never merged.

Settings shows a disabled unlink action and email-binding guidance until a
verified login email is present. A confirmation describes the effect before the
request. Successful unlinking updates the app session and invalidates old GitHub
refresh and session-recheck generations. Unconfirmed results require an explicit
reload before another unlink attempt. All new copy supports the six app locales.

Local lifecycle, cookie/Origin, identity-conflict, SQL admission and transaction
race coverage lives in `tests/test_github_unlink.py`. Web coverage includes email
binding eligibility, confirmation/cancel, duplicate submission, failed/late
responses and app-level scope invalidation. These fixtures send no real email,
call no GitHub provider and write no production data.
