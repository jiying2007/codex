from __future__ import annotations

import argparse
import contextlib
import io
import json
import pathlib
import tempfile
import time
import types
import unittest
from unittest import mock

from tools.codex_assets import feishu_cli_read as read

WIKI = "https://example.feishu.cn/wiki/Node1?sheet=Sheet1"
DOC = "https://example.feishu.cn/docx/Doc1"


def args(url=WIKI, **changes):
    parser = argparse.ArgumentParser()
    read.configure_parser(parser)
    value = parser.parse_args(["read", "--url", url])
    for key, item in changes.items():
        setattr(value, key, item)
    return value


def backend():
    value = object.__new__(read.Backend)
    value.binary = pathlib.Path("/unused-cli")
    value.runtime = pathlib.Path("/tmp")
    value.env = {}
    value.secrets = ["secret-value"]
    value.deadline = time.monotonic() + 60
    return value


class ReadBoundaryTest(unittest.TestCase):
    def test_missing_or_modified_binary_fails_before_policy_or_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "manifests").mkdir()
            manifest = {"allowed_commands": list(read.ALLOWED), "writes_allowed": False,
                        "binary_rel": "cli", "binary_sha256": "0" * 64, "policy_rel": "policy.yml"}
            (root / "manifests/feishu_cli.json").write_text(json.dumps(manifest))
            for installed in (False, True):
                if installed:
                    (root / "cli").write_bytes(b"unexpected binary")
                with mock.patch.object(read.Backend, "verify_policy") as policy, self.assertRaises(read.ReadError) as raised:
                    read.Backend(root, root)
                self.assertEqual("backend_unavailable", raised.exception.kind)
                policy.assert_not_called()

    def test_dry_run_never_constructs_backend_or_loads_credentials(self):
        with mock.patch.object(read, "Backend") as constructor, contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(0, read.run(args(dry_run=True)))
        constructor.assert_not_called()
        self.assertFalse(json.loads(out.getvalue())["credentials_loaded"])

    def test_invalid_url_or_budget_fails_before_credentials(self):
        for value in (args(url="https://evil.example/docx/Doc1"), args(range="A1:Z100"), args(max_chars=999)):
            with mock.patch.object(read, "Backend") as constructor, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(2, read.run(value))
            constructor.assert_not_called()

    def test_write_command_is_denied_before_subprocess(self):
        value = backend()
        with mock.patch.object(value, "invoke") as invoke, self.assertRaises(read.ReadError):
            value.read("docs/+update", ["--content", "untrusted"])
        invoke.assert_not_called()

    def test_effective_policy_rejects_fallback_user_writes_and_malformed_rules(self):
        valid = {"source": "yaml", "rules": [{"allow": list(read.ALLOWED), "max_risk": "read", "identities": ["bot"], "allow_unannotated": False}]}
        value = backend()
        with mock.patch.object(value, "invoke", return_value=valid):
            value.verify_policy()
        for payload in ({"source": "default", "rules": valid["rules"]}, {"source": "yaml", "rules": None},
                        {"source": "yaml", "rules": [None]},
                        {"source": "yaml", "rules": [dict(valid["rules"][0], identities=["user"])]},
                        {"source": "yaml", "rules": [dict(valid["rules"][0], max_risk="write")]}):
            with mock.patch.object(value, "invoke", return_value=payload), self.assertRaises(read.ReadError):
                value.verify_policy()

    def test_native_error_is_redacted_and_exit_zero_still_requires_ok(self):
        value = backend()
        result = types.SimpleNamespace(returncode=3, stdout="", stderr=json.dumps({"error": {"app_secret": "abc", "message": "secret-value"}}))
        with mock.patch.object(read.subprocess, "run", return_value=result), self.assertRaises(read.ReadError) as raised:
            value.invoke(["docs", "+fetch"])
        self.assertNotIn("secret-value", json.dumps(raised.exception.details))
        self.assertEqual("REDACTED", raised.exception.details["app_secret"])
        for payload in ({"ok": False, "identity": "bot", "data": {}}, {"ok": True, "identity": "user", "data": {}}, {"ok": True, "identity": "bot", "data": []}):
            with mock.patch.object(value, "invoke", return_value=payload), self.assertRaises(read.ReadError):
                value.read("docs/+fetch", [])

    def test_invalid_json_and_timeout_have_stable_errors(self):
        value = backend()
        with mock.patch.object(read.subprocess, "run", return_value=types.SimpleNamespace(returncode=0, stdout="oops")), self.assertRaises(read.ReadError) as raised:
            value.invoke([])
        self.assertEqual("invalid_response", raised.exception.kind)
        with mock.patch.object(read.subprocess, "run", side_effect=read.subprocess.TimeoutExpired("cli", 30)), self.assertRaises(read.ReadError) as raised:
            value.invoke([])
        self.assertEqual("timeout", raised.exception.kind)

    def test_recursive_redaction(self):
        self.assertEqual({"nested": [{"Authorization": "REDACTED", "text": "REDACTED"}]}, read.redact({"nested": [{"Authorization": "bearer", "text": "secret-value"}]}, ["secret-value"]))


