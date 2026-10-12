"""Bounded API-key input and pages retain session and ledger visibility fences."""
import asyncio
import base64
import json

import pytest

from norulo_server.cloudflare_http_contract import handle_http_request
from ledger_d1_fixture import D1ShapedSQLite, seed, seed_auth


def request(binding, now, *, method="GET", body=b"", params=None, length=None):
    async def read_body():
        return body
    headers = {"Cookie": "nr_session=session-local", "Origin": "https://app.example"}
    if length is not None:
        headers["Content-Length"] = length
    return asyncio.run(handle_http_request(method=method, path="/api-keys",
        headers=headers, read_body=read_body, binding=binding, creem_secret="",
        configured_products={}, now=now, params=params,
        trusted_origins={"https://app.example"}))


@pytest.mark.parametrize("name", ["x" * 121, "bad\nname", "bad\rname", None, 10])
def test_invalid_name_does_not_authorize_or_write(tmp_path, name):
    fixture, _, _ = seed(tmp_path / "domain.db")
    seed_auth(fixture)
    binding = D1ShapedSQLite(fixture.store)
    status, payload = request(binding, fixture.now, method="POST", body=json.dumps({"name": name}).encode())
    assert (status, payload["error"]["code"]) == (400, "INVALID_REQUEST")
    assert binding.batch_count == 0


@pytest.mark.parametrize("name", ["边" * 120, "  "])
def test_absent_content_length_accepts_bounded_utf8_name(tmp_path, name):
    fixture, _, _ = seed(tmp_path / "domain.db")
    seed_auth(fixture)
    binding = D1ShapedSQLite(fixture.store)
    status, payload = request(binding, fixture.now, method="POST",
        body=json.dumps({"name": name}, ensure_ascii=False).encode("utf-8"))
    assert status == 201 and payload["name"] == (name.strip() or "API key")


@pytest.mark.parametrize("length,body,status", [
    (None, b" " * 8193, 413), ("8193", b"{}", 413),
    ("1", b"{}", 400), ("٣", b"{}", 400), ("x" * 6000, b"{}", 400),
])
def test_optional_length_retains_actual_and_declared_body_bounds(tmp_path, length, body, status):
    fixture, _, _ = seed(tmp_path / "domain.db")
    seed_auth(fixture)
    binding = D1ShapedSQLite(fixture.store)
    assert request(binding, fixture.now, method="POST", body=body, length=length)[0] == status
    assert binding.batch_count == 0


def test_pages_cover_equal_timestamp_keys_without_duplicates_or_usage_writes(tmp_path):
    fixture, _, _ = seed(tmp_path / "domain.db")
    seed_auth(fixture)
    with fixture.store._immediate() as db:
        db.executemany("""INSERT INTO api_keys VALUES(?,?,?,?,?,?,?,?,?,?,?)""", [
            (f"ak_{index:03}", "owner", "Synthetic", "nrk_local", f"hash_{index}",
             '["profile:read"]', None, '{}', fixture.now, None, None)
            for index in range(205)])
        expected = [row[0] for row in db.execute("""SELECT id FROM api_keys WHERE user_id='owner'
            AND revoked_at IS NULL ORDER BY created_at DESC,id DESC""")]
    binding = D1ShapedSQLite(fixture.store)
    received, cursor = [], None
    for _ in range(3):
        status, page = request(binding, fixture.now, params={"cursor": cursor} if cursor else {})
        assert status == 200 and len(page["items"]) <= 100
        assert page["apiKeys"] == page["items"]
        received.extend(row["id"] for row in page["items"])
        cursor = page["nextCursor"]
    assert cursor is None and received == expected
    assert len(set(received)) == len(received)
    with fixture.store._immediate() as db:
        assert db.execute("SELECT COUNT(*) FROM api_keys WHERE last_used_at IS NOT NULL").fetchone()[0] == 0


def test_workspace_filter_applies_before_limit_and_revoked_keys_stay_hidden(tmp_path):
    fixture, _, _ = seed(tmp_path / "domain.db")
    seed_auth(fixture)
    with fixture.store._immediate() as db:
        db.executemany("INSERT INTO api_keys VALUES(?,?,?,?,?,?,?,?,?,?,?)", [
            (identifier, "owner", "Synthetic", "nrk_local", identifier, '["profile:read"]',
             None, restrictions, fixture.now + offset, None, revoked)
            for identifier, restrictions, offset, revoked in (
                ("ak_other", '{"workspaceId":"other"}', 3, None),
                ("ak_revoked", '{}', 2, fixture.now), ("ak_personal", '{}', 1, None))])
    binding = D1ShapedSQLite(fixture.store)
    status, page = request(binding, fixture.now,
        params={"workspaceId": "owner", "limit": "1"})
    assert status == 200 and [row["id"] for row in page["items"]] == ["ak_personal"]
    status, page = request(binding, fixture.now, params={
        "workspaceId": "owner", "limit": "1", "cursor": page["nextCursor"]})
    assert status == 200 and [row["id"] for row in page["items"]] == ["key-local"]
    assert page["nextCursor"] is None


@pytest.mark.parametrize("params", [
    {"limit": "0"}, {"limit": "101"}, {"limit": "٣"}, {"limit": ["1", "2"]},
    {"cursor": "?"}, {"cursor": "a" * 257},
    {"cursor": base64.urlsafe_b64encode(b"9007199254740992|ak_x").decode().rstrip("=")},
    {"cursor": ["abc", "def"]},
])
def test_invalid_pagination_rejected_before_auth(tmp_path, params):
    fixture, _, _ = seed(tmp_path / "domain.db")
    binding = D1ShapedSQLite(fixture.store)
    status, payload = request(binding, fixture.now, params=params)
    assert (status, payload["error"]["code"]) == (422, "INVALID_INPUT")
    assert binding.batch_count == 0
