from __future__ import annotations

import json
import os
import pathlib
import sqlite3
import subprocess
import tempfile
import unittest

from tools.codex_assets.runtime_control import (
    RuntimeControlAdapterError,
    active_thread,
    load_runtime_config,
    snapshot,
    usage_event,
)


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/runtime-control.sh"


class RuntimeControlAdapterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = pathlib.Path(tempfile.mkdtemp(prefix="codex-runtime-control-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.temp))
        self.codex_home = self.temp / ".codex"
        self.codex_home.mkdir()
        rollout = self.codex_home / "rollout.jsonl"
        token_record = {
            "timestamp": "2026-08-24T02:00:00Z",
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
        return subprocess.run(
            [str(SCRIPT), "--codex-home", str(self.codex_home), *args],
            cwd=str(self.temp),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_snapshot_uses_only_canonical_sources_and_hides_raw_cwd(self) -> None:
        thread = active_thread(self.codex_home / "state_5.sqlite")
        event = usage_event(thread)
        self.assertEqual("usage.snapshot", event["event_type"])
        self.assertNotIn("/private/workspace", json.dumps(event))
        state, decision = snapshot(ROOT, self.config, codex_home=str(self.codex_home))
        self.assertEqual("runtime_control.state/v1", state["schema_version"])
        self.assertEqual("idle", state["goal"]["status"])
        self.assertEqual("continue", decision["recommended_action"])

    def test_explicit_thread_identity_wins_over_newer_concurrent_thread(self) -> None:
        with sqlite3.connect(self.codex_home / "state_5.sqlite") as db:
            db.execute(
                "insert into threads values (?, ?, ?, ?, ?, ?)",
                ("thread-newer", "gpt-5.6-sol", str(self.codex_home / "rollout.jsonl"), "/other", 99, 0),
            )
        selected = active_thread(self.codex_home / "state_5.sqlite", "thread-1")
        self.assertEqual("thread-1", selected["thread_id"])

    def test_single_cli_completes_goal_and_final_gate_from_non_repo_cwd(self) -> None:
        commands = [
            ("goal", "start", "--goal-id", "goal-1", "--token-budget", "1000", "--time-budget-seconds", "7200", "--success-criterion", "tests", "--required-evidence", "tests", "--required-evidence", "review", "--open-items", "1"),
            ("progress", "--revision", "1"),
            ("evidence", "--evidence-id", "tests", "--sha256", "b" * 64),
            ("evidence", "--evidence-id", "review", "--sha256", "c" * 64),
            ("checkpoint", "--revision", "1", "--evidence-id", "tests", "--evidence-id", "review"),
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
        journal_text = next((self.codex_home / "runtime-control").glob("*.jsonl")).read_text(encoding="utf-8")
        for forbidden in ("prompt", "objective", "/private/workspace"):
            self.assertNotIn(forbidden, journal_text)

    def test_gate_fails_without_completed_goal(self) -> None:
        result = self.run_cli("gate", "--event", "final")
        self.assertEqual(3, result.returncode)
        self.assertEqual("replan", json.loads(result.stdout)["recommended_action"])

    def test_snapshot_and_watch_share_the_decision_contract(self) -> None:
        one = self.run_cli("snapshot")
        watched = self.run_cli("watch", "--iterations", "1")
        self.assertEqual(0, one.returncode, one.stderr)
        self.assertEqual(0, watched.returncode, watched.stderr)
        self.assertEqual("runtime_control.decision/v1", json.loads(one.stdout)["schema_version"])
        self.assertEqual("runtime_control.decision/v1", json.loads(watched.stdout)["schema_version"])

    def test_apply_gate_passes_for_healthy_active_goal_with_verified_artifacts(self) -> None:
        commands = [
            ("goal", "start", "--goal-id", "goal-apply", "--token-budget", "1000", "--time-budget-seconds", "7200", "--success-criterion", "tests", "--required-evidence", "tests", "--open-items", "1"),
            ("evidence", "--evidence-id", "tests", "--sha256", "b" * 64),
            ("artifact", "--artifact-type", "repo", "--evidence-id", "tests"),
            ("artifact", "--artifact-type", "build", "--evidence-id", "tests"),
            ("artifact", "--artifact-type", "plan", "--evidence-id", "tests"),
            ("artifact", "--artifact-type", "dry-run", "--evidence-id", "tests"),
        ]
        for command in commands:
            completed = self.run_cli(*command)
            self.assertEqual(0, completed.returncode, completed.stderr)
        gate = self.run_cli("gate", "--event", "apply")
        self.assertEqual(0, gate.returncode, gate.stderr)
        decision = json.loads(gate.stdout)
        self.assertTrue(decision["gate_allowed"])
        self.assertFalse(decision["completion_allowed"])

    def test_engine_hash_mismatch_fails_closed(self) -> None:
        config = json.loads((ROOT / "manifests/runtime_control.json").read_text(encoding="utf-8"))
        config["engine"]["sha256"] = "0" * 64
        path = self.temp / "bad-config.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        with self.assertRaises(RuntimeControlAdapterError):
            load_runtime_config(ROOT, str(path))


if __name__ == "__main__":
    unittest.main()
