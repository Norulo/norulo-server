"""Public status summaries. No ledger, identity or business-provider access.

Only relative levels and coarse outcomes leave this module. Credentials,
account/script identifiers, exact counts and upstream bodies stay private.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import hashlib
import json
import math
import re
import time

STATUS_TRAFFIC_PATH = "/status/traffic.json"
GRAPHQL_URL = "https://api.cloudflare.com/client/v4/graphql"
MCP_HEALTH_URL = "https://mcp.norulo.com/health"
SERVICES = (("web", "norulo-web"), ("api", "norulo-server-production"), ("mcp", "norulo-connect"))
HOUR, HOURS, CACHE_SECONDS = 3600, 168, 600
MAX_RESPONSE_BYTES = 1024 * 1024
# Serialized public data only; never retain a request, credential or IO promise
# across Worker request contexts. Cache expiry is not extended on a cache hit.
_memo = None


class AnalyticsFailure(Exception):
    def __init__(self, reason, status=None):
        self.reason, self.status = reason, status
        super().__init__(reason)


def iso(at):
    return datetime.fromtimestamp(at, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.timestamp() if parsed.tzinfo is not None else None
    except (ValueError, OverflowError):
        return None


def activity_level(requests, peak):
    if requests <= 0 or peak <= 0:
        return 0
    return min(4, max(1, math.ceil(4 * math.log1p(requests) / math.log1p(peak))))


def error_level(requests, errors):
    return 0 if errors <= 0 else 2 if requests <= 0 or errors / requests >= .05 else 1


def traffic_window(now):
    end = math.floor(now / HOUR) * HOUR + HOUR
    return end - HOURS * HOUR, end


def invocations_query():
    declarations = ", ".join(f"$since{d}: Time!, $until{d}: Time!" for d in range(7))
    fields = "\n".join(f"""d{d}: workersInvocationsAdaptive(limit: 1000,
        filter: {{scriptName_in: $scripts, datetime_geq: $since{d}, datetime_lt: $until{d}}}) {{
          sum {{requests errors}} dimensions {{scriptName datetimeHour}}
        }}""" for d in range(7))
    return f"""query StatusTraffic($accountTag: string!, $scripts: [string!], {declarations}) {{
      viewer {{accounts(filter: {{accountTag: $accountTag}}) {{{fields}}}}}
    }}"""


SCHEDULER_QUERY = """query StatusScheduler($accountTag: string!, $script: string!, $since: Time!) {
  viewer {accounts(filter: {accountTag: $accountTag}) {
    workersInvocationsScheduled(limit: 1, orderBy: [datetime_DESC],
      filter: {scriptName: $script, datetime_geq: $since}) {datetime status}
  }}
}"""


def _count(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        return 0
    return max(0, value)


def summarize_invocations(account, start):
    requests = {script: [0] * HOURS for _, script in SERVICES}
    errors = {script: [0] * HOURS for _, script in SERVICES}
    for day in range(7):
        rows = account.get(f"d{day}")
        # Missing aliases must not turn an incomplete query into healthy zeroes.
        if not isinstance(rows, list) or len(rows) > 1000:
            raise AnalyticsFailure("response_invalid")
        for row in rows:
            if not isinstance(row, dict):
                continue
            dimensions, totals = row.get("dimensions"), row.get("sum")
            if not isinstance(dimensions, dict) or not isinstance(totals, dict):
                continue
            script, at = dimensions.get("scriptName"), timestamp(dimensions.get("datetimeHour"))
            if not isinstance(script, str) or script not in requests or at is None:
                continue
            index = math.floor((at - start) / HOUR)
            if not 0 <= index < HOURS:
                continue
            requests[script][index] += _count(totals.get("requests"))
            errors[script][index] += _count(totals.get("errors"))
    return [{"id": name,
             "levels": [activity_level(value, max(requests[script])) for value in requests[script]],
             "errors": [error_level(value, errors[script][i]) for i, value in enumerate(requests[script])]}
            for name, script in SERVICES]


async def graphql(transport, token, query, variables):
    payload = await transport.json(GRAPHQL_URL, token=token, body={"query": query, "variables": variables})
    if not isinstance(payload, dict):
        raise AnalyticsFailure("response_invalid")
    if payload.get("errors"):
        raise AnalyticsFailure("query_rejected")
    try:
        account = payload["data"]["viewer"]["accounts"][0]
        if not isinstance(account, dict):
            raise ValueError()
    except (KeyError, TypeError, IndexError, ValueError):
        raise AnalyticsFailure("account_missing") from None
    return account


async def last_scheduled_run(transport, token, account, now):
    result = await graphql(transport, token, SCHEDULER_QUERY,
        {"accountTag": account, "script": SERVICES[1][1], "since": iso(now - 3 * 24 * HOUR)})
    rows = result.get("workersInvocationsScheduled")
    if not isinstance(rows, list):
        raise AnalyticsFailure("response_invalid")
    if not rows:
        return None
    run = rows[0]
    at = timestamp(run.get("datetime")) if isinstance(run, dict) else None
    if at is None:
        return None
    status = str(run.get("status", "")).lower()
    if not status:
        return None
    return {"lastRunAt": iso(at), "outcome": "success" if status == "success" else "failure"}


async def mcp_reachable(transport):
    try:
        payload = await transport.json(MCP_HEALTH_URL)
        return isinstance(payload, dict) and payload.get("ok") is True
    except Exception:
        return False


def configuration(env):
    token = str(getattr(env, "NORULO_CF_ANALYTICS_TOKEN", "") or "").strip()
    account = str(getattr(env, "NORULO_CF_ACCOUNT_ID", "") or "").strip().lower()
    if not token or re.fullmatch(r"[0-9a-f]{32}", account) is None:
        return "", ""
    return token, account


def diagnostic(operation, error):
    event = {"code": "NORULO_STATUS_ANALYTICS_FAILED", "operation": operation,
             "reason": error.reason if isinstance(error, AnalyticsFailure) else "unavailable"}
    if isinstance(error, AnalyticsFailure) and error.status is not None:
        event["providerStatus"] = error.status
    print(json.dumps(event))


async def build_status_traffic(env, transport, now):
    start, end = traffic_window(now)
    base = {"version": 1, "generatedAt": iso(now), "windowStart": iso(start),
            "windowEnd": iso(end), "bucketMinutes": 60, "timezone": "UTC"}
    token, account = configuration(env)
    if not token:
        return {**base, "available": False, "reason": "not_configured", "services": [],
                "scheduler": None, "mcp": {"reachable": await mcp_reachable(transport)}}
    variables = {"accountTag": account, "scripts": [script for _, script in SERVICES]}
    for day in range(7):
        variables[f"since{day}"] = iso(start + day * 24 * HOUR)
        variables[f"until{day}"] = iso(start + (day + 1) * 24 * HOUR)

    async def traffic():
        return summarize_invocations(await graphql(transport, token, invocations_query(), variables), start)

    services, scheduler, reachable = await asyncio.gather(traffic(),
        last_scheduled_run(transport, token, account, now), mcp_reachable(transport), return_exceptions=True)
    for operation, result in (("traffic", services), ("scheduler", scheduler)):
        if isinstance(result, Exception):
            diagnostic(operation, result)
    failed = isinstance(services, Exception)
    return {**base, "available": not failed, **({"reason": "unavailable"} if failed else {}),
            "services": [] if failed else services,
            "scheduler": None if isinstance(scheduler, Exception) else scheduler,
            "mcp": {"reachable": reachable is True}}


class WorkerStatusIO:
    """Request-scoped JS interop. Fixed URLs, bounded bodies and no redirects."""
    async def json(self, url, *, token="", body=None):
        from js import fetch, Object, AbortSignal
        from pyodide.ffi import to_js
        if url not in {GRAPHQL_URL, MCP_HEALTH_URL}:
            raise AnalyticsFailure("url_invalid")
        headers = {"Accept": "application/json"}
        options = {"method": "GET", "headers": headers, "redirect": "manual",
                   "signal": AbortSignal.timeout(5000)}
        if body is not None:
            headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
            options.update(method="POST", body=json.dumps(body))
        reader = response = None
        try:
            response = await fetch(url, to_js(options, dict_converter=Object.fromEntries))
            if not response.ok:
                raise AnalyticsFailure("http_failure", int(response.status))
            reader = response.body.getReader()
            chunks, size = [], 0
            while True:
                part = await reader.read()
                if part.done:
                    break
                size += int(part.value.byteLength)
                if size > MAX_RESPONSE_BYTES:
                    raise AnalyticsFailure("response_invalid")
                chunks.append(bytes(part.value.to_py()))
            payload = json.loads(b"".join(chunks))
            if not isinstance(payload, dict):
                raise AnalyticsFailure("response_invalid")
            return payload
        except AnalyticsFailure:
            raise
        except Exception:
            raise AnalyticsFailure("unavailable") from None
        finally:
            if reader is not None:
                try:
                    await reader.cancel()
                except Exception:
                    pass
            elif response is not None and response.body is not None:
                try:
                    await response.body.cancel()
                except Exception:
                    pass

    async def match(self, key):
        from js import caches
        response = await caches.default.match(key)
        if not response:
            return None
        return str(await response.text()), float(response.headers.get("X-Norulo-Status-Expires"))

    async def put(self, key, body, expires, ttl):
        from js import caches, Response, Object
        from pyodide.ffi import to_js
        headers = {"Cache-Control": f"public, max-age={ttl}", "Content-Type": "application/json",
                   "X-Norulo-Status-Expires": str(expires)}
        await caches.default.put(key, Response.new(body, to_js({"headers": headers}, dict_converter=Object.fromEntries)))


async def status_traffic(method, env, *, io=None, now=None):
    """Return status/body/headers independently of database and product flags."""
    global _memo
    headers = {"Content-Type": "application/json; charset=utf-8", "X-Content-Type-Options": "nosniff"}
    if method not in {"GET", "HEAD"}:
        return 405, json.dumps({"error": {"code": "METHOD_NOT_ALLOWED"}}), {
            **headers, "Cache-Control": "no-store", "Allow": "GET, HEAD"}
    now = time.time() if now is None else now
    io = WorkerStatusIO() if io is None else io
    token, account = configuration(env)
    scope = hashlib.sha256((str(getattr(env, "NORULO_MODE", "")) + ":" + account + ":" + token).encode()).hexdigest()
    key = "https://api.norulo.com/__status/traffic-server-v1/" + scope
    cached = _memo[1:] if _memo is not None and _memo[0] == key and _memo[2] > now else None
    if cached is None:
        try:
            cached = await io.match(key)
        except Exception:
            cached = None
    if cached is None or cached[1] <= now:
        payload = await build_status_traffic(env, io, now)
        body = json.dumps(payload, separators=(",", ":"), allow_nan=False)
        ttl = CACHE_SECONDS if payload["available"] else 60
        expires = now + ttl
        cached = body, expires
        try:
            await io.put(key, body, expires, ttl)
        except Exception:
            pass
    body, expires = cached
    _memo = key, body, expires
    headers["Cache-Control"] = f"public, max-age={min(300, max(0, math.floor(expires - now)))}"
    return 200, None if method == "HEAD" else body, headers
