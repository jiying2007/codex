"""Read-only, provider-backed budget admission. No model calls in this module."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class BudgetError(ValueError):
    pass


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


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise BudgetError("redirect refused")


def read_key_info(url, key):
    # Same gateway origin as the model, same bearer, no query-string credentials,
    # no redirect or environment-proxy forwarding, bounded read and timeout.
    request = Request(url[:-3] + "/key/info", headers={
        "Authorization": "Bearer " + key, "Accept": "application/json"})
    try:
        with build_opener(ProxyHandler({}), _NoRedirect()).open(request, timeout=8) as response:
            raw = response.read(262145)
        if len(raw) > 262144:
            raise BudgetError("oversized key info")
        return json.loads(raw, parse_float=Decimal)
    except Exception:
        raise BudgetError("gateway key information unavailable") from None


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
