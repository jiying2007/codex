"""No-model regressions for the provider budget boundary."""
import unittest
from types import SimpleNamespace
from unittest import mock

from tools.codex_assets.feishu_engineering_agent import budget


class BudgetTests(unittest.TestCase):
    def config(self, **changes):
        data = dict(agent_budget_backend="litellm", agent_billing_source="external_gateway",
                    agent_openai_api_key="synthetic-key", agent_budget_key_alias="agent",
                    agent_model="model", agent_openai_base_url="https://gateway.example/v1",
                    agent_budget_max_usd="10")
        data.update(changes)
        return SimpleNamespace(**data)

    def test_provider_budget_and_route(self):
        config = self.config()
        with mock.patch.object(budget, "read_key_info",
                               return_value={"info": {"key_alias": "agent",
                                                      "max_budget": 8, "spend": "2.25"}}) as read:
            result = budget.observe_budget(config, "before")
        read.assert_called_once_with(config.agent_openai_base_url, config.agent_openai_api_key)
        self.assertEqual("2.25", result["provider_cumulative_spend_usd"])
        self.assertNotIn(config.agent_openai_api_key, str(result))
        args = budget.provider_overrides(config)
        self.assertIn('model_provider="feishu_agent_gateway"', args)
        self.assertNotIn(config.agent_openai_api_key, str(args))

    def test_fail_closed(self):
        for extra in ({"spend": 10}, {"max_budget": 11}, {"max_budget": None},
                      {"spend": float("nan")}, {"spend": -1}, {"key_alias": "other"},
                      {"budget_duration": "1d"}, {"blocked": True}):
            with self.subTest(extra=extra):
                info = dict(key_alias="agent", max_budget=10, spend=2)
                info.update(extra)
                with mock.patch.object(budget, "read_key_info", return_value={"info": info}):
                    with self.assertRaises(budget.BudgetError):
                        budget.observe_budget(self.config(), "before")
        for changes in ({"agent_budget_backend": ""}, {"agent_billing_source": "external_api_key"},
                        {"agent_openai_base_url": "http://gateway.example/v1"},
                        {"agent_openai_base_url": "https://gateway.example/v1?token=x"}):
            with self.assertRaises(budget.BudgetError):
                budget.provider_overrides(self.config(**changes))

    def test_after_observation_preserves_exhausted_state(self):
        with mock.patch.object(budget, "read_key_info",
                               return_value={"info": {"key_alias": "agent",
                                                      "max_budget": 10, "spend": 12}}):
            self.assertTrue(budget.observe_budget(self.config(), "after")["exhausted"])


if __name__ == "__main__":
    unittest.main()
