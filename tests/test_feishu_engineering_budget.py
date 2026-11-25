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

SESSION_ID = "e374db99-6b40-4a46-beb8-a03cdf52443c"


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

    def request_row(self, **changes):
        row = {"session_id": SESSION_ID,
               "api_key": hashlib.sha256(self.config().agent_openai_api_key.encode()).hexdigest(),
               "request_id": "resp_fixture", "model_group": "model", "model": "provider/actual-model",
               "status": "success", "spend": "0.1",
               "messages": "private prompt", "response": "private result",
               "metadata": {"private": "must not persist"}}
        row.update(changes)
        return row

    def spend_page(self, rows, **changes):
        page = {"data": rows, "page": 1, "page_size": 100, "total": len(rows),
                "total_pages": 1 if rows else 0, "total_is_capped": False}
        page.update(changes)
        return page

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

    def test_request_headers_require_exact_random_session_and_no_key(self):
        override = budget.provider_session_overrides(SESSION_ID)
        self.assertEqual(["-c", 'model_providers.feishu_agent_gateway.http_headers={'
                          '"x-litellm-session-id"="' + SESSION_ID + '"}'], override)
        for value in (None, "", "not-a-session", SESSION_ID.upper(), SESSION_ID + "\n"):
            with self.subTest(value=value), self.assertRaises(budget.BudgetError):
                budget.provider_session_overrides(value)

    def test_request_observation_preserves_alias_and_underlying_model_without_payloads(self):
        rows = [self.request_row(request_id="resp_second", spend=Decimal("0.2"), status="failure"),
                self.request_row(request_id="resp_first", spend="0.1")]
        with mock.patch.object(budget, "read_spend_page", return_value=self.spend_page(rows)):
            receipt = budget.observe_requests(self.config(), SESSION_ID)
        self.assertEqual("0.3", receipt["observed_request_cost_usd"])
        self.assertEqual("pending", receipt["settlement"])
        self.assertEqual("observed", receipt["request_observation"])
        self.assertEqual(2, receipt["request_count"])
        self.assertEqual("model", receipt["requests"][0]["model_group"])
        self.assertEqual("provider/actual-model", receipt["requests"][0]["model"])
        self.assertEqual("resp_first", receipt["requests"][0]["request_id"])
        self.assertEqual(64, len(receipt["request_evidence_sha256"]))
        for value in ("synthetic-key", "private prompt", "private result", "must not persist"):
            self.assertNotIn(value, json.dumps(receipt))
        # Gateway row order and non-accounting payloads do not change evidence.
        with mock.patch.object(budget, "read_spend_page", return_value=self.spend_page(list(reversed(rows)))):
            again = budget.observe_requests(self.config(), SESSION_ID)
        self.assertEqual(receipt["request_evidence_sha256"], again["request_evidence_sha256"])

    def test_empty_logs_are_pending_not_zero_cost_or_final_settlement(self):
        with mock.patch.object(budget, "read_spend_page", return_value=self.spend_page([])) as read:
            receipt = budget.observe_requests(self.config(), SESSION_ID)
        self.assertEqual(1, read.call_count)
        self.assertEqual("pending", receipt["request_observation"])
        self.assertEqual("pending", receipt["settlement"])
        self.assertIsNone(receipt["observed_request_cost_usd"])
        self.assertNotIn("request_evidence_sha256", receipt)
        with mock.patch.object(budget, "read_spend_page",
                               return_value=self.spend_page([self.request_row(spend=0)])):
            zero = budget.observe_requests(self.config(), SESSION_ID)
        self.assertEqual("observed", zero["request_observation"])
        self.assertEqual("0", zero["observed_request_cost_usd"])
        self.assertEqual(1, zero["request_count"])

    def test_request_rows_reject_partial_session_foreign_key_model_and_invalid_amounts(self):
        invalid = ({"session_id": "prefix-" + SESSION_ID}, {"session_id": SESSION_ID + "-suffix"},
                   {"api_key": "synthetic-key"}, {"api_key": "f" * 64},
                   {"model_group": "other"}, {"model_group": None}, {"model": None},
                   {"request_id": ""}, {"request_id": "private\ntext"},
                   {"status": None}, {"status": "pending"},
                   {"spend": None}, {"spend": True}, {"spend": -1},
                   {"spend": float("nan")}, {"spend": "Infinity"}, {"spend": "1e999999"})
        for change in invalid:
            with self.subTest(change=change):
                with mock.patch.object(budget, "read_spend_page",
                                       return_value=self.spend_page([self.request_row(**change)])):
                    with self.assertRaises(budget.BudgetError):
                        budget.observe_requests(self.config(), SESSION_ID)
        duplicate = [self.request_row(), self.request_row()]
        with mock.patch.object(budget, "read_spend_page", return_value=self.spend_page(duplicate)):
            with self.assertRaisesRegex(budget.BudgetError, "duplicate"):
                budget.observe_requests(self.config(), SESSION_ID)

    def test_request_pages_are_bounded_complete_and_consistent(self):
        first = self.spend_page([self.request_row(request_id="resp_one"), self.request_row(request_id="resp_two")],
                                page_size=2, total=3, total_pages=2)
        second = self.spend_page([self.request_row(request_id="resp_three")], page=2,
                                 page_size=2, total=3, total_pages=2)
        with mock.patch.object(budget, "_SPEND_PAGE_SIZE", 2), \
                mock.patch.object(budget, "read_spend_page", side_effect=[first, second]) as read:
            receipt = budget.observe_requests(self.config(), SESSION_ID)
        self.assertEqual(2, read.call_count)
        self.assertEqual("0.3", receipt["observed_request_cost_usd"])
        for change in ({"page": True}, {"page": 2}, {"page_size": 99}, {"total": True},
                       {"total": 501}, {"total": -1}, {"total_pages": 2},
                       {"total_is_capped": True}, {"total_is_capped": None}, {"data": []}):
            with self.subTest(change=change):
                broken = self.spend_page([self.request_row()], **change)
                with mock.patch.object(budget, "read_spend_page", return_value=broken) as read:
                    with self.assertRaises(budget.BudgetError):
                        budget.observe_requests(self.config(), SESSION_ID)
                    self.assertEqual(1, read.call_count)
        for second_page in (dict(second, total=2, total_pages=1),
                            dict(second, data=[self.request_row(request_id="resp_one")])):
            with mock.patch.object(budget, "_SPEND_PAGE_SIZE", 2), \
                    mock.patch.object(budget, "read_spend_page", side_effect=[first, second_page]):
                with self.assertRaises(budget.BudgetError):
                    budget.observe_requests(self.config(), SESSION_ID)

    def test_before_after_identity_policy_and_cumulative_spend_cannot_drift(self):
        with mock.patch.object(budget, "read_key_info", return_value=self.key_info()):
            before = budget.observe_budget(self.config(), "before")
        before["session_id"] = SESSION_ID
        after = dict(before, provider_cumulative_spend_usd="3")
        budget.validate_observation_binding(before, after)
        for change in ({"gateway": "https://other.example/v1"}, {"model": "other"},
                       {"key_alias": "other"}, {"key_fingerprint": "f" * 64},
                       {"approved_usd": "11"}, {"provider_cap_usd": "9"},
                       {"provider_cumulative_spend_usd": "1"}):
            with self.subTest(change=change), self.assertRaises(budget.BudgetError):
                budget.validate_observation_binding(before, dict(after, **change))

    def test_spend_lookup_uses_self_bearer_header_and_session_filter(self):
        body = self.spend_page([self.request_row()])
        with local_gateway(json.dumps(body).encode()) as (url, calls):
            budget.read_spend_page(url, self.config().agent_openai_api_key, SESSION_ID, 1)
        self.assertEqual(1, len(calls))
        self.assertEqual("Bearer synthetic-key", calls[0][1])
        self.assertTrue(calls[0][0].startswith("/spend/logs/v2?"))
        self.assertIn("session_id=" + SESSION_ID, calls[0][0])
        self.assertNotIn("synthetic-key", calls[0][0])
        self.assertNotIn("api_key", calls[0][0])


if __name__ == "__main__":
    unittest.main()
