from __future__ import annotations

import json

from test_execution_policy import ExecutionPolicyAdapterTest


class IntakeTest(ExecutionPolicyAdapterTest):
    def intake_args(self, *extra):
        request = self.temp / "request.md"
        if not request.exists():
            request.write_text("实现 Provider 自动归档和任务 intake。", encoding="utf-8")
        return ("ensure", "--request-file", str(request), "--task-mode", "implementation",
                "--success-criterion", "tests", "--required-evidence", "tests", "--open-items", "1", *extra)

    def test_ensure_is_bound_and_idempotent(self):
        first = self.run_cli(*self.intake_args())
        self.assertEqual(0, first.returncode, first.stderr)
        result = json.loads(first.stdout)
        self.assertEqual("REGISTERED", result["status"])
        self.assertTrue(result["persisted"])
        journal = next((self.codex_home / "execution-policy").glob("*.jsonl"))
        before = journal.read_bytes()
        self.assertNotIn("实现 Provider", before.decode())
        second = self.run_cli(*self.intake_args())
        self.assertEqual(0, second.returncode, second.stderr)
        self.assertEqual("ALREADY_REGISTERED", json.loads(second.stdout)["status"])
        self.assertEqual(before, journal.read_bytes())
        gate = self.run_cli("gate", "--event", "final")
        self.assertEqual(3, gate.returncode)
        self.assertFalse(json.loads(gate.stdout)["gate_allowed"])
        (self.temp / "request.md").write_text("另一个请求", encoding="utf-8")
        changed = self.run_cli(*self.intake_args())
        self.assertEqual(2, changed.returncode)
        self.assertEqual(before, journal.read_bytes())

    def test_ensure_dry_run_does_not_create_journal(self):
        result = self.run_cli(*self.intake_args("--dry-run"))
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("PLANNED", json.loads(result.stdout)["status"])
        self.assertFalse((self.codex_home / "execution-policy").exists())

    def test_invalid_start_never_persists(self):
        result = self.run_cli(*self.intake_args("--token-budget", "-1"))
        self.assertEqual(2, result.returncode)
        self.assertEqual([], list((self.codex_home / "execution-policy").glob("*.jsonl")))

    def test_existing_dry_run_reports_persisted_without_writing(self):
        self.assertEqual(0, self.run_cli(*self.intake_args()).returncode)
        journal = next((self.codex_home / "execution-policy").glob("*.jsonl"))
        before = journal.read_bytes()
        result = self.run_cli(*self.intake_args("--dry-run"))
        self.assertEqual(0, result.returncode, result.stderr)
        receipt = json.loads(result.stdout)
        self.assertEqual("ALREADY_REGISTERED", receipt["status"])
        self.assertTrue(receipt["persisted"])
        self.assertTrue(receipt["read_only"])
        self.assertFalse(receipt["write_performed"])
        self.assertEqual(before, journal.read_bytes())

    def test_ensure_rejects_symlink_request(self):
        args = self.intake_args()
        request = self.temp / "request.md"
        saved = self.temp / "saved.md"
        request.rename(saved)
        request.symlink_to(saved)
        result = self.run_cli(*args)
        self.assertEqual(2, result.returncode)
        self.assertFalse((self.codex_home / "execution-policy").exists())

    def test_new_goal_preserves_completed_history(self):
        self.assertEqual(0, self.run_cli(*self.intake_args()).returncode)
        self.assertEqual(0, self.run_cli("goal", "abort").returncode)
        journal = next((self.codex_home / "execution-policy").glob("*.jsonl"))
        before = journal.read_bytes()
        (self.temp / "request.md").write_text("新的授权任务", encoding="utf-8")
        planned = self.run_cli(*self.intake_args("--dry-run"))
        self.assertEqual(0, planned.returncode, planned.stderr)
        created = self.run_cli(*self.intake_args())
        self.assertEqual(0, created.returncode, created.stderr)
        self.assertEqual("REGISTERED", json.loads(created.stdout)["status"])
        self.assertTrue(journal.read_bytes().startswith(before))
