from __future__ import annotations

import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def read_json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class ActivityReportingSkillTest(unittest.TestCase):
    def test_active_versions_and_workflow_are_registered(self) -> None:
        skills = {row["name"]: row for row in read_json("manifests/skills.json")["skills"]}
        expected = {
            "activity-report": "1.0.0",
            "git-activity-summary": "1.0.0",
            "session-wrap": "4.0.0",
            "chronicle-workflow-miner": "1.3.0",
        }
        for name, version in expected.items():
            with self.subTest(skill=name):
                self.assertEqual(version, skills[name]["version"])
                self.assertTrue((ROOT / "src/codex-home" / skills[name]["vendor_rel"] / "SKILL.md").is_file())

        workflows = {row["name"]: row for row in read_json("manifests/workflows.json")["workflows"]}
        workflow = workflows["activity-reporting"]
        self.assertEqual("activity-report", workflow["routes"][0]["primary_skill"])
        self.assertIn("token-lean", workflow["profiles"])
        self.assertTrue(all(not route.get("fallback_skill") for route in workflow["routes"]))

    def test_reporting_skill_is_facts_first_and_privacy_bounded(self) -> None:
        skill = (
            ROOT
            / "src/codex-home/vendor/skills/activity-report/1.0.0/SKILL.md"
        ).read_text(encoding="utf-8")
        contract = (
            ROOT
            / "src/codex-home/vendor/skills/activity-report/1.0.0/references/facts-contract.md"
        ).read_text(encoding="utf-8")
        self.assertIn("activity-facts-v2", skill)
        self.assertIn("Do not read raw sessions", skill)
        self.assertIn("do not prove completion or personal ownership", skill)
        self.assertIn("work-activity-item", contract)
        self.assertIn("identity inference", contract)
        self.assertIn("needs-fix", contract)

    def test_session_receipt_is_bounded_and_chronicle_uses_it_first(self) -> None:
        session_wrap = (
            ROOT / "src/codex-home/vendor/skills/session-wrap/4.0.0/SKILL.md"
        ).read_text(encoding="utf-8")
        miner = (
            ROOT / "src/codex-home/vendor/skills/chronicle-workflow-miner/1.3.0/SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn('"kind": "activity-session-receipt"', session_wrap)
        self.assertIn('"kind": "work-activity-item"', session_wrap)
        self.assertIn('"verification": "verified|reported|missing"', session_wrap)
        self.assertIn("Governed daily/weekly activity facts", miner)
        self.assertIn("Raw Codex history/session transcripts only as an explicit", miner)
        self.assertIn("three sessions across at least two projects", miner)


if __name__ == "__main__":
    unittest.main()
