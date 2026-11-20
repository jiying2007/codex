"""No-enterprise-API fallback and authorized WorkItem source recheck."""
from __future__ import annotations

import pathlib
import sqlite3
import tempfile
import unittest
from unittest import mock

from tools.codex_assets.feishu_engineering_agent.models import (
    InboundEvent, IntakeRejected, WorkItemKey,
)
from tools.codex_assets.feishu_engineering_agent.source_bridge import SourceReconciler
from tools.codex_assets.feishu_engineering_agent.state import RunStore
from tools.codex_assets.feishu_engineering_agent.workitems import WorkItemSnapshot


class SourceContractTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="fea-source-")
        self.addCleanup(temp.cleanup)
        self.db = pathlib.Path(temp.name) / "source.sqlite3"
        self.store = RunStore(self.db)
        self.event = InboundEvent("feishu_message", "tenantA", "oc_chat",
                                  "ou_owner", "msg1", "读工作项")
        self.key = WorkItemKey("tapd", "tenantA", "10104801", "defect", "123456")
        self.run = self.store.create_run(
            self.event, "robot-app", {"robot-app"}, "read", self.key,
        )
        self.bridge = SourceReconciler(self.store)

    def test_no_api_fallback_does_not_call_reader(self):
        reader = mock.Mock()
        result = self.bridge.read_optional(self.run, self.event, reader, False)
        self.assertFalse(result["source_api_available"])
        self.assertEqual("user_supplied_unverified", result["source"])
        self.assertFalse(result["model_invoked"])
        reader.assert_not_called()

    def test_authorized_read_only_snapshot_is_versioned_and_not_persisted_raw(self):
        snapshot = WorkItemSnapshot(
            self.key, "电机低速过流", "Open", "version1",
            "复现：低速上桩过流，期望正确保护；禁止自动修改",
        )
        reader = mock.Mock(return_value=snapshot)
        first = self.bridge.read_optional(self.run, self.event, reader, True)
        self.assertTrue(first["source_api_available"])
        self.assertFalse(first["workitem_closed"])
        self.assertEqual("电机低速过流", first["title"])
        second = self.bridge.read_optional(self.run, self.event, reader, True)
        self.assertEqual(first["version"], second["version"])
        self.assertEqual(2, reader.call_count)
        with sqlite3.connect(str(self.db)) as db:
            self.assertEqual(1, db.execute(
                "SELECT COUNT(*) FROM fea_source_reads"
            ).fetchone()[0])
        self.assertNotIn("禁止自动修改".encode("utf-8"), self.db.read_bytes())

    def test_scope_or_same_version_content_drift_is_rejected(self):
        other = WorkItemKey("tapd", "tenantB", "10104801", "defect", "123456")
        with self.assertRaises(IntakeRejected):
            self.bridge.read_optional(
                self.run, self.event,
                lambda key: WorkItemSnapshot(other, "wrong", "Open", "version1", ""),
                True,
            )
        first = WorkItemSnapshot(self.key, "title", "Open", "version1", "hello")
        self.bridge.read_optional(self.run, self.event, lambda x: first, True)
        bad = WorkItemSnapshot(self.key, "title", "Open", "version1", "changed")
        with self.assertRaises(IntakeRejected):
            self.bridge.read_optional(self.run, self.event, lambda x: bad, True)
        attacker = InboundEvent("feishu_message", "tenantA", "oc_chat",
                                "ou_attacker", "msg2", "读工作项")
        with self.assertRaises(IntakeRejected):
            self.bridge.read_optional(self.run, attacker, lambda x: first, True)


if __name__ == "__main__":
    unittest.main()
