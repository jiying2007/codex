"""Quiesced migration archives legacy metadata, never executes or guesses sessions."""
import json
import pathlib
import sqlite3
import tempfile
import unittest

from tools.codex_assets.feishu_codex_bot import StateStore
from tools.codex_assets.feishu_engineering_agent.manual_items import ManualWorkItemService
from tools.codex_assets.feishu_engineering_agent.migration import MigrationPlan, MigrationRejected
from tools.codex_assets.feishu_engineering_agent.models import InboundEvent
from tools.codex_assets.feishu_engineering_agent.service import LinkContextService
from tools.codex_assets.feishu_task_spool import TaskSpool


class UnifyTest(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix="fea-unify-")
        self.addCleanup(tmp.cleanup)
        self.root=pathlib.Path(tmp.name)
        self.store=StateStore(self.root/"bot.sqlite3")
        self.spool=TaskSpool(self.root/"spool")
        self.old=ManualWorkItemService(self.root/"feishu-engineering-agent.sqlite3")
        self.policy=self.root/"policy.json"
        self.policy.write_text(json.dumps({"manual_workitems_enabled":True,"engineering_cards_enabled":False}))
        self.policy.chmod(0o600)
        self.lock=self.root/"bot.lock"
        self.lock.touch(mode=0o600)
        event=InboundEvent("feishu_message","tenant","oc_chat","ou_owner","om_legacy",
            "/wi add feishu_project 缺陷 example-space 1000000001 repo=robot | synthetic")
        self.old.handle(event,"robot",{"robot"})
        self.plan=MigrationPlan(self.store.path,self.spool.root,self.policy)
        self.backup=self.root/"backup"
    def test_archive_once_and_future_backup_one_live_ledger(self):
        self.plan.backup(self.backup)
        report=self.plan.unify(self.backup,self.lock)
        self.assertTrue(report["unified_state"])
        self.assertEqual(1,report["archived_runs"])
        self.assertTrue(self.store.is_engineering_migrated())
        self.assertTrue(self.old.store.path.exists())
        with self.store._connect() as db:
            self.assertEqual(1,db.execute("SELECT COUNT(*) FROM engineering_legacy_runs").fetchone()[0])
            self.assertGreater(db.execute("SELECT COUNT(*) FROM engineering_legacy_records").fetchone()[0],0)
        with self.assertRaises(MigrationRejected):
            self.plan.unify(self.backup,self.lock)
        new=self.root/"backup-after"
        self.plan.backup(new)
        self.assertFalse((new/"feishu-engineering-agent.sqlite3").exists())
        self.assertTrue(MigrationPlan.rehearse_restore(new)["restore_rehearsed"])
        service=LinkContextService(self.store)
        e=InboundEvent("feishu_message","tenant","oc_chat","ou_owner","om_new",
            "https://project.feishu.cn/example-space/issue/detail/1000000001")
        result=service.handle(e,"root:om_new",{"robot"},{"feishu_project:example-space":["robot"]})
        self.assertIn("历史归档记录：1",result.reply)
        old=InboundEvent("feishu_message","tenant","oc_chat","ou_owner","om_legacy",
            "分析 https://project.feishu.cn/example-space/issue/detail/1000000001")
        self.assertIsNone(service.handle(old,"root:om_legacy",{"robot"},{}).reply)
    def test_rejects_drift_and_keeps_original(self):
        self.plan.backup(self.backup)
        self.store.claim_message("om_changed")
        with self.assertRaisesRegex(MigrationRejected,"changed since"):
            self.plan.unify(self.backup,self.lock)
        self.assertFalse(self.store.is_engineering_migrated())
        self.assertTrue(self.old.store.path.exists())
