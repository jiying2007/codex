from __future__ import annotations

import unittest
from datetime import date

from tools.codex_assets.workflow_mining_report import make_report


class WorkflowMiningReportTest(unittest.TestCase):
    def test_groups_titles_without_exposing_raw_session_content(self) -> None:
        report = make_report(
            [
                {"date": "2026-08-20", "title": "设备休眠后自动唤醒"},
                {"date": "2026-08-21", "title": "排查 prog_pcr02 高负载"},
            ],
            date(2026, 8, 20),
            date(2026, 8, 21),
            3,
        )
        names = [item["name"] for item in report["clusters"]]
        self.assertEqual("title-only", report["source_coverage"]["session_index"])
        self.assertEqual("not-read", report["source_coverage"]["raw_session_body"])
        self.assertIn("low_power_wakeup", names)
        self.assertIn("runtime_performance", names)


if __name__ == "__main__":
    unittest.main()
