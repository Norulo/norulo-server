"""Explicit, fenced rotation of a GitHub App user's expiring token pair.

Repository GETs never write. A persisted claim excludes concurrent consumers
and survives restarts or unknown provider/native outcomes without being retried.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .cloudflare_github_gateway import GitHubFailure, GitHubTokenBundle, token_bundle
from .cloudflare_state_records import decode_record, encode_record, read_record_json, record_name
from .cloudflare_session_adapter import read_session_snapshot, session_record_ids
from .cloudflare_validation_budget import _field

REFRESH_MARGIN = 60
CLAIM_SECONDS = 60
MAX_SAFE_INTEGER = 9007199254740991
TOKEN_FIELDS = ("githubAccessTokenExpiresAt", "githubRefreshToken", "githubRefreshTokenExpiresAt", "githubTokenRefresh")


def refresh_required(user: dict, now: int | None) -> bool:
    """Only complete, still-valid refresh facts permit an automatic attempt."""
    access_expiry, refresh_expiry = user.get("githubAccessTokenExpiresAt"), user.get("githubRefreshTokenExpiresAt")
    return (type(now) is int and 0 <= now <= MAX_SAFE_INTEGER - REFRESH_MARGIN
            and bool(user.get("githubId"))
            and isinstance(user.get("githubAccessToken"), str) and bool(user["githubAccessToken"])
            and isinstance(user.get("githubRefreshToken"), str) and bool(user["githubRefreshToken"])
            and type(access_expiry) is int and 0 < access_expiry <= now + REFRESH_MARGIN
            and type(refresh_expiry) is int and now < refresh_expiry <= MAX_SAFE_INTEGER
            and "githubTokenRefresh" not in user)


async def sealed_token_fields(bundle: GitHubTokenBundle, gateway: Any, now: int) -> dict:
    """Validate and encrypt provider token facts before any persistence."""
    if not isinstance(bundle, GitHubTokenBundle) or type(now) is not int or not 0 <= now <= MAX_SAFE_INTEGER:
        raise GitHubFailure("GITHUB_RESPONSE_INVALID")
    raw = {"access_token": bundle.access_token, "token_type": "bearer"}
    if any(value is not None for value in (bundle.expires_in, bundle.refresh_token, bundle.refresh_token_expires_in)):
        raw.update(expires_in=bundle.expires_in, refresh_token=bundle.refresh_token,
                   refresh_token_expires_in=bundle.refresh_token_expires_in)
    bundle = token_bundle(raw)
    result = {"githubAccessToken": await gateway.seal(bundle.access_token), "githubAccessTokenUpdatedAt": now}
    if bundle.expires_in is not None:
        if now > MAX_SAFE_INTEGER - max(bundle.expires_in, bundle.refresh_token_expires_in):
            raise GitHubFailure("GITHUB_RESPONSE_INVALID")
        result.update(githubAccessTokenExpiresAt=now + bundle.expires_in,
                      githubRefreshToken=await gateway.seal(bundle.refresh_token),
                      githubRefreshTokenExpiresAt=now + bundle.refresh_token_expires_in)
    return result


async def _publish_user(binding: Any, *, user: dict, expected_json: str,
                        session: dict, session_json: str, now: int) -> bool:
    """One bounded CAS; a losing consumer cannot call the provider."""
    saved_session = json.loads(session_json)
    identity = saved_session.get('id', session['id']) if isinstance(saved_session, dict) else None
    if (identity not in session_record_ids(session['id'])
            or {**saved_session, 'id': session['id']} != session):
        return False
    # The validated snapshot identifies either the new fingerprint key or its
    # original legacy key. The SQL EXISTS below rechecks that exact snapshot
    # atomically; no redundant D1 read or enlarged refresh budget is needed.
    decode_record('sessions', identity, session_json)
    statement = binding.prepare("""UPDATE app_state SET payload=?,updated_at=?
        WHERE name=? AND payload=? AND EXISTS(SELECT 1 FROM app_state
          WHERE name=? AND payload=? AND json_extract(payload,'$.userId')=?
            AND json_extract(payload,'$.expiresAt')>?) RETURNING name""").bind(
                encode_record("users", user["id"], user), now,
                record_name("users", user["id"]), expected_json,
                record_name("sessions", identity), session_json, user["id"], now)
    result = await binding.batch([statement])
    rows = list(_field(result[0], "results", []))
    return len(rows) == 1


async def _current_claim(binding: Any, *, expected: dict, claim: dict) -> tuple[dict | None, str | None]:
    snapshot = await read_record_json(binding, "users", expected["id"])
    current = json.loads(snapshot) if snapshot is not None else None
    if (not isinstance(current, dict) or current.get("githubId") != expected.get("githubId")
            or current.get("githubTokenRefresh") != claim
            or any(current.get(field) != expected.get(field) for field in (
                "githubAccessToken", "githubAccessTokenExpiresAt", "githubRefreshToken", "githubRefreshTokenExpiresAt"))):
        return None, None
    return current, snapshot


async def _publish_key_user(binding: Any, *, user: dict, expected_json: str,
                            proof: dict, now: int) -> bool:
    """Rotate only the actor, fencing the delegated key and ledger membership.

    The user CAS follows the current token generation. A shared ledger's owner
    snapshot is a separate authorization fence, never a source of credentials.
    """
    if proof["actor_user_id"] != user["id"]:
        return False
    key = proof["key"]
    checks = ["""EXISTS(SELECT 1 FROM api_keys WHERE key_hash=? AND user_id=?
        AND scopes=? AND restrictions=? AND revoked_at IS NULL
        AND (expires_at IS NULL OR expires_at>=?))"""]
    values = [hashlib.sha256(proof["token"].encode()).hexdigest(), user["id"],
              key["scopes"], key["restrictions"], now]
    workspace = proof["workspace_id"]
    if workspace != user["id"]:
        checks.extend(["EXISTS(SELECT 1 FROM app_state WHERE name=? AND payload=?)",
            """EXISTS(SELECT 1 FROM workspace_members WHERE workspace_id=?
                AND user_id=? AND role=? AND revision=? AND removed_at IS NULL)"""])
        values.extend([record_name("users", workspace), proof["owner_user"], workspace,
                       user["id"], proof["workspace_role"], proof["workspace_revision"]])
    statement = binding.prepare("""UPDATE app_state SET payload=?,updated_at=?
        WHERE name=? AND payload=? AND """ + " AND ".join(checks) + " RETURNING name").bind(
            encode_record("users", user["id"], user), now,
            record_name("users", user["id"]), expected_json, *values)
    result = await binding.batch([statement])
    return len(list(_field(result[0], "results", []))) == 1


async def handle_key_github_refresh(*, binding: Any, gateway: Any, method: str,
                                   headers: dict, body: object, now: int):
    """Explicit API-key maintenance of the actor's existing GitHub grant."""
    from .cloudflare_ledger_auth import ledger_principal
    from .cloudflare_principal import PrincipalAuthError
    if method != "POST":
        return 405, {"error": {"code": "METHOD_NOT_ALLOWED"}}
    if body != {}:
        return 422, {"error": {"code": "INVALID_INPUT"}}
    proof = {}
    try:
        effective, _, auth, validate = await ledger_principal(binding=binding,
            headers=headers, scope="projects:read", now=now, proof=proof)
        snapshot = await binding.batch(auth)
        validate([part.results for part in snapshot])
        if proof.get("key") is None:
            return 401, {"error": {"code": "UNAUTHENTICATED"}}
        status, payload, _ = await handle_github_refresh(binding=binding, gateway=gateway,
            session=None, user=effective["_actor"], now=now, key_proof=proof)
        return status, payload
    except PrincipalAuthError as error:
        return error.status, {"error": {"code": error.code}}
    except GitHubFailure as error:
        return error.status, {"error": {"code": error.code}}


