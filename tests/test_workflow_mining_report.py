from __future__ import annotations

import unittest
import json
import tempfile
from pathlib import Path
from datetime import date

from tools.codex_assets.workflow_mining_report import make_report, load_rows, metadata_coverage


class WorkflowMiningReportTest(unittest.TestCase):
    def test_thread_rename_is_not_an_independent_recurrence(self):
        rows = [{"thread_id": "a", "date": "2026-10-01", "title": "休眠失败"},
                {"thread_id": "a", "date": "2026-10-02", "title": "语音唤醒词"},
                {"thread_id": "b", "date": "2026-10-02", "title": "休眠失败"}]
        report = make_report(rows, date(2026, 10, 1), date(2026, 10, 2), 3)
        clusters = {x["name"]: x for x in report["clusters"]}
        self.assertEqual(2, report["total_threads"])
        self.assertEqual(1, report["duplicate_rows"])
        self.assertEqual(1, clusters["low_power_wakeup"]["count"])
        self.assertEqual(1, clusters["speech_wakeup"]["count"])

    def test_unknown_ids_are_not_counted_as_threads(self):
        report = make_report([{"date": "2026-10-01", "title": "休眠"}], date(2026, 10, 1), date(2026, 10, 1), 3)
        self.assertEqual(0, report["total_threads"])
        self.assertEqual(1, report["unidentified_rows"])

    def test_hong_kong_cutoff_and_nanosecond_timestamps(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "index.jsonl"
            path.write_text("\n".join(json.dumps(x) for x in [
                {"id": "a", "thread_name": "休眠", "updated_at": "2026-10-01T16:00:00.123456789Z"},
                {"id": "b", "thread_name": "休眠", "updated_at": "2026-10-01T15:59:59Z"},
                {"id": "c", "thread_name": "休眠", "updated_at": "2026-10-02T00:00:00"}]))
            rows = load_rows(path, date(2026, 10, 2), date(2026, 10, 2))
            self.assertEqual(["a"], [x["thread_id"] for x in rows])

    def test_non_string_ids_remain_unidentified(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "index.jsonl"
            path.write_text("\n".join(json.dumps({"id": value, "thread_name": "休眠",
                            "updated_at": "2026-10-02T00:00:00Z"}) for value in (None, 42, {})))
            rows = load_rows(path, date(2026, 10, 2), date(2026, 10, 2))
            report = make_report(rows, date(2026, 10, 2), date(2026, 10, 2), 3)
            self.assertEqual(0, report["total_threads"])
            self.assertEqual(3, report["unidentified_rows"])

    def test_inventory_never_reads_body_and_separates_children(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / "2026/10/02"
            folder.mkdir(parents=True)
            for name, source in [("a", "cli"), ("b", {"subagent": {"thread_spawn": {}}})]:
                header = {"type": "session_meta", "payload": {"id": name, "source": source,
                          "timestamp": "2026-10-02T00:00:00Z"}}
                (folder / (name + ".jsonl")).write_text(json.dumps(header) + "\nRAW_SECRET_BODY\n")
            report = metadata_coverage(root, date(2026, 10, 2), date(2026, 10, 2))
            self.assertEqual(1, report["main_threads"])
            self.assertEqual(1, report["subagent_threads"])
            self.assertIsNone(report["coverage_ratio"])
            self.assertNotIn("RAW_SECRET", json.dumps(report))

    def test_inventory_rejects_links_and_malformed_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "sessions"
            folder = root / "2026/10/02"
            folder.mkdir(parents=True)
            outside = Path(directory) / "outside.jsonl"
            outside.write_text(json.dumps({"type": "session_meta", "payload": {"id": "outside",
                "source": "cli", "timestamp": "2026-10-02T00:00:00Z"}}))
            (folder / "link.jsonl").symlink_to(outside)
            (folder / "list.jsonl").write_text("[]\n")
            (folder / "bad-payload.jsonl").write_text('{"type":"session_meta","payload":[]}\n')
            report = metadata_coverage(root, date(2026, 10, 2), date(2026, 10, 2))
            self.assertEqual(0, report["main_threads"])
            self.assertEqual(3, report["invalid_or_unknown_headers"])

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
