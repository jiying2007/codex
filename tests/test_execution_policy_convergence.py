from __future__ import annotations

import argparse
import json
import os
import unittest
from unittest import mock

import test_execution_policy as fixtures
from tools.codex_assets.core import CodexAssetError
from tools.codex_assets import execution_policy_convergence as convergence
from tools.codex_assets.cli import build_parser


class ExecutionPolicyConvergenceTest(unittest.TestCase):
    setUp = fixtures.ExecutionPolicyAdapterTest.setUp
    run_cli = fixtures.ExecutionPolicyAdapterTest.run_cli
    start_args = fixtures.ExecutionPolicyAdapterTest.start_args

    def test_unsupported_provider_leaves_journal_unchanged(self) -> None:
        started = self.run_cli(*self.start_args("capability-test"))
        self.assertEqual(0, started.returncode, started.stderr)
        journal = next((self.codex_home / "execution-policy").glob("thread-*.jsonl"))
        before = journal.read_bytes()
        for command in (("milestone", "--criterion-id", "tests"),
                        ("progress", "--revision", "1", "--criterion-id", "tests",
                         "--change-kind", "evidence-changed", "--evidence-id", "tests")):
            with mock.patch.dict(os.environ, {"CODEX_THREAD_ID": "thread-1"}):
                args = build_parser().parse_args([
                    "execution-policy", "--root", str(fixtures.ROOT),
                    "--codex-home", str(self.codex_home), *command])
                with mock.patch.object(convergence, "require_capability", side_effect=CodexAssetError("signed exact provider required")):
                    with self.assertRaisesRegex(CodexAssetError, "signed exact provider"):
                        args.func(args)
            self.assertEqual(before, journal.read_bytes())

    def test_progress_arguments_require_complete_binding(self) -> None:
        args = argparse.Namespace(revision=1, criterion_id=None, change_kind=None, evidence_id=None,
                                  plan_before_sha256=None, plan_after_sha256=None, adjustment=None)
        self.assertEqual({"revision": 1}, convergence.progress_payload(args))
        with mock.patch.object(convergence.engine, "CONVERGENCE_CONTRACT", "execution_policy.convergence/v1", create=True):
            args.criterion_id = "tests"
            with self.assertRaises(CodexAssetError):
                convergence.progress_payload(args)
            args.change_kind = "evidence-changed"
            args.evidence_id = ["tests"]
            self.assertEqual(["tests"], convergence.progress_payload(args)["evidence_ids"])
            args.change_kind = "replan"
            with self.assertRaises(CodexAssetError):
                convergence.progress_payload(args)
            args.plan_before_sha256, args.plan_after_sha256, args.adjustment = "a" * 64, "b" * 64, "dependency"
            self.assertEqual("dependency", convergence.progress_payload(args)["adjustment"])

    def test_legacy_progress_still_uses_existing_engine_contract(self) -> None:
        self.assertEqual(0, self.run_cli(*self.start_args("legacy-test")).returncode)
        result = self.run_cli("progress", "--revision", "1")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(1, json.loads(result.stdout)["progress"]["revision"])
