"""Stable errors and bounded recovery advice for the read-only adapters."""

import json
import re


class ReadError(ValueError):
    def __init__(self, kind, message, details=None):
        super().__init__(message)
        self.kind, self.details = kind, details


def recovery(kind):
    advice = {
        "timeout": (True, 1, "retry-same-read"),
        "network_error": (True, 1, "retry-same-read"),
        "service_unavailable": (True, 2, "retry-same-read"),
        "rate_limited": (True, 60, "wait-then-resume"),
        "preview_pending": (True, 5, "wait-then-query-preview"),
        "application_scope_missing": (False, 0, "verify-minimal-app-scope"),
        "access_denied": (False, 0, "verify-app-and-resource-access"),
        "authentication_failed": (False, 0, "verify-managed-bot-authentication"),
        "not_found": (False, 0, "verify-resource-link"),
        "content_mismatch": (False, 0, "start-new-session-for-changed-content"),
        "revision_mismatch": (False, 0, "start-new-session-for-changed-revision"),
        "session_mismatch": (False, 0, "use-matching-resource-or-new-session"),
        "session_busy": (True, 1, "wait-for-current-session-reader"),
        "session_stalled": (False, 0, "inspect-session-and-correct-blocked-window"),
        "content_budget_exceeded": (False, 0, "split-range-or-increase-output-budget"),
        "okr_mapping_unverified": (False, 0, "verify-explicit-okr-user-and-cycle-mapping"),
        "resource_mismatch": (False, 0, "verify-resource-identity-do-not-merge"),
        "snapshot_changed": (False, 0, "restart-stateless-read-for-changed-content"),
        "coverage_limit": (False, 0, "inspect-bounded-okr-selection"),
    }
    retryable, delay, action = advice.get(kind, (False, 0, "inspect-error-and-correct-input"))
    return {"retryable": retryable, "retry_after_seconds": delay, "next_action": action}


def backend_error(error):
    """Project diagnostics, never echo signed URLs or arbitrary server messages."""
    error = error if isinstance(error, dict) else {}
    detail = {key: error[key] for key in ("type", "subtype", "code")
              if isinstance(error.get(key), (str, int)) and not isinstance(error.get(key), bool)}
    for key in ("type", "subtype", "code"):
        if key in detail and not re.fullmatch(r"[A-Za-z0-9_.:-]{1,80}", str(detail[key])):
            detail.pop(key)
    status = error.get("code")
    api = {}
    message = error.get("message", "")
    if isinstance(message, str) and "{" in message:
        try:
            value = json.loads(message[message.index("{"):])
            api = value if isinstance(value, dict) else {}
        except ValueError:
            pass
    if isinstance(api.get("code"), int):
        detail["api_code"] = api["code"]
    label = str(error.get("subtype", "")) + " " + str(error.get("type", ""))
    kind = "backend_error"
    if status in (429, 99991400) or api.get("code") == 99991400 or "rate_limit" in label:
        kind = "rate_limited"
    elif status == 401 or "unauthenticated" in label or "invalid_token" in label:
        kind = "authentication_failed"
    elif status == 403 or "permission_denied" in label or "access_denied" in label:
        kind = "access_denied"
    elif status == 404 or "not_found" in label:
        kind = "not_found"
    elif isinstance(status, int) and 500 <= status <= 599:
        kind = "service_unavailable"
    elif "timeout" in label:
        kind = "timeout"
    elif "transport" in label and status in (None, 0):
        kind = "network_error"
    elif "processing" in label or "not_ready" in label:
        kind = "preview_pending"
    return ReadError(kind, "官方飞书只读请求失败；请按 recovery 建议处理", detail)


def error_payload(error):
    kind = getattr(error, "kind", "invalid_input")
    result = {"kind": kind, "message": str(error), "recovery": recovery(kind)}
    if getattr(error, "details", None) is not None:
        result["details"] = error.details
    return result
