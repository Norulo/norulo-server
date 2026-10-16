"""Local account lifecycle and race checks; no provider or remote writes."""
import asyncio
import sqlite3

import pytest

from norulo_server.cloudflare_email_auth import email_key
from norulo_server.cloudflare_github_identity_http import _user
from norulo_server.cloudflare_state_records import encode_record, record_name
from test_cloudflare_email_auth import (
    EMAIL, NOW, ORIGIN, records, request, runtime, seed_user, verify,
)
from test_cloudflare_github_identity_http import GitHubStub, call, link_state, login


def put(runtime, kind, identity, value):
    with runtime.binding.store.connect() as db:
        db.execute("INSERT OR REPLACE INTO app_state VALUES(?,?,?)",
            (record_name(kind, identity), encode_record(kind, identity, value), NOW))


def unlink(runtime, cookie, *, now=NOW + 1, headers=None, gateway=None):
    return call(runtime.binding, gateway or GitHubStub(), now, "DELETE", "/integrations/github",
        headers=headers if headers is not None else {"Cookie": cookie, "Origin": ORIGIN})


@pytest.mark.parametrize("owner,mapped", [
    ("usr_github_77", False), ("usr_github_77", True), ("usr_email_alice", True),
])
def test_unlink_preserves_email_login_owner_session_billing_and_history(runtime, owner, mapped):
    user, cookie = seed_user(runtime, email=EMAIL, verified=True, user_id=owner)
    user.update(githubLogin="alice", githubRefreshToken="sealed:refresh",
        githubAccessTokenExpiresAt=NOW + 30, githubRefreshTokenExpiresAt=NOW + 100,
        githubAccessTokenUpdatedAt=NOW, githubTokenRefresh={"id": "pending", "startedAt": NOW},
        githubRepositoryAccess={"mode": "github-app", "status": "authorized"})
    put(runtime, "users", owner, user)
    if mapped:
        put(runtime, "githubIdentities", "77", {"githubId": "77", "userId": owner, "createdAt": NOW})
    before_email, before_sessions = records(runtime, "emailIdentities"), records(runtime, "sessions")
    with runtime.binding.store.connect() as db:
        db.execute("CREATE TABLE retained_history(id TEXT PRIMARY KEY, payload TEXT)")
        db.execute("INSERT INTO retained_history VALUES('expense', 'financial-history')")
        before_billing = [tuple(row) for row in db.execute("SELECT * FROM account_entitlement_authority")]

    class NoProvider(GitHubStub):
        async def unseal(self, token):
            raise AssertionError("Unlinking must not call GitHub")

    status, payload, headers = unlink(runtime, cookie, gateway=NoProvider())
    assert status == 200 and headers == {"Cache-Control": "no-store"}
    assert payload["user"]["id"] == owner and payload["user"]["providers"] == ["email"]
    assert payload["user"]["emailVerified"] is True
    assert payload["github"] == {"identityConnected": False, "repositoriesConnected": False}
    saved = records(runtime, "users")[0]
    assert {key: value for key, value in saved.items() if key != "githubLinkRevision"} == {
        key: (["email"] if key == "providers" else value)
        for key, value in user.items() if not key.startswith("github")}
    assert records(runtime, "githubIdentities") == []
    assert records(runtime, "emailIdentities") == before_email
    assert records(runtime, "sessions") == before_sessions
    with runtime.binding.store.connect() as db:
        assert [tuple(row) for row in db.execute("SELECT * FROM account_entitlement_authority")] == before_billing
        assert tuple(db.execute("SELECT * FROM retained_history").fetchone()) == ("expense", "financial-history")
    assert call(runtime.binding, NoProvider(), NOW + 2, "GET", "/auth/session",
        headers={"Cookie": cookie})[1] == payload
    groups = len(runtime.binding.groups)
    assert unlink(runtime, cookie)[1] == payload
    assert len(runtime.binding.groups) == groups  # repeated DELETE is read-only
    issued = request(runtime, now=NOW + 3)
    status, email_session, _ = verify(runtime, issued, now=NOW + 4)
    assert status == 200 and email_session["user"]["id"] == owner


@pytest.mark.parametrize("case", ["none", "contact", "unverified", "missing-map", "other-owner"])
def test_unlink_requires_independent_verified_email_mapping_without_writes(runtime, case):
    user, cookie = seed_user(runtime, email=EMAIL if case != "none" else None,
                            verified=case in {"missing-map", "other-owner"})
    if case == "unverified":
        user.update(providers=["github", "email"], emailVerified=True)
        put(runtime, "users", user["id"], user)
    if case in {"missing-map", "other-owner"}:
        with runtime.binding.store.connect() as db:
            db.execute("DELETE FROM app_state WHERE name=?", (record_name("emailIdentities", email_key(EMAIL)),))
        if case == "other-owner":
            put(runtime, "emailIdentities", email_key(EMAIL),
                {"email": EMAIL, "userId": "usr_other", "createdAt": NOW, "verifiedAt": NOW})
    before, groups = records(runtime, "users"), list(runtime.binding.groups)
    result = unlink(runtime, cookie)
    assert (result[0], result[1]["error"]["code"]) == (409, "EMAIL_REQUIRED_FOR_GITHUB_UNLINK")
    assert records(runtime, "users") == before and runtime.binding.groups == groups


