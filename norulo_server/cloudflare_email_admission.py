"""Binding-only production OTP admission, independent of preview and D1."""
from __future__ import annotations

from .cloudflare_preview_rate import EmailRateLimit
from .cloudflare_validation_budget import _field


EMAIL_ADMISSION_SCOPE = "norulo-production-email-admission-v1"


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
