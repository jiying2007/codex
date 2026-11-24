"""Quiesced migration archives legacy metadata, never executes or guesses sessions."""
import json
import contextlib
import fcntl
import os
import pathlib
import sqlite3
import tempfile
import unittest
from unittest import mock

from tools.codex_assets.feishu_codex_bot import StateStore
from tests.feishu_legacy_fixture import create_legacy_ledger
from tools.codex_assets.feishu_engineering_agent.migration import (
    MigrationPlan, MigrationRejected, ensure_engineering_migrated,
)
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
        self.old=create_legacy_ledger(self.root/"feishu-engineering-agent.sqlite3")
        self.policy=self.root/"policy.json"
        self.lock=self.root/"bot.lock"
        self.lock.touch(mode=0o600)
        self.policy.write_text(json.dumps({"manual_workitems_enabled":True,"engineering_cards_enabled":False,
            "lock_file":str(self.lock),"state_db":str(self.store.path)}))
        self.policy.chmod(0o600)
        self.plan=MigrationPlan(self.store.path,self.spool.root,self.policy)
        self.backup=self.root/"backup"
    def test_archive_once_and_future_backup_one_live_ledger(self):
        self.plan.backup(self.backup)
        report=self.plan.unify(self.backup,self.lock)
        self.assertTrue(report["unified_state"])
        self.assertEqual(1,report["archived_runs"])
        self.assertTrue(self.store.is_engineering_migrated())
        self.assertTrue(self.old.exists())
        ensure_engineering_migrated(self.store.path)
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
        self.assertTrue(self.old.exists())

    def test_wrong_or_held_service_lock_rejects_without_retiring(self):
        self.plan.backup(self.backup)
        wrong_lock=self.root/"unrelated.lock"
        wrong_lock.touch(mode=0o600)
        with self.lock.open("r+") as held:
            fcntl.flock(held,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaisesRegex(MigrationRejected,"private policy lock_file"):
                self.plan.unify(self.backup,wrong_lock)
            with self.assertRaisesRegex(MigrationRejected,"lock is held"):
                self.plan.unify(self.backup,self.lock)
        self.assertFalse(self.store.is_engineering_migrated())

    def test_target_and_environment_must_match_frozen_policy(self):
        self.plan.backup(self.backup)
        with mock.patch.dict(os.environ,{"FEISHU_LOCK_FILE":str(self.root/"wrong.lock")}):
            with self.assertRaisesRegex(MigrationRejected,"conflicts with environment"):
                self.plan.unify(self.backup,self.lock)
        with mock.patch.dict(os.environ,{"FEISHU_STATE_DB":str(self.root/"wrong.sqlite3")}):
            with self.assertRaisesRegex(MigrationRejected,"conflicts with environment"):
                self.plan.unify(self.backup,self.lock)
        self.assertFalse(self.store.is_engineering_migrated())

    def test_backed_up_environment_cannot_be_omitted_or_changed(self):
        env=self.root/"private.env"
        env.write_text("FEISHU_LOCK_FILE="+str(self.lock)+"\n")
        env.chmod(0o600)
        plan=MigrationPlan(self.store.path,self.spool.root,self.policy,env)
        plan.backup(self.backup)
        with self.assertRaisesRegex(MigrationRejected,"same backed-up private environment"):
            self.plan.unify(self.backup,self.lock)
        env.write_text("FEISHU_LOCK_FILE="+str(self.root/"wrong.lock")+"\n")
        with self.assertRaisesRegex(MigrationRejected,"environment differs"):
            plan.unify(self.backup,self.lock)
        self.assertFalse(self.store.is_engineering_migrated())

    def test_unresolved_publication_cannot_be_hidden_by_terminal_run(self):
        with contextlib.closing(sqlite3.connect(str(self.old))) as db:
            db.execute("UPDATE fea_runs SET status='blocked'")
            db.execute("CREATE TABLE fea_publications(run_id TEXT PRIMARY KEY,effect_state TEXT)")
            db.execute("INSERT INTO fea_publications VALUES (?, 'unknown')",('a'*32,))
            db.commit()
        self.plan.backup(self.backup)
        with self.assertRaisesRegex(MigrationRejected,"publication remains unresolved"):
            self.plan.unify(self.backup,self.lock)
        self.assertFalse(self.store.is_engineering_migrated())

    def test_startup_refuses_old_ledger_and_link_without_mutating_them(self):
        original=self.old.read_bytes()
        with self.assertRaisesRegex(MigrationRejected,"offline backup"):
            ensure_engineering_migrated(self.store.path)
        self.assertEqual(original,self.old.read_bytes())
        self.old.unlink()
        with self.store._connect() as db:
            db.execute("INSERT INTO agent_run_task_links VALUES (?,?,?,?)",('a'*32,1,os.getuid(),1))
        with self.assertRaisesRegex(MigrationRejected,"offline backup"):
            ensure_engineering_migrated(self.store.path)
        self.assertFalse(self.old.exists())

    def test_startup_allows_fresh_deployment_without_creating_files(self):
        fresh=self.root/"new"
        fresh.mkdir(mode=0o700)
        missing=fresh/"bot.sqlite3"
        ensure_engineering_migrated(missing)
        self.assertFalse(missing.exists())
        StateStore(missing)
        ensure_engineering_migrated(missing)
        self.assertFalse((fresh/"feishu-engineering-agent.sqlite3").exists())

    def test_orphan_legacy_sidecars_are_not_treated_as_fresh_state(self):
        self.old.unlink()
        for suffix in ("-wal", "-shm"):
            with self.subTest(suffix=suffix):
                sidecar = self.old.with_name(self.old.name + suffix)
                sidecar.write_bytes(b"synthetic unrecovered history")
                sidecar.chmod(0o600)
                with self.assertRaisesRegex(MigrationRejected, "offline backup"):
                    ensure_engineering_migrated(self.store.path)
                with self.assertRaises(MigrationRejected):
                    self.plan.inspect()
                with self.assertRaises(MigrationRejected):
                    self.plan.backup(self.backup)
                self.assertFalse(self.backup.exists())
                self.assertFalse(self.old.exists())
                self.assertEqual(b"synthetic unrecovered history", sidecar.read_bytes())
                sidecar.unlink()

    def test_orphan_bot_sidecars_refuse_new_database_creation(self):
        missing = self.root / "new-bot.sqlite3"
        sidecar = missing.with_name(missing.name + "-wal")
        sidecar.touch(mode=0o600)
        with self.assertRaisesRegex(MigrationRejected, "orphan Bot"):
            ensure_engineering_migrated(missing)
        self.assertFalse(missing.exists())

    def test_startup_refuses_incomplete_archive_marker(self):
        self.plan.backup(self.backup)
        self.plan.unify(self.backup,self.lock)
        with self.store._connect() as db:
            db.execute("DELETE FROM engineering_legacy_records")
        with self.assertRaisesRegex(MigrationRejected,"archive does not match"):
            ensure_engineering_migrated(self.store.path)
