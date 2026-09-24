"""Declared operator commands must resolve to the current parser, not a retired wrapper."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import shlex
import unittest

from tools.codex_assets.cli import build_parser

ROOT = Path(__file__).resolve().parents[1]


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from strings(child)


class OperatorExecutionPolicyTests(unittest.TestCase):
    def test_manifests_do_not_recommend_retired_runtime_entrypoints(self) -> None:
        for path in sorted((ROOT / "manifests").glob("*.json")):
            if path.name == "lock.json":
                continue  # generated asset index is not an operator contract
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path.name):
                self.assertNotIn("scripts/runtime-control.sh", text)
                self.assertNotIn("tests.test_runtime_control", text)
                self.assertNotIn('"name": "runtime-control"', text)

    def test_declared_commands_parse_and_runtime_actions_bind_current_thread(self) -> None:
        prefix = "rtk python3 -m tools.codex_assets execution-policy"
        count = 0
        for path in sorted((ROOT / "manifests").glob("*.json")):
            if path.name == "lock.json":
                continue
            for command in strings(json.loads(path.read_text(encoding="utf-8"))):
                if not command.startswith(prefix):
                    continue
                count += 1
                args = shlex.split(command)[4:]
                with self.subTest(path=path.name, command=command), contextlib.redirect_stdout(io.StringIO()):
                    if "--help" in args:
                        with self.assertRaises(SystemExit) as exit:
                            build_parser().parse_args(args)
                        self.assertEqual(0, exit.exception.code)
                    else:
                        parsed = build_parser().parse_args(args)
                        self.assertEqual("${CODEX_THREAD_ID:?current thread id required}", parsed.thread_id)
                        self.assertIn(parsed.runtime_action, {"snapshot", "watch", "gate"})
        self.assertGreaterEqual(count, 20)

    def test_canonical_workflow_keeps_existing_profiles_and_skills(self) -> None:
        items = json.loads((ROOT / "manifests/workflows.json").read_text())["workflows"]
        workflow = next(item for item in items if item["name"] == "execution-policy")
        self.assertIs(workflow["enabled"], True)
        self.assertEqual(["solo-dev", "team-collab"], workflow["profiles"])
        self.assertEqual(["adk-planning-execution-loop", "adk-token-context-governance", "adk-verification-before-completion"], workflow["skills"])
        self.assertNotIn("Runtime Control", workflow["triggers"])
        self.assertIn("Execution Policy", workflow["triggers"])


if __name__ == "__main__":
    unittest.main()
