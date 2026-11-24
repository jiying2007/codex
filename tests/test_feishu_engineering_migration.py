"""Host cutover preparation: private WAL-safe backup and disposable restore."""
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

from tools.codex_assets.feishu_engineering_agent.migration import (
    MigrationPlan, MigrationRejected,
)
from tools.codex_assets.feishu_engineering_agent.migration_cli import main


class MigrationContractTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="fea-migration-")
        self.addCleanup(temp.cleanup)
        self.root = pathlib.Path(temp.name)
        self.db = self.root / "bot-state.sqlite3"
        self.spool = self.root / "feishu-pending-jobs"
        self.spool.mkdir(mode=0o700)
        self.payload = self.spool / "job_1.json"
        self.payload.write_text("sensitive-ephemeral-test-message", encoding="utf-8")
        self.payload.chmod(0o600)
        self.policy = self.root / "private-policy.json"
        self.policy.write_text('{"secret":"test-only-credential"}', encoding="utf-8")
        self.policy.chmod(0o600)
        with sqlite3.connect(str(self.db)) as connection:
            connection.execute("CREATE TABLE jobs(id INTEGER PRIMARY KEY,state TEXT)")
            connection.execute("INSERT INTO jobs VALUES (1,'queued')")
        self.db.chmod(0o600)
        self.plan = MigrationPlan(self.db, self.spool, self.policy)

    def test_inspection_backup_rehearsal_does_not_change_source(self):
        inspected = self.plan.inspect()
        self.assertEqual(1, inspected["spool_count"])
        self.assertFalse(inspected["no_second_consumer_proven"])
        target = self.root / "archive-1"
        receipt = self.plan.backup(target)
        self.assertFalse(receipt["restored"])
        self.assertEqual(0, target.stat().st_mode & 0o077)
        self.assertTrue(MigrationPlan.verify_backup(target)["valid"])
        self.assertTrue(MigrationPlan.rehearse_restore(target)["restore_rehearsed"])
        with sqlite3.connect(str(self.db)) as db:
            self.assertEqual(1, db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0])
        self.assertEqual("sensitive-ephemeral-test-message",
                         self.payload.read_text(encoding="utf-8"))
        manifest = (target / "manifest.json").read_text(encoding="utf-8")
        self.assertNotIn("test-only-credential", manifest)
        self.assertNotIn("sensitive-ephemeral", manifest)
        with self.assertRaises(MigrationRejected):
            self.plan.backup(target)

    def test_tampered_backup_and_symlink_source_fail_closed(self):
        target = self.root / "archive-2"
        self.plan.backup(target)
        (target / "spool" / "job_1.json").write_text("tampered", encoding="utf-8")
        with self.assertRaises(MigrationRejected):
            MigrationPlan.verify_backup(target)
        self.payload.unlink()
        self.payload.symlink_to(self.policy)
        with self.assertRaises(MigrationRejected):
            self.plan.inspect()

    def test_backup_preserves_both_linked_ledgers_and_private_environment(self):
        agent = self.root / "feishu-engineering-agent.sqlite3"
        env = self.root / "private.env"
        env.write_text("FIXTURE_VALUE=private-value\n", encoding="utf-8")
        env.chmod(0o600)
        with contextlib.closing(sqlite3.connect(str(self.db))) as db:
            db.executescript("""
                CREATE TABLE tasks(id INTEGER PRIMARY KEY,repository TEXT,sender_open_id TEXT,mode TEXT);
                INSERT INTO tasks VALUES (1,'codex','agent:1000','explain');
                CREATE TABLE agent_run_task_links(agent_run_id TEXT,task_id INTEGER,unix_uid INTEGER);
                INSERT INTO agent_run_task_links VALUES ('fixture-run',1,1000);
            """)
            db.commit()
        with contextlib.closing(sqlite3.connect(str(agent))) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE fea_runs(run_id TEXT PRIMARY KEY,repo TEXT,mode TEXT)")
            db.execute("INSERT INTO fea_runs VALUES ('fixture-run','codex','read')")
            db.commit()
            agent.chmod(0o600)
            plan = MigrationPlan(self.db, self.spool, self.policy, env)
            target = self.root / "paired-backup"
            receipt = plan.backup(target)
            self.assertTrue(receipt["agent_ledger_present"])
            self.assertEqual(1, receipt["linked_run_count"])
            self.assertEqual(1, MigrationPlan.verify_backup(target)["linked_run_count"])
            restored = MigrationPlan.rehearse_restore(target)
            self.assertTrue(restored["agent_ledger_present"])
            self.assertEqual(1, restored["linked_run_count"])
            self.assertEqual(env.read_bytes(), (target / "environment.private").read_bytes())
            self.assertNotIn("private-value", (target / "manifest.json").read_text())
        # A paired backup must not silently drop the new ledger.
        agent.unlink()
        with self.assertRaisesRegex(MigrationRejected, "matching AgentRun"):
            self.plan.backup(self.root / "missing-agent-backup")

    def test_mismatched_linked_run_rejects_backup(self):
        agent = self.root / "feishu-engineering-agent.sqlite3"
        with contextlib.closing(sqlite3.connect(str(self.db))) as db:
            db.executescript("""
                CREATE TABLE tasks(id INTEGER PRIMARY KEY,repository TEXT,sender_open_id TEXT,mode TEXT);
                INSERT INTO tasks VALUES (1,'codex','agent:1000','edit');
                CREATE TABLE agent_run_task_links(agent_run_id TEXT,task_id INTEGER,unix_uid INTEGER);
                INSERT INTO agent_run_task_links VALUES ('fixture-run',1,1000);
            """)
            db.commit()
        with contextlib.closing(sqlite3.connect(str(agent))) as db:
            db.execute("CREATE TABLE fea_runs(run_id TEXT PRIMARY KEY,repo TEXT,mode TEXT)")
            db.execute("INSERT INTO fea_runs VALUES ('fixture-run','other','edit')")
            db.commit()
        agent.chmod(0o600)
        with self.assertRaisesRegex(MigrationRejected, "snapshot linkage mismatch"):
            self.plan.backup(self.root / "mismatched-backup")

    def test_cutover_gate_never_starts_services(self):
        result = MigrationPlan.cutover_gate(
            backup_verified=True, restore_rehearsed=True,
            old_consumer_stopped=True, singleton_lock_acquired=True,
            callbacks_qualified=False, runtime_qualified=False,
        )
        self.assertFalse(result["can_cutover"])
        self.assertIn("callbacks_qualified", result["missing"])
        self.assertFalse(result["service_changed"])
        self.assertFalse(result["consumer_started"])
        with self.assertRaises(MigrationRejected):
            MigrationPlan.cutover_gate(True, True, True, True, 1, False)

    def test_migration_cli_inspect_backup_and_rehearse(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(0, main([
                "inspect", "--db", str(self.db), "--spool", str(self.spool),
            ]))
        self.assertEqual(1, json.loads(output.getvalue())["spool_count"])
        target = self.root / "backup_cli"
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                main(["backup", "--db", str(self.db), "--spool", str(self.spool),
                      "--backup-dir", str(target)])
        self.assertFalse(target.exists())
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(0, main([
                "backup", "--db", str(self.db), "--spool", str(self.spool),
                "--private-policy", str(self.policy), "--backup-dir", str(target),
                "--consumer-paused",
            ]))
        self.assertNotIn("test-only-credential", output.getvalue())
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(0, main(["rehearse", "--backup-dir", str(target)]))
        self.assertTrue(json.loads(output.getvalue())["restore_rehearsed"])


if __name__ == "__main__":
    unittest.main()
