from __future__ import annotations

import contextlib
import io
import json
import os
import pathlib
import subprocess
import tempfile
import unittest
from unittest import mock

from tools.codex_assets import feishu_cli_coverage as cover
from tools.codex_assets import feishu_cli_read as read
from tests.test_feishu_cli_read import args, DOC


class CoverageTest(unittest.TestCase):
    def test_column_gap_never_skips_unread_cells(self):
        value = cover.sheet_coverage({"actual_range": "A1:B7", "has_more": True, "col_indices": ["A", "B"]}, "A1:C20")
        self.assertEqual("partial", value["status"])
        self.assertNotIn("next_range", value["upstream_coverage"][0])
        self.assertTrue(value["upstream_coverage"][0]["continuation_requires_smaller_window"])

    def test_all_truncation_names_and_nested_signals_prevent_complete(self):
        for flag in cover.TRUNCATION_KEYS:
            for payload in ({"actual_range": "A1:C3", flag: True}, {"ranges": [{"actual_range": "A1:C3", flag: True}]}, {"actual_range": "A1:C3", "sheets": [{"ranges": [{flag: True}]}]}):
                result = cover.sheet_coverage(payload, "A1:C3")
                self.assertFalse(result["window_complete"])
                self.assertTrue(result["truncation_signals"])

    def test_coordinates_outside_window_or_sparse_are_unknown(self):
        for payload in ({"actual_range": "A1:C4"}, {"actual_range": "A1:C3", "row_indices": [1, 3]}, {"actual_range": "A1:C3", "col_indices": ["A", "C"]}, {}):
            result = cover.sheet_coverage(payload, "A1:C3")
            self.assertEqual("unknown", result["status"])
            self.assertFalse(result["window_complete"])

    def test_exact_window_with_coordinates_is_complete_but_not_whole_sheet(self):
        source = {"sheet_id": "Sheet1"}
        result = cover.sheet_coverage({"actual_range": "AA101:AZ102", "row_indices": [101, 102], "col_indices": [cover.column_label(i) for i in range(27, 53)]}, "AA101:AZ102")
        self.assertTrue(result["window_complete"])
        self.assertFalse(cover.coverage_receipt(source, result, "1")["whole_resource_complete"])

    def test_complete_width_row_continuation_overlaps_last_row(self):
        result = cover.sheet_coverage({"actual_range": "A1:C7", "has_more": True}, "A1:C20")
        self.assertEqual("A7:C20", result["upstream_coverage"][0]["next_range"])

    def test_doc_full_and_unheaded_prelude_are_in_inventory(self):
        data = {"document": {"content": '<p block-id="pre">前言</p><h1 block-id="head">章</h1><p block-id="body">正文</p>', "revision_id": 42}}
        value = cover.document_coverage(data, "full")
        self.assertEqual(["pre", "head", "body"], value["top_level_block_ids"])
        self.assertTrue(value["full_document_complete"])
        self.assertEqual("42", cover.revision_of(data))

    def test_outline_depth_excerpt_and_embedded_never_claim_full(self):
        for content, scope, depth in (('<fragment><h1 block-id="h">标题</h1></fragment>', "outline", -1), ('<p block-id="p"/>', "range", 0), ('<excerpt top-block-id="t"><table block-id="t"/></excerpt>', "full", -1), ('<p/><img token="unsupported"/>', "full", -1)):
            value = cover.document_coverage({"document": {"content": content}}, scope, "0", "-1", depth)
            self.assertFalse(value["full_document_complete"])

    def test_unsafe_or_invalid_xml_is_unknown(self):
        for content in ('<!DOCTYPE x [<!ENTITY a "x">]><p>&a;</p>', '<p>unclosed'):
            value = cover.document_coverage({"document": {"content": content}}, "full")
            self.assertEqual("unknown", value["status"])

    def test_comments_truncation_and_limited_depth_do_not_claim_full(self):
        data = {"document": {"content": '<p block-id="P1">x</p>', "reference_map": {"comments": {"tips": {"data": "comments truncated"}}}}}
        self.assertFalse(cover.document_coverage(data, "full")["full_document_complete"])
        value = cover.document_coverage({"document": {"content": '<p block-id="P1">x</p>'}}, "range", "0", "-1", 1)
        self.assertEqual("structure-only", value["status"])
        self.assertFalse(value["full_document_complete"])

    def test_upstream_scope_mismatch_cannot_claim_full(self):
        for content in ('<fragment mode="keyword"><p block-id="P1">x</p></fragment>', '<fragment><p block-id="P1">x</p></fragment>'):
            value = cover.document_coverage({"document": {"content": content}}, "full")
            self.assertEqual("unknown", value["status"])
            self.assertFalse(value["full_document_complete"])

    def test_bounded_response_missing_endpoint_cannot_claim_complete_scope(self):
        value = cover.document_coverage({"document": {"content": '<fragment mode="range"><p block-id="P1">x</p></fragment>'}}, "range", "P1", "P2")
        self.assertEqual("unknown", value["status"])
        self.assertEqual("requested_endpoint_missing", value["reason"])

    def test_malformed_truncation_flags_are_unknown(self):
        for flag in cover.TRUNCATION_KEYS:
            for value in ("true", 1, None):
                result = cover.sheet_coverage({"actual_range": "A1:C3", flag: value}, "A1:C3")
                self.assertEqual("unknown", result["status"])
                self.assertFalse(result["window_complete"])


