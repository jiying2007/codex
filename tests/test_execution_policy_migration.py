"""Frozen old-source replay and host integration; no live-provider qualification."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from datetime import datetime
from pathlib import Path
import tempfile
import unittest

from tests import test_execution_policy as adapter_fixtures
from tests.test_governance import make_repo
from tools.codex_assets import execution_policy
from tools.codex_assets.execution_policy.contracts import ExecutionPolicyError, validate_policy
from tools.codex_assets.execution_policy.decision import evaluate
from tools.codex_assets.execution_policy.reducer import reduce_events
from tools.codex_assets.execution_policy_adapter import (
    ExecutionPolicyAdapterError, load_journal, load_runtime_config,
)

ROOT = Path(__file__).resolve().parents[1]
REPLAY = ROOT / "tests/fixtures/execution-policy-migration-replay.json"


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()


class ExecutionPolicyMigrationTests(unittest.TestCase):
    def test_public_api_and_consumers_use_real_owners_without_engine_shim(self) -> None:
        self.assertIs(execution_policy.evaluate, evaluate)
        self.assertIs(execution_policy.reduce_events, reduce_events)
        self.assertIs(execution_policy.validate_policy, validate_policy)
        self.assertEqual("tools.codex_assets.execution_policy.decision", evaluate.__module__)
        self.assertEqual("tools.codex_assets.execution_policy.reducer", reduce_events.__module__)
        self.assertEqual("tools.codex_assets.execution_policy.contracts", validate_policy.__module__)
        self.assertIsNone(importlib.util.find_spec("tools.codex_assets.execution_policy.engine"))

    def test_frozen_old_journal_replays_with_identical_state_and_gate_results(self) -> None:
        fixture = json.loads(REPLAY.read_text(encoding="utf-8"))
        self.assertEqual("synthetic-regression-not-live", fixture["evidence_class"])
        self.assertEqual("7.0.4", fixture["baseline_provider_version"])
        self.assertEqual("05dd80065ec4c58c342e48ff12d4cd53d3897740", fixture["baseline_engine_blob"])
        self.assertEqual("626af591141b2dda6302edbe4363637435066628", fixture["baseline_contracts_blob"])
        self.assertEqual(19, len(fixture["cases"]))
        self.assertEqual(fixture["policy"], load_runtime_config(ROOT)["policy"])
        for case in fixture["cases"]:
            with self.subTest(case=case["name"]), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "old-journal.jsonl"
                original = "".join(json.dumps(event) + "\n" for event in case["events"]).encode()
                path.write_bytes(original)
                events = load_journal(path)
                if "expected_error" in case:
                    with self.assertRaises(ExecutionPolicyError) as error:
                        reduce_events(events)
                    self.assertEqual(case["expected_error"], str(error.exception))
                else:
                    state = reduce_events(events)
                    result = evaluate(state, fixture["policy"], gate_event=case["gate_event"],
                                      as_of=datetime.fromisoformat(case["as_of"]))
                    self.assertEqual(case["state_sha256"], digest(state))
                    self.assertEqual(case["decision_sha256"], digest(result))
                    self.assertEqual(case["expected_action"], result["recommended_action"])
                    self.assertIs(case["expected_gate_allowed"], result["gate_allowed"])
                self.assertEqual(original, path.read_bytes())

    def test_old_custom_config_is_rejected_not_silently_reinterpreted(self) -> None:
        root = make_repo(self)
        path = root / "manifests/execution_policy.json"
        original = json.loads(path.read_text(encoding="utf-8"))
        for mutation in ("schema", "module", "blobs"):
            value = copy.deepcopy(original)
            if mutation == "schema":
                value["schema_version"] = 3
            elif mutation == "module":
                value["engine"]["module"] += ".engine"
            else:
                value["engine"]["behavior_baseline"]["engine_blob"] = "0" * 40
            custom = root / "custom.json"
            custom.write_text(json.dumps(value), encoding="utf-8")
            with self.subTest(mutation=mutation), self.assertRaises(ExecutionPolicyAdapterError):
                load_runtime_config(root, str(custom))

    def test_retired_engine_cannot_remain_alongside_valid_new_source(self) -> None:
        root = make_repo(self)
        path = root / "tools/codex_assets/execution_policy/engine.py"
        path.write_text("# old namespace must not be retained\n", encoding="utf-8")
        with self.assertRaisesRegex(ExecutionPolicyAdapterError, "retired Execution Policy module"):
            load_runtime_config(root)

    def test_each_new_module_rejects_symbolic_substitution(self) -> None:
        root = make_repo(self)
        for name in ("__init__.py", "contracts.py", "decision.py", "reducer.py"):
            path = root / "tools/codex_assets/execution_policy" / name
            data = path.read_bytes()
            substitute = root / (name + ".copy")
            substitute.write_bytes(data)
            path.unlink()
            path.symlink_to(substitute)
            with self.subTest(name=name), self.assertRaises(ExecutionPolicyAdapterError):
                load_runtime_config(root)
            path.unlink()
            path.write_bytes(data)

    def test_project_owned_cli_goal_completes_without_digital_worker_authority(self) -> None:
        fixture = adapter_fixtures.ExecutionPolicyAdapterTest()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        arguments = tuple("project-owner" if value == "digital-worker" else value
                          for value in fixture.start_args("project-goal"))
        result = fixture.run_cli(*arguments)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("project-owner", json.loads(result.stdout)["goal"]["mode_authority_id"])
        for command in (
            ("progress", "--revision", "1"),
            ("evidence", "--evidence-id", "tests", "--sha256", "c" * 64),
            ("checkpoint", "--revision", "1", "--evidence-id", "tests"),
            ("artifact", "--artifact-type", "repo", "--evidence-id", "tests"),
            ("artifact", "--artifact-type", "build", "--evidence-id", "tests"),
            ("goal", "update", "--open-items", "0"), ("goal", "complete"),
        ):
            result = fixture.run_cli(*command)
            self.assertEqual(0, result.returncode, result.stderr)
        gate = fixture.run_cli("gate", "--event", "final")
        self.assertEqual(0, gate.returncode, gate.stderr)
        self.assertTrue(json.loads(gate.stdout)["completion_allowed"])


if __name__ == "__main__":
    unittest.main()
