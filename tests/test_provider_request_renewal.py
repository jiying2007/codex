"""Explicit cross-day request renewal preserves expiry, budgets and read-only provenance."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.codex_assets import execution_policy_adapter as adapter
from tools.codex_assets.execution_policy_intake import verify_request


RENEWAL = "将当前目标总时间预算延长至 24 小时，沿用剩余 token 和既有提交、推送、合并、应用授权继续执行。"


class ProviderRequestRenewalTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.now = datetime.now(timezone.utc)
        self.old = self.now - timedelta(days=1)
        self.request = self.root / "request.txt"
        self.request.write_text("全部优化落地\n")
        self.renewal = self.root / "renewal.txt"
        self.renewal.write_text(RENEWAL + "\n")
        self.rollout = self.root / "rollout.jsonl"
        self.journal = self.root / "journal.jsonl"
        self.thread = {"thread_id": "current", "rollout_path": str(self.rollout),
                       "cwd": str(self.root), "model": "fixture"}
        self.config = adapter.load_runtime_config(Path(__file__).resolve().parents[1])
        args = argparse.Namespace(task_mode="implementation", issued_at="", goal_id="existing-goal",
            request_sha256=hashlib.sha256(self.request.read_bytes()).hexdigest(),
            routing_decision_sha256="b" * 64, authority_id="digital-worker", source_id="fixture",
            source_version="1", decision_id="original-decision")
        with patch.object(adapter, "_now", return_value=self.old):
            self.intake = adapter._goal_intake(args, self.old)
            self.events = [adapter.control_event("goal.started", "current", {
                "goal_id": "existing-goal", "token_budget": 1000, "time_budget_seconds": 172800,
                "usage_baseline_tokens": 0, "success_criteria": ["verified"],
                "required_evidence": ["verified"], "open_items_count": 1, "intake": self.intake})]
        self._write_journal()
        self._write_rollout()

    def _write_journal(self):
        self.journal.write_text("\n".join(json.dumps(row) for row in self.events) + "\n")

    def _write_rollout(self, *, old_role="user", renewal_role="user", renewal_at=None, renewal_text=RENEWAL):
        rows = [{"timestamp": self.old.isoformat(), "type": "response_item", "payload": {
            "role": old_role, "content": [{"type": "input_text", "text": self.request.read_text().strip()}]}},
            {"timestamp": (renewal_at or self.now).isoformat(), "type": "response_item", "payload": {
                "role": renewal_role, "content": [{"type": "input_text", "text": renewal_text}]}},
            {"timestamp": self.now.isoformat(), "payload": {"type": "token_count", "info": {
                "total_token_usage": {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
                "last_token_usage": {"input_tokens": 10, "total_tokens": 12}, "model_context_window": 1000}}}]
        self.rollout.write_text("\n".join(json.dumps(row, separators=(",", ":")) for row in rows) + "\n")

    def _verify(self, renewal=True, budget=None):
        args = argparse.Namespace(thread_id="current", request_file=str(self.request),
                                  renewal_request_file=str(self.renewal) if renewal else "")
        receipts = []
        def evaluated(state, config, event):
            result = adapter.evaluate(state, config["policy"], gate_event=event, as_of=self.now)
            if budget:
                result["budget_status"]["status"] = budget
            return result
        before = self.journal.read_bytes(), self.rollout.read_bytes()
        with patch.dict(os.environ, {"CODEX_THREAD_ID": "current"}), \
                patch.object(adapter, "_active_context", return_value=(None, self.config, None, self.thread, self.journal)), \
                patch.object(adapter, "_now", return_value=self.now), \
                patch.object(adapter, "_decision", side_effect=evaluated), \
                patch.object(adapter, "_emit", side_effect=receipts.append):
            code = verify_request(args)
        self.assertEqual(before, (self.journal.read_bytes(), self.rollout.read_bytes()))
        return code, receipts[-1]

    def test_expired_without_explicit_renewal_still_fails(self):
        code, receipt = self._verify(renewal=False)
        self.assertEqual(code, 2)
        self.assertEqual(receipt["status"], "UNVERIFIED")

    def test_fresh_native_renewal_uses_real_engine_budget_and_binds_all_inputs(self):
        code, receipt = self._verify()
        self.assertEqual(code, 0)
        provenance = receipt["renewal_provenance"]
        attestation = provenance.pop("attestation_sha256")
        self.assertEqual(attestation, hashlib.sha256(json.dumps(
            provenance, sort_keys=True, separators=(",", ":")).encode()).hexdigest())
        self.assertEqual(provenance["original_attestation_sha256"], self.intake["attestation_sha256"])
        self.assertEqual(provenance["renewal_request_sha256"], hashlib.sha256(self.renewal.read_bytes()).hexdigest())
        self.assertEqual(provenance["goal_id"], "existing-goal")
        self.assertEqual(provenance["issued_on"], self.now.date().isoformat())
        self.assertEqual(receipt["purpose"], "request-provenance-only;not-owner-approval")
        self.assertNotIn(RENEWAL, json.dumps(receipt, ensure_ascii=False))
        self.assertNotIn(str(self.root), json.dumps(receipt))

    def test_old_request_must_be_native_user(self):
        self._write_rollout(old_role="assistant")
        self.assertEqual(self._verify()[0], 2)

    def test_renewal_must_be_native_user(self):
        self._write_rollout(renewal_role="assistant")
        self.assertEqual(self._verify()[0], 2)

    def test_renewal_must_match_exact_native_text(self):
        self._write_rollout(renewal_text=RENEWAL + " 改变范围")
        self.assertEqual(self._verify()[0], 2)

    def test_native_renewal_must_be_current_utc_day(self):
        self._write_rollout(renewal_at=self.old)
        self.assertEqual(self._verify()[0], 2)

    def test_future_day_native_renewal_is_not_current(self):
        self._write_rollout(renewal_at=self.now + timedelta(days=1))
        self.assertEqual(self._verify()[0], 2)

    def test_explicit_continuation_and_existing_authorization_are_required(self):
        for text in ("将当前目标预算延长24小时", "沿用授权继续执行", "不要将当前目标预算延长，沿用授权继续执行"):
            with self.subTest(text=text):
                self.renewal.write_text(text)
                self._write_rollout(renewal_text=text)
                self.assertEqual(self._verify()[0], 2)

    def test_original_intake_is_required(self):
        self.events = []
        self._write_journal()
        with self.assertRaises(adapter.ExecutionPolicyAdapterError):
            self._verify()

    def test_completed_or_aborted_current_goal_cannot_renew(self):
        for kind in ("goal.completed", "goal.aborted"):
            with self.subTest(kind=kind), patch.object(adapter, "_now", return_value=self.now):
                self.events = self.events[:1] + [adapter.control_event(kind, "current", {})]
                self._write_journal()
                self.assertEqual(self._verify()[0], 2)

    def test_exhausted_actual_token_budget_cannot_renew(self):
        self.events[0]["payload"]["token_budget"] = 100
        self._write_journal()
        self.assertEqual(self._verify()[0], 2)

    def test_exhausted_actual_time_budget_cannot_renew(self):
        self.events[0]["payload"]["time_budget_seconds"] = 3600
        self._write_journal()
        self.assertEqual(self._verify()[0], 2)

    def test_unknown_budget_is_not_within(self):
        self.assertEqual(self._verify(budget="unknown")[0], 2)

    def test_current_thread_must_match_environment(self):
        args = argparse.Namespace(thread_id="other", request_file=str(self.request), renewal_request_file=str(self.renewal))
        with patch.dict(os.environ, {"CODEX_THREAD_ID": "current"}), self.assertRaises(adapter.ExecutionPolicyAdapterError):
            verify_request(args)

    def test_parser_renewal_is_explicit_optional_flag(self):
        parser = argparse.ArgumentParser()
        adapter.configure_parser(parser)
        base = ["verify-request", "--request-file", str(self.request)]
        self.assertEqual(parser.parse_args(base).renewal_request_file, "")
        self.assertEqual(parser.parse_args(base + ["--renewal-request-file", str(self.renewal)]).renewal_request_file, str(self.renewal))

    def test_renewal_symlink_is_rejected(self):
        saved = self.root / "saved-renewal.txt"
        self.renewal.rename(saved)
        self.renewal.symlink_to(saved)
        with self.assertRaises(adapter.ExecutionPolicyAdapterError):
            self._verify()


if __name__ == "__main__":
    unittest.main()
