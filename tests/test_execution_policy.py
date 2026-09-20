from __future__ import annotations

import json
import os
import pathlib
import sqlite3
import subprocess
import tempfile
import unittest

from tools.codex_assets.execution_policy_adapter import (
    ExecutionPolicyAdapterError,
    active_thread,
    load_runtime_config,
    usage_event,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]


class ExecutionPolicyAdapterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = pathlib.Path(tempfile.mkdtemp(prefix="codex-execution-policy-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.temp))
        self.codex_home = self.temp / ".codex"
        self.codex_home.mkdir()
        rollout = self.codex_home / "rollout.jsonl"
        token_record = {
            "timestamp": "2026-09-20T00:00:00Z",
            "payload": {
                "type": "token_count",
                "info": {
                    "total_token_usage": {
                        "input_tokens": 100,
                        "cached_input_tokens": 80,
                        "output_tokens": 20,
                        "reasoning_output_tokens": 5,
                        "total_tokens": 120,
                    },
                    "last_token_usage": {"input_tokens": 10, "total_tokens": 12},
                    "model_context_window": 1000,
                },
            },
        }
        rollout.write_text(json.dumps(token_record, separators=(",", ":")) + "\n", encoding="utf-8")
        with sqlite3.connect(self.codex_home / "state_5.sqlite") as db:
            db.execute(
                "create table threads (id text, model text, rollout_path text, cwd text, updated_at integer, archived integer)"
            )
            db.execute(
                "insert into threads values (?, ?, ?, ?, ?, ?)",
                ("thread-1", "gpt-5.6-sol", str(rollout), "/private/workspace", 1, 0),
            )
        self.config = load_runtime_config(ROOT)

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ)
        env["CODEX_THREAD_ID"] = "thread-1"
        env["PYTHONPATH"] = str(ROOT) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        return subprocess.run(
            ["python3", "-m", "tools.codex_assets", "execution-policy", "--root", str(ROOT), "--codex-home", str(self.codex_home), *args],
            cwd=str(self.temp),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def start_args(self, goal_id: str, *, open_items: int = 1) -> tuple[str, ...]:
        return (
            "goal", "start",
            "--goal-id", goal_id,
            "--token-budget", "1000",
            "--time-budget-seconds", "7200",
            "--success-criterion", "tests",
            "--required-evidence", "tests",
            "--open-items", str(open_items),
            "--task-mode", "implementation",
            "--request-sha256", "a" * 64,
            "--routing-decision-sha256", "b" * 64,
            "--authority-id", "digital-worker",
            "--decision-id", f"decision-{goal_id}",
            "--source-id", "digital-worker",
            "--source-version", "1.0.0",
        )

    def test_source_observation_hides_raw_cwd(self) -> None:
        thread = active_thread(self.codex_home / "state_5.sqlite")
        event = usage_event(thread)
        self.assertEqual("usage.snapshot", event["event_type"])
        self.assertNotIn("/private/workspace", json.dumps(event))

    def test_attested_goal_can_complete_final_gate(self) -> None:
        started = self.run_cli(*self.start_args("goal-1"))
        self.assertEqual(0, started.returncode, started.stderr)
        state = json.loads(started.stdout)
        self.assertEqual("implementation", state["goal"]["task_mode"])
        self.assertEqual("implementation", state["goal"]["artifact_mode"])
        self.assertEqual(1, state["goal"]["intake_revision"])

        commands = [
            ("progress", "--revision", "1"),
            ("evidence", "--evidence-id", "tests", "--sha256", "c" * 64),
            ("checkpoint", "--revision", "1", "--evidence-id", "tests"),
            ("artifact", "--artifact-type", "repo", "--evidence-id", "tests"),
            ("artifact", "--artifact-type", "build", "--evidence-id", "tests"),
            ("goal", "update", "--open-items", "0"),
            ("goal", "complete"),
        ]
        for command in commands:
            completed = self.run_cli(*command)
            self.assertEqual(0, completed.returncode, completed.stderr)
        gate = self.run_cli("gate", "--event", "final")
        self.assertEqual(0, gate.returncode, gate.stderr)
        decision = json.loads(gate.stdout)
        self.assertTrue(decision["completion_allowed"])
        self.assertEqual("pass", decision["recommended_action"])
        self.assertEqual("runtime_control.decision/v2", decision["schema_version"])

    def test_final_gate_fails_closed_for_active_goal(self) -> None:
        started = self.run_cli(*self.start_args("goal-active"))
        self.assertEqual(0, started.returncode, started.stderr)
        gate = self.run_cli("gate", "--event", "final")
        self.assertEqual(3, gate.returncode, gate.stderr)

    def test_missing_attested_goal_blocks_snapshot(self) -> None:
        result = self.run_cli("snapshot")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("requires an attested goal intake", result.stderr)

    def test_behavior_baseline_mismatch_fails_closed(self) -> None:
        config = json.loads((ROOT / "manifests/execution_policy.json").read_text(encoding="utf-8"))
        config["engine"]["behavior_baseline"]["commit"] = "0" * 40
        path = self.temp / "bad-config.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        with self.assertRaises(ExecutionPolicyAdapterError):
            load_runtime_config(ROOT, str(path))

    def test_retired_runtime_control_surfaces_are_absent(self) -> None:
        for relative in (
            "manifests/runtime_control.json",
            "scripts/runtime-control.sh",
            "scripts/execution-policy.sh",
            "tools/codex_assets/runtime_control.py",
            "tools/codex_assets/runtime_kernel.py",
        ):
            self.assertFalse((ROOT / relative).exists(), relative)


if __name__ == "__main__":
    unittest.main()
