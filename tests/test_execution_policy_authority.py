"""Exercise host routing against native user events and conservative fallbacks."""

import hashlib
import json
import os
import subprocess
from unittest.mock import patch

from test_execution_policy import ExecutionPolicyAdapterTest, ROOT
from tools.codex_assets.execution_policy_authority import routing_record
from tools.codex_assets.execution_policy_adapter import run
from tools.codex_assets.cli import build_parser


class RoutingAuthorityTest(ExecutionPolicyAdapterTest):
    def readonly_goal(self, *, real_request=True, mode="readonly"):
        request = self.temp / "request.md"
        request.write_text("请只读解释当前审批机制。\n")
        if real_request:
            rollout = self.codex_home / "rollout.jsonl"
            with rollout.open("a") as stream:
                stream.write(json.dumps({"type": "event_msg", "payload": {
                    "type": "user_message", "message": request.read_text().rstrip("\n")}}) + "\n")
        result = self.run_cli("ensure", "--request-file", str(request), "--task-mode", mode,
                              "--success-criterion", "explanation", "--required-evidence", "sources",
                              "--open-items", "1")
        self.assertEqual(0, result.returncode, result.stderr)
        return request

    def finish(self):
        for command in (("evidence", "--evidence-id", "sources", "--sha256", hashlib.sha256(b"sources").hexdigest()),
                        ("progress", "--revision", "1"),
                        ("checkpoint", "--revision", "1", "--evidence-id", "sources"),
                        ("goal", "update", "--open-items", "0"),
                        ("goal", "complete")):
            result = self.run_cli(*command)
            self.assertEqual(0, result.returncode, result.stderr)

    def test_verified_readonly_final_requires_evidence_but_no_build(self):
        self.readonly_goal()
        before = json.loads(self.run_cli("gate", "--event", "final").stdout)
        self.assertTrue(before["mode_authority_managed"])
        self.assertEqual("readonly", before["effective_artifact_mode"])
        self.assertFalse(before["gate_allowed"])
        self.assertEqual(["sources"], before["missing_evidence"])
        self.finish()
        result = self.run_cli("gate", "--event", "final")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual([], json.loads(result.stdout)["required_artifacts"])
        for event in ("apply", "commit", "release"):
            decision = json.loads(self.run_cli("gate", "--event", event).stdout)
            self.assertFalse(decision["gate_allowed"])
            self.assertFalse(decision["gate_applicable"])

    def test_request_without_native_user_event_keeps_implementation_floor(self):
        self.readonly_goal(real_request=False)
        decision = json.loads(self.run_cli("gate", "--event", "final").stdout)
        self.assertFalse(decision["mode_authority_managed"])
        self.assertEqual("implementation", decision["effective_artifact_mode"])
        self.assertEqual(["build", "repo"], decision["missing_artifacts"])

    def test_verified_implementation_retains_build_requirements(self):
        self.readonly_goal(mode="implementation")
        decision = json.loads(self.run_cli("gate", "--event", "final").stdout)
        self.assertTrue(decision["mode_authority_managed"])
        self.assertEqual(["build", "repo"], decision["missing_artifacts"])

    def test_routing_rules_drift_fails_closed(self):
        self.readonly_goal()
        with patch("tools.codex_assets.execution_policy_authority.routing_record", return_value={"changed": True}):
            from tools.codex_assets.execution_policy_adapter import snapshot
            with patch.dict(os.environ, {"CODEX_THREAD_ID": "thread-1"}):
                _, decision = snapshot(ROOT, self.config, codex_home=str(self.codex_home),
                                       gate_event="final", thread_id="thread-1")
        self.assertFalse(decision["mode_authority_managed"])
        self.assertEqual("implementation", decision["effective_artifact_mode"])

    def test_routing_digest_is_bound_to_thread_and_workspace(self):
        thread = {"thread_id": "thread-1", "cwd": str(self.temp)}
        baseline = routing_record(ROOT, thread, "a" * 64, "readonly", ["done"], ["proof"], 1)
        for changed in (dict(thread, thread_id="thread-2"), dict(thread, cwd="/")):
            self.assertNotEqual(baseline, routing_record(ROOT, changed, "a" * 64,
                                                        "readonly", ["done"], ["proof"], 1))

    def test_missing_thread_never_uses_latest_thread(self):
        env = dict(os.environ, PYTHONPATH=str(ROOT))
        env.pop("CODEX_THREAD_ID", None)
        result = subprocess.run(["bash", str(ROOT / "scripts/codex-policy.sh"),
                                 "--codex-home", str(self.codex_home), "snapshot"],
                                cwd=str(self.temp), env=env, capture_output=True, text=True)
        self.assertEqual(2, result.returncode, result.stderr)
        self.assertIn("requires CODEX_THREAD_ID", result.stderr)
        self.assertFalse((self.codex_home / "execution-policy").exists())

    def test_foreign_thread_mutation_is_rejected_before_reading_state(self):
        args = build_parser().parse_args(["execution-policy", "--thread-id", "thread-2", "goal", "abort"])
        with patch.dict(os.environ, {"CODEX_THREAD_ID": "thread-1"}):
            with self.assertRaisesRegex(RuntimeError, "cannot mutate a different thread"):
                run(args)

    def test_wrapper_help_and_dry_run_work_outside_repository(self):
        env = dict(os.environ, CODEX_THREAD_ID="thread-1")
        env.pop("PYTHONPATH", None)
        request = self.temp / "request.md"
        request.write_text("请只读解释。\n")
        for command in (("--help",), ("--codex-home", str(self.codex_home), "ensure", "--request-file", str(request),
                                      "--task-mode", "readonly", "--success-criterion", "done",
                                      "--required-evidence", "sources", "--open-items", "1", "--dry-run")):
            result = subprocess.run(["bash", str(ROOT / "scripts/codex-policy.sh"), *command],
                                    cwd=str(self.temp), env=env, capture_output=True, text=True)
            self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse((self.codex_home / "execution-policy").exists())