@pytest.mark.parametrize("headers,status", [
    ({"Origin": ORIGIN}, 401),
    ({"Cookie": "nr_session=ses-existing", "Origin": "https://evil.example"}, 403),
    ({"Cookie": "nr_session=ses-existing"}, 403),
    ({"Cookie": "nr_session=ses-existing", "Origin": ORIGIN, "Authorization": "Bearer nrk_key"}, 401),
])
def test_unlink_requires_trusted_cookie_session(runtime, headers, status):
    seed_user(runtime, email=EMAIL, verified=True)
    assert unlink(runtime, "", headers=headers)[0] == status
    assert runtime.binding.groups == []


def test_detached_legacy_account_is_never_recovered_by_standalone_github_login(runtime):
    original, cookie = seed_user(runtime, email=EMAIL, verified=True)
    assert unlink(runtime, cookie)[0] == 200
    status, _, headers = login(runtime.binding, GitHubStub(), NOW + 2)
    assert status == 302
    new_cookie = headers["Set-Cookie"].split(";", 1)[0]
    new_user = call(runtime.binding, GitHubStub(), NOW + 3, "GET", "/auth/session",
                    headers={"Cookie": new_cookie})[1]["user"]
    assert new_user["id"] != original["id"] and new_user["providers"] == ["github"]
    assert new_user["email"] is None
    assert records(runtime, "githubIdentities")[0]["userId"] == new_user["id"]
    # The next GitHub login resolves the claimed mapping, not another account.
    assert login(runtime.binding, GitHubStub(), NOW + 4)[0] == 302
    assert len(records(runtime, "users")) == 2
    assert asyncio.run(_user(runtime.binding, original["id"]))["providers"] == ["email"]


@pytest.mark.parametrize("owner", ["usr_github_77", "usr_email_alice"])
def test_explicit_relink_can_reclaim_released_identity_and_old_callbacks_stay_invalid(runtime, owner):
    user, cookie = seed_user(runtime, email=EMAIL, verified=True, user_id=owner)
    headers = {"Cookie": cookie, "Origin": ORIGIN}
    fixture = type("Fixture", (), {"now": NOW})()
    old_state = link_state(runtime.binding, GitHubStub(), fixture, headers)
    assert unlink(runtime, cookie)[0] == 200
    state = link_state(runtime.binding, GitHubStub(), fixture, headers)
    assert call(runtime.binding, GitHubStub(), NOW + 2, "GET", "/auth/github/callback",
        {"state": state, "code": "synthetic-code"}, headers)[0] == 302
    result = call(runtime.binding, GitHubStub(), NOW + 3, "GET", "/auth/github/callback",
        {"state": old_state, "code": "synthetic-code"}, headers)
    assert (result[0], result[1]["error"]["code"]) == (409, "ACCOUNT_CHANGED")
    assert records(runtime, "githubIdentities")[0]["userId"] == owner
    assert len(records(runtime, "users")) == 1


@pytest.mark.parametrize("change", ["users", "sessions", "emailIdentities", "githubIdentities"])
def test_unlink_batch_rolls_back_on_concurrent_identity_or_session_change(runtime, change):
    user, cookie = seed_user(runtime, email=EMAIL, verified=True)
    mapping = {"githubId": "77", "userId": user["id"], "createdAt": NOW}
    put(runtime, "githubIdentities", "77", mapping)
    def race():
        identity = {"users": user["id"], "sessions": "ses-existing",
                    "emailIdentities": email_key(EMAIL), "githubIdentities": "77"}[change]
        with runtime.binding.store.connect() as db:
            db.execute("DELETE FROM app_state WHERE name=?", (record_name(change, identity),))
    runtime.binding.before_group = race
    with pytest.raises(sqlite3.IntegrityError):
        unlink(runtime, cookie)
    if change != "users":
        assert records(runtime, "users") == [user]
    if change != "githubIdentities":
        assert records(runtime, "githubIdentities") == [mapping]
    with runtime.binding.store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM d1_command_guard").fetchone()[0] == 0