class AdapterContractTest(unittest.TestCase):
    def test_every_invalid_selection_fails_dry_run_without_credentials(self):
        for options in ({"scope": "section"}, {"scope": "keyword"}, {"scope": "range"}, {"scope": "full", "start_block": "Block1"}, {"revision_id": 0}, {"max_depth": -2}, {"format": "cells"}):
            value = args(url=DOC, dry_run=True, **options)
            with mock.patch.object(read, "Backend") as backend, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(2, read.run(value), options)
            backend.assert_not_called()

    def test_bounded_doc_read_forwards_end_and_fixed_revision(self):
        backend = mock.Mock()
        backend.read.return_value = {"document": {"content": '<fragment><p block-id="Block1">x</p></fragment>', "revision_id": 42}}
        result = read.fetch(backend, args(url=DOC, scope="range", start_block="Block1", end_block="Block1", revision_id=42, expected_revision="42"))
        flags = backend.read.call_args[0][1]
        self.assertEqual("Block1", flags[flags.index("--end-block-id") + 1])
        self.assertEqual("42", flags[flags.index("--revision-id") + 1])
        self.assertEqual("matched", result["coverage"]["revision_check"])
        self.assertFalse(result["receipt"]["whole_resource_complete"])

    def test_catalog_uses_all_top_level_blocks_including_no_heading(self):
        backend = mock.Mock()
        backend.read.return_value = {"document": {"content": '<fragment><p block-id="P1">no heading</p></fragment>', "revision_id": 1}}
        result = read.fetch(backend, args(url=DOC, action="catalog"))
        self.assertEqual(["P1"], result["coverage"]["top_level_block_ids"])
        self.assertEqual("structure-only", result["coverage"]["status"])
        flags = backend.read.call_args[0][1]
        self.assertEqual("0", flags[flags.index("--start-block-id") + 1])
        self.assertEqual("-1", flags[flags.index("--end-block-id") + 1])

    def test_revision_changes_and_missing_revision_reject_merge(self):
        for data in ({"revision": 2}, {}, {"document": {"revision_id": 2}}):
            with self.assertRaises(read.ReadError) as raised:
                read.check_revision(data, args(expected_revision="1"))
            self.assertEqual("revision_mismatch", raised.exception.kind)

    def test_cells_mode_uses_official_read_only_command(self):
        backend = mock.Mock()
        backend.read.return_value = {"ranges": [{"actual_range": "A1:C3", "has_more": False}], "revision": 1}
        result = read.fetch(backend, args(url="https://example.feishu.cn/sheets/Table1?sheet=Sheet1", range="A1:C3", format="cells", include="formula,comment", expected_revision="1"))
        self.assertEqual("sheets/+cells-get", backend.read.call_args[0][0])
        self.assertIn("formula,comment", backend.read.call_args[0][1])
        self.assertEqual("cells", result["source"]["read_format"])

    def test_budget_failure_provides_block_inventory_without_body(self):
        backend = mock.Mock()
        backend.read.return_value = {"document": {"content": '<p block-id="P1">' + "private text" * 200 + '</p>', "revision_id": 1}}
        with self.assertRaises(read.ReadError) as raised:
            read.fetch(backend, args(url=DOC, scope="full", max_chars=1000))
        self.assertEqual(["P1"], raised.exception.details["top_level_block_ids"])
        self.assertNotIn("private text", json.dumps(raised.exception.details))

    def test_non_repo_cwd_and_python_environment_cannot_replace_entry(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            temp = pathlib.Path(directory)
            package = temp / "tools/codex_assets"
            package.mkdir(parents=True)
            (temp / "tools/__init__.py").write_text("")
            (package / "__init__.py").write_text("")
            (package / "__main__.py").write_text('print("SHADOW_WAS_EXECUTED")')
            env = dict(os.environ, PYTHONPATH=str(temp), PYTHONHOME=str(temp))
            command = ["rtk", "bash", str(root / "scripts/feishu-read.sh"), "read", "--url", DOC, "--dry-run"]
            result = subprocess.run(command, cwd=temp, env=env, capture_output=True, text=True, timeout=15)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertNotIn("SHADOW_WAS_EXECUTED", result.stdout)
            self.assertTrue(json.loads(result.stdout)["dry_run"])


if __name__ == "__main__":
    unittest.main()
