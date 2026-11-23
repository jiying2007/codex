from __future__ import annotations

import unittest
import json
import tempfile
from pathlib import Path
from datetime import date

from tools.codex_assets.workflow_mining_report import make_report, load_rows, metadata_coverage, receipt_coverage


class WorkflowMiningReportTest(unittest.TestCase):
    def test_activity_project_reports_exact_match_and_filter_reasons(self):
        day = date(2026, 10, 2)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            item = {"schema_version": 2, "kind": "work-activity-item", "raw_content_stored": False,
                    "subject_id": "team", "project_id": "agent-dev-kit", "item_id": "goal",
                    "activity_date": day.isoformat(), "title": "Goal private title"}
            path.write_text(json.dumps({"schema_version": 2, "kind": "activity-session-receipt",
                "raw_content_stored": False, "work_items": [
                    item, item, dict(item, project_id=""), dict(item, project_id="adk"),
                    dict(item, item_id="old", activity_date="2026-10-01"),
                ]}))
            result = receipt_coverage([path], day, day, project_id="agent-dev-kit")
            self.assertEqual(1, result["distinct_work_items"])
            self.assertEqual({"out_of_window": 1, "missing_project": 1, "different_project": 1},
                             result["project_filter"]["excluded_distinct_items_by_reason"])
            self.assertEqual("zero-hit", receipt_coverage(
                [path], day, day, project_id="other")["project_filter"]["status"])
            self.assertNotIn("private title", json.dumps(result))

    def test_thread_refs_are_opt_in_and_exclude_orphans(self):
        day = date(2026, 10, 2)
        parent = "01a1f949-15c5-76d0-8d8d-cecca2ec6121"
        rows = [{"thread_id": name, "date": day.isoformat(), "title": "Goal private title"}
                for name in (parent, "child", "orphan")]
        mapping = {parent: None, "child": parent, "orphan": "missing"}
        default = make_report(rows, day, day, 3, parents=mapping)["clusters"][0]
        self.assertNotIn("main_thread_refs", default)
        sample = make_report(rows, day, day, 3, parents=mapping, include_thread_refs=True)["clusters"][0]
        self.assertEqual([parent], sample["main_thread_refs"])
        self.assertEqual(1, sample["unmapped_title_rows"])

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

    def test_parent_mapping_and_receipts_have_separate_denominators(self):
        day = date(2026, 10, 2)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / "2026/10/02"
            folder.mkdir(parents=True)
            for thread, source in (("root", "cli"), ("child", {"subagent": {
                    "thread_spawn": {"parent_thread_id": "root"}}})):
                header = {"type": "session_meta", "payload": {"id": thread, "source": source,
                          "timestamp": "2026-10-02T00:00:00Z"}}
                (folder / f"{thread}.jsonl").write_text(json.dumps(header) + "\nRAW_BODY\n")
            parents = {}
            metadata_coverage(root, day, day, parents=parents)
            rows = [{"thread_id": thread, "date": day.isoformat(), "title": "Goal private title"}
                    for thread in ("root", "child", "missing")]
            report = make_report(rows, day, day, 5, parents=parents, include_examples=True)
            cluster, = report["clusters"]
            self.assertEqual("goal_convergence", cluster["name"])
            self.assertEqual(1, cluster["mapped_main_threads"])
            self.assertEqual(1, cluster["unmapped_title_rows"])
            self.assertEqual(["goal"], cluster["examples"])
            self.assertNotIn("private title", json.dumps(report))
            item = {"schema_version": 2, "kind": "work-activity-item", "raw_content_stored": False,
                    "subject_id": "explicit-subject", "project_id": "explicit-project", "item_id": "same-item",
                    "activity_date": day.isoformat(), "title": "Goal private receipt"}
            path = root / "receipt.json"
            path.write_text(json.dumps({"schema_version": 2, "kind": "activity-session-receipt",
                "raw_content_stored": False, "work_items": [item, item]}))
            receipts = receipt_coverage([path], day, day)
            self.assertEqual(1, receipts["distinct_work_items"])
            self.assertEqual({"goal_convergence": 1}, receipts["theme_counts"])
            self.assertFalse(receipts["independent_sessions_verified"])
            self.assertNotIn("private receipt", json.dumps(receipts))

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
