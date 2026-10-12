"""Production GitHub authorization admission before any D1 state write."""
from __future__ import annotations

import hashlib

from .cloudflare_email_admission import email_ip_subject
from .cloudflare_validation_budget import _field


def _options(key):
    try:
        from js import Object
        from pyodide.ffi import to_js
    except ModuleNotFoundError:
        return {"key": key}
    return to_js({"key": key}, dict_converter=Object.fromEntries)


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
        result = await prefix_binding.limit(_options(prefix))
        success = _field(result, "success", None)
        if success is False:
            return 429, {"error": {"code": "AUTH_RATE_LIMIT"}}, {**headers, "Retry-After": "60"}
        if success is not True:
            raise RuntimeError("AUTH_ADMISSION_UNAVAILABLE")
    except Exception:
        return 503, {"error": {"code": "AUTH_ADMISSION_UNAVAILABLE"}}, headers
    return None
