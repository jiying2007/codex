from __future__ import annotations

import json
import pathlib
import subprocess
import unittest

from tools.codex_assets.core import Repo
from tools.codex_assets.governance import governance_errors


ROOT = pathlib.Path(__file__).resolve().parents[1]


class GovernanceSummaryTest(unittest.TestCase):
    def test_repository_governance_has_no_errors(self) -> None:
        self.assertEqual([], governance_errors(Repo.from_path(ROOT)))

    def test_summary_json_is_bounded_and_count_only(self) -> None:
        result = subprocess.run(
            [
                "rtk",
                "python3",
                "-m",
                "tools.codex_assets",
                "governance-report",
                "--root",
                str(ROOT),
                "--summary-json",
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(result.stdout)
        self.assertEqual("governance-summary-v1", payload["projection"])
        self.assertEqual("pass", payload["status"])
        self.assertIn("skills", payload["counts"])
        self.assertNotIn("workflow_links", payload)
        self.assertLessEqual(len(result.stdout.encode("utf-8")), 2048)


if __name__ == "__main__":
    unittest.main()
