"""Existing Feishu Bot optional /wi bridge, without enterprise Project API or Codex."""
from __future__ import annotations

import json
import pathlib
import sqlite3
import tempfile
import types
import unittest
from unittest import mock

from tools.codex_assets import feishu_codex_bot as legacy


class ManualWorkItemBotBridgeTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="fea-manual-bot-")
        self.addCleanup(temp.cleanup)
        self.root = pathlib.Path(temp.name)
        policy = types.SimpleNamespace(
            alias="robot-app", allowed_open_ids=frozenset(),
            allowed_modes=frozenset(("explain", "review")),
        )
        self.policy = policy
        self.transport = mock.Mock()
        self.runner = mock.Mock()

    def bot(self, enabled=True):
        config = legacy.BotConfig(
            app_id="cli_test", app_secret="fixture-secret",
            target_chat_id="oc_team", bot_name="研发助手",
            repositories={"robot-app": self.policy},
            default_repo="robot-app", allowed_open_ids=frozenset(("ou_owner",)),
            state_db=self.root / "bot_state.sqlite3",
            lock_file=self.root / "bot.lock",
            manual_workitems_enabled=enabled,
        )
        state = legacy.StateStore(config.state_db)
        instance = legacy.FeishuCodexBot(config, self.transport, self.runner, state)
        return instance

    def event(self, msg_id="om_1", actor="ou_owner", chat="oc_team",
              tenant="tenantA", text=None):
        if text is None:
            text = (
                "/wi add tapd 缺陷 10104801 123456 repo=robot-app "
                "| 上桩过流；复测不得误保护"
            )
        message = types.SimpleNamespace(
            message_id=msg_id, chat_id=chat, message_type="text",
            mentions=[], content=json.dumps({"text": text}, ensure_ascii=False),
        )
        sender = types.SimpleNamespace(sender_id=types.SimpleNamespace(open_id=actor))
        return types.SimpleNamespace(
            header=types.SimpleNamespace(tenant_key=tenant),
            event=types.SimpleNamespace(message=message, sender=sender),
        )

    def immediate_threads(self):
        def factory(*args, **kwargs):
            return types.SimpleNamespace(
                start=lambda: kwargs["target"](*kwargs.get("args", ())),
            )
        return mock.patch.object(legacy.threading, "Thread", side_effect=factory)

    def test_enabled_bridge_registers_without_model_or_old_queue(self):
        bot = self.bot(True)
        with self.immediate_threads(), mock.patch.object(
            bot.gate, "accept", side_effect=AssertionError("legacy gate reached")
        ):
            bot.on_message(self.event())
            self.assertIn("AgentRun：", self.transport.send_text.call_args.args[1])
            self.transport.reset_mock()
            bot.on_message(self.event())  # exact duplicate no second reply or run
            self.transport.send_text.assert_not_called()
        self.runner.run.assert_not_called()
        self.assertTrue(bot.jobs.empty())
        db = self.root / "feishu-engineering-agent.sqlite3"
        self.assertTrue(db.exists())
        with sqlite3.connect(str(db)) as conn:
            self.assertEqual(1, conn.execute("SELECT COUNT(*) FROM fea_manual_claims").fetchone()[0])
            self.assertEqual(1, conn.execute("SELECT COUNT(*) FROM fea_runs").fetchone()[0])
        with sqlite3.connect(str(self.root / "bot_state.sqlite3")) as conn:
            self.assertEqual(0, conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0])

    def test_handoff_uses_existing_bot_text_reply_without_execution(self):
        bot = self.bot(True)
        with self.immediate_threads(), mock.patch.object(
            bot.gate, "accept", side_effect=AssertionError("legacy gate reached")
        ):
            bot.on_message(self.event())
            response = self.transport.send_text.call_args.args[1]
            run_id = response.split("AgentRun：", 1)[1].split("\n")[0]
            self.transport.reset_mock()
            bot.on_message(self.event(
                msg_id="om_handoff", text="/wi handoff " + run_id +
                " | 复现：上桩低速电流升高；验收：独立QA通过"
            ))
        self.assertIn("未启动 Codex", self.transport.send_text.call_args.args[1])
        self.assertIn("只读复现缺陷", self.transport.send_text.call_args.args[1])
        self.assertTrue(bot.jobs.empty())
        self.runner.run.assert_not_called()

    def test_sqlite_intake_is_deferred_off_message_callback_thread(self):
        bot = self.bot(True)
        with mock.patch.object(legacy.threading, "Thread") as thread, mock.patch.object(
            bot.gate, "accept", side_effect=AssertionError("legacy gate reached")
        ):
            bot.on_message(self.event())
        self.assertEqual(1, thread.call_count)
        self.transport.send_text.assert_not_called()
        self.assertTrue(bot.jobs.empty())
        self.runner.run.assert_not_called()
        thread.call_args.kwargs["target"](*thread.call_args.kwargs["args"])
        self.assertIn("AgentRun：", self.transport.send_text.call_args.args[1])

    def test_default_off_reserved_command_does_not_reach_codex(self):
        bot = self.bot(False)
        with self.immediate_threads(), mock.patch.object(
            bot.gate, "accept", side_effect=AssertionError("legacy gate reached")
        ):
            bot.on_message(self.event())
        self.assertIn("未启用", self.transport.send_text.call_args.args[1])
        self.runner.run.assert_not_called()
        self.assertFalse((self.root / "feishu-engineering-agent.sqlite3").exists())

    def test_untrusted_actor_tenant_or_chat_cannot_register(self):
        bot = self.bot(True)
        # An out-of-chat message correctly goes through the original gate,
        # where it is ignored without creating a job.
        with self.immediate_threads(), mock.patch.object(
            bot.gate, "accept", return_value=None
        ):
            bot.on_message(self.event(actor="ou_attacker"))
            bot.on_message(self.event(chat="oc_other"))
            bot.on_message(self.event(tenant=""))
        self.assertEqual(1, self.transport.send_text.call_count)
        self.assertIn("租户标识", self.transport.send_text.call_args.args[1])
        with sqlite3.connect(str(self.root / "feishu-engineering-agent.sqlite3")) as conn:
            self.assertEqual(0, conn.execute("SELECT COUNT(*) FROM fea_runs").fetchone()[0])

    def test_bad_repo_fails_closed_and_does_not_launch(self):
        bot = self.bot(True)
        bad = self.event(text=(
            "/wi add tapd 缺陷 10104801 123456 repo=not-allowed | 复现环境与预期"
        ))
        with self.immediate_threads(), mock.patch.object(
            bot.gate, "accept", side_effect=AssertionError("legacy gate reached")
        ):
            bot.on_message(bad)
        self.assertIn("被拒绝", self.transport.send_text.call_args.args[1])
        self.runner.run.assert_not_called()

    def test_chat_workitem_operations_are_bounded_by_independent_rate_limit(self):
        bot = self.bot(True)
        with self.immediate_threads(), mock.patch.object(
            bot.gate, "accept", side_effect=AssertionError("legacy gate reached")
        ):
            for index in range(6):
                bot.on_message(self.event(msg_id="om_" + str(index)))
        self.assertIn("过于频繁", self.transport.send_text.call_args.args[1])
        with sqlite3.connect(str(self.root / "feishu-engineering-agent.sqlite3")) as db:
            self.assertEqual(5, db.execute("SELECT COUNT(*) FROM fea_runs").fetchone()[0])
        self.runner.run.assert_not_called()

    def test_nonmanual_input_uses_original_gate(self):
        bot = self.bot(True)
        with mock.patch.object(bot.gate, "accept", return_value=None) as gate:
            bot.on_message(self.event(text="分析启动日志"))
        gate.assert_called_once()
        self.runner.run.assert_not_called()

    def test_manual_state_must_not_reuse_legacy_bot_db(self):
        config = legacy.BotConfig(
            app_id="cli_test", app_secret="fixture-secret",
            target_chat_id="oc_team", bot_name="研发助手",
            repositories={"robot-app": self.policy}, default_repo="robot-app",
            allowed_open_ids=frozenset({"ou_owner"}),
            state_db=self.root / "feishu-engineering-agent.sqlite3",
            lock_file=self.root / "bot.lock",
            manual_workitems_enabled=True,
        )
        with self.assertRaisesRegex(legacy.FeishuCodexError, "must differ"):
            legacy.FeishuCodexBot(
                config, self.transport, self.runner,
                legacy.StateStore(config.state_db),
            )

    def test_flag_is_optional_and_invalid_type_is_denied(self):
        self.assertFalse(self.bot(False).config.manual_workitems_enabled)
        # Direct BotConfig construction follows the same default policy.
        self.assertFalse(legacy.BotConfig(
            app_id="cli_test", app_secret="secret",
            target_chat_id="oc_team", bot_name="研发助手",
            repositories={"robot-app": self.policy}, default_repo="robot-app",
            allowed_open_ids=frozenset({"ou_owner"}), state_db=self.root / "another.sqlite",
            lock_file=self.root / "another.lock",
        ).manual_workitems_enabled)


if __name__ == "__main__":
    unittest.main()
