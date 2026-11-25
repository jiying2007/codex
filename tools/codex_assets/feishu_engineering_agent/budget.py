"""Read-only, provider-backed budget admission. No model calls in this module."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import json
import re
import uuid
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class BudgetError(ValueError):
    pass


_SPEND_PAGE_SIZE = 100
_SPEND_MAX_PAGES = 5
_REQUEST_SCOPE = "observed gateway requests; not a complete task bill or final settlement"


def _amount(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise BudgetError("invalid amount")
    try:
        amount = Decimal(str(value))
    except InvalidOperation:
        raise BudgetError("invalid amount") from None
    if not amount.is_finite() or amount < 0:
        raise BudgetError("invalid amount")
    return amount


def _policy(config):
    # A local timeout, token count or declared billing source is not a monetary limit.
    if (config.agent_budget_backend != "litellm"
            or config.agent_billing_source != "external_gateway"
            or not config.agent_openai_api_key
            or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", config.agent_budget_key_alias)
            or not re.fullmatch(r"[A-Za-z0-9_./:-]{1,128}", config.agent_model)):
        raise BudgetError("verified gateway policy required")
    url = config.agent_openai_base_url.rstrip("/")
    try:
        parsed = urlsplit(url)
        valid = (parsed.scheme == "https" or
                 (parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1", "::1")))
        if (not valid or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or parsed.path != "/v1"
                or parsed.hostname.lower() == "api.openai.com"):
            raise BudgetError("invalid gateway URL")
        _ = parsed.port
    except ValueError:
        raise BudgetError("invalid gateway URL") from None
    limit = _amount(config.agent_budget_max_usd)
    if limit <= 0:
        raise BudgetError("positive approved budget required")
    return url, limit


def provider_overrides(config):
    url, _ = _policy(config)
    # Bind the actual Codex model route to the same gateway and dedicated key.
    provider = ('{name="Feishu dedicated gateway",base_url=' + json.dumps(url)
                + ',env_key="OPENAI_API_KEY",wire_api="responses",'
                  'requires_openai_auth=false,supports_websockets=false}')
    return ["-c", 'model_provider="feishu_agent_gateway"',
            "-c", "model_providers.feishu_agent_gateway=" + provider,
            "-c", "model=" + json.dumps(config.agent_model)]


def _session_id(value):
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        raise BudgetError("invalid task accounting session") from None
    if str(parsed) != value or parsed.version != 4:
        raise BudgetError("invalid task accounting session")
    return value


def provider_session_overrides(session_id):
    # Codex's provider headers are copied into every HTTP Responses request.
    # LiteLLM gives this explicit header precedence over native Codex thread IDs.
    # It is an accounting correlation, never a budget grant or a native thread ID.
    value = _session_id(session_id)
    return ["-c", 'model_providers.feishu_agent_gateway.http_headers={'
            '"x-litellm-session-id"=' + json.dumps(value) + '}']


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise BudgetError("redirect refused")


def _read_gateway_json(url, path, key):
    # Same gateway origin as the model, same bearer, no query-string credentials,
    # no redirect or environment-proxy forwarding, bounded read and timeout.
    request = Request(url[:-3] + path, headers={
        "Authorization": "Bearer " + key, "Accept": "application/json"})
    try:
        with build_opener(ProxyHandler({}), _NoRedirect()).open(request, timeout=8) as response:
            raw = response.read(262145)
        if len(raw) > 262144:
            raise BudgetError("oversized key info")
        return json.loads(raw, parse_float=Decimal)
    except Exception:
        raise BudgetError("gateway accounting information unavailable") from None


def read_key_info(url, key):
    return _read_gateway_json(url, "/key/info", key)


def read_spend_page(url, key, session_id, page):
    if type(page) is not int or not 1 <= page <= _SPEND_MAX_PAGES:
        raise BudgetError("invalid spend page")
    query = urlencode({"session_id": _session_id(session_id), "page": page,
                       "page_size": _SPEND_PAGE_SIZE, "sort_by": "startTime",
                       "sort_order": "asc"})
    # No raw or hashed credential in URLs. The gateway must scope this bearer
    # to its own key; every returned row is checked again below.
    return _read_gateway_json(url, "/spend/logs/v2?" + query, key)


def validate_observation_binding(before, after):
    if not isinstance(before, dict) or not isinstance(after, dict):
        raise BudgetError("missing budget observation")
    _session_id(before.get("session_id"))
    for field in ("backend", "gateway", "model", "key_alias", "key_fingerprint"):
        if not before.get(field) or before[field] != after.get(field):
            raise BudgetError("budget observation identity changed")
    for field in ("approved_usd", "provider_cap_usd"):
        if _amount(before.get(field)) != _amount(after.get(field)):
            raise BudgetError("budget observation policy changed")
    if _amount(after.get("provider_cumulative_spend_usd")) < _amount(
            before.get("provider_cumulative_spend_usd")):
        raise BudgetError("provider cumulative spend moved backwards")


def observe_requests(config, session_id):
    """Read a bounded request snapshot; absence is unknown, never zero cost.

    LiteLLM /spend/logs/v2 uses a partial session filter. Exact session, key and
    routed model are therefore mandatory on every row. A complete page set is
    only a snapshot: there is no final-billing barrier in this API.
    """
    url, _ = _policy(config)
    session_id = _session_id(session_id)
    fingerprint = hashlib.sha256(config.agent_openai_api_key.encode("utf-8")).hexdigest()
    rows = []
    seen = set()
    total = None
    pages = None
    for page in range(1, _SPEND_MAX_PAGES + 1):
        payload = read_spend_page(url, config.agent_openai_api_key, session_id, page)
        if (not isinstance(payload, dict)
                or not isinstance(payload.get("data"), list)
                or any(type(payload.get(name)) is not int
                       for name in ("total", "page", "page_size", "total_pages"))
                or payload.get("total_is_capped") is not False
                or payload["page"] != page or payload["page_size"] != _SPEND_PAGE_SIZE
                or not 0 <= payload["total"] <= _SPEND_PAGE_SIZE * _SPEND_MAX_PAGES
                or payload["total_pages"] != (payload["total"] + _SPEND_PAGE_SIZE - 1) // _SPEND_PAGE_SIZE):
            raise BudgetError("incomplete gateway request pages")
        if total is None:
            total, pages = payload["total"], payload["total_pages"]
        if (payload["total"] != total or payload["total_pages"] != pages
                or len(payload["data"]) != min(_SPEND_PAGE_SIZE, max(total - len(rows), 0))):
            raise BudgetError("gateway request pages changed or were truncated")
        for item in payload["data"]:
            if (not isinstance(item, dict) or item.get("session_id") != session_id
                    or item.get("api_key") != fingerprint
                    or item.get("model_group") != config.agent_model
                    or item.get("status") not in ("success", "failure")
                    or any(not isinstance(item.get(field), str)
                           or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/@+-]{0,255}", item[field])
                           for field in ("request_id", "model"))):
                raise BudgetError("gateway request identity not verified")
            request_id = item["request_id"]
            if request_id in seen:
                raise BudgetError("duplicate gateway request identity")
            spend = _amount(item.get("spend"))
            if len(str(spend)) > 128 or not -128 <= spend.as_tuple().exponent <= 128:
                raise BudgetError("unbounded gateway request amount")
            seen.add(request_id)
            rows.append({"request_id": request_id, "model_group": item["model_group"],
                         "model": item["model"], "status": item["status"],
                         "spend_usd": str(spend)})
        if page >= pages:
            break
    if len(rows) != total:
        raise BudgetError("incomplete gateway request snapshot")
    result = {"session_id": session_id, "settlement": "pending",
              "request_observation": "observed" if rows else "pending",
              "observed_request_cost_usd": None,
              "request_count": len(rows), "request_scope": _REQUEST_SCOPE}
    if rows:
        rows.sort(key=lambda row: row["request_id"])
        # Bounded decimal inputs need no binary float rounding and cannot
        # exhaust this precision even across the full permitted page set.
        with localcontext() as context:
            context.prec = 512
            amount = sum((Decimal(row["spend_usd"]) for row in rows), Decimal(0))
        result.update({"observed_request_cost_usd": str(amount), "requests": rows,
                       "request_evidence_sha256": hashlib.sha256(json.dumps(
                           rows, sort_keys=True, separators=(",", ":")
                       ).encode("utf-8")).hexdigest()})
    return result


def observe_budget(config, phase):
    if phase not in ("before", "after"):
        raise BudgetError("invalid observation phase")
    url, approved = _policy(config)
    payload = read_key_info(url, config.agent_openai_api_key)
    info = payload.get("info") if isinstance(payload, dict) else None
    fingerprint = hashlib.sha256(config.agent_openai_api_key.encode("utf-8")).hexdigest()
    # LiteLLM's self lookup returns the authenticated key (normally its hash).
    # Require explicit evidence: absent fields and permissive model groups do
    # not establish this adapter's dedicated, non-resetting key policy.
    if (not isinstance(info, dict)
            or payload.get("key") not in (config.agent_openai_api_key, fingerprint)
            or info.get("key_alias") != config.agent_budget_key_alias
            or info.get("blocked") is not False
            or "budget_duration" not in info or info["budget_duration"] is not None
            or ("status" in info and info["status"] != "active")):
        raise BudgetError("key identity or non-resetting budget not verified")
    models = info.get("models")
    if (not isinstance(models, list) or not models
            or any(not isinstance(model, str) for model in models)
            or config.agent_model not in models):
        raise BudgetError("dedicated model access not verified")
    expires = info.get("expires")
    if expires is not None:
        try:
            if not isinstance(expires, str):
                raise ValueError("invalid expiry")
            expiry = datetime.fromisoformat(expires.replace("Z", "+00:00"))
            if expiry.tzinfo is None or expiry <= datetime.now(timezone.utc):
                raise ValueError("expired key")
        except ValueError:
            raise BudgetError("key expiry not verified") from None
    cap = _amount(info.get("max_budget"))
    spend = _amount(info.get("spend"))
    if cap <= 0 or cap > approved or (phase == "before" and spend >= cap):
        raise BudgetError("budget exhausted or exceeds approved limit")
    return {
        "backend": "litellm", "gateway": url, "model": config.agent_model,
        "key_alias": config.agent_budget_key_alias,
        "key_fingerprint": fingerprint,
        "approved_usd": str(approved), "provider_cap_usd": str(cap),
        "provider_cumulative_spend_usd": str(spend),
        "exhausted": spend >= cap,
        "scope": "provider cumulative key spend; not per-task final settlement",
    }
