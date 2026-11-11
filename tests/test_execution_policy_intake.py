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

    def test_automatic_budget_scales_with_trusted_last_turn_usage(self):
        # One large observed turn must no longer silently inherit a 300K cap.
        rollout = self.codex_home / "rollout.jsonl"
        item = json.loads(rollout.read_text(encoding="utf-8").splitlines()[0])
        item["payload"]["info"]["total_token_usage"] = {
            "input_tokens": 240000, "cached_input_tokens": 230000,
            "output_tokens": 10000, "reasoning_output_tokens": 2000,
            "total_tokens": 250000,
        }
        item["payload"]["info"]["last_token_usage"] = {
            "input_tokens": 220000, "total_tokens": 250000,
        }
        rollout.write_text(json.dumps(item, separators=(",", ":")) + "\n", encoding="utf-8")
        result = self.run_cli(*self.intake_args())
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt["budget_basis"], "measured-last-turn-per-goal-proposal")
        self.assertGreaterEqual(receipt["token_budget"], 2000000)
        journal = next((self.codex_home / "execution-policy").glob("*.jsonl"))
        recorded = json.loads(journal.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(recorded["payload"]["token_budget"], receipt["token_budget"])
        # Retry does not append a new Goal or change its budget.
        before = journal.read_bytes()
        retry = self.run_cli(*self.intake_args())
        self.assertEqual(retry.returncode, 0, retry.stderr)
        self.assertEqual(json.loads(retry.stdout)["budget_basis"], "existing-goal")
        self.assertEqual(journal.read_bytes(), before)

    def test_explicit_budget_overrides_automatic_estimate(self):
        result = self.run_cli(*self.intake_args("--token-budget", "450000"))
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt["budget_basis"], "explicit")
        self.assertEqual(receipt["token_budget"], 450000)

    def test_missing_last_turn_usage_requires_explicit_budget(self):
        rollout = self.codex_home / "rollout.jsonl"
        item = json.loads(rollout.read_text(encoding="utf-8").splitlines()[0])
        item["payload"]["info"]["last_token_usage"]["total_tokens"] = 0
        rollout.write_text(json.dumps(item, separators=(",", ":")) + "\n", encoding="utf-8")
        refused = self.run_cli(*self.intake_args())
        self.assertEqual(refused.returncode, 2)
        self.assertIn("--token-budget", refused.stderr)
        self.assertFalse((self.codex_home / "execution-policy").exists())
        explicit = self.run_cli(*self.intake_args("--token-budget", "500000"))
        self.assertEqual(explicit.returncode, 0, explicit.stderr)

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

    def test_rejected_actions_do_not_poison_journal(self):
        self.assertEqual(0, self.run_cli(*self.intake_args()).returncode)
        self.assertEqual(0, self.run_cli('progress', '--revision', '1').returncode)
        journal = next((self.codex_home / 'execution-policy').glob('*.jsonl'))
        before = journal.read_bytes()
        for action in [('progress', '--revision', '1'),
                       ('progress', '--revision', '0')]:
            rejected = self.run_cli(*action)
            self.assertEqual(2, rejected.returncode, rejected.stderr)
            self.assertEqual(before, journal.read_bytes())
        self.assertEqual(0, self.run_cli('goal', 'status').returncode)

    def test_duplicate_progress_recovery_preserves_original_and_valid_history(self):
        self.assertEqual(0, self.run_cli(*self.intake_args()).returncode)
        self.assertEqual(0, self.run_cli('progress', '--revision', '1').returncode)
        journal = next((self.codex_home / 'execution-policy').glob('*.jsonl'))
        event = json.loads(journal.read_text().splitlines()[-1])
        event['event_id'] = 'evt-rejected-duplicate'
        with journal.open('a') as stream:
            stream.write(json.dumps(event) + '\n')
        before = journal.read_bytes()
        plan = self.run_cli('journal')
        self.assertEqual(0, plan.returncode, plan.stderr)
        result = json.loads(plan.stdout)
        self.assertEqual(1, result['rejected_count'])
        self.assertEqual(before, journal.read_bytes())
        stale = self.run_cli('journal', '--apply', '--expected-sha256', '0' * 64)
        self.assertEqual(2, stale.returncode)
        self.assertEqual(before, journal.read_bytes())
        applied = self.run_cli('journal', '--apply', '--expected-sha256', result['before_sha256'])
        self.assertEqual(0, applied.returncode, applied.stderr)
        receipt = json.loads(applied.stdout)
        self.assertEqual('RECOVERED', receipt['status'])
        self.assertEqual(before, (journal.parent / receipt['backup_name']).read_bytes())
        self.assertEqual(0, self.run_cli('goal', 'status').returncode)
