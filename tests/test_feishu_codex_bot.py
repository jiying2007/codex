from __future__ import annotations

import argparse
import contextlib
import dataclasses
import hashlib
import json
import os
import pathlib
import sqlite3
import subprocess
import tempfile
import types
import unittest
from unittest import mock

from tools.codex_assets import feishu_codex_bot
from tools.codex_assets.feishu_agent_mcp import AgentTaskIntake


class FakeProcess:
    def __init__(self, stdout: str = "完成\n", returncode: int = 0) -> None:
        self.stdout = stdout
        self.returncode = returncode
        self.terminated = False
        self.killed = False

    def communicate(self, timeout: float = 0) -> object:
        return self.stdout, ""

    def poll(self) -> object:
        return None if not self.terminated else self.returncode

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True

    def wait(self, timeout: float = 0) -> int:
        return self.returncode


class FeishuCodexBotTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="feishu-codex-test-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp))
        (self.tmp / ".git").mkdir()
        self.policy_path = self.tmp / "bot.json"
        self.policy = {
            "schema_version": 1,
            "default_repo": "codex",
            "allowed_open_ids": ["ou_owner"],
            "repositories": {
                "codex": {
                    "path": str(self.tmp),
                    "allowed_modes": ["explain", "review"],
                    "allowed_open_ids": [],
                }
            },
            "worker_count": 2,
            "queue_size": 4,
            "rate_limit_count": 2,
            "rate_limit_window_sec": 60,
            "reply_chunk_chars": 500,
            "state_db": str(self.tmp / "state.sqlite3"),
            "lock_file": str(self.tmp / "bot.lock"),
        }
        self.write_policy()
        self.values = {
            "FEISHU_APP_ID": "cli_test",
            "FEISHU_APP_SECRET": "secret-value",
            "FEISHU_TARGET_CHAT_ID": "oc_target",
            "FEISHU_BOT_NAME": "AI助手",
            "FEISHU_BOT_CONFIG": str(self.policy_path),
        }
        self.agent_home = pathlib.Path(tempfile.mkdtemp(prefix="feishu-agent-home-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.agent_home))
        self.agent_home.chmod(0o700)
        self.agent_key = "fixture-dedicated-test-key"
        budget = mock.patch(
            "tools.codex_assets.feishu_engineering_agent.budget.read_key_info",
            return_value={"key": hashlib.sha256(self.agent_key.encode()).hexdigest(), "info": {
                "key_alias": "fixture-agent", "blocked": False, "budget_duration": None,
                "models": ["fixture-model"], "max_budget": 10, "spend": 1,
            }},
        )
        budget.start()
        self.addCleanup(budget.stop)

    def write_policy(self) -> None:
        self.policy_path.write_text(json.dumps(self.policy), encoding="utf-8")
        self.policy_path.chmod(0o600)

    def config(self) -> feishu_codex_bot.BotConfig:
        return feishu_codex_bot.BotConfig.from_values(self.values, self.tmp)

    def agent_config(self) -> feishu_codex_bot.BotConfig:
        self.policy["agent_intake_enabled"] = True
        self.policy["agent_codex_home"] = str(self.agent_home)
        for repository in self.policy["repositories"].values():
            repository["agent_allowed_modes"] = list(repository["allowed_modes"])
        self.write_policy()
        self.values.update({
            "FEISHU_AGENT_BILLING_SOURCE": "external_gateway",
            "FEISHU_AGENT_OPENAI_API_KEY": self.agent_key,
            "FEISHU_AGENT_OPENAI_BASE_URL": "https://gateway.example/v1",
            "FEISHU_AGENT_BUDGET_BACKEND": "litellm",
            "FEISHU_AGENT_BUDGET_MAX_USD": "10",
            "FEISHU_AGENT_BUDGET_KEY_ALIAS": "fixture-agent",
            "FEISHU_AGENT_MODEL": "fixture-model",
        })
        return self.config()

    def queued_agent(self, key: str, task: str = "检查测试", mode: str = "review"):
        config = self.agent_config()
        intake = AgentTaskIntake(config)
        record = intake.submit_task("codex", mode, task, key)
        bot = feishu_codex_bot.FeishuCodexBot(config, mock.Mock(), mock.Mock(), intake.store)
        job = bot._decode_job(intake.spool.get(record["id"]), intake.store.queued_task(record["id"]))
        return config, intake.store, bot, job

    @contextlib.contextmanager
    def sandboxed_git_checks(self, config):
        """Real fixture Git checks behind a mocked sandbox process transport."""
        original_run = subprocess.run
        calls = []
        def run(arguments, **kwargs):
            if arguments[0] != config.isolation_bin:
                return original_run(arguments, **kwargs)
            calls.append(arguments)
            self.assertIn("--unshare-net", arguments)
            self.assertIn("--unshare-pid", arguments)
            self.assertLess(arguments.index("--tmpfs"), arguments.index("--bind"))
            inner = arguments[arguments.index("--") + 1:]
            self.assertEqual(["rtk", "proxy", "git", "diff", "--check"], inner)
            environment = dict(kwargs["env"])
            self.assertEqual("/tmp/feishu-verification-home", environment["HOME"])
            self.assertNotIn("OPENAI_API_KEY", environment)
            # This test substitutes only bwrap transport, then runs the real
            # fixed Git command against a disposable, synthetic repository.
            test_home = self.tmp / "fixture-verification-home"
            test_home.mkdir(exist_ok=True)
            environment.update(HOME=str(test_home), XDG_DATA_HOME=str(test_home),
                               XDG_CONFIG_HOME=str(test_home), XDG_CACHE_HOME=str(test_home))
            return original_run(inner, **dict(kwargs, env=environment))
        with mock.patch.object(feishu_codex_bot.subprocess, "run", side_effect=run):
            yield calls
        self.assertTrue(calls)

    def event(
        self,
        message_id: str = "om_1",
        chat_id: str = "oc_target",
        open_id: str = "ou_owner",
        text: str = "@_user_1 检查测试",
    ) -> object:
        message = types.SimpleNamespace(
            message_id=message_id,
            chat_id=chat_id,
            message_type="text",
            content=json.dumps({"text": text}, ensure_ascii=False),
            mentions=[types.SimpleNamespace(key="_user_1")],
        )
        sender = types.SimpleNamespace(sender_id=types.SimpleNamespace(open_id=open_id))
        return types.SimpleNamespace(event=types.SimpleNamespace(message=message, sender=sender))

    def env_args(self, action: str) -> argparse.Namespace:
        env_path = self.tmp / "bot.env"
        env_path.write_text("\n".join(f"{key}={value}" for key, value in self.values.items()), encoding="utf-8")
        env_path.chmod(0o600)
        return argparse.Namespace(
            root=str(self.tmp),
            action=action,
            env_file=str(env_path),
            prompt="",
            repo="",
            mode="explain",
            confirm_send=False,
        )

    def test_private_config_files_are_required(self) -> None:
        path = self.tmp / "unsafe.env"
        path.write_text("FEISHU_APP_ID=cli_test\n", encoding="utf-8")
        path.chmod(0o644)
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "600"):
            feishu_codex_bot.load_env_file(path)
        self.policy_path.chmod(0o644)
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "600"):
            feishu_codex_bot.BotConfig.from_values(self.values, self.tmp)

    def test_repository_alias_and_layered_allowlist_are_configurable(self) -> None:
        other = self.tmp / "other"
        other.mkdir()
        (other / ".git").mkdir()
        self.policy["repositories"]["other"] = {
            "path": str(other),
            "allowed_modes": ["review"],
            "allowed_open_ids": ["ou_owner"],
        }
        self.write_policy()
        config = self.config()
        self.assertEqual(other, config.repository("other").path)
        self.assertTrue(config.sender_allowed("ou_owner", config.repository("other")))
        self.assertFalse(config.sender_allowed("ou_other", config.repository("other")))
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "未知仓库别名"):
            config.repository("missing")

    def test_runtime_rejects_repository_without_any_allowlist(self) -> None:
        self.policy["allowed_open_ids"] = []
        self.write_policy()
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "没有用户白名单"):
            self.config().validate_runtime()

    def test_edit_mode_defaults_to_in_place_without_commit(self) -> None:
        self.policy["repositories"]["codex"]["allowed_modes"] = ["edit"]
        self.write_policy()
        repository = self.config().repository("codex")
        self.assertEqual("in_place", repository.edit_strategy)
        self.assertIsNone(repository.worktree_root)
        self.assertFalse(repository.commit_enabled)

    def test_worktree_strategy_requires_isolated_root(self) -> None:
        self.policy["repositories"]["codex"].update(
            {"allowed_modes": ["edit"], "edit_strategy": "worktree"}
        )
        self.write_policy()
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "worktree_root"):
            self.config()

    def test_in_place_strategy_rejects_automatic_commit(self) -> None:
        self.policy["repositories"]["codex"].update(
            {
                "allowed_modes": ["edit"],
                "edit_strategy": "in_place",
                "commit_enabled": True,
            }
        )
        self.write_policy()
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "禁止自动提交"):
            self.config()

    def test_edit_strategy_summary_reports_only_editable_repositories(self) -> None:
        self.policy["repositories"]["codex"]["allowed_modes"] = ["edit"]
        self.write_policy()
        self.assertEqual("in_place:1", feishu_codex_bot.edit_strategy_summary(self.config()))

    def test_artifact_upload_policy_is_explicit_and_bounded(self) -> None:
        self.policy["repositories"]["codex"].update(
            {
                "allowed_modes": ["edit"],
                "artifact_upload": {
                    "enabled": True,
                    "allowed_roots": ["dist/android"],
                    "allowed_extensions": [".APK"],
                    "max_bytes": 1024,
                },
            }
        )
        self.write_policy()
        repository = self.config().repository("codex")
        self.assertTrue(repository.artifact_upload_enabled)
        self.assertEqual(
            (pathlib.PurePosixPath("dist/android"),),
            repository.artifact_roots,
        )
        self.assertEqual(frozenset({".apk"}), repository.artifact_extensions)
        self.assertEqual(1024, repository.artifact_max_bytes)
        self.assertEqual("codex", feishu_codex_bot.artifact_upload_summary(self.config()))

    def test_artifact_upload_policy_rejects_escape_and_platform_oversize(self) -> None:
        self.policy["repositories"]["codex"].update(
            {
                "allowed_modes": ["edit"],
                "artifact_upload": {
                    "enabled": True,
                    "allowed_roots": ["../outside"],
                    "allowed_extensions": [".apk"],
                },
            }
        )
        self.write_policy()
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "仓库相对路径"):
            self.config()
        self.policy["repositories"]["codex"]["artifact_upload"]["allowed_roots"] = ["dist"]
        self.policy["repositories"]["codex"]["artifact_upload"]["max_bytes"] = (
            feishu_codex_bot.FEISHU_FILE_MAX_BYTES + 1
        )
        self.write_policy()
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "max_bytes"):
            self.config()

    def test_command_parser_supports_alias_modes_and_controls(self) -> None:
        command = feishu_codex_bot.parse_command("repo=codex mode=review 检查并发", "codex")
        self.assertEqual(("task", "codex", "review", "检查并发"), dataclass_values(command))
        self.assertEqual("status", feishu_codex_bot.parse_command("/status", "codex").action)
        self.assertEqual("cancel", feishu_codex_bot.parse_command("取消", "codex").action)
        self.assertEqual(
            ("repo", "codex", "explain", ""),
            dataclass_values(feishu_codex_bot.parse_command("/repo", "codex")),
        )
        self.assertEqual(
            ("set_repo", "x5", "explain", ""),
            dataclass_values(feishu_codex_bot.parse_command("/repo X5", "codex")),
        )
        self.assertEqual(
            ("reset_repo", "codex", "explain", ""),
            dataclass_values(feishu_codex_bot.parse_command("/repo reset", "codex")),
        )
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "用法"):
            feishu_codex_bot.parse_command("/repo x5 extra", "codex")
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "格式无效"):
            feishu_codex_bot.parse_command("/repo ../x5", "codex")
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "任务内容为空"):
            feishu_codex_bot.parse_command("repo=codex", "codex")
        artifact = feishu_codex_bot.parse_command(
            "repo=codex mode=edit artifact=dist/android/app.apk 编译 APK",
            "codex",
        )
        self.assertEqual("dist/android/app.apk", artifact.artifact)
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "仓库相对路径"):
            feishu_codex_bot.parse_command(
                "mode=edit artifact=../secret.apk 编译",
                "codex",
            )
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "只能声明一个"):
            feishu_codex_bot.parse_command(
                "mode=edit artifact=dist/a.apk artifact=dist/b.apk 编译",
                "codex",
            )

    def test_unknown_slash_control_is_not_a_model_prompt(self) -> None:
        for text in ("/wl help", "/w1 list", "/HELP", "/status extra", "/unknown",
                     "  /wi help", "/wiki"):
            with self.subTest(text=text):
                with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "未启动 Codex"):
                    feishu_codex_bot.parse_command(text, "codex")
        for text in ("检查 /tmp", "/home/user/project 分析日志",
                     "mode=explain /tmp 检查目录", "repo=codex /wl 是什么"):
            with self.subTest(text=text):
                self.assertEqual("task", feishu_codex_bot.parse_command(text, "codex").action)
        config = self.config()
        store = feishu_codex_bot.StateStore(config.state_db)
        gate = feishu_codex_bot.MessageGate(config, store)
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "未启动 Codex"):
            gate.accept(self.event(message_id="om_typo", text="@_user_1 /wl help"))
        self.assertEqual([], store.pending())
        with store._connect() as db:
            self.assertEqual(0, db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0])

    def test_message_gate_requires_edit_and_enabled_policy_for_artifact(self) -> None:
        config = self.config()
        store = feishu_codex_bot.StateStore(config.state_db)
        gate = feishu_codex_bot.MessageGate(config, store)
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "仅允许用于 edit"):
            gate.accept(
                self.event(
                    message_id="om_artifact_read",
                    text="@_user_1 artifact=dist/app.apk 检查",
                )
            )
        self.policy["repositories"]["codex"]["allowed_modes"] = [
            "explain",
            "review",
            "edit",
        ]
        self.write_policy()
        config = self.config()
        gate = feishu_codex_bot.MessageGate(
            config,
            feishu_codex_bot.StateStore(config.state_db),
        )
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "未启用产物回传"):
            gate.accept(
                self.event(
                    message_id="om_artifact_disabled",
                    text="@_user_1 mode=edit artifact=dist/app.apk 编译",
                )
            )
        self.policy["repositories"]["codex"].update(
            {
                "allowed_modes": ["edit"],
                "artifact_upload": {
                    "enabled": True,
                    "allowed_roots": ["dist"],
                    "allowed_extensions": [".apk"],
                },
            }
        )
        self.write_policy()
        config = self.config()
        gate = feishu_codex_bot.MessageGate(config, feishu_codex_bot.StateStore(config.state_db))
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "旧任务入口已退役"):
            gate.accept(self.event(message_id="om_artifact_edit",
                text="@_user_1 mode=edit artifact=dist/app.apk 编译"))
        self.assertEqual([], gate.store.pending())

    def test_sqlite_dedupe_survives_gate_recreation(self) -> None:
        config = self.config()
        first_store = feishu_codex_bot.StateStore(config.state_db)
        event = self.event(text="@_user_1 /status")
        first = feishu_codex_bot.MessageGate(config, first_store).accept(event)
        self.assertIsNotNone(first)
        self.assertEqual("status", first.action)
        self.assertEqual(0, first.task_id)
        second_store = feishu_codex_bot.StateStore(config.state_db)
        self.assertIsNone(feishu_codex_bot.MessageGate(config, second_store).accept(event))
        self.assertIsNone(
            feishu_codex_bot.MessageGate(config, second_store).accept(
                self.event(message_id="om_2", chat_id="oc_other")
            )
        )
        self.assertIsNone(
            feishu_codex_bot.MessageGate(config, second_store).accept(
                self.event(message_id="om_3", open_id="ou_other")
            )
        )

    def test_feishu_task_dedupe_and_task_identity_are_atomic(self) -> None:
        config, store, bot, job = self.queued_agent("atomic-request-1")
        with store._connect() as conn:
            tasks = conn.execute(
                "SELECT id,status FROM tasks WHERE message_id=?", (job.message_id,)
            ).fetchall()
            sources = conn.execute(
                "SELECT kind,value FROM task_sources WHERE task_id=?", (job.task_id,)
            ).fetchall()
        self.assertEqual(1, len(tasks))
        self.assertEqual("queued", tasks[0]["status"])
        self.assertEqual({"agent-request-sha256", "agent-policy-sha256"},
                         {row["kind"] for row in sources})
        self.assertEqual(job.task, bot.spool.get(job.task_id)["task"])
        repeated = AgentTaskIntake(config).submit_task("codex", "review", "检查测试", "atomic-request-1")
        self.assertEqual(job.task_id, repeated["id"])
        self.assertFalse(repeated["created"])
        with store._connect() as conn:
            self.assertEqual(1, conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE message_id=?", (job.message_id,)
            ).fetchone()[0])

    def test_ordinary_message_never_creates_a_legacy_paid_task(self) -> None:
        config = self.config()
        store = feishu_codex_bot.StateStore(config.state_db)
        gate = feishu_codex_bot.MessageGate(config, store)
        for _attempt in range(2):
            with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "旧任务入口已退役"):
                gate.accept(self.event())
        self.assertEqual([], store.pending())
        with store._connect() as db:
            self.assertEqual(0, db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0])

    def test_feishu_event_claim_rolls_back_when_task_insertion_fails(self) -> None:
        config = self.config()
        store = feishu_codex_bot.StateStore(config.state_db)
        # Simulate the legacy crash-window database state: tasks already has
        # this ID, but messages has no deduplication receipt yet.
        store.create_task("om_orphan", "ou_owner", "codex", "review")
        with self.assertRaises(sqlite3.IntegrityError):
            store.create_message_task(
                "om_orphan", "ou_owner", "codex", "review",
                (feishu_codex_bot.SourceRef("message", "om_orphan"),),
            )
        with store._connect() as conn:
            receipt = conn.execute(
                "SELECT COUNT(*) FROM messages WHERE message_id='om_orphan'"
            ).fetchone()[0]
            task_count = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE message_id='om_orphan'"
            ).fetchone()[0]
        self.assertEqual(0, receipt)
        self.assertEqual(1, task_count)

    def test_state_store_tracks_status_and_cancels_queued_tasks(self) -> None:
        store = feishu_codex_bot.StateStore(self.config().state_db)
        task_id = store.create_task("om_state", "ou_owner", "codex", "explain")
        self.assertEqual("queued", store.task_status(task_id))
        self.assertEqual(1, store.cancel_queued("ou_owner"))
        self.assertEqual("canceled", store.task_status(task_id))
        summary = store.summary("ou_owner")
        self.assertEqual(1, summary["counts"]["canceled"])

    def test_state_store_creates_private_db_and_refuses_unsafe_existing_state(self) -> None:
        config = self.config()
        store = feishu_codex_bot.StateStore(config.state_db)
        self.assertEqual(0o600, config.state_db.stat().st_mode & 0o777)
        store.create_task("om_private", "ou_owner", "codex", "explain")
        config.state_db.chmod(0o644)
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "0600"):
            feishu_codex_bot.StateStore(config.state_db)
        self.assertEqual(0o644, config.state_db.stat().st_mode & 0o777)
        config.state_db.chmod(0o600)
        link = self.tmp / "linked.sqlite3"
        link.symlink_to(config.state_db)
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "0600"):
            feishu_codex_bot.StateStore(link)
        self.assertEqual("queued", feishu_codex_bot.StateStore(config.state_db).task_status(1))

    def test_state_store_closes_connections_after_commit_and_rollback(self) -> None:
        store = feishu_codex_bot.StateStore(self.config().state_db)
        insert = "INSERT INTO messages (message_id, received_at) VALUES (?, ?)"
        with store._connect() as committed:
            committed.execute(insert, ("committed", 1))
        with self.assertRaises(sqlite3.ProgrammingError):
            committed.execute("SELECT 1")

        with self.assertRaisesRegex(RuntimeError, "rollback"):
            with store._connect() as rolled_back:
                rolled_back.execute(insert, ("rolled-back", 1))
                raise RuntimeError("rollback")
        with self.assertRaises(sqlite3.ProgrammingError):
            rolled_back.execute("SELECT 1")

        with store._connect() as connection:
            rows = connection.execute("SELECT message_id FROM messages").fetchall()
        self.assertEqual(["committed"], [row[0] for row in rows])

    def test_user_default_repository_persists_and_can_be_cleared(self) -> None:
        store = feishu_codex_bot.StateStore(self.config().state_db)
        self.assertEqual("", store.default_repository("ou_owner"))
        store.set_default_repository("ou_owner", "x5")
        recreated = feishu_codex_bot.StateStore(self.config().state_db)
        self.assertEqual("x5", recreated.default_repository("ou_owner"))
        self.assertEqual("", recreated.default_repository("ou_other"))
        recreated.clear_default_repository("ou_owner")
        self.assertEqual("", recreated.default_repository("ou_owner"))

    def test_repo_command_changes_only_sender_default_and_explicit_repo_wins(self) -> None:
        other = self.tmp / "other"
        other.mkdir()
        (other / ".git").mkdir()
        self.policy["repositories"]["other"] = {
            "path": str(other),
            "allowed_modes": ["explain", "review"],
            "allowed_open_ids": [],
        }
        self.write_policy()
        config = self.config()
        store = feishu_codex_bot.StateStore(config.state_db)
        gate = feishu_codex_bot.MessageGate(config, store)

        selected = gate.accept(self.event(message_id="om_repo", text="@_user_1 /repo other"))
        self.assertIsNotNone(selected)
        self.assertEqual(("set_repo", "other"), (selected.action, selected.repository))
        self.assertEqual("other", store.default_repository("ou_owner"))

        inherited = gate.accept(self.event(message_id="om_inherited", text="@_user_1 /repo"))
        self.assertIsNotNone(inherited)
        self.assertEqual("other", inherited.repository)
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "旧任务入口已退役"):
            gate.accept(self.event(message_id="om_explicit", text="@_user_1 repo=codex 检查测试"))
        self.assertEqual("other", store.default_repository("ou_owner"))
        self.assertEqual([], store.pending())

        reset = gate.accept(self.event(message_id="om_reset", text="@_user_1 /repo reset"))
        self.assertIsNotNone(reset)
        self.assertEqual(("reset_repo", "codex"), (reset.action, reset.repository))
        self.assertEqual("", store.default_repository("ou_owner"))
        self.assertEqual("codex", gate.default_repository("ou_owner"))

    def test_removed_user_default_falls_back_to_system_default(self) -> None:
        config = self.config()
        store = feishu_codex_bot.StateStore(config.state_db)
        store.set_default_repository("ou_owner", "removed")
        job = feishu_codex_bot.MessageGate(config, store).accept(self.event(text="@_user_1 /repo"))
        self.assertIsNotNone(job)
        self.assertEqual("codex", job.repository)

    def test_rate_limiter_is_per_sender_and_windowed(self) -> None:
        limiter = feishu_codex_bot.RateLimiter(2, 60)
        self.assertTrue(limiter.allow("ou_owner", now=0))
        self.assertTrue(limiter.allow("ou_owner", now=1))
        self.assertFalse(limiter.allow("ou_owner", now=2))
        self.assertTrue(limiter.allow("ou_other", now=2))
        self.assertTrue(limiter.allow("ou_owner", now=61))

    def test_outer_sandbox_uses_private_pid_namespace_and_procfs(self) -> None:
        config = self.agent_config()
        runner = feishu_codex_bot.CodexRunner(config)
        args = ["exec", "--sandbox", "read-only", "-C", str(config.workdir), "fixture"]
        cmd = runner._isolated_command(config.workdir, args, dedicated=True, writable_workdir=False)
        root = cmd.index("--ro-bind")
        proc = cmd.index("--proc")
        sep = cmd.index("--")
        self.assertIn("--unshare-pid", cmd[:root])
        self.assertEqual(["--ro-bind", "/", "/"], cmd[root:root + 3])
        self.assertGreater(proc, root + 2)
        self.assertEqual("/proc", cmd[proc + 1])
        self.assertLess(proc, sep)
        self.assertIn("--die-with-parent", cmd[:sep])
        self.assertIn("--new-session", cmd[:sep])
        for index, arg in enumerate(cmd[:sep]):
            if arg in ("--bind", "--ro-bind", "--dev-bind"):
                self.assertNotEqual("/proc", cmd[index + 1])
                self.assertNotEqual("/proc", cmd[index + 2])
        for denied in config.deny_read_paths:
            self.assertTrue(any(
                cmd[i:i + 2] == ["--tmpfs", str(denied)]
                for i in range(proc + 2, sep)
            ))
        self.assertEqual([config.codex_bin, *args], cmd[sep + 1:])
        writable = [cmd[i + 1:i + 3] for i, value in enumerate(cmd[:sep]) if value == "--bind"]
        self.assertEqual([[str(self.agent_home), str(self.agent_home)]], writable)
        self.assertIn([str(self.tmp / ".git"), str(self.tmp / ".git")],
                      [cmd[i + 1:i + 3] for i, value in enumerate(cmd[:sep]) if value == "--ro-bind"])

    def test_verification_is_offline_and_cannot_read_execution_credentials(self) -> None:
        config = self.agent_config()
        repository = dataclasses.replace(config.repository("codex"), commit_enabled=False,
                                         verification_commands=(("python", "-m", "pytest"),))
        manager = feishu_codex_bot.WorktreeManager(config)
        with tempfile.TemporaryDirectory(prefix="verification-personal-") as directory:
            personal = pathlib.Path(directory)
            for relative in (".codex", ".ssh", ".aws", ".config/gh", ".config/gcloud", ".kube", ".gnupg"):
                (personal / relative).mkdir(parents=True)
            (personal / ".git-credentials").write_text("synthetic-credential")
            (personal / ".netrc").write_text("synthetic-credential")
            unsafe_environment = {
                "PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(personal),
                "CODEX_HOME": str(personal / ".codex"), "OPENAI_API_KEY": "must-not-pass",
                "FEISHU_APP_SECRET": "must-not-pass", "FEISHU_AGENT_OPENAI_API_KEY": "must-not-pass",
                "CODEX_API_KEY": "must-not-pass", "HTTP_PROXY": "must-not-pass",
                "HTTPS_PROXY": "must-not-pass", "SSH_AUTH_SOCK": "must-not-pass",
                "PYTHONPATH": "must-not-pass",
            }
            with mock.patch.object(pathlib.Path, "home", return_value=personal), \
                    mock.patch.dict(os.environ, unsafe_environment, clear=True), \
                    mock.patch.object(manager, "snapshot", return_value="after"), \
                    mock.patch.object(feishu_codex_bot.subprocess, "run", return_value=types.SimpleNamespace(returncode=0)) as run:
                self.assertEqual("", manager.verify_and_commit(self.tmp, repository, 1, "before"))
            run.assert_called_once()
            arguments = run.call_args.args[0]
            environment = run.call_args.kwargs["env"]
            self.assertEqual(config.isolation_bin, arguments[0])
            self.assertIn("--unshare-net", arguments)
            self.assertEqual(["rtk", "proxy", "python", "-m", "pytest"], arguments[arguments.index("--") + 1:])
            binds = [arguments[i + 1:i + 3] for i, value in enumerate(arguments) if value == "--bind"]
            self.assertEqual([[str(self.tmp), str(self.tmp)]], binds)
            masks = [arguments[i + 1] for i, value in enumerate(arguments) if value == "--tmpfs"]
            for path in (config.agent_codex_home, personal / ".codex", personal / ".ssh", personal / ".aws",
                         personal / ".config/gh", personal / ".config/gcloud", personal / ".kube", personal / ".gnupg"):
                self.assertIn(str(path), masks)
            self.assertIn("/run", masks)
            readonly = [arguments[i + 1:i + 3] for i, value in enumerate(arguments) if value == "--ro-bind"]
            self.assertIn(["/dev/null", str(personal / ".netrc")], readonly)
            self.assertIn(["/dev/null", str(personal / ".git-credentials")], readonly)
            self.assertIn([str(self.tmp / ".git"), str(self.tmp / ".git")], readonly)
            self.assertNotIn("must-not-pass", environment.values())
            self.assertNotIn("CODEX_HOME", environment)
            self.assertEqual("/tmp/feishu-verification-home", environment["HOME"])
            self.assertEqual("1", environment["GIT_CONFIG_NOSYSTEM"])
            self.assertEqual("/dev/null", environment["GIT_CONFIG_GLOBAL"])

    def test_verification_sandbox_failure_never_falls_back_to_host_or_commits(self) -> None:
        config = self.config()
        manager = feishu_codex_bot.WorktreeManager(config)
        for outcome in (OSError("sandbox unavailable"), types.SimpleNamespace(returncode=1)):
            with self.subTest(outcome=type(outcome).__name__), \
                    mock.patch.object(manager, "snapshot", return_value="after"), \
                    mock.patch.object(manager, "_git") as git, \
                    mock.patch.object(feishu_codex_bot.subprocess, "run") as run:
                if isinstance(outcome, Exception):
                    run.side_effect = outcome
                else:
                    run.return_value = outcome
                with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "验证"):
                    manager.verify_and_commit(self.tmp, config.repository("codex"), 1, "before")
                run.assert_called_once()
                self.assertEqual(config.isolation_bin, run.call_args.args[0][0])
                git.assert_not_called()

    def test_codex_runner_is_read_only_fixed_to_alias_and_strips_secrets(self) -> None:
        runner = feishu_codex_bot.CodexRunner(self.agent_config())
        job = feishu_codex_bot.BotJob(
            1,
            "om_1",
            "oc_target",
            f"agent:{os.getuid()}",
            "task",
            "codex",
            "review",
            "检查仓库",
        )
        process = FakeProcess()
        with mock.patch.dict(
            feishu_codex_bot.os.environ,
            {"FEISHU_APP_SECRET": "must-not-leak", "CODEX_API_KEY": "personal-must-not-leak",
             "OPENAI_API_KEY": "personal-api-must-not-leak"},
            clear=True,
        ), mock.patch.object(feishu_codex_bot.subprocess, "Popen", return_value=process) as popen:
            self.assertEqual("完成", runner.run(job).text)
        command = popen.call_args.args[0]
        child_env = popen.call_args.kwargs["env"]
        self.assertIn("--sandbox", command)
        self.assertIn("read-only", command)
        self.assertIn("--tmpfs", command)
        self.assertIn(str(self.tmp / "mcp/secrets"), command)
        self.assertIn("-C", command)
        self.assertIn(str(self.tmp), command)
        self.assertNotIn("FEISHU_APP_SECRET", child_env)
        self.assertNotIn("CODEX_API_KEY", child_env)
        self.assertEqual(self.agent_key, child_env["OPENAI_API_KEY"])
        self.assertEqual(str(self.agent_home), child_env["HOME"])
        self.assertEqual(str(self.agent_home), child_env["CODEX_HOME"])
        self.assertEqual("core.hooksPath", child_env["GIT_CONFIG_KEY_0"])
        self.assertEqual("never", child_env["GIT_CONFIG_VALUE_1"])

    def test_agent_intake_rejects_in_place_edit_before_execution(self) -> None:
        self.policy["repositories"]["codex"].update(
            {
                "allowed_modes": ["explain", "review", "edit"],
                "verification_commands": [["git", "diff", "--check"]],
            }
        )
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "隔离 worktree"):
            self.agent_config()
        # Recheck at the execution boundary even for a directly constructed
        # configuration that did not pass through the file loader.
        self.policy["repositories"]["codex"]["agent_allowed_modes"] = ["explain", "review"]
        self.write_policy()
        base = self.config()
        unsafe = dataclasses.replace(base, repositories={"codex": dataclasses.replace(
            base.repository("codex"), agent_allowed_modes=frozenset(("explain", "review", "edit")))})
        intake = AgentTaskIntake(unsafe)
        with mock.patch.object(feishu_codex_bot.subprocess, "Popen") as popen:
            with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "worktree 隔离"):
                intake.submit_task("codex", "edit", "修复问题", "in-place-refused")
            runner = feishu_codex_bot.CodexRunner(unsafe)
            job = feishu_codex_bot.BotJob(8, "agent:fixture", "oc_target", f"agent:{os.getuid()}",
                                         "task", "codex", "edit", "修复问题")
            with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "worktree 隔离"):
                runner.run(job)
        popen.assert_not_called()
        self.assertEqual([], intake.store.pending())

    def test_artifact_edit_allows_build_only_and_prompts_for_exact_output(self) -> None:
        self.policy["repositories"]["codex"].update(
            {
                "allowed_modes": ["edit"],
                "edit_strategy": "worktree",
                "worktree_root": str(self.tmp.parent / f"{self.tmp.name}-worktrees"),
                "commit_enabled": True,
                "artifact_upload": {
                    "enabled": True,
                    "allowed_roots": ["dist"],
                    "allowed_extensions": [".apk"],
                },
            }
        )
        self.write_policy()
        runner = feishu_codex_bot.CodexRunner(self.agent_config())
        runner.worktrees = mock.Mock()
        runner.worktrees.prepare.return_value = (self.tmp, "")
        runner.worktrees.snapshot.return_value = "unchanged"
        runner.worktrees.verify_and_commit.return_value = ""
        job = feishu_codex_bot.BotJob(
            10,
            "om_10",
            "oc_target",
            f"agent:{os.getuid()}",
            "task",
            "codex",
            "edit",
            "只执行构建",
            artifact="dist/app.apk",
        )
        with mock.patch.object(
            feishu_codex_bot.subprocess,
            "Popen",
            return_value=FakeProcess("构建完成\n"),
        ) as popen:
            runner.run(job)
        runner.worktrees.verify_and_commit.assert_called_once_with(
            self.tmp,
            self.config().repository("codex"),
            10,
            "unchanged",
            allow_unchanged=True,
        )
        self.assertTrue(
            any("dist/app.apk" in str(argument) for argument in popen.call_args.args[0])
        )

    def test_explicit_worktree_mode_records_local_commit(self) -> None:
        hooks = self.tmp / "hooks"
        hooks.mkdir()
        hook = hooks / "pre-push"
        hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        hook.chmod(0o755)
        self.policy["deny_push_hooks_path"] = str(hooks)
        self.policy["repositories"]["codex"].update(
            {
                "allowed_modes": ["explain", "review", "edit"],
                "edit_strategy": "worktree",
                "worktree_root": str(self.tmp.parent / f"{self.tmp.name}-worktrees"),
                "verification_commands": [["git", "diff", "--check"]],
            }
        )
        self.write_policy()
        runner = feishu_codex_bot.CodexRunner(self.agent_config())
        worktree = self.tmp.parent / f"{self.tmp.name}-worktrees" / "task-9"
        runner.worktrees = mock.Mock()
        runner.worktrees.prepare.return_value = (worktree, "codex/feishu-9")
        runner.worktrees.snapshot.return_value = "before"
        runner.worktrees.verify_and_commit.return_value = "a" * 40
        job = feishu_codex_bot.BotJob(
            9, "om_9", "oc_target", f"agent:{os.getuid()}", "task", "codex", "edit", "修复问题"
        )
        process = FakeProcess("已修改\n")
        with mock.patch.object(feishu_codex_bot.subprocess, "Popen", return_value=process) as popen:
            result = runner.run(job)
        self.assertEqual("codex/feishu-9", result.branch_name)
        self.assertEqual("a" * 40, result.commit_hash)
        self.assertIn("未执行 push", result.text)
        self.assertIn("workspace-write", popen.call_args.args[0])
        self.assertEqual(str(worktree), popen.call_args.kwargs["cwd"])
        self.assertTrue(
            any("当前隔离 worktree" in str(argument) for argument in popen.call_args.args[0])
        )

    def test_worktree_manager_creates_branch_and_local_commit(self) -> None:
        repository = self.tmp / "real-repo"
        subprocess.run(["rtk", "git", "init", str(repository)], check=True, capture_output=True, text=True)
        subprocess.run(
            ["rtk", "git", "-C", str(repository), "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "--allow-empty", "-m", "init"],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(["rtk", "git", "-C", str(repository), "config", "user.name", "Test"], check=True)
        subprocess.run(["rtk", "git", "-C", str(repository), "config", "user.email", "test@example.com"], check=True)
        hooks = self.tmp / "hooks-real"
        hooks.mkdir()
        hook = hooks / "pre-push"
        hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        hook.chmod(0o755)
        self.policy["default_repo"] = "real"
        self.policy["deny_push_hooks_path"] = str(hooks)
        self.policy["repositories"]["real"] = {
            "path": str(repository),
            "allowed_modes": ["edit"],
            "allowed_open_ids": [],
            "edit_strategy": "worktree",
            "worktree_root": str(self.tmp / "worktrees"),
            "verification_commands": [["git", "diff", "--check"]],
        }
        self.write_policy()
        config = self.config()
        manager = feishu_codex_bot.WorktreeManager(config)
        worktree, branch = manager.create(23, config.repository("real"))
        before_snapshot = manager.snapshot(worktree)
        (worktree / "change.txt").write_text("safe change\n", encoding="utf-8")
        with self.sandboxed_git_checks(config):
            commit_hash = manager.verify_and_commit(
                worktree,
                config.repository("real"),
                23,
                before_snapshot,
            )
        self.assertEqual("codex/feishu-23", branch)
        self.assertRegex(commit_hash, r"^[0-9a-f]{40}$")
        self.assertEqual("", manager._git(repository, ["status", "--porcelain"]))

        # The real Git fixture exercises continuing the exact original branch,
        # not a fresh worktree and not only mocked identity checks.
        policy = config.repository("real")
        target = feishu_codex_bot.ResumeTarget(
            "01979c6c-0354-7000-8000-000000000001", worktree, 23, branch, commit_hash,
        )
        manager.require_resume_base(target, policy)
        before = manager.snapshot(worktree)
        (worktree / "change.txt").write_text("second verified change\n", encoding="utf-8")
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "uncommitted changes"):
            manager.require_resume_base(target, policy)
        manager.require_resume_base(target, policy, clean=False)
        with self.sandboxed_git_checks(config):
            second_commit = manager.verify_and_commit(worktree, policy, 24, before)
        self.assertNotEqual(commit_hash, second_commit)
        self.assertEqual(commit_hash, manager._git(worktree, ["rev-parse", "HEAD^"]))
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "HEAD changed"):
            manager.require_resume_base(target, policy)
        manager.require_resume_base(
            feishu_codex_bot.ResumeTarget(target.thread_id, worktree, 23, branch, second_commit),
            policy,
        )
        self.assertEqual("", manager._git(repository, ["status", "--porcelain"]))

    def test_in_place_manager_detects_change_without_committing_dirty_workspace(self) -> None:
        repository = self.tmp / "direct-repo"
        subprocess.run(["rtk", "git", "init", str(repository)], check=True, capture_output=True, text=True)
        tracked = repository / "tracked.txt"
        tracked.write_text("base\n", encoding="utf-8")
        subprocess.run(["rtk", "git", "-C", str(repository), "add", "tracked.txt"], check=True)
        subprocess.run(
            [
                "rtk",
                "git",
                "-C",
                str(repository),
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.com",
                "commit",
                "-m",
                "init",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        self.policy["default_repo"] = "direct"
        self.policy["repositories"]["direct"] = {
            "path": str(repository),
            "allowed_modes": ["edit"],
            "allowed_open_ids": [],
            "verification_commands": [["git", "diff", "--check"]],
        }
        self.write_policy()
        config = self.config()
        manager = feishu_codex_bot.WorktreeManager(config)
        working_directory, branch = manager.prepare(24, config.repository("direct"))
        tracked.write_text("user change\n", encoding="utf-8")
        before_snapshot = manager.snapshot(working_directory)
        tracked.write_text("assistant change\n", encoding="utf-8")
        head_before = manager._git(repository, ["rev-parse", "HEAD"])
        with self.sandboxed_git_checks(config):
            self.assertEqual(
                "",
                manager.verify_and_commit(
                    working_directory,
                    config.repository("direct"),
                    24,
                    before_snapshot,
                ),
            )
        self.assertEqual("", branch)
        self.assertEqual(head_before, manager._git(repository, ["rev-parse", "HEAD"]))
        self.assertIn("tracked.txt", manager._git(repository, ["status", "--porcelain"]))

    def test_command_parser_tracks_feishu_sources(self) -> None:
        command = feishu_codex_bot.parse_command(
            "mode=edit task=guid-1 requirement=REQ-2 defect=BUG-3 log=om_4 修复崩溃",
            "pcr02-demo",
        )
        self.assertEqual("edit", command.mode)
        self.assertEqual("pcr02-demo", command.repository)
        self.assertEqual("修复崩溃", command.task)
        self.assertEqual(
            (("task", "guid-1"), ("requirement", "REQ-2"), ("defect", "BUG-3"), ("log", "om_4")),
            tuple((source.kind, source.value) for source in command.sources),
        )

    def test_artifact_manager_validates_file_snapshot_and_rejects_symlink(self) -> None:
        dist = self.tmp / "dist"
        dist.mkdir()
        apk = dist / "app.apk"
        apk.write_bytes(b"apk-content")
        self.policy["repositories"]["codex"].update(
            {
                "allowed_modes": ["edit"],
                "artifact_upload": {
                    "enabled": True,
                    "allowed_roots": ["dist"],
                    "allowed_extensions": [".apk"],
                    "max_bytes": 1024,
                },
            }
        )
        self.write_policy()
        repository = self.config().repository("codex")
        artifact = feishu_codex_bot.ArtifactManager.prepare(
            repository,
            self.tmp,
            "dist/app.apk",
        )
        self.assertEqual("app.apk", artifact.file_name)
        self.assertEqual(len(b"apk-content"), artifact.size)
        self.assertEqual(
            __import__("hashlib").sha256(b"apk-content").hexdigest(),
            artifact.sha256,
        )
        apk.write_bytes(b"changed-after-validation")
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "验证后发生变化"):
            object.__new__(feishu_codex_bot.FeishuTransport).send_file(
                "oc_target",
                artifact,
                "om_source",
            )
        empty = dist / "empty.apk"
        empty.touch()
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "不能为空"):
            feishu_codex_bot.ArtifactManager.prepare(
                repository,
                self.tmp,
                "dist/empty.apk",
            )
        large = dist / "large.apk"
        large.write_bytes(b"x" * 1025)
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "超过大小上限"):
            feishu_codex_bot.ArtifactManager.prepare(
                repository,
                self.tmp,
                "dist/large.apk",
            )

        target = self.tmp / "other.apk"
        target.write_bytes(b"outside")
        (dist / "link.apk").symlink_to(target)
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "符号链接"):
            feishu_codex_bot.ArtifactManager.prepare(
                repository,
                self.tmp,
                "dist/link.apk",
            )
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "扩展名"):
            feishu_codex_bot.ArtifactManager.prepare(
                repository,
                self.tmp,
                "dist/app.txt",
            )

    def test_transport_uploads_stream_then_replies_with_file_key(self) -> None:
        dist = self.tmp / "dist"
        dist.mkdir()
        (dist / "app.apk").write_bytes(b"apk-content")
        self.policy["repositories"]["codex"].update(
            {
                "allowed_modes": ["edit"],
                "artifact_upload": {
                    "enabled": True,
                    "allowed_roots": ["dist"],
                    "allowed_extensions": [".apk"],
                },
            }
        )
        self.write_policy()
        artifact = feishu_codex_bot.ArtifactManager.prepare(
            self.config().repository("codex"),
            self.tmp,
            "dist/app.apk",
        )
        transport = feishu_codex_bot.FeishuTransport(self.config())
        upload_response = mock.Mock()
        upload_response.success.return_value = True
        upload_response.data = types.SimpleNamespace(file_key="file_test")
        reply_response = mock.Mock()
        reply_response.success.return_value = True
        def upload(request: object) -> object:
            self.assertEqual("stream", request.body.file_type)
            self.assertEqual("app.apk", request.body.file_name)
            self.assertEqual(b"apk-content", request.body.file.read())
            return upload_response

        file_create = mock.Mock(side_effect=upload)
        message_reply = mock.Mock(return_value=reply_response)
        transport.client = types.SimpleNamespace(
            im=types.SimpleNamespace(
                v1=types.SimpleNamespace(
                    file=types.SimpleNamespace(create=file_create),
                    message=types.SimpleNamespace(reply=message_reply),
                )
            )
        )

        transport.send_file("oc_target", artifact, "om_source")

        file_create.assert_called_once()
        message_reply.assert_called_once()
        reply_request = message_reply.call_args.args[0]
        self.assertEqual("file", reply_request.body.msg_type)
        self.assertTrue(reply_request.body.reply_in_thread)
        payload = json.loads(reply_request.body.content)
        self.assertEqual(
            {"file_key": "file_test", "file_name": "app.apk"},
            payload,
        )

    def test_bot_delivers_only_declared_prepared_artifact(self) -> None:
        dist = self.tmp / "dist"
        dist.mkdir()
        (dist / "app.apk").write_bytes(b"apk-content")
        self.policy["repositories"]["codex"].update(
            {
                "allowed_modes": ["edit"],
                "artifact_upload": {
                    "enabled": True,
                    "allowed_roots": ["dist"],
                    "allowed_extensions": [".apk"],
                },
            }
        )
        self.write_policy()
        config = self.config()
        transport = mock.Mock()
        bot = feishu_codex_bot.FeishuCodexBot(
            config,
            transport,
            mock.Mock(),
            feishu_codex_bot.StateStore(config.state_db),
        )
        job = feishu_codex_bot.BotJob(
            31,
            "om_31",
            "oc_target",
            "ou_owner",
            "task",
            "codex",
            "edit",
            "编译",
            artifact="dist/app.apk",
        )
        prepared = bot._send_artifact(
            job,
            feishu_codex_bot.ExecutionResult("完成", worktree_path=self.tmp),
        )
        self.assertEqual("app.apk", prepared.file_name)
        transport.send_file.assert_called_once_with("oc_target", prepared, "om_31")
        self.assertIn("sha256=", transport.send_text.call_args.args[1])

    def test_running_process_can_only_be_canceled_by_owner(self) -> None:
        runner = feishu_codex_bot.CodexRunner(self.config())
        owner_process = FakeProcess()
        other_process = FakeProcess()
        runner._running = {1: ("ou_owner", owner_process), 2: ("ou_other", other_process)}
        self.assertEqual(1, runner.cancel_sender("ou_owner"))
        self.assertTrue(owner_process.terminated)
        self.assertFalse(other_process.terminated)

    def test_long_replies_are_chunked_with_sequence_headers(self) -> None:
        chunks = feishu_codex_bot.split_reply("x" * 1200, 500)
        self.assertEqual(3, len(chunks))
        self.assertTrue(chunks[0].startswith("[1/3]"))
        self.assertTrue(all(len(chunk) <= 500 for chunk in chunks))

    def test_single_instance_lock_rejects_second_owner(self) -> None:
        first = feishu_codex_bot.SingleInstanceLock(self.tmp / "instance.lock")
        second = feishu_codex_bot.SingleInstanceLock(self.tmp / "instance.lock")
        first.acquire()
        self.addCleanup(first.release)
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "已有"):
            second.acquire()

    def test_send_test_requires_explicit_confirmation(self) -> None:
        args = self.env_args("send-test")
        fake_transport = mock.Mock()
        with mock.patch.object(feishu_codex_bot, "FeishuTransport", return_value=fake_transport):
            with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "外部写操作"):
                feishu_codex_bot.run(args)
        fake_transport.send_text.assert_not_called()

    def test_discover_owner_only_prints_sender_from_target_chat(self) -> None:
        args = self.env_args("discover-owner")
        fake_transport = mock.Mock()

        def start(callback: object) -> None:
            callback(self.event())
            callback(self.event(message_id="om_2", chat_id="oc_other"))

        fake_transport.start.side_effect = start
        with mock.patch.object(feishu_codex_bot, "FeishuTransport", return_value=fake_transport), mock.patch("builtins.print") as output:
            self.assertEqual(0, feishu_codex_bot.run(args))
        rendered = [call.args[0] for call in output.call_args_list if call.args]
        self.assertIn("FEISHU_ALLOWED_OPEN_IDS=ou_owner", rendered)

    def test_transport_uses_error_log_level_to_avoid_connection_ticket_logs(self) -> None:
        transport = object.__new__(feishu_codex_bot.FeishuTransport)
        transport.config = self.config()
        transport.lark = types.SimpleNamespace(
            LogLevel=types.SimpleNamespace(ERROR="error"),
            EventDispatcherHandler=builder_factory(),
            ws=types.SimpleNamespace(Client=mock.Mock()),
        )
        transport.start(mock.Mock())
        self.assertEqual("error", transport.lark.ws.Client.call_args.kwargs["log_level"])


    def test_private_spool_replays_only_queued_after_restart(self) -> None:
        config, store, first, original = self.queued_agent("queued-restart-1")
        restarted = feishu_codex_bot.FeishuCodexBot(
            config, mock.Mock(), mock.Mock(), feishu_codex_bot.StateStore(config.state_db)
        )
        restarted.recover_pending()
        recovered = restarted.jobs.get_nowait()
        self.assertEqual((original.task_id, original.task), (recovered.task_id, recovered.task))
        self.assertEqual("queued", restarted.store.task_status(original.task_id))
        self.assertFalse(restarted.jobs.qsize())
        restarted.refill_pending()
        self.assertEqual(0, restarted.jobs.qsize())  # no duplicate enqueue

    def test_running_is_unknown_and_never_replayed_after_restart(self) -> None:
        config, store, bot, job = self.queued_agent("running-restart-1")
        self.assertTrue(store.claim_queued(job.task_id))
        restarted = feishu_codex_bot.FeishuCodexBot(
            config, mock.Mock(), mock.Mock(), feishu_codex_bot.StateStore(config.state_db)
        )
        restarted.recover_pending()
        self.assertEqual("unknown", restarted.store.task_status(job.task_id))
        self.assertEqual(0, restarted.jobs.qsize())
        self.assertFalse((restarted.spool.root / f"{job.task_id}.json").exists())
        restarted.transport.send_text.assert_called_once()
        restarted.recover_pending()
        self.assertEqual(1, restarted.transport.send_text.call_count)

    def test_legacy_queued_without_spool_is_unknown_not_automatically_retried(self) -> None:
        config = self.config()
        store = feishu_codex_bot.StateStore(config.state_db)
        task_id = store.create_task("om_old", "ou_owner", "codex", "explain")
        bot = feishu_codex_bot.FeishuCodexBot(config, mock.Mock(), mock.Mock(), store)
        bot.recover_pending()
        self.assertEqual("unknown", store.task_status(task_id))
        self.assertEqual(0, bot.jobs.qsize())

    def test_queued_spool_rechecks_policy_and_permissions(self) -> None:
        config, store, bot, job = self.queued_agent("changed-policy-1")
        self.policy["repositories"]["codex"]["agent_allowed_modes"] = ["explain"]
        self.write_policy()
        changed = feishu_codex_bot.FeishuCodexBot(
            self.config(), mock.Mock(), mock.Mock(), store
        )
        changed.recover_pending()
        self.assertEqual("unknown", store.task_status(job.task_id))
        self.assertEqual(0, changed.jobs.qsize())

    def test_spool_rejects_world_readable_payload_and_foreign_file(self) -> None:
        config, store, bot, job = self.queued_agent("private-payload-1")
        path = bot.spool.root / f"{job.task_id}.json"
        self.assertEqual(0, path.stat().st_mode & 0o077)
        path.chmod(0o644)
        bot.recover_pending()
        self.assertEqual("unknown", store.task_status(job.task_id))
        self.assertEqual(0, bot.jobs.qsize())


    def test_non_task_commands_can_queue_without_zero_id_collision(self) -> None:
        config = self.config()
        bot = feishu_codex_bot.FeishuCodexBot(
            config, mock.Mock(), mock.Mock(), feishu_codex_bot.StateStore(config.state_db)
        )
        first = feishu_codex_bot.BotJob(0, "om_help", "oc_target", "ou_owner", "help", "codex", "explain", "")
        second = feishu_codex_bot.BotJob(0, "om_status", "oc_target", "ou_owner", "status", "codex", "explain", "")
        self.assertTrue(bot._schedule(first))
        self.assertTrue(bot._schedule(second))
        self.assertEqual(2, bot.jobs.qsize())

    def test_poll_grace_does_not_race_with_new_incoming_task(self) -> None:
        config = self.config()
        store = feishu_codex_bot.StateStore(config.state_db)
        task_id = store.create_task("om_grace", "ou_owner", "codex", "explain")
        bot = feishu_codex_bot.FeishuCodexBot(config, mock.Mock(), mock.Mock(), store)
        bot.refill_pending()
        self.assertEqual("queued", store.task_status(task_id))
        self.assertEqual(0, bot.jobs.qsize())
        bot.recover_pending()
        self.assertEqual("unknown", store.task_status(task_id))


    def test_unattended_worktree_rejects_sensitive_untracked_before_staging(self) -> None:
        repo_path = self.tmp / "sensitive-repo"
        subprocess.run(["rtk", "git", "init", str(repo_path)], check=True, capture_output=True)
        subprocess.run(
            ["rtk", "git", "-C", str(repo_path), "-c", "user.name=Test",
             "-c", "user.email=test@example.com", "commit", "--allow-empty", "-m", "start"],
            check=True, capture_output=True,
        )
        self.policy["default_repo"] = "sensitive"
        self.policy["repositories"]["sensitive"] = {
            "path": str(repo_path),
            "allowed_modes": ["edit"],
            "edit_strategy": "worktree",
            "worktree_root": str(self.tmp / "sensitive-worktrees"),
            "verification_commands": [["git", "diff", "--check"]],
        }
        self.write_policy()
        cfg = self.config()
        manager = feishu_codex_bot.WorktreeManager(cfg)
        isolated, _branch = manager.create(77, cfg.repository("sensitive"))
        original = manager.snapshot(isolated)
        private = isolated / ".env.local"
        private.write_text("TOKEN=private-test-value\n", encoding="utf-8")
        with self.sandboxed_git_checks(cfg):
            with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "敏感"):
                manager.verify_and_commit(isolated, cfg.repository("sensitive"), 77, original)
        self.assertEqual("?? .env.local", manager._git(isolated, ["status", "--short"]))
        self.assertEqual("", manager._git(isolated, ["diff", "--cached", "--name-only"]))

    def test_unattended_stage_rejects_untracked_symlink_and_large_file(self) -> None:
        manager = feishu_codex_bot.WorktreeManager(self.config())
        with mock.patch.object(manager, "_git", side_effect=[
            "external\n\0", "",  # untracked and modified
        ]):
            (self.tmp / "external").symlink_to(self.tmp / "missing-target")
            with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "未跟踪文件"):
                manager._check_safe_stage(self.tmp)
        (self.tmp / "external").unlink()
        (self.tmp / "large.dat").write_bytes(b"x")
        with mock.patch.object(manager, "_git", side_effect=[
            "large.dat\0", "",
        ]), mock.patch.object(feishu_codex_bot.pathlib.Path, "lstat", autospec=True) as stat_call:
            # Synthetic giant file; never allocate or read 64 MiB in a test.
            stat_call.return_value.st_mode = feishu_codex_bot.stat.S_IFREG | 0o600
            stat_call.return_value.st_nlink = 1
            stat_call.return_value.st_size = 65 * 1024 * 1024
            with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "未跟踪文件"):
                manager._check_safe_stage(self.tmp)

    def test_codex_timeout_is_unknown_not_normal_failure(self) -> None:
        cfg = self.agent_config()
        runner = feishu_codex_bot.CodexRunner(cfg)
        job = feishu_codex_bot.BotJob(
            41, "om_timeout", "oc_target", f"agent:{os.getuid()}", "task", "codex", "review", "检查问题"
        )
        process = FakeProcess()
        process.communicate = mock.Mock(
            side_effect=subprocess.TimeoutExpired(cmd=["codex"], timeout=0.5)
        )
        clock = [0]
        def advanced_clock() -> float:
            # Other Python internals can call the mocked clock too; a growing
            # value avoids StopIteration and still makes the timeout deterministic.
            clock[0] += 10000
            return float(clock[0])
        with mock.patch.object(
            feishu_codex_bot.subprocess, "Popen", return_value=process,
        ), mock.patch.object(feishu_codex_bot.time, "monotonic", side_effect=advanced_clock):
            with self.assertRaises(feishu_codex_bot.CodexOutcomeUnknown):
                runner.run(job)
        self.assertTrue(process.terminated)

    def test_worker_records_unknown_and_does_not_retry_timeout(self) -> None:
        cfg, store, _queued_bot, job = self.queued_agent("unknown-timeout-1", "只读检查")
        task_id = job.task_id
        transport = mock.Mock()
        transport.resolve_sources.return_value = ""
        runner = mock.Mock()
        runner.run.side_effect = feishu_codex_bot.CodexOutcomeUnknown("timeout")
        bot = feishu_codex_bot.FeishuCodexBot(cfg, transport, runner, store)
        with mock.patch.object(bot.jobs, "get", side_effect=[job, SystemExit]), mock.patch.object(bot.jobs, "task_done"):
            with self.assertRaises(SystemExit):
                bot.worker()
        self.assertEqual("unknown", store.task_status(task_id))
        self.assertEqual(1, runner.run.call_count)

    def test_retired_sender_cannot_launch_runner_or_worker(self) -> None:
        cfg = self.agent_config()
        store = feishu_codex_bot.StateStore(cfg.state_db)
        task_id = store.create_task("om_retired", "ou_owner", "codex", "review")
        job = feishu_codex_bot.BotJob(task_id, "om_retired", "oc_target", "ou_owner",
                                    "task", "codex", "review", "只读检查")
        runner = feishu_codex_bot.CodexRunner(cfg)
        with mock.patch.object(feishu_codex_bot.subprocess, "Popen") as popen:
            with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "共享执行身份已退役"):
                runner.run(job)
        popen.assert_not_called()
        fake_runner = mock.Mock()
        bot = feishu_codex_bot.FeishuCodexBot(cfg, mock.Mock(), fake_runner, store)
        with mock.patch.object(bot.jobs, "get", side_effect=[job, SystemExit]), mock.patch.object(bot.jobs, "task_done"):
            with self.assertRaises(SystemExit):
                bot.worker()
        fake_runner.run.assert_not_called()
        self.assertEqual("unknown", store.task_status(task_id))

    def test_completed_model_with_lost_git_receipt_stays_unknown_after_restart(self) -> None:
        self.policy["repositories"]["codex"].update({
            "allowed_modes": ["edit"], "edit_strategy": "worktree", "commit_enabled": True,
            "worktree_root": str(self.tmp.parent / f"{self.tmp.name}-worktrees"),
        })
        cfg, store, bot, job = self.queued_agent("lost-git-receipt-1", "修复测试", "edit")
        bot.transport.resolve_sources.return_value = ""
        bot.runner.run.return_value = feishu_codex_bot.ExecutionResult(
            "修复完成", branch_name=f"codex/feishu-{job.task_id}", commit_hash="a" * 40,
            worktree_path=cfg.repository("codex").worktree_root / f"task-{job.task_id}")
        with mock.patch.object(store, "record_result", side_effect=sqlite3.OperationalError("fixture disk error")), \
                mock.patch.object(bot.jobs, "get", side_effect=[job, SystemExit]), \
                mock.patch.object(bot.jobs, "task_done"):
            with self.assertRaises(SystemExit):
                bot.worker()
        self.assertEqual("unknown", store.task_status(job.task_id))
        bot.runner.run.assert_called_once()
        restarted = feishu_codex_bot.FeishuCodexBot(cfg, mock.Mock(), mock.Mock(), store)
        restarted.recover_pending()
        self.assertEqual("unknown", store.task_status(job.task_id))
        self.assertEqual(0, restarted.jobs.qsize())
        repeated = AgentTaskIntake(cfg).submit_task("codex", "edit", "修复测试", "lost-git-receipt-1")
        self.assertEqual(job.task_id, repeated["id"])
        self.assertEqual("unknown", repeated["status"])
        self.assertFalse(repeated["created"])


def dataclass_values(command: feishu_codex_bot.ParsedCommand) -> object:
    return command.action, command.repository, command.mode, command.task


def builder_factory() -> object:
    handler = mock.Mock()
    handler.register_p2_im_message_receive_v1.return_value = handler
    handler.build.return_value = object()
    return types.SimpleNamespace(builder=mock.Mock(return_value=handler))


if __name__ == "__main__":
    unittest.main()
