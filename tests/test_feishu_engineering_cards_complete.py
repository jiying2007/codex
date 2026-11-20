"""Card callback layouts, durable action review and opt-in existing-Bot wiring."""
from __future__ import annotations

import pathlib
import tempfile
import time
import types
import unittest
from unittest import mock

from tools.codex_assets import feishu_codex_bot as legacy
from tools.codex_assets.feishu_engineering_agent.actions import CardActionQueue
from tools.codex_assets.feishu_engineering_agent.cards import (
    accept_callback, bind_sent_message, register_card, render_card,
)
from tools.codex_assets.feishu_engineering_agent.models import InboundEvent, IntakeRejected
from tools.codex_assets.feishu_engineering_agent.state import RunStore

KEY = b"test-only-opaque-private-hmac-signing-key-32-bytes"


class CardCompletionTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="fea-card-complete-")
        self.addCleanup(temp.cleanup)
        self.root = pathlib.Path(temp.name)
        self.store = RunStore(self.root / "private.sqlite3")
        self.event = InboundEvent("feishu_message", "tenantA", "oc_team",
                                  "ou_owner", "om_msg", "检查")
        self.run = self.store.create_run(self.event, "robot-app", {"robot-app"})
        register_card(self.store, self.run, "card_1")
        bind_sent_message(self.store, "card_1", "om_card")
        self.actions = CardActionQueue(self.store)

    def value(self, name):
        card = render_card(self.store, "card_1", KEY)
        return next(x["behaviors"][0]["value"]
                    for x in card["body"]["elements"]
                    if x["tag"] == "button"
                    and x["behaviors"][0]["value"]["action"] == name)

    def payload(self, value, layout="outer", click="evt_1"):
        event = {
            "operator": {"open_id": "ou_owner", "tenant_key": "tenantA"},
            "action": {"tag": "button", "value": value},
        }
        context = {"open_chat_id": "oc_team", "open_message_id": "om_card"}
        source = {
            "schema": "2.0",
            "header": {
                "event_type": "card.action.trigger", "app_id": "cli_test",
                "token": "token-test", "event_id": click, "tenant_key": "tenantA",
            },
            "event": event,
        }
        if layout == "nested":
            event.update({"host": "im_message", "context": context})
        else:
            source.update({"host": "im_message", "context": context})
        return source

    def accept(self, payload):
        return accept_callback(self.store, payload, "token-test", "cli_test", KEY)

    def test_official_outer_and_nested_callback_layouts(self):
        receipt = self.accept(self.payload(self.value("status"), layout="outer"))
        self.assertTrue(receipt["accepted"])
        self.assertTrue(self.accept(self.payload(
            self.value("status"), layout="nested", click="evt_2",
        ))["accepted"])
        forged = self.payload(self.value("status"), click="evt_3")
        forged["event"]["host"] = "not_the_same"
        with self.assertRaises(IntakeRejected):
            self.accept(forged)

    def test_pending_execution_does_not_grant_model_and_is_owner_scoped(self):
        self.accept(self.payload(self.value("request_execution")))
        pending = self.actions.pending_for(self.event)
        self.assertEqual(1, len(pending))
        click = pending[0]["click_key"]
        refused_user = InboundEvent("feishu_message", "tenantA", "oc_team",
                                    "ou_attacker", "om_hacker", "状态")
        self.assertEqual([], self.actions.pending_for(refused_user))
        with self.assertRaises(IntakeRejected):
            self.actions.resolve(click, refused_user, {"robot-app"}, "recorded")
        decision = self.actions.resolve(click, self.event, {"robot-app"}, "recorded")
        self.assertIn("separate_runtime", decision["result"])
        self.assertFalse(decision["model_started"])
        self.assertEqual("proposed", self.store.get_run(self.run)["status"])
        self.assertTrue(self.actions.resolve(
            click, self.event, {"robot-app"}, "recorded",
        )["duplicate"])
        self.assertEqual([], self.actions.pending_for(self.event))

    def test_queued_run_can_cancel_but_running_requires_exact_native_interrupt(self):
        row = self.store.transition(self.run, 0, "ready", self.event.actor)
        self.store.transition(self.run, row["revision"], "queued", self.event.actor)
        self.accept(self.payload(self.value("request_cancel")))
        click = self.actions.pending_for(self.event)[0]["click_key"]
        outcome = self.actions.resolve(
            click, self.event, {"robot-app"}, "cancel_if_not_running",
        )
        self.assertEqual("canceled_before_execution", outcome["result"])
        self.assertEqual("canceled", self.store.get_run(self.run)["status"])


class BotCardOptinTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="fea-bot-optin-")
        self.addCleanup(temp.cleanup)
        self.root = pathlib.Path(temp.name)
        policy = types.SimpleNamespace(alias="robot-app",
                                       allowed_open_ids=frozenset(),
                                       allowed_modes=frozenset(("explain", "review")))
        self.transport = mock.Mock()
        self.config = legacy.BotConfig(
            app_id="cli_test", app_secret="private-test-secret",
            target_chat_id="oc_team", bot_name="AI助手",
            repositories={"robot-app": policy},
            default_repo="robot-app", allowed_open_ids=frozenset(("ou_owner",)),
            state_db=self.root / "bot.sqlite3", lock_file=self.root / "bot.lock",
            manual_workitems_enabled=True, engineering_cards_enabled=True,
            card_verification_token="token-test",
            card_signing_key_hex=KEY.hex(),
        )

    def test_opt_in_card_send_uses_existing_transport_once(self):
        with mock.patch(
            "tools.codex_assets.feishu_engineering_agent.channel.send_interactive_via_existing_transport",
            return_value="om_card",
        ) as sender:
            bot = legacy.FeishuCodexBot(
                self.config, self.transport, mock.Mock(),
                legacy.StateStore(self.config.state_db),
            )
            event = InboundEvent(
                "feishu_message", "tenantA", "oc_team", "ou_owner",
                "om_first",
                "/wi add tapd 缺陷 10104801 123456 repo=robot-app | 回充上桩过流",
            )
            bot._run_manual_message(event, "ou_owner", frozenset(("robot-app",)))
            sender.assert_called_once()
            bot._run_manual_message(event, "ou_owner", frozenset(("robot-app",)))
            sender.assert_called_once()  # duplicate event is idempotent
            with mock.patch(
                "tools.codex_assets.feishu_engineering_agent.channel.make_single_consumer_card_callback",
                return_value="card_callback",
            ):
                with mock.patch.object(legacy.threading, "Thread"):
                    bot.start()
            self.transport.start.assert_called_once()
            self.assertEqual("card_callback", self.transport.start.call_args.args[1])

    def test_card_optin_requires_private_key_and_manual_workitems(self):
        with self.assertRaises(legacy.FeishuCodexError):
            legacy.FeishuCodexBot(
                legacy.dataclasses.replace(self.config,
                                           manual_workitems_enabled=False),
                self.transport, mock.Mock(),
                legacy.StateStore(self.config.state_db),
            )


if __name__ == "__main__":
    unittest.main()
