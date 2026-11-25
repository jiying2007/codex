"""Retired entry points cannot revive a second ledger or model execution."""
from __future__ import annotations

import contextlib
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

from tools.codex_assets import feishu_codex_bot as bot_module
from tools.codex_assets.feishu_engineering_agent.__main__ import main
from tools.codex_assets.feishu_engineering_agent.models import InboundEvent, IntakeRejected


class RetirementBotTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="fea-retirement-")
        self.addCleanup(temp.cleanup)
        self.root = pathlib.Path(temp.name)
        self.policy = types.SimpleNamespace(
            alias="robot-app", allowed_open_ids=frozenset(),
            allowed_modes=frozenset(("explain", "review")),
            agent_allowed_modes=frozenset(),
        )
        self.transport = mock.Mock()
        self.runner = mock.Mock()

    def bot(self, enabled=True):
        config = bot_module.BotConfig(
            app_id="cli_test", app_secret="fixture-secret",
            target_chat_id="oc_team", bot_name="研发助手",
            repositories={"robot-app": self.policy},
            default_repo="robot-app", allowed_open_ids=frozenset(("ou_owner",)),
            state_db=self.root / "bot_state.sqlite3",
            lock_file=self.root / "bot.lock",
            engineering_enabled=enabled,
        )
        state = bot_module.StateStore(config.state_db)
        return bot_module.FeishuCodexBot(config, self.transport, self.runner, state)

    def event(self, msg_id="om_1", actor="ou_owner", chat="oc_team",
              tenant="tenantA", text="/wi help"):
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
        return mock.patch.object(bot_module.threading, "Thread", side_effect=factory)

    def assert_no_execution(self, bot):
        self.runner.run.assert_not_called()
        self.assertTrue(bot.jobs.empty())
        self.assertFalse((self.root / "feishu-engineering-agent.sqlite3").exists())
        with bot.store._connect() as db:
            self.assertEqual(0, db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0])

    def test_retired_workitem_commands_never_reach_model_gate(self):
        for enabled in (True, False):
            with self.subTest(engineering_enabled=enabled):
                bot = self.bot(enabled)
                with self.immediate_threads():
                    bot.on_message(self.event(text="/wi add tapd 缺陷 1000 2000 repo=robot-app | synthetic"))
                    bot.on_message(self.event(msg_id="om_help", text="/wi help"))
                self.assert_no_execution(bot)
                self.assertIn("链接", self.transport.send_text.call_args.args[1])

    def test_link_intake_precedes_model_gate_and_persists_topic(self):
        bot = self.bot()
        root = self.event(msg_id="om_link", text=(
            "分析 https://project.feishu.cn/example-space/issue/detail/1000000001 "
            "https://tenant-example.feishu.cn/wiki/ExampleWikiToken123?from=copy"
        ))
        with self.immediate_threads():
            bot.on_message(root)
            self.assertIn("缺陷 #1000000001", self.transport.send_text.call_args.args[1])
            self.assertIn("尚未读取", self.transport.send_text.call_args.args[1])
            self.transport.reset_mock()
            bot.on_message(root)
            self.transport.send_text.assert_not_called()
            bot = self.bot()
            reply = self.event(msg_id="om_followup", text="/repo robot-app")
            reply.event.message.root_id = "om_link"
            bot.on_message(reply)
            self.assertIn("研发仓库：robot-app", self.transport.send_text.call_args.args[1])
            status = self.event(msg_id="om_status", text="/status")
            status.event.message.root_id = "om_link"
            bot.on_message(status)
            self.assertIn("关联文档：1", self.transport.send_text.call_args.args[1])
        self.assert_no_execution(bot)
        with bot.store._connect() as db:
            self.assertEqual(1, db.execute("SELECT COUNT(*) FROM engineering_contexts").fetchone()[0])
            self.assertEqual(2, db.execute("SELECT COUNT(*) FROM engineering_context_sources").fetchone()[0])

    def test_unlinked_group_reply_does_not_create_paid_context(self):
        bot = self.bot()
        event = self.event(text="修复启动日志问题")
        event.event.message.root_id = "om_other_thread"
        bot.on_message(event)
        self.assert_no_execution(bot)
        self.transport.send_text.assert_not_called()
        with bot.store._connect() as db:
            self.assertEqual(0, db.execute("SELECT COUNT(*) FROM engineering_contexts").fetchone()[0])

    def test_removed_interfaces_are_not_available(self):
        self.assertFalse(hasattr(bot_module, "MessageGate"))
        self.assertFalse(hasattr(bot_module, "parse_command"))
        self.assertFalse(hasattr(bot_module, "ArtifactManager"))
        self.assertFalse(hasattr(bot_module.CodexRunner, "cancel_sender"))

    def test_disabled_engineering_never_falls_back_to_shared_model(self):
        bot = self.bot(False)
        with self.immediate_threads():
            bot.on_message(self.event(text="https://project.feishu.cn/example-space/story/detail/1000000002"))
            bot.on_message(self.event(msg_id="om_plain", text="分析启动日志"))
        self.assert_no_execution(bot)

    def test_unknown_slash_and_missing_billing_never_launch(self):
        bot = self.bot()
        with self.immediate_threads():
            bot.on_message(self.event(text="/wl help"))
            bot.on_message(self.event(msg_id="om_natural", text="repo=robot-app 分析启动日志"))
        self.assert_no_execution(bot)
        self.assertIn("未配置独立模型执行授权", self.transport.send_text.call_args.args[1])

    def test_untrusted_source_cannot_create_context(self):
        bot = self.bot()
        link = "https://project.feishu.cn/example-space/issue/detail/1000000001"
        with self.immediate_threads():
            bot.on_message(self.event(actor="ou_other", text=link))
            bot.on_message(self.event(msg_id="om_tenant", tenant="", text=link))
            bot.on_message(self.event(msg_id="om_chat", chat="oc_other", text=link))
        self.assert_no_execution(bot)
        with bot.store._connect() as db:
            self.assertEqual(0, db.execute("SELECT COUNT(*) FROM engineering_contexts").fetchone()[0])


