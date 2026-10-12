"""Admission regressions for the real refresh CAS and typed user envelope."""
import asyncio
from types import SimpleNamespace

import pytest

from norulo_server.cloudflare_github_refresh import _publish_user
from norulo_server.cloudflare_preview_budget import _input_bound, _tokens, _where_keys, sql_write_bound
from norulo_server.cloudflare_preview_schema import INDEX_COUNTS
from norulo_server.cloudflare_state_records import USER_RECORD_BYTES, encode_record
from norulo_server.cloudflare_session_adapter import session_storage_id


class Capture:
    def prepare(self, sql):
        class Statement:
            def bind(self, *params):
                self.sql, self.params = sql, params
                return self

        return Statement()

    async def batch(self, statements):
        self.statements = statements
        return [SimpleNamespace(results=[{"name": "record:users:owner"}])]


def captured_refresh_cas(session_kind='legacy'):
    binding = Capture()
    existing = {"id": "owner", "githubId": "81", "githubAccessToken": "gcm1:synthetic-access",
        "githubRefreshToken": "gcm1:synthetic-refresh", "githubAccessTokenExpiresAt": 90,
        "githubRefreshTokenExpiresAt": 200,
        "githubRepositoryAccess": {"repositoryItems": [
            {"id": str(index), "fullName": "synthetic/repository-" + str(index)} for index in range(1000)]}}
    token = 'ses-v2.synthetic-refresh-session' if session_kind == 'hashed' else 'session'
    identity = session_storage_id(token) if session_kind == 'hashed' else token
    session = {"id": token, "userId": "owner", "expiresAt": 300}
    stored_session = {**session, 'id': identity}
    if session_kind == 'legacy_idless':
        stored_session.pop('id')
    assert asyncio.run(_publish_user(binding, user={**existing,
        "githubTokenRefresh": {"id": "synthetic-claim", "startedAt": 100}},
        expected_json=encode_record("users", "owner", existing), session=session,
        session_json=encode_record("sessions", identity, stored_session), now=100))
    return binding.statements[0]


def test_refresh_claim_cas_accepts_retained_large_user_and_independent_session_snapshot():
    statement = captured_refresh_cas()
    assert len(statement.params[0].encode()) > 8192
    assert len(statement.params[0].encode()) < USER_RECORD_BYTES
    assert _input_bound(statement.params, sql=statement.sql) == 1000
    assert sql_write_bound(statement.sql) == 1 + 2 * INDEX_COUNTS["app_state"]
    assert {"name", "payload"} <= _where_keys(_tokens(statement.sql))
    assert "RETURNING name" in statement.sql and len(statement.params) == 8


def test_refresh_budget_keeps_exact_typed_user_target_and_scalar_sql_fences():
    statement = captured_refresh_cas()
    params = list(statement.params)
    params[2] = "record:users:another-owner"
    with pytest.raises(ValueError, match="typed record"):
        _input_bound(params, sql=statement.sql)
    with pytest.raises(ValueError, match="unique key"):
        sql_write_bound("UPDATE app_state SET payload=? WHERE payload=? RETURNING name")
    with pytest.raises(ValueError, match="disjunctive"):
        sql_write_bound("UPDATE app_state SET payload=? WHERE name=? OR name=? RETURNING name")


@pytest.mark.parametrize('session_kind', ['hashed', 'legacy_idless'])
def test_refresh_cas_resolves_validated_storage_identity_without_extra_queries(session_kind):
    # Capture deliberately implements only batch(), so a redundant .first()
    # read fails this finite-budget regression before SQL can be admitted.
    statement = captured_refresh_cas(session_kind)
    if session_kind == 'hashed':
        assert statement.params[4] == 'record:sessions:' + session_storage_id('ses-v2.synthetic-refresh-session')
        assert all('ses-v2.synthetic-refresh-session' not in str(value) for value in statement.params)
    else:
        assert statement.params[4] == 'record:sessions:session'
    assert len(statement.params) == 8 and sql_write_bound(statement.sql) == 1 + 2 * INDEX_COUNTS['app_state']
