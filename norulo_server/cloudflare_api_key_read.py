"""Session-only API-key metadata read over one D1 authorization snapshot."""
from __future__ import annotations

import base64
import re
from typing import Any, Mapping

from .api_key_dto_rules import api_key_public_payload
from .cloudflare_principal import (
    PrincipalAuthError, _bearer, _cookie_sessions, _header,
)
from .cloudflare_ledger_auth import ledger_principal


def api_key_page_inputs(params: Mapping[str, object]) -> tuple[int, tuple[int, str] | None]:
    def value(name):
        item = params.get(name, "")
        if isinstance(item, list):
            if len(item) != 1:
                raise ValueError("api key parameter")
            item = item[0]
        if not isinstance(item, str):
            raise ValueError("api key parameter")
        return item

    raw_limit, raw_cursor = value("limit"), value("cursor")
    if raw_limit and (len(raw_limit) > 3 or not raw_limit.isascii() or not raw_limit.isdigit()):
        raise ValueError("api key limit")
    limit = int(raw_limit) if raw_limit else 100
    if not 1 <= limit <= 100:
        raise ValueError("api key limit")
    cursor = None
    if raw_cursor:
        if len(raw_cursor) > 256 or not re.fullmatch(r"[A-Za-z0-9_-]+", raw_cursor):
            raise ValueError("api key cursor")
        try:
            timestamp, identifier = base64.urlsafe_b64decode(
                raw_cursor + "=" * (-len(raw_cursor) % 4)).decode("ascii").split("|", 1)
            if (not re.fullmatch(r"[0-9]{1,16}", timestamp)
                    or not 0 <= int(timestamp) <= 9007199254740991
                    or not re.fullmatch(r"[A-Za-z0-9_-]{1,120}", identifier)):
                raise ValueError("api key cursor")
            cursor = int(timestamp), identifier
        except (ValueError, UnicodeError):
            raise ValueError("api key cursor") from None
    return limit, cursor


def _cursor(row):
    return base64.urlsafe_b64encode(
        (str(row["created_at"]) + "|" + row["id"]).encode("ascii")).decode().rstrip("=")


async def list_api_keys(*, binding: Any, headers: Mapping[str, object],
                        now: int, workspace_id: str | None = None,
                        limit: int = 100, cursor: tuple[int, str] | None = None) -> tuple[int, dict]:
    if (_bearer(headers) or _header(headers, "Authorization")
            or _header(headers, "X-Norulo-Api-Key")
            or not _cookie_sessions(headers)):
        return 401, {"error": {"code": "UNAUTHENTICATED"}}
    if workspace_id is not None:
        if _header(headers, "X-Norulo-Workspace") not in {"", workspace_id}:
            return 422, {"error": {"code": "INVALID_INPUT"}}
        headers = {**headers, "X-Norulo-Workspace": workspace_id}
    selected = _header(headers, "X-Norulo-Workspace")
    try:
        user, _, auth, validate = await ledger_principal(binding=binding,
            headers=headers, scope="profile:read", now=now)
    except PrincipalAuthError as failure:
        return failure.status, {"error": {"code": failure.code}}
    where, values = "user_id=? AND revoked_at IS NULL", [user["_actor"]["id"]]
    if selected:
        # Filter before LIMIT so unrelated ledger keys cannot consume the page.
        where += " AND COALESCE(json_extract(restrictions,'$.workspaceId'),user_id)=?"
        values.append(selected)
    if cursor:
        where += " AND (created_at,id)<(?,?)"
        values.extend(cursor)
    result = await binding.batch([*auth, binding.prepare("""SELECT id,user_id,name,
        key_prefix,scopes,expires_at,restrictions,created_at,last_used_at,revoked_at
        FROM api_keys WHERE """ + where + " ORDER BY created_at DESC,id DESC LIMIT ?")
        .bind(*values, limit + 1)])
    try:
        validate([part.results for part in result[:len(auth)]])
    except PrincipalAuthError as failure:
        return failure.status, {"error": {"code": failure.code}}
    rows = result[-1].results
    items = [api_key_public_payload(row) for row in rows[:limit]]
    return 200, {"items": items, "apiKeys": items,
                 "nextCursor": _cursor(rows[limit - 1]) if len(rows) > limit else None}