class RetiredLocalCLItest(unittest.TestCase):
    def test_manual_writer_is_rejected_without_creating_state(self):
        with tempfile.TemporaryDirectory() as directory:
            database = pathlib.Path(directory) / "legacy.sqlite3"
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                main(["--manual", "--db", str(database), "--event-id", "fixture-1",
                      "--allow-repo", "robot-app"])
            self.assertEqual(2, raised.exception.code)
            self.assertFalse(database.exists())

    def test_link_preview_from_other_cwd_uses_current_parser_without_state(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        environ = dict(os.environ, PYTHONPATH=str(root))
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([
                sys.executable, "-m", "tools.codex_assets.feishu_engineering_agent",
                "--dry-run", "--allow-repo", "robot-app", "--selected-repo", "robot-app",
                "--text", "修复启动问题 https://project.feishu.cn/example-space/issue/detail/1000000001",
            ], cwd=directory, env=environ, check=False, capture_output=True, text=True, timeout=10)
            self.assertEqual(0, result.returncode, result.stderr)
            response = json.loads(result.stdout)
            self.assertEqual("edit", response["intent"])
            self.assertEqual("robot-app", response["repo"])
            self.assertEqual("link_unverified", response["source_level"])
            self.assertEqual("defect", response["sources"][0]["kind"])
            self.assertFalse(response["run_enqueued"])
            self.assertFalse(response["runtime_accessed"])
            self.assertFalse(response["state_accessed"])
            self.assertNotIn("修复启动问题", result.stdout)
            self.assertEqual([], list(pathlib.Path(directory).iterdir()))

    def test_event_identity_and_bounds_are_still_enforced(self):
        event = InboundEvent("feishu_message", "tenant", "oc_chat", "ou_owner", "om_1", "分析")
        other = InboundEvent("feishu_message", "other", "oc_chat", "ou_owner", "om_1", "分析")
        self.assertNotEqual(event.event_key, other.event_key)
        for ident, text in (("bad id", "分析"), ("om_1", "x" * 12001), ("om_1", "")):
            with self.assertRaises(IntakeRejected):
                InboundEvent("feishu_message", "tenant", "oc_chat", "ou_owner", ident, text)


if __name__ == "__main__":
    unittest.main()
