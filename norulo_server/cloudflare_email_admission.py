"""Binding-only production OTP admission, independent of preview and D1."""
from __future__ import annotations

import hashlib
import ipaddress

from .cloudflare_preview_rate import EmailRateLimit
from .cloudflare_validation_budget import _field


EMAIL_ADMISSION_SCOPE = "norulo-production-email-admission-v1"


def email_ip_subject(address):
    """Hash a canonical trusted ingress address, grouping IPv6 hosts by /64.

    Invalid/missing addresses share one conservative bucket; changing an invalid
    header never yields unlimited subjects. IPv4-mapped IPv6 uses the same
    bucket as its IPv4 address. No raw address reaches DO storage or RPC.
    """
    network = "unknown"
    if isinstance(address, str) and len(address) <= 64:
        try:
            parsed = ipaddress.ip_address(address.strip())
            if isinstance(parsed, ipaddress.IPv6Address):
                if parsed.scope_id is not None:
                    raise ValueError("invalid ingress scope")
                if parsed.ipv4_mapped is not None:
                    network = str(parsed.ipv4_mapped)
                else:
                    network = str(ipaddress.IPv6Network((parsed, 64), strict=False))
            else:
                network = str(parsed)
        except ValueError:
            pass
    return hashlib.sha256(("norulo-email-ip:" + network).encode("ascii")).hexdigest()


def production_email_admission_enabled(env):
    return (getattr(env, "NORULO_MODE", "") == "production"
        and str(getattr(env, "NORULO_D1_ACCESS_ENABLED", "0")) == "1"
        and str(getattr(env, "NORULO_EMAIL_AUTH_ENABLED", "0")) == "1")


def validate_admission_subjects(kind, email_subject, ip_subject):
    """Reject malformed binding calls before even initializing DO storage."""
    if (type(kind) is not str or kind not in {"send", "verify"}
            or any(type(value) is not str or len(value) != 64
                   or any(char not in "0123456789abcdef" for char in value)
                   for value in (email_subject, ip_subject))):
        raise ValueError("EMAIL_ADMISSION_INVALID")


def require_email_admission(result):
    """Accept only a definite success or the bounded rate-limit RPC response."""
    ok = _field(result, "ok", None)
    retry_after = _field(result, "retryAfter", None)
    error = _field(result, "error", None)
    if ok is True and retry_after is None and error is None:
        return True
    if (ok is False and error is None and type(retry_after) in {int, float}
            and 1 <= retry_after <= 3600 and int(retry_after) == retry_after):
        raise EmailRateLimit(retry_after)
    # No fallback, refund or retry after an uncertain RPC/storage outcome.
    raise RuntimeError("EMAIL_ADMISSION_UNAVAILABLE")
