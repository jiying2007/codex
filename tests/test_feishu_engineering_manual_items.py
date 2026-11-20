"""No-enterprise-API work item intake: local SQLite and message-only contracts."""
from __future__ import annotations

import contextlib
import io
import json
import os
import pathlib
import sqlite3
import tempfile
import unittest
from unittest import mock

from tools.codex_assets.feishu_engineering_agent import (
    EventConflict, InboundEvent, IntakeRejected, WorkItemKey,
)
from tools.codex_assets.feishu_engineering_agent.__main__ import main
from tools.codex_assets.feishu_engineering_agent.manual_items import (
    ManualWorkItemService, is_manual_command, parse_manual_command,
)

COMMAND = (
    "/wi add tapd 缺陷 10104801 123456 repo=robot-app "
    "| 提交的电机低速过流，复现：回充上桩，期望：不误保护。"
)


class ManualWorkItemTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="fea-manual-")
        self.addCleanup(temp.cleanup)
        self.root = pathlib.Path(temp.name)
        self.db = self.root / "manual.sqlite3"
        self.service = ManualWorkItemService(self.db)
        self.repos = {"robot-app", "pcr02-mcu"}
        self.event = InboundEvent(
            "feishu_message", "tenantA", "oc_team", "ou_owner",
            "om_100", COMMAND,
        )

    def _run_id(self, receipt):
        self.assertIn("AgentRun：", receipt)
        return receipt.split("AgentRun：", 1)[1].split("\n")[0]

    def test_manual_register_has_exact_source_but_no_api_verification(self):
        receipt = self.service.handle(self.event, "robot-app", self.repos)
        self.assertIn("未核验", receipt)
        self.assertIn("proposed", receipt)
        self.assertIn("不会启动模型", receipt)
        run_id = self._run_id(receipt)
        record = self.service.store.get_run(run_id, self.event)
        self.assertEqual("tapd", record["provider"])
        self.assertEqual("defect", record["kind"])
        self.assertEqual("10104801", record["workspace"])
        self.assertEqual("123456", record["item_id"])
        self.assertEqual("read", record["mode"])
        self.assertEqual("proposed", record["status"])
        with sqlite3.connect(str(self.db)) as db:
            row = db.execute(
                "SELECT source_level,origin_message_id,summary_sha256 "
                "FROM fea_manual_claims",
            ).fetchone()
        self.assertEqual("user_supplied_unverified", row[0])
        self.assertEqual("om_100", row[1])
        self.assertEqual(64, len(row[2]))
        self.assertNotIn("电机低速过流".encode(), self.db.read_bytes())
        self.assertEqual(0, self.db.stat().st_mode & 0o077)

    def test_duplicate_delivery_does_not_mint_a_new_run(self):
        self._run_id(self.service.handle(self.event, "robot-app", self.repos))
        self.assertIsNone(self.service.handle(self.event, "robot-app", self.repos))
        with sqlite3.connect(str(self.db)) as db:
            self.assertEqual(1, db.execute("SELECT COUNT(*) FROM fea_runs").fetchone()[0])
        conflict = InboundEvent(
            "feishu_message", "tenantA", "oc_team", "ou_owner",
            "om_100", COMMAND.replace("123456", "999999"),
        )
        with self.assertRaises(EventConflict):
            self.service.handle(conflict, "robot-app", self.repos)
        with sqlite3.connect(str(self.db)) as db:
            self.assertEqual(1, db.execute("SELECT COUNT(*) FROM fea_runs").fetchone()[0])

    def test_source_ids_do_not_collide_across_providers_or_workspaces(self):
        first = self._run_id(self.service.handle(self.event, "robot-app", self.repos))
        other = InboundEvent(
            "feishu_message", "tenantA", "oc_team", "ou_owner", "om_101",
            COMMAND.replace("tapd", "feishu_project"),
        )
        second = self._run_id(self.service.handle(other, "robot-app", self.repos))
        self.assertNotEqual(first, second)
        key = WorkItemKey("tapd", "tenantA", "10104801", "defect", "123456")
        rows = self.service.store.workitem_runs(key)
        self.assertEqual(first, rows[0]["run_id"])

    def test_status_and_list_are_restricted_by_user_chat_tenant_and_repo(self):
        run = self._run_id(self.service.handle(self.event, "robot-app", self.repos))
        owner = InboundEvent(
            "feishu_message", "tenantA", "oc_team", "ou_owner",
            "om_read", "/wi status " + run,
        )
        self.assertIn("未通过原系统 API 核验",
                      self.service.handle(owner, "robot-app", self.repos))
        listing = InboundEvent(
            "feishu_message", "tenantA", "oc_team", "ou_owner",
            "om_list", "/wi list",
        )
        self.assertIn(run, self.service.handle(listing, "robot-app", self.repos))
        for tenant, chat, actor in (
            ("tenantB", "oc_team", "ou_owner"),
            ("tenantA", "oc_other", "ou_owner"),
            ("tenantA", "oc_team", "ou_attacker"),
        ):
            with self.assertRaises(IntakeRejected):
                self.service.handle(
                    InboundEvent("feishu_message", tenant, chat, actor,
                                 "om_read", "/wi status " + run),
                    "robot-app", self.repos,
                )
        with self.assertRaises(IntakeRejected):
            self.service.handle(owner, "robot-app", {"pcr02-mcu"})
        with self.assertRaises(IntakeRejected):
            self.service.handle(self.event, "robot-app", {"pcr02-mcu"})

    def test_command_syntax_is_bounded_and_disallows_implicit_source(self):
        self.assertTrue(is_manual_command(" /wi add tapd defect 1 2 | text"))
        self.assertFalse(is_manual_command("/wiki article"))
        self.assertEqual("help",
                         parse_manual_command("/wi help", "tenantA", "robot-app").action)
        for bad in (
            "/wi add unknown defect 101 123 | summary",
            "/wi add tapd mystery 101 123 | summary",
            "/wi add tapd defect 101 123 | ",
            "/wi add tapd defect 101 123 | " + "x" * 4100,
            "/wi add tapd defect 101 123 repo=../../tmp | summary",
            "/wi status last",
            "/wi please automatically run codex",
        ):
            with self.assertRaises(IntakeRejected, msg=bad[:60]):
                parse_manual_command(bad, "tenantA", "robot-app")
        self.assertEqual(
            "robot-app",
            parse_manual_command(
                "/wi add 飞书项目 需求 workspace1 9876 | 增加固件OTA回滚机制",
                "tenantA", "robot-app",
            ).repo,
        )

    def test_local_cli_stdin_works_without_feishu_and_never_calls_model(self):
        database = self.root / "cli.sqlite3"
        args = [
            "--manual", "--db", str(database), "--event-id", "local_req_1",
            "--allow-repo", "robot-app", "--selected-repo", "robot-app",
        ]
        output = io.StringIO()
        with mock.patch("sys.stdin", io.StringIO(COMMAND)), contextlib.redirect_stdout(output):
            self.assertEqual(0, main(args))
        response = json.loads(output.getvalue())
        self.assertFalse(response["model_invoked"])
        self.assertFalse(response["external_api_accessed"])
        self.assertIn("AgentRun：", response["reply"])
        self.assertNotIn("低速过流", database.read_bytes().decode("utf-8", errors="ignore"))
        repeat = io.StringIO()
        with mock.patch("sys.stdin", io.StringIO(COMMAND)), contextlib.redirect_stdout(repeat):
            self.assertEqual(0, main(args))
        self.assertEqual("duplicate_event_ignored", json.loads(repeat.getvalue())["reply"])

    def test_local_cli_requires_explicit_private_db_and_command_scope(self):
        with mock.patch("sys.stdin", io.StringIO(COMMAND)), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                main(["--manual", "--db", "relative.db", "--event-id", "one",
                      "--allow-repo", "robot-app"])
        self.assertEqual(2, error.exception.code)


if __name__ == "__main__":
    unittest.main()
