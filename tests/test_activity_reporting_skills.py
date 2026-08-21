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
            "project-activity-report": "1.0.0",
            "project-daily-summary": "3.2.0",
            "commit-daily-summary": "3.2.0",
            "session-wrap": "3.2.0",
            "chronicle-workflow-miner": "1.2.0",
        }
        for name, version in expected.items():
            with self.subTest(skill=name):
                self.assertEqual(version, skills[name]["version"])
                self.assertTrue((ROOT / "src/codex-home" / skills[name]["vendor_rel"] / "SKILL.md").is_file())

        workflows = {row["name"]: row for row in read_json("manifests/workflows.json")["workflows"]}
        workflow = workflows["activity-reporting"]
        self.assertEqual("project-activity-report", workflow["routes"][0]["primary_skill"])
        self.assertIn("token-lean", workflow["profiles"])

    def test_reporting_skill_is_facts_first_and_privacy_bounded(self) -> None:
        skill = (
            ROOT
            / "src/codex-home/vendor/skills/project-activity-report/1.0.0/SKILL.md"
        ).read_text(encoding="utf-8")
        contract = (
            ROOT
            / "src/codex-home/vendor/skills/project-activity-report/1.0.0/references/facts-contract.md"
        ).read_text(encoding="utf-8")
        self.assertIn("activity facts JSON", skill)
        self.assertIn("Do not read raw sessions", skill)
        self.assertIn("Never infer completion from commit count", skill)
        self.assertIn('"raw_content_stored": false', contract)
        self.assertIn("`session_receipts[]`", contract)
        self.assertIn(".tmp/session-receipts/YYYY-MM-DD/<receipt-id>.json", contract)
        self.assertIn("Stop and report `needs-fix`", contract)

    def test_session_receipt_is_bounded_and_chronicle_uses_it_first(self) -> None:
        session_wrap = (
            ROOT / "src/codex-home/vendor/skills/session-wrap/3.2.0/SKILL.md"
        ).read_text(encoding="utf-8")
        miner = (
            ROOT / "src/codex-home/vendor/skills/chronicle-workflow-miner/1.2.0/SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn('"kind": "codex-session-receipt"', session_wrap)
        self.assertIn('"completion_status": "complete|partial|blocked"', session_wrap)
        self.assertIn("Governed daily/weekly activity facts", miner)
        self.assertIn("Raw Codex history/session transcripts only as an explicit", miner)
        self.assertIn("three sessions across at least two projects", miner)


if __name__ == "__main__":
    unittest.main()
