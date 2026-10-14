"""Production Workers rate-limit admission before any D1 or provider work."""
from __future__ import annotations

import hashlib

from .cloudflare_email_admission import email_ip_subject
from .cloudflare_validation_budget import _field


# Every production request passes all applicable windows before routing. The
# numeric limits live in the reviewed Wrangler ratelimits configuration; each
# binding supports only 10- or 60-second periods. A short burst window plus a
# sustained minute window approximates a token bucket without a total-volume
# cap. Ledger-owner write allowances and email/GitHub admission still apply.
API_RATE_LIMITS = (
    ("API_IP_BURST_RATE_LIMIT", "ip", 10),
    ("API_IP_RATE_LIMIT", "ip", 60),
    ("API_CREDENTIAL_BURST_RATE_LIMIT", "credential", 10),
    ("API_CREDENTIAL_RATE_LIMIT", "credential", 60),
)


def _options(key):
    try:
        from js import Object
        from pyodide.ffi import to_js
    except ModuleNotFoundError:
        return {"key": key}
    return to_js({"key": key}, dict_converter=Object.fromEntries)


async def _admitted(binding, key):
    """Return only a definite native verdict; anything else is unavailable."""
    success = _field(await binding.limit(_options(key)), "success", None)
    if success is True or success is False:
        return success
    raise RuntimeError("RATE_ADMISSION_UNKNOWN")


def _presented_credential(get):
    # The first credential the principal would consider, without D1. Varying
    # extra credentials cannot escape the per-network windows checked first.
    parts = str(get("authorization") or "").split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    header_key = str(get("x-norulo-api-key") or "").strip()
    if header_key:
        return header_key
    for piece in str(get("cookie") or "").split(";"):
        name, separator, value = piece.partition("=")
        if separator and name.strip() == "nr_session" and value.strip().strip('"'):
            return value.strip().strip('"')
    return ""


async def api_admission(env, request):
    """Bound request frequency per client network and presented credential.

    Workers rate limits are local to a Cloudflare location and approximate, so
    this protects D1/provider capacity from high-frequency clients without
    claiming a strict global ceiling. Keys are SHA-256 digests; no raw address
    or credential reaches the binding. Missing bindings or uncertain native
    outcomes fail closed. Rejected/unknown admissions are never retried.
    """
    if getattr(env, "NORULO_MODE", "") != "production":
        return None
    headers = {"Cache-Control": "no-store"}
    bindings = [(getattr(env, name, None), subject, period) for name, subject, period in API_RATE_LIMITS]
    if any(binding is None for binding, _, _ in bindings):
        return 503, {"error": {"code": "API_ADMISSION_UNAVAILABLE"}}, headers
    ingress = getattr(request, "headers", None)
    get = ingress.get if ingress is not None else (lambda _: None)
    subjects = {"ip": hashlib.sha256(("norulo-api-ip:" + email_ip_subject(
        get("cf-connecting-ip"))).encode("ascii")).hexdigest()}
    credential = _presented_credential(get)
    if credential:
        subjects["credential"] = hashlib.sha256(("norulo-api-credential:" + credential).encode(
            "utf-8", errors="replace")).hexdigest()
    try:
        for binding, subject, period in bindings:
            if subject in subjects and not await _admitted(binding, subjects[subject]):
                return 429, {"error": {"code": "API_RATE_LIMIT",
                    "message": "Too many requests. Please slow down and retry after the Retry-After interval."}}, {
                    **headers, "Retry-After": str(period)}
    except Exception:
        return 503, {"error": {"code": "API_ADMISSION_UNAVAILABLE"}}, headers
    return None


async def authorize_admission(env, request):
    """Fail closed on missing bindings or uncertain native outcomes.

    Workers rate limits are local to a Cloudflare location and best effort.
    This bounds ordinary abuse before D1, without claiming an account-wide
    strict cost ceiling. Rejected/unknown admissions are never retried.
    """
    if getattr(env, "NORULO_MODE", "") != "production":
        return None
    headers = {"Cache-Control": "no-store"}
    prefix_binding = getattr(env, "AUTH_RATE_LIMIT", None)
    if prefix_binding is None:
        return 503, {"error": {"code": "AUTH_ADMISSION_UNAVAILABLE"}}, headers
    ingress = getattr(request, "headers", None)
    address = ingress.get("cf-connecting-ip") if ingress is not None else None
    prefix = hashlib.sha256(("norulo-github-ip:" + email_ip_subject(address)).encode("ascii")).hexdigest()
    try:
        if not await _admitted(prefix_binding, prefix):
            return 429, {"error": {"code": "AUTH_RATE_LIMIT"}}, {**headers, "Retry-After": "60"}
    except Exception:
        return 503, {"error": {"code": "AUTH_ADMISSION_UNAVAILABLE"}}, headers
    return None
