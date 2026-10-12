"""Trusted exact-key session commands over persisted account authority."""
from __future__ import annotations
import hashlib
from typing import Any
from .cloudflare_state_records import (
    record_name, read_record_json, decode_record, encode_record, expired_record_commands, changed_guard,
)
from .cloudflare_d1_batch import execute_d1_batch

HASHED_SESSION_PREFIX = 'ses-v2.'


def session_storage_id(token: str) -> str:
    """A database fingerprint cannot itself be presented as a credential."""
    record_name('sessions', token)
    if token.startswith('sesh-'):
        raise ValueError('invalid session credential')
    return 'sesh-' + hashlib.sha256(token.encode('utf-8')).hexdigest()


def session_record_ids(token: str) -> tuple[str, ...]:
    """Prefer hashed new records; retain read-only compatibility until expiry."""
    identity = session_storage_id(token)
    # The dot never occurred in the old URL-safe random credential format.
    # New session SQL therefore never carries the bearer as a fallback key.
    return (identity,) if token.startswith(HASHED_SESSION_PREFIX) else (identity, token)


async def read_session_snapshot(binding: Any, token: str) -> tuple[str, str | None]:
    for identity in session_record_ids(token):
        snapshot = await read_record_json(binding, 'sessions', identity)
        if snapshot is not None:
            return identity, snapshot
    return session_storage_id(token), None


async def read_session(binding: Any, token: str) -> dict | None:
    identity, snapshot = await read_session_snapshot(binding, token)
    if snapshot is None:
        return None
    return {**decode_record('sessions', identity, snapshot), 'id': token}


def session_binding_matches(expected: object, token: str) -> bool:
    """Pending pre-cutover links may retain their original session identity."""
    return expected in session_record_ids(token)


class D1SessionTransactions:
    def __init__(self, binding: Any) -> None:
        self.binding = binding

    async def issue_session(self, *, owner_id: str, session_id: str,
                            now: int, expires_at: int) -> dict:
        if (not isinstance(owner_id, str) or not owner_id
                or not isinstance(session_id, str) or not session_id.startswith('ses-')
                or any(char in session_id for char in '\r\n\x00')
                or type(now) is not int or type(expires_at) is not int
                or not now < expires_at <= now + 30 * 86400):
            raise ValueError('invalid trusted session command')
        user = await read_record_json(self.binding, 'users', owner_id)
        if user is None:
            raise ValueError('UNAUTHENTICATED')
        identity = session_storage_id(session_id)
        # Trusted issuers generate fresh random credentials. Never bind their
        # bearer text into even a collision-check query or native SQL log.
        if await read_record_json(self.binding, 'sessions', identity) is not None:
            raise ValueError('SESSION_ALREADY_EXISTS')
        session = {'id': identity, 'userId': owner_id, 'createdAt': now, 'expiresAt': expires_at}
        name = record_name('sessions', identity)
        cleanup = await expired_record_commands(self.binding, 'sessions', now=now)
        await execute_d1_batch(self.binding, [*cleanup,
            ('''INSERT INTO app_state(name,payload,updated_at)
                SELECT ?,?,? WHERE NOT EXISTS(SELECT 1 FROM app_state WHERE name=?)
                  AND EXISTS(SELECT 1 FROM app_state WHERE name=? AND payload=?)''',
             (name, encode_record('sessions', identity, session), now, name,
              record_name('users', owner_id), user)), changed_guard(),
            ('DELETE FROM d1_command_guard', ())])
        return {**session, 'id': session_id}

    async def revoke_session(self, *, owner_id: str, session_id: str, now: int) -> bool:
        if not isinstance(owner_id, str) or not owner_id or type(now) is not int:
            raise ValueError('invalid session revocation')
        identity, snapshot = await read_session_snapshot(self.binding, session_id)
        if snapshot is None:
            return False
        session = decode_record('sessions', identity, snapshot)
        if session.get('userId') != owner_id:
            return False
        await execute_d1_batch(self.binding, [
            ('DELETE FROM app_state WHERE name=? AND payload=?', (record_name('sessions', identity), snapshot)),
            changed_guard(), ('DELETE FROM d1_command_guard', ())])
        return True
