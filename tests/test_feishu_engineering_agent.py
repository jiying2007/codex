"""SDD TASK-001: offline Feishu Engineering Agent contract tests, zero model calls."""
from __future__ import annotations

import json
import os
import pathlib
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tools.codex_assets.feishu_engineering_agent import (
    EventConflict, InboundEvent, IntakeRejected, WorkItemKey, route_message,
)
from tools.codex_assets.feishu_engineering_agent.store import OfflineIntakeStore


class EngineeringAgentIntakeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="fea-sdd-")
        self.addCleanup(self.temp.cleanup)
        self.path = pathlib.Path(self.temp.name) / "preview.sqlite3"
        self.store = OfflineIntakeStore(self.path)
        self.allowed = frozenset({"robot-app", "codex", "pcr02-mcu"})

    def event(
        self, event_id: str, text: str,
        tenant: str = "tenantA", chat: str = "oc_team",
        actor: str = "ou_owner", source: str = "feishu_message",
    ) -> InboundEvent:
        return InboundEvent(source, tenant, chat, actor, event_id, text)

    def test_project_switch_and_read_are_deterministic(self) -> None:
        selected = route_message("切换到 robot-app 项目", "", self.allowed)
        self.assertEqual("switch_project", selected.kind)
        self.assertEqual("robot-app", selected.repo)
        for text in ("分析 sensor 初始化", "请帮我分析 UART 中断", "检查系统日志"):
            decision = route_message(text, "robot-app", self.allowed)
            self.assertEqual("read_proposal", decision.kind)
            self.assertEqual("robot-app", decision.repo)
            self.assertFalse(decision.run_enqueued)
        review = route_message("审查 sensor 资源释放", "robot-app", self.allowed)
        self.assertEqual("review_proposal", review.kind)
        self.assertFalse(review.run_enqueued)

    def test_write_and_privileged_intents_never_launch(self) -> None:
        for text in ("修复 sensor 初始化失败", "请帮我实现电机接口", "修改权限检查"):
            proposed = route_message(text, "robot-app", self.allowed)
            self.assertEqual("write_proposal", proposed.kind)
            self.assertTrue(proposed.requires_approval)
            self.assertFalse(proposed.run_enqueued)
        for text in ("上线生产版本", "刷写固件", "删除仓库", "合并 main"):
            blocked = route_message(text, "robot-app", self.allowed)
            self.assertEqual("blocked", blocked.kind)
            self.assertFalse(blocked.run_enqueued)

    def test_no_implicit_repository_or_unknown_model_request(self) -> None:
        self.assertEqual(
            "need_project", route_message("分析启动问题", "", self.allowed).kind,
        )
        self.assertEqual(
            "blocked", route_message("/repo unknown", "codex", self.allowed).kind,
        )
        self.assertEqual(
            "clarify", route_message("随便做点事情", "codex", self.allowed).kind,
        )
        self.assertEqual(
            "clarify", route_message("/execute rm -rf /", "codex", self.allowed).kind,
        )
        self.assertEqual(
            "clarify", route_message("继续刚才的会话", "codex", self.allowed).kind,
        )
        self.assertEqual(
            "show_project", route_message("当前项目", "robot-app", self.allowed).kind,
        )

    def test_task_commands_require_exact_id(self) -> None:
        status = route_message("任务 #23 状态", "robot-app", self.allowed)
        self.assertEqual(("task_status", 23), (status.kind, status.task_id))
        resume = route_message("继续任务 #23", "robot-app", self.allowed)
        self.assertEqual(("resume_proposal", 23), (resume.kind, resume.task_id))
        self.assertTrue(resume.requires_approval)
        cancel = route_message("取消任务 #23", "robot-app", self.allowed)
        self.assertEqual(("cancel_proposal", 23), (cancel.kind, cancel.task_id))
        self.assertFalse(cancel.run_enqueued)
        self.assertEqual("clarify", route_message("取消", "codex", self.allowed).kind)
        self.assertEqual(
            "need_project", route_message("继续任务 #23", "", self.allowed).kind,
        )

    def test_workitem_identity_is_source_scoped_not_inferred(self) -> None:
        source_a = WorkItemKey("tapd", "tenantA", "12345", "defect", "456")
        source_b = WorkItemKey("feishu_project", "tenantA", "12345", "defect", "456")
        source_c = WorkItemKey("tapd", "tenantA", "54321", "defect", "456")
        self.assertNotEqual(source_a.fingerprint, source_b.fingerprint)
        self.assertNotEqual(source_a.fingerprint, source_c.fingerprint)
        self.assertEqual(source_a.fingerprint, WorkItemKey(
            "tapd", "tenantA", "12345", "defect", "456",
        ).fingerprint)
        for bad in (
            ("github", "tenantA", "123", "defect", "456"),
            ("tapd", "tenantA", "123", "issue", "456"),
            ("tapd", "tenantA", "", "defect", "456"),
            ("tapd", "tenantA", "123", "defect", "../secret"),
        ):
            with self.assertRaises(IntakeRejected):
                WorkItemKey(*bad)

    def test_event_deduplication_and_conflicting_payload(self) -> None:
        event = self.event("om_test_1", "切换到 robot-app 项目")
        decision = self.store.ingest(event, self.allowed)
        self.assertEqual("switch_project", decision.kind)
        self.assertEqual("robot-app", self.store.selected_project(event))
        replay = self.store.ingest(event, self.allowed)
        self.assertTrue(replay.replayed)
        self.assertFalse(replay.run_enqueued)
        with self.assertRaises(EventConflict):
            self.store.ingest(
                self.event("om_test_1", "切换到 codex 项目"), self.allowed,
            )
        with sqlite3.connect(str(self.path)) as conn:
            self.assertEqual(1, conn.execute("SELECT COUNT(*) FROM fea_preview_events").fetchone()[0])

    def test_atomic_rollback_preserves_existing_project(self) -> None:
        previous = self.event("om_first", "切换到 codex 项目")
        self.store.ingest(previous, self.allowed)
        with sqlite3.connect(str(self.path)) as conn:
            conn.execute(
                "CREATE TRIGGER fail_receipt BEFORE INSERT ON fea_preview_events "
                "BEGIN SELECT RAISE(ABORT, 'fixture failure'); END"
            )
        next_event = self.event("om_second", "切换到 robot-app 项目")
        with self.assertRaises(sqlite3.DatabaseError):
            self.store.ingest(next_event, self.allowed)
        self.assertEqual("codex", self.store.selected_project(previous))
        with sqlite3.connect(str(self.path)) as conn:
            self.assertEqual(1, conn.execute("SELECT COUNT(*) FROM fea_preview_events").fetchone()[0])

    def test_user_chat_tenant_isolation_and_stale_repo_policy(self) -> None:
        user = self.event("om_1", "切换到 robot-app 项目")
        self.store.ingest(user, self.allowed)
        for diff in (
            self.event("om_2", "当前项目", actor="ou_other"),
            self.event("om_3", "当前项目", chat="oc_other"),
            self.event("om_4", "当前项目", tenant="tenantB"),
        ):
            self.assertEqual("", self.store.selected_project(diff))
            self.assertEqual("need_project",
                             self.store.ingest(
                                 self.event(diff.event_id + "x", "分析系统", diff.tenant,
                                            diff.chat, diff.actor),
                                 self.allowed,
                             ).kind)
        self.assertEqual("blocked", self.store.ingest(
            user, {"codex"},
        ).kind)
        self.assertEqual("robot-app", self.store.selected_project(user))

    def test_deduplication_is_scoped_and_no_prompt_stored(self) -> None:
        secret = "TOPSECRET_NOT_FOR_STORAGE"
        first = self.event("om_one", "分析 " + secret)
        self.store.ingest(first, self.allowed, default_repo="codex")
        second = self.event("om_one", "分析 " + secret, chat="oc_other")
        self.store.ingest(second, self.allowed, default_repo="codex")
        with sqlite3.connect(str(self.path)) as conn:
            self.assertEqual(2, conn.execute("SELECT COUNT(*) FROM fea_preview_events").fetchone()[0])
            columns = conn.execute(
                "SELECT event_key,content_sha256,kind,repository,reason "
                "FROM fea_preview_events"
            ).fetchall()
        self.assertNotIn(secret, repr(columns))
        self.assertEqual(0, os.stat(self.path).st_mode & 0o077)

    def test_reset_and_default_repo_is_explicit(self) -> None:
        choice = self.event("om_set", "切换到 robot-app 项目")
        self.store.ingest(choice, self.allowed)
        reset = self.store.ingest(
            self.event("om_reset", "/repo reset"), self.allowed, default_repo="codex",
        )
        self.assertEqual("reset_project", reset.kind)
        self.assertEqual("", self.store.selected_project(choice))
        read = self.store.ingest(
            self.event("om_read", "分析应用代码"), self.allowed, default_repo="codex",
        )
        self.assertEqual("codex", read.repo)

    def test_invalid_identity_and_bounded_input_fail_closed(self) -> None:
        with self.assertRaises(IntakeRejected):
            self.event("invalid id with spaces", "分析安全")
        with self.assertRaises(IntakeRejected):
            self.event("om_long", "a" * 12001)
        with self.assertRaises(IntakeRejected):
            self.store.ingest(
                self.event("om_bad", "分析代码"), self.allowed, default_repo="not-allowed",
            )

    def test_offline_cli_from_other_cwd_no_repo_or_model(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        environ = dict(os.environ)
        environ["PYTHONPATH"] = str(root)
        result = subprocess.run(
            [
                sys.executable, "-m", "tools.codex_assets.feishu_engineering_agent",
                "--dry-run", "--allow-repo", "codex",
                "--selected-repo", "codex", "--text", "修复启动问题",
            ],
            cwd=self.temp.name, env=environ,
            check=False, capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        response = json.loads(result.stdout)
        self.assertEqual("write_proposal", response["kind"])
        self.assertTrue(response["requires_approval"])
        self.assertFalse(response["run_enqueued"])
        self.assertFalse(response["runtime_accessed"])
        self.assertNotIn("修复启动问题", result.stdout)


if __name__ == "__main__":
    unittest.main()
