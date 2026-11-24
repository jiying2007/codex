"""No-model regressions for the provider budget boundary."""
from contextlib import contextmanager
from decimal import Decimal
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import unittest
from types import SimpleNamespace
from unittest import mock

from tools.codex_assets.feishu_engineering_agent import budget


@contextmanager
def local_gateway(body, *, status=200, location=None):
    """A local metadata-only fixture; no model endpoint or upstream exists."""
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            calls.append((self.path, self.headers.get("Authorization")))
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            if location is not None:
                self.send_header("Location", location)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1", calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class BudgetTests(unittest.TestCase):
    def config(self, **changes):
        data = dict(agent_budget_backend="litellm", agent_billing_source="external_gateway",
                    agent_openai_api_key="synthetic-key", agent_budget_key_alias="agent",
                    agent_model="model", agent_openai_base_url="https://gateway.example/v1",
                    agent_budget_max_usd="10")
        data.update(changes)
        return SimpleNamespace(**data)

    def key_info(self, **changes):
        config = self.config()
        info = dict(key_alias="agent", max_budget=10, spend=2,
                    blocked=False, budget_duration=None, models=["model"],
                    expires=None, status="active")
        info.update(changes)
        return {"key": hashlib.sha256(config.agent_openai_api_key.encode()).hexdigest(),
                "info": info}

    def test_provider_budget_and_route(self):
        config = self.config()
        with mock.patch.object(budget, "read_key_info",
                               return_value=self.key_info(max_budget=8, spend="2.25")) as read:
            result = budget.observe_budget(config, "before")
        read.assert_called_once_with(config.agent_openai_base_url, config.agent_openai_api_key)
        self.assertEqual("2.25", result["provider_cumulative_spend_usd"])
        self.assertNotIn(config.agent_openai_api_key, str(result))
        args = budget.provider_overrides(config)
        self.assertIn('model_provider="feishu_agent_gateway"', args)
        self.assertNotIn(config.agent_openai_api_key, str(args))

    def test_fail_closed(self):
        for extra in ({"spend": 10}, {"max_budget": 11}, {"max_budget": None},
                      {"spend": float("nan")}, {"spend": -1}, {"spend": True},
                      {"key_alias": "other"}, {"budget_duration": "1d"},
                      {"budget_duration": ""}, {"blocked": True},
                      {"blocked": "false"}, {"blocked": 0}, {"blocked": None},
                      {"models": "model"}, {"models": []}, {"models": ["other"]},
                      {"models": ["model", 1]}, {"status": "expired"},
                      {"expires": "2000-01-01T00:00:00Z"}, {"expires": True},
                      {"expires": "9999-01-01T00:00:00"}):
            with self.subTest(extra=extra):
                with mock.patch.object(budget, "read_key_info", return_value=self.key_info(**extra)):
                    with self.assertRaises(budget.BudgetError):
                        budget.observe_budget(self.config(), "before")
        for field in ("blocked", "budget_duration", "models", "key_alias", "max_budget", "spend"):
            with self.subTest(missing=field):
                payload = self.key_info()
                del payload["info"][field]
                with mock.patch.object(budget, "read_key_info", return_value=payload):
                    with self.assertRaises(budget.BudgetError):
                        budget.observe_budget(self.config(), "before")
        for identity in (None, "unrelated-key", {"unexpected": "object"}):
            with self.subTest(identity=identity):
                payload = self.key_info()
                payload["key"] = identity
                with mock.patch.object(budget, "read_key_info", return_value=payload):
                    with self.assertRaises(budget.BudgetError):
                        budget.observe_budget(self.config(), "before")
        for changes in ({"agent_budget_backend": ""}, {"agent_billing_source": "external_api_key"},
                        {"agent_openai_base_url": "http://gateway.example/v1"},
                        {"agent_openai_base_url": "https://gateway.example/v1?token=x"},
                        {"agent_openai_base_url": "https://user:secret@gateway.example/v1"},
                        {"agent_openai_base_url": "https://api.openai.com/v1"}):
            with self.assertRaises(budget.BudgetError):
                budget.provider_overrides(self.config(**changes))

    def test_after_observation_preserves_exhausted_state(self):
        with mock.patch.object(budget, "read_key_info",
                               return_value=self.key_info(spend=12)):
            self.assertTrue(budget.observe_budget(self.config(), "after")["exhausted"])

    def test_raw_self_identity_and_future_expiry_are_not_persisted(self):
        config = self.config()
        payload = self.key_info(expires="9999-01-01T00:00:00Z")
        payload["key"] = config.agent_openai_api_key
        with mock.patch.object(budget, "read_key_info", return_value=payload):
            receipt = budget.observe_budget(config, "before")
        self.assertNotIn(config.agent_openai_api_key, json.dumps(receipt))

    def test_invalid_phase_never_contacts_gateway(self):
        with mock.patch.object(budget, "read_key_info") as read:
            with self.assertRaises(budget.BudgetError):
                budget.observe_budget(self.config(), "unknown")
        read.assert_not_called()

    def test_http_self_lookup_uses_header_and_no_environment_proxy(self):
        payload = self.key_info(spend=2.25)
        with local_gateway(json.dumps(payload).encode()) as (url, calls):
            with mock.patch.dict("os.environ", {"HTTP_PROXY": "http://127.0.0.1:1",
                                                "ALL_PROXY": "http://127.0.0.1:1"}):
                result = budget.read_key_info(url, self.config().agent_openai_api_key)
        self.assertEqual([("/key/info", "Bearer synthetic-key")], calls)
        self.assertEqual(Decimal("2.25"), result["info"]["spend"])

    def test_http_refuses_redirect_errors_and_unbounded_or_malformed_json(self):
        for body, status, location in ((b"{}", 302, "/responses"), (b"{}", 503, None),
                                      (b"invalid", 200, None), (b" " * 262145, 200, None)):
            with self.subTest(status=status, size=len(body)):
                with local_gateway(body, status=status, location=location) as (url, calls):
                    with self.assertRaises(budget.BudgetError) as failure:
                        budget.read_key_info(url, self.config().agent_openai_api_key)
                self.assertEqual([("/key/info", "Bearer synthetic-key")], calls)
                self.assertNotIn(self.config().agent_openai_api_key, str(failure.exception))


if __name__ == "__main__":
    unittest.main()