def test_unlink_during_github_link_provider_await_prevents_credential_publication(runtime):
    user, cookie = seed_user(runtime, email=EMAIL, verified=True)
    headers = {"Cookie": cookie, "Origin": ORIGIN}
    fixture = type("Fixture", (), {"now": NOW})()
    state = link_state(runtime.binding, GitHubStub(), fixture, headers)
    class Unlinking(GitHubStub):
        async def profile(self, token):
            from norulo_server.cloudflare_github_identity_http import _session_user, _unlink_github
            session, current = await _session_user(runtime.binding, headers, NOW)
            await _unlink_github(runtime.binding, user=current, session=session, now=NOW + 1)
            return await super().profile(token)
    result = call(runtime.binding, Unlinking(), NOW + 2, "GET", "/auth/github/callback",
        {"state": state, "code": "synthetic-code"}, headers)
    assert (result[0], result[1]["error"]["code"]) == (409, "ACCOUNT_CHANGED")
    assert records(runtime, "users")[0]["providers"] == ["email"]


def test_installation_callback_issued_before_unlink_stays_invalid_after_relink(runtime):
    from urllib.parse import parse_qs, urlsplit
    _, cookie = seed_user(runtime, email=EMAIL, verified=True)
    headers = {"Cookie": cookie, "Origin": ORIGIN}
    status, payload, _ = call(runtime.binding, GitHubStub(), NOW, "GET", "/integrations/github/authorize", headers=headers)
    assert status == 200
    install_state = parse_qs(urlsplit(payload["url"]).query)["state"][0]
    assert unlink(runtime, cookie)[0] == 200
    fixture = type("Fixture", (), {"now": NOW + 2})()
    state = link_state(runtime.binding, GitHubStub(), fixture, headers)
    assert call(runtime.binding, GitHubStub(), NOW + 3, "GET", "/auth/github/callback",
        {"state": state, "code": "synthetic-code"}, headers)[0] == 302
    result = call(runtime.binding, GitHubStub(), NOW + 4, "GET", "/integrations/github/callback",
        {"state": install_state, "installation_id": "501"}, headers)
    assert (result[0], result[1]["error"]["code"]) == (409, "ACCOUNT_CHANGED")


def test_email_cannot_be_changed_or_unlinked_after_github_unlink(runtime):
    from test_cloudflare_email_auth import call as email_call, REQUEST
    _, cookie = seed_user(runtime, email=EMAIL, verified=True)
    assert unlink(runtime, cookie)[0] == 200
    result = email_call(runtime, REQUEST, {"email": "other@example.test", "purpose": "link"}, cookie=cookie)
    assert (result[0], result[1]["error"]["code"]) == (409, "EMAIL_CHANGE_NOT_SUPPORTED")
    assert runtime.gateway.sent == []
    assert call(runtime.binding, GitHubStub(), NOW + 2, "DELETE", "/integrations/email", headers={"Cookie": cookie, "Origin": ORIGIN}) is None
    assert records(runtime, "emailIdentities")[0]["email"] == EMAIL


def test_in_flight_github_refresh_cannot_restore_unlinked_credentials(runtime):
    from test_github_token_refresh import ExpiringGitHub, ACCESS, REFRESH
    from norulo_server.cloudflare_github_identity_http import _session_user, _unlink_github
    user, cookie = seed_user(runtime, email=EMAIL, verified=True)
    user.update(githubAccessToken="sealed:" + ACCESS, githubAccessTokenExpiresAt=NOW,
                githubRefreshToken="sealed:" + REFRESH, githubRefreshTokenExpiresAt=NOW + 1000)
    put(runtime, "users", user["id"], user)
    headers = {"Cookie": cookie, "Origin": ORIGIN}
    gateway = ExpiringGitHub()
    async def detach():
        session, current = await _session_user(runtime.binding, headers, NOW)
        await _unlink_github(runtime.binding, user=current, session=session, now=NOW + 1)
    gateway.refresh_wait = detach
    result = call(runtime.binding, gateway, NOW, "POST", "/integrations/github/refresh", headers=headers)
    assert result[0] == 409
    assert records(runtime, "users")[0]["providers"] == ["email"]
    assert "githubAccessToken" not in records(runtime, "users")[0]
    assert len(gateway.refresh_calls) == 1


def test_unlink_uses_admitted_bounded_sql(runtime):
    from norulo_server.cloudflare_preview_budget import _input_bound, sql_write_bound
    _, cookie = seed_user(runtime, email=EMAIL, verified=True)
    batch = runtime.binding.batch
    async def bounded(statements):
        guards = 0
        for item in statements:
            _input_bound(item.params, sql=item.sql)
            assert sql_write_bound(item.sql, guards) <= 4
            guards += item.sql.startswith("INSERT INTO d1_command_guard")
        return await batch(statements)
    runtime.binding.batch = bounded
    assert unlink(runtime, cookie)[0] == 200
