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

    def test_retired_upload_policy_is_rejected(self):
        self.policy["repositories"]["codex"]["artifact_upload"] = {"enabled": True}
        self.write_policy()
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "artifact_upload"):
            self.config()
        self.assertFalse(hasattr(feishu_codex_bot.FeishuTransport, "send_file"))

    def test_local_mcp_replies_are_not_broadcast_to_group(self):
        config, store, bot, job = self.queued_agent("private-reply-1")
        bot._send_safe(job.chat_id, "private task", job.message_id)
        bot._send_chunks(job.chat_id, "private result", job.message_id)
        bot.transport.send_text.assert_not_called()
        remote = store.create_task("om_remote", f"agent:{os.getuid()}", "codex", "review")
        self.assertIsNone(store.agent_task_detail(remote, f"agent:{os.getuid()}"))
        self.assertFalse(store.cancel_agent_queued(remote, f"agent:{os.getuid()}"))
        self.assertEqual("queued", store.task_status(remote))

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
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "隔离 worktree"):
            self.config()

    def test_edit_strategy_summary_reports_only_editable_repositories(self) -> None:
        self.policy["repositories"]["codex"].update({"allowed_modes": ["edit"], "worktree_root": str(self.tmp.parent / (self.tmp.name + "-worktrees"))})
        self.write_policy()
        self.assertEqual("worktree:1", feishu_codex_bot.edit_strategy_summary(self.config()))

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
        task_id = store.create_task("agent:state", f"agent:{os.getuid()}", "codex", "explain")
        self.assertEqual("queued", store.task_status(task_id))
        self.assertTrue(store.cancel_agent_queued(task_id, f"agent:{os.getuid()}"))
        self.assertEqual("canceled", store.task_status(task_id))

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
        self.assertNotIn(["/", "/"], [cmd[i+1:i+3] for i,x in enumerate(cmd) if x=="--ro-bind"])
        self.assertIn([str(config.workdir),str(config.workdir)],
                      [cmd[i+1:i+3] for i,x in enumerate(cmd) if x=="--ro-bind"])
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

    def test_sandbox_refuses_broad_toolchain_mounts_and_other_repository_paths(self) -> None:
        config=self.agent_config()
        for path in (pathlib.Path("/"),self.tmp,self.tmp.parent,pathlib.Path.home()):
            changed=dataclasses.replace(config,sandbox_read_paths=(path,))
            with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError,"sandbox_read_paths"):
                feishu_codex_bot.sandbox_command(changed,config.workdir,["git","status"],verification=True)
        other=self.tmp/"unregistered"
        other.mkdir()
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError,"唯一授权"):
            feishu_codex_bot.sandbox_command(config,other,["git","status"],verification=True)

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
        with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "worktree_root"):
            self.agent_config()
        # Recheck at the execution boundary even for a directly constructed
        # configuration that did not pass through the file loader.
        self.policy["repositories"]["codex"].update({"allowed_modes": ["explain", "review"], "agent_allowed_modes": ["explain", "review"]})
        self.write_policy()
        base = self.config()
        unsafe = dataclasses.replace(base, repositories={"codex": dataclasses.replace(
            base.repository("codex"), allowed_modes=frozenset(("explain", "review", "edit")), edit_strategy="in_place", agent_allowed_modes=frozenset(("explain", "review", "edit")))})
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

    def test_running_process_can_only_be_canceled_by_owner(self) -> None:
        runner = feishu_codex_bot.CodexRunner(self.config())
        owner_process = FakeProcess()
        other_process = FakeProcess()
        runner._running = {1: ("ou_owner", owner_process), 2: ("ou_other", other_process)}
        self.assertFalse(runner.cancel_task(2, "ou_owner"))
        self.assertTrue(runner.cancel_task(1, "ou_owner"))
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
        restarted.transport.send_text.assert_not_called()
        restarted.recover_pending()
        restarted.transport.send_text.assert_not_called()

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


    def test_controller_git_rejects_external_programs_and_does_not_inherit_credentials(self) -> None:
        repo = self.tmp / "external-filter-repo"
        subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
        marker = self.tmp / "external-command-ran"
        (repo / ".gitattributes").write_text("*.txt filter=fixture diff=fixture\n")
        (repo / "tracked.txt").write_text("base\n")
        subprocess.run(["git","-C",str(repo),"add","."],check=True)
        subprocess.run(["git","-C",str(repo),"-c","user.name=Test","-c","user.email=test@example.com",
                        "commit","-m","start"],check=True,capture_output=True)
        manager = feishu_codex_bot.WorktreeManager(self.config())
        for key in ("filter.fixture.clean","diff.fixture.textconv"):
            subprocess.run(["git","-C",str(repo),"config",key,"touch "+str(marker)],check=True)
            with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError,"外部过滤"):
                manager.snapshot(repo)
            self.assertFalse(marker.exists())
            subprocess.run(["git","-C",str(repo),"config","--unset",key],check=True)
        env = feishu_codex_bot.controller_git_environment({
            "PATH":"/usr/bin:/bin","OPENAI_API_KEY":"fixture","SSH_AUTH_SOCK":"fixture",
            "GITHUB_TOKEN":"fixture","GIT_CONFIG_PARAMETERS":"fixture","HOME":"/private"})
        self.assertNotIn("fixture",env.values())
        self.assertEqual("/dev/null",env["GIT_CONFIG_GLOBAL"])

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

    def test_late_cancel_cannot_acknowledge_model_completion(self) -> None:
        cfg, store, bot, job = self.queued_agent("late-cancel-1")
        bot.transport.resolve_sources.return_value = ""

        def return_after_cancel(*args, **kwargs):
            self.assertEqual("requested", store.request_agent_cancel(job.task_id, job.sender_open_id))
            return feishu_codex_bot.ExecutionResult("已返回模型结果")

        bot.runner.run.side_effect = return_after_cancel
        with mock.patch.object(bot.jobs, "get", side_effect=[job, SystemExit]), \
                mock.patch.object(bot.jobs, "task_done"):
            with self.assertRaises(SystemExit):
                bot.worker()
        self.assertEqual("unknown", store.task_status(job.task_id))
        self.assertTrue(store.cancel_requested(job.task_id))
        with store._connect() as db:
            self.assertIsNone(db.execute(
                "SELECT 1 FROM engineering_task_outputs WHERE task_id=?", (job.task_id,)
            ).fetchone())
        bot.runner.run.assert_called_once()
        restarted = feishu_codex_bot.FeishuCodexBot(cfg, mock.Mock(), mock.Mock(), store)
        restarted.recover_pending()
        self.assertEqual("unknown", store.task_status(job.task_id))
        self.assertEqual(0, restarted.jobs.qsize())

    def test_notification_failure_preserves_completed_receipt(self) -> None:
        cfg, store, bot, job = self.queued_agent("notification-failure-1")
        bot.transport.resolve_sources.return_value = ""
        bot.runner.run.return_value = feishu_codex_bot.ExecutionResult("已完成")
        with mock.patch.object(bot, "_send_chunks", side_effect=RuntimeError("fixture transport failure")), \
                mock.patch.object(bot.jobs, "get", side_effect=[job, SystemExit]), \
                mock.patch.object(bot.jobs, "task_done"):
            with self.assertRaises(SystemExit):
                bot.worker()
        self.assertEqual("completed", store.task_status(job.task_id))
        bot._record_task_failure(job, "unknown", "LateFailure")
        self.assertEqual("completed", store.task_status(job.task_id))
        with store._connect() as db:
            row = db.execute(
                "SELECT body,body_sha256 FROM engineering_task_outputs WHERE task_id=?", (job.task_id,)
            ).fetchone()
        self.assertEqual("已完成", row["body"])
        self.assertEqual(hashlib.sha256("已完成".encode("utf-8")).hexdigest(), row["body_sha256"])
        self.assertEqual("completed", store.request_agent_cancel(job.task_id, job.sender_open_id))
        self.assertFalse(store.cancel_requested(job.task_id))
        bot.runner.run.assert_called_once()

    def test_transport_sdk_exception_does_not_expose_payload(self) -> None:
        transport = object.__new__(feishu_codex_bot.FeishuTransport)
        with mock.patch.object(transport, "_send_message", side_effect=RuntimeError("fixture-sensitive-payload")):
            with self.assertRaisesRegex(feishu_codex_bot.FeishuCodexError, "RuntimeError") as caught:
                transport.send_text("oc_target", "fixture message", "om_target")
        self.assertNotIn("fixture-sensitive-payload", str(caught.exception))

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


def builder_factory() -> object:
    handler = mock.Mock()
    handler.register_p2_im_message_receive_v1.return_value = handler
    handler.build.return_value = object()
    return types.SimpleNamespace(builder=mock.Mock(return_value=handler))


if __name__ == "__main__":
    unittest.main()