def _error(status: int, code: str):
    return status, {"error": {"code": code}}, {"Cache-Control": "no-store"}


async def handle_github_refresh(*, binding: Any, gateway: Any, session: dict | None,
                               user: dict, now: int, key_proof: dict | None = None):
    """Called after a trusted cookie session or a validated delegated-key proof."""
    claim = user.get("githubTokenRefresh")
    if "githubTokenRefresh" in user:
        started = claim.get("startedAt") if isinstance(claim, dict) else None
        if type(started) is int and started <= now < started + CLAIM_SECONDS:
            return _error(409, "GITHUB_REFRESH_PENDING")
        return _error(403, "GITHUB_REAUTHORIZATION_REQUIRED")
    access_expiry, refresh_expiry = user.get("githubAccessTokenExpiresAt"), user.get("githubRefreshTokenExpiresAt")
    if (not user.get("githubId") or not isinstance(user.get("githubAccessToken"), str)
            or not user.get("githubAccessToken") or type(access_expiry) is not int
            or not 0 < access_expiry <= MAX_SAFE_INTEGER
            or not isinstance(user.get("githubRefreshToken"), str) or not user["githubRefreshToken"]
            or type(refresh_expiry) is not int or not now < refresh_expiry <= MAX_SAFE_INTEGER):
        return _error(403, "GITHUB_REAUTHORIZATION_REQUIRED")
    if access_expiry > now + REFRESH_MARGIN:
        return 200, {"ok": True, "refreshed": False}, {"Cache-Control": "no-store"}

    # Decryption/configuration are local and cannot consume the provider token.
    refresh_token = await gateway.unseal(user["githubRefreshToken"])
    validate = getattr(gateway, "validate_refresh_configuration", None)
    if validate is not None:
        await validate()
    user_json = await read_record_json(binding, "users", user["id"])
    if user_json is None or json.loads(user_json) != user:
        return _error(409, "ACCOUNT_CHANGED")
    if key_proof is None:
        if session is None:
            return _error(401, "UNAUTHENTICATED")
        _, session_json = await read_session_snapshot(binding, session["id"])
        if session_json is None or {**json.loads(session_json), "id": session["id"]} != session:
            return _error(409, "ACCOUNT_CHANGED")

    async def publish(updated, expected):
        if key_proof is not None:
            return await _publish_key_user(binding, user=updated, expected_json=expected,
                                           proof=key_proof, now=now)
        return await _publish_user(binding, user=updated, expected_json=expected,
                                  session=session, session_json=session_json, now=now)

    from .cloudflare_github_identity_http import _random_urlsafe
    claim = {"id": _random_urlsafe(32), "startedAt": now}
    claimed = {**user, "githubTokenRefresh": claim}
    if not await publish(claimed, user_json):
        return _error(409, "ACCOUNT_CHANGED")

    try:
        bundle = await gateway.refresh(refresh_token)
    except GitHubFailure as failure:
        if failure.request_rejected:
            current, snapshot = await _current_claim(binding, expected=user, claim=claim)
            if current is not None:
                next_user = {key: value for key, value in current.items() if key != "githubTokenRefresh"}
                if failure.code == "GITHUB_REAUTHORIZATION_REQUIRED":
                    next_user.pop("githubRefreshToken", None)
                    next_user.pop("githubRefreshTokenExpiresAt", None)
                await publish(next_user, snapshot)
        # Transport, malformed success and unknown D1 outcomes keep the claim.
        raise
    fields = await sealed_token_fields(bundle, gateway, now)
    if not all(field in fields for field in ("githubAccessTokenExpiresAt", "githubRefreshToken", "githubRefreshTokenExpiresAt")):
        raise GitHubFailure("GITHUB_RESPONSE_INVALID")
    current, snapshot = await _current_claim(binding, expected=user, claim=claim)
    if current is None:
        return _error(409, "ACCOUNT_CHANGED")
    next_user = {**{key: value for key, value in current.items() if key not in TOKEN_FIELDS}, **fields}
    if not await publish(next_user, snapshot):
        return _error(401, "UNAUTHENTICATED")
    return 200, {"ok": True, "refreshed": True}, {"Cache-Control": "no-store"}
