from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import tempfile
import types
import unittest
from unittest import mock

from tools.codex_assets import feishu_codex_bot


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

    def write_policy(self) -> None:
        self.policy_path.write_text(json.dumps(self.policy), encoding="utf-8")
        self.policy_path.chmod(0o600)

    def config(self) -> feishu_codex_bot.BotConfig:
        return feishu_codex_bot.BotConfig.from_values(self.values, self.tmp)

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
        job = gate.accept(
            self.event(
                message_id="om_artifact_edit",
                text="@_user_1 mode=edit artifact=dist/app.apk 编译",
            )
        )
        self.assertIsNotNone(job)
        self.assertEqual("dist/app.apk", job.artifact)

    def test_sqlite_dedupe_survives_gate_recreation(self) -> None:
        config = self.config()
        first_store = feishu_codex_bot.StateStore(config.state_db)
        first = feishu_codex_bot.MessageGate(config, first_store).accept(self.event())
        self.assertIsNotNone(first)
        self.assertEqual("检查测试", first.task)
        second_store = feishu_codex_bot.StateStore(config.state_db)
        self.assertIsNone(feishu_codex_bot.MessageGate(config, second_store).accept(self.event()))
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

    def test_state_store_tracks_status_and_cancels_queued_tasks(self) -> None:
        store = feishu_codex_bot.StateStore(self.config().state_db)
        task_id = store.create_task("om_state", "ou_owner", "codex", "explain")
        self.assertEqual("queued", store.task_status(task_id))
        self.assertEqual(1, store.cancel_queued("ou_owner"))
        self.assertEqual("canceled", store.task_status(task_id))
        summary = store.summary("ou_owner")
        self.assertEqual(1, summary["counts"]["canceled"])

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

        inherited = gate.accept(self.event(message_id="om_inherited"))
        self.assertIsNotNone(inherited)
        self.assertEqual("other", inherited.repository)
        explicit = gate.accept(
            self.event(message_id="om_explicit", text="@_user_1 repo=codex 检查测试")
        )
        self.assertIsNotNone(explicit)
        self.assertEqual("codex", explicit.repository)

        reset = gate.accept(self.event(message_id="om_reset", text="@_user_1 /repo reset"))
        self.assertIsNotNone(reset)
        self.assertEqual(("reset_repo", "codex"), (reset.action, reset.repository))
        self.assertEqual("", store.default_repository("ou_owner"))
        self.assertEqual("codex", gate.default_repository("ou_owner"))

    def test_removed_user_default_falls_back_to_system_default(self) -> None:
        config = self.config()
        store = feishu_codex_bot.StateStore(config.state_db)
        store.set_default_repository("ou_owner", "removed")
        job = feishu_codex_bot.MessageGate(config, store).accept(self.event())
        self.assertIsNotNone(job)
        self.assertEqual("codex", job.repository)

    def test_rate_limiter_is_per_sender_and_windowed(self) -> None:
        limiter = feishu_codex_bot.RateLimiter(2, 60)
        self.assertTrue(limiter.allow("ou_owner", now=0))
        self.assertTrue(limiter.allow("ou_owner", now=1))
        self.assertFalse(limiter.allow("ou_owner", now=2))
        self.assertTrue(limiter.allow("ou_other", now=2))
        self.assertTrue(limiter.allow("ou_owner", now=61))

    def test_codex_runner_is_read_only_fixed_to_alias_and_strips_secrets(self) -> None:
        runner = feishu_codex_bot.CodexRunner(self.config())
        job = feishu_codex_bot.BotJob(
            1,
            "om_1",
            "oc_target",
            "ou_owner",
            "task",
            "codex",
            "review",
            "检查仓库",
        )
        process = FakeProcess()
        with mock.patch.dict(
            feishu_codex_bot.os.environ,
            {"FEISHU_APP_SECRET": "must-not-leak", "CODEX_API_KEY": "keep-for-codex"},
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
        self.assertEqual("keep-for-codex", child_env["CODEX_API_KEY"])
        self.assertEqual("core.hooksPath", child_env["GIT_CONFIG_KEY_0"])
        self.assertEqual("never", child_env["GIT_CONFIG_VALUE_1"])

    def test_edit_mode_defaults_to_in_place_without_branch_or_commit(self) -> None:
        self.policy["repositories"]["codex"].update(
            {
                "allowed_modes": ["explain", "review", "edit"],
                "verification_commands": [["git", "diff", "--check"]],
            }
        )
        self.write_policy()
        runner = feishu_codex_bot.CodexRunner(self.config())
        runner.worktrees = mock.Mock()
        runner.worktrees.prepare.return_value = (self.tmp, "")
        runner.worktrees.snapshot.return_value = "before"
        runner.worktrees.verify_and_commit.return_value = ""
        job = feishu_codex_bot.BotJob(
            8, "om_8", "oc_target", "ou_owner", "task", "codex", "edit", "修复问题"
        )
        process = FakeProcess("已修改\n")
        with mock.patch.object(feishu_codex_bot.subprocess, "Popen", return_value=process) as popen:
            result = runner.run(job)
        repository = self.config().repository("codex")
        self.assertEqual("", result.branch_name)
        self.assertEqual("", result.commit_hash)
        self.assertIn("直接修改", result.text)
        self.assertIn("未创建分支，未提交", result.text)
        self.assertIn("workspace-write", popen.call_args.args[0])
        self.assertEqual(str(self.tmp), popen.call_args.kwargs["cwd"])
        self.assertTrue(
            any("当前仓库工作目录" in str(argument) for argument in popen.call_args.args[0])
        )
        runner.worktrees.prepare.assert_called_once_with(8, repository)
        runner.worktrees.verify_and_commit.assert_called_once_with(
            self.tmp,
            repository,
            8,
            "before",
            allow_unchanged=False,
        )

    def test_artifact_edit_allows_build_only_and_prompts_for_exact_output(self) -> None:
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
        runner = feishu_codex_bot.CodexRunner(self.config())
        runner.worktrees = mock.Mock()
        runner.worktrees.prepare.return_value = (self.tmp, "")
        runner.worktrees.snapshot.return_value = "unchanged"
        runner.worktrees.verify_and_commit.return_value = ""
        job = feishu_codex_bot.BotJob(
            10,
            "om_10",
            "oc_target",
            "ou_owner",
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
        runner = feishu_codex_bot.CodexRunner(self.config())
        worktree = self.tmp.parent / f"{self.tmp.name}-worktrees" / "task-9"
        runner.worktrees = mock.Mock()
        runner.worktrees.prepare.return_value = (worktree, "codex/feishu-9")
        runner.worktrees.snapshot.return_value = "before"
        runner.worktrees.verify_and_commit.return_value = "a" * 40
        job = feishu_codex_bot.BotJob(
            9, "om_9", "oc_target", "ou_owner", "task", "codex", "edit", "修复问题"
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
        commit_hash = manager.verify_and_commit(
            worktree,
            config.repository("real"),
            23,
            before_snapshot,
        )
        self.assertEqual("codex/feishu-23", branch)
        self.assertRegex(commit_hash, r"^[0-9a-f]{40}$")
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


def dataclass_values(command: feishu_codex_bot.ParsedCommand) -> object:
    return command.action, command.repository, command.mode, command.task


def builder_factory() -> object:
    handler = mock.Mock()
    handler.register_p2_im_message_receive_v1.return_value = handler
    handler.build.return_value = object()
    return types.SimpleNamespace(builder=mock.Mock(return_value=handler))


if __name__ == "__main__":
    unittest.main()
