"""Codex local Skill audit regressions: source-only, not native host effects."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class LocalSkillsAuditClosureTests(unittest.TestCase):
    def test_current_registrations_reject_stale_legacy_instruction(self) -> None:
        records = {r["name"]: r for r in json.loads((ROOT / "manifests/skills.json").read_text())["skills"]}
        names = ("worktree-closeout", "caveman", "codex-parallel-collab", "research-note-wrap")
        skills = {n: (ROOT / "src/codex-home" / records[n]["vendor_rel"] / "SKILL.md").read_text() for n in names}
        self.assertIn("adk-branch-closeout", skills["worktree-closeout"])
        self.assertNotIn("finishing-a-development-branch", skills["worktree-closeout"])
        self.assertNotIn("~75%", skills["caveman"])
        self.assertIn("explicit", skills["caveman"].lower())
        self.assertIn("uncertainty", skills["caveman"])
        self.assertNotIn("6-8", skills["codex-parallel-collab"])
        self.assertIn("并发上限 4", skills["codex-parallel-collab"])
        self.assertIn("授权", skills["codex-parallel-collab"])
        self.assertIn("fast path", skills["research-note-wrap"].lower())

    def test_versions_are_explicitly_bumped(self) -> None:
        records = {r["name"]: r for r in json.loads((ROOT / "manifests/skills.json").read_text())["skills"]}
        self.assertEqual("3.1.1", records["worktree-closeout"]["version"])
        self.assertEqual("1.0.1", records["caveman"]["version"])
        self.assertEqual("3.1.1", records["codex-parallel-collab"]["version"])
        self.assertEqual("3.1.1", records["research-note-wrap"]["version"])


if __name__ == "__main__":
    unittest.main()