class ReadRoutingTest(unittest.TestCase):
    def test_wiki_sheet_preserves_coordinates_and_explicit_selection(self):
        value = mock.Mock()
        data = {"actual_range": "Sheet1!A1:C3", "row_indices": [1, 3], "col_indices": [1, 3], "has_more": False, "annotated_csv": "a\nembedded\nnewlines"}
        value.read.side_effect = [{"obj_type": "sheet", "obj_token": "Table1"}, data]
        result = read.fetch(value, args(range="A1:C3"))
        self.assertEqual(data, result["data"])
        self.assertEqual([1, 3], result["coverage"]["upstream_coverage"][0]["row_indices"])
        self.assertEqual("Sheet1", result["source"]["sheet_id"])
        self.assertEqual(mock.call("sheets/+csv-get", ["--spreadsheet-token", "Table1", "--sheet-id", "Sheet1", "--range", "A1:C3", "--max-chars", "8000"]), value.read.call_args)

    def test_sheet_without_selection_never_guesses_first_tab(self):
        value = mock.Mock()
        with self.assertRaises(read.ReadError) as raised:
            read.fetch(value, args(url="https://example.feishu.cn/sheets/Table1"))
        self.assertEqual("selection_required", raised.exception.kind)
        value.read.assert_not_called()

    def test_continuation_overlaps_partial_final_row_and_requires_progress(self):
        result = read.continuation({"actual_range": "Sheet1!A1:C7", "has_more": True}, "A1:C20")
        row = result["upstream_coverage"][0]
        self.assertEqual("A7:C20", row["next_range"])
        self.assertTrue(row["overlap_last_row"])
        for actual in ("A1:C1", "A1:C20", "A1:C21", "unknown"):
            row = read.continuation({"actual_range": actual, "has_more": True}, "A1:C20")["upstream_coverage"][0]
            self.assertNotIn("next_range", row)
            self.assertTrue(row["continuation_requires_smaller_window"])

    def test_doc_content_is_rejected_without_character_truncation(self):
        value = mock.Mock()
        value.read.return_value = {"document": {"content": "<p>" + "文" * 1100 + "</p>", "revision_id": 1}}
        with self.assertRaises(read.ReadError) as raised:
            read.fetch(value, args(url=DOC, max_chars=1000))
        self.assertEqual("content_budget_exceeded", raised.exception.kind)

    def test_doc_keyword_and_section_require_explicit_selection(self):
        for options in ({"scope": "keyword"}, {"scope": "section", "start_block": "--unsafe"}):
            value = mock.Mock()
            with self.assertRaises(read.ReadError):
                read.fetch(value, args(url=DOC, **options))
            value.read.assert_not_called()

    def test_unsupported_wiki_object_is_not_downloaded(self):
        value = mock.Mock()
        value.read.return_value = {"obj_type": "bitable", "obj_token": "Table1"}
        with self.assertRaises(read.ReadError) as raised:
            read.fetch(value, args())
        self.assertEqual("unsupported_type", raised.exception.kind)
        self.assertEqual(1, value.read.call_count)


if __name__ == "__main__":
    unittest.main()
