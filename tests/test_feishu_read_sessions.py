from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import pathlib
import tempfile
import unittest
from unittest import mock

from tools.codex_assets import feishu_read_sessions as sessions
from tools.codex_assets import feishu_cli_files as files
from tools.codex_assets import feishu_cli_read as cli
from tools.codex_assets.feishu_cli_errors import ReadError, backend_error, error_payload
from tools.codex_assets.feishu_read_evidence import enrich
from tools.codex_assets.feishu_cli_coverage import document_coverage
from tests.test_feishu_cli_read import args, backend

FILE = "https://example.feishu.cn/file/File1"
SHEET = "https://example.feishu.cn/sheets/Table1?sheet=Sheet1"
DOC = "https://example.feishu.cn/docx/Doc1"
PIN = "a" * 64


def file_result(options=None, raw=b"0123456789abcdefghij", mode="download"):
    options = options or args(url=FILE)
    value = mock.Mock()
    value.download.return_value = raw
    options.file_mode = mode
    return files.read_file(value, {"url": FILE, "type": "file", "token": "File1"}, "x.txt", options)


def sheet_result(cell_range, revision="3", complete=True):
    return {"ok": True, "source": {"url": SHEET, "type": "sheets", "token": "Table1",
            "sheet_id": "Sheet1", "read_format": "csv"},
            "data": {"revision": revision, "annotated_csv": "text-must-not-be-persisted"},
            "coverage": {"revision": revision, "status": "complete" if complete else "partial",
                         "window_complete": complete, "requested_range": cell_range,
                         "upstream_coverage": [{"actual_range": "Sheet1!" + cell_range, "status": "complete" if complete else "partial"}]}}


def doc_result(catalog=False, block="Preamble", revision="3", partial=False, unidentified=0):
    coverage = {"revision": revision, "status": "partial" if partial else "structure-only" if catalog else "complete-scope",
                "full_document_requested": catalog, "top_level_block_ids": ["Preamble", "Heading"] if catalog else [block],
                "top_level_unidentified_count": unidentified, "block_ids": [block],
                "excerpts": [], "truncation_signals": []}
    return {"ok": True, "source": {"url": DOC, "type": "docx", "token": "Doc1"},
            "data": {"document": {"revision_id": revision, "content": "private-content"}},
            "coverage": coverage}


class CoverageSessionTest(unittest.TestCase):
    def test_file_union_reports_gap_overlap_and_original_completion(self):
        state = sessions.new_state(FILE, PIN)
        first = args(url=FILE, file_length=7)
        state = sessions.record(state, file_result(first), first)
        info = sessions.summary(state)
        self.assertEqual([[7, 20]], info["missing"])
        self.assertFalse(info["scope_complete"])
        second = args(url=FILE, file_offset=5)
        state = sessions.record(state, file_result(second), second)
        info = sessions.summary(state)
        self.assertTrue(info["scope_complete"])
        self.assertTrue(info["whole_resource_complete"])
        self.assertTrue(info["overlap_observed"])
        self.assertIsNone(info["next"])

    def test_holes_do_not_disappear_when_reading_out_of_order(self):
        state = sessions.new_state(FILE, PIN)
        for offset, length in ((12, 8), (0, 3), (6, 3)):
            options = args(url=FILE, file_offset=offset, file_length=length)
            state = sessions.record(state, file_result(options), options)
        self.assertEqual([[3, 6], [9, 12]], sessions.summary(state)["missing"])

    def test_catalog_of_empty_file_is_not_content_completion(self):
        options = args(url=FILE, action="catalog")
        state = sessions.record(sessions.new_state(FILE, PIN), file_result(options, b""), options)
        self.assertFalse(sessions.summary(state)["scope_complete"])
        self.assertEqual({"action": "read"}, sessions.summary(state)["next"])
        options = args(url=FILE)
        state = sessions.record(state, file_result(options, b""), options)
        self.assertTrue(sessions.summary(state)["whole_resource_complete"])

    def test_converted_preview_only_completes_representation(self):
        options = args(url=FILE)
        state = sessions.record(sessions.new_state(FILE, PIN), file_result(options, mode="text-preview"), options)
        self.assertTrue(sessions.summary(state)["scope_complete"])
        self.assertFalse(sessions.summary(state)["whole_resource_complete"])

    def test_redacted_window_is_not_original_coverage(self):
        options = args(url=FILE)
        result = file_result(options)
        result["coverage"]["content_redacted"] = True
        state = sessions.record(sessions.new_state(FILE, PIN), result, options)
        info = sessions.summary(state)
        self.assertFalse(info["whole_resource_complete"])
        self.assertEqual("redacted-content-not-complete", info["blocking_reason"])

    def test_resume_pins_hash_mode_and_first_missing_offset(self):
        first = args(url=FILE, file_length=7)
        state = sessions.record(sessions.new_state(FILE, PIN), file_result(first, mode="source-preview"), first)
        resumed = args(url=FILE, resume=True)
        self.assertTrue(sessions.prepare(state, resumed))
        self.assertEqual(7, resumed.file_offset)
        self.assertEqual("source-preview", resumed.file_mode)
        self.assertEqual(state["binding"]["value"], resumed.expected_content_sha256)

    def test_snapshot_mismatch_invalidates_instead_of_mixing(self):
        options = args(url=FILE, file_length=3)
        state = sessions.record(sessions.new_state(FILE, PIN), file_result(options), options)
        original = copy.deepcopy(state)
        with self.assertRaises(ReadError):
            sessions.record(state, file_result(options, b"changed"), options)
        self.assertEqual(original, state)
        invalid = sessions.failed(state, ReadError("content_mismatch", "changed"))
        self.assertFalse(sessions.summary(invalid)["scope_complete"])
        self.assertIsNone(sessions.summary(invalid)["next"])

    def test_complete_resume_revalidates_snapshot_instead_of_assuming_freshness(self):
        options = args(url=FILE)
        state = sessions.record(sessions.new_state(FILE, PIN), file_result(options), options)
        resumed = args(url=FILE, resume=True)
        self.assertTrue(sessions.prepare(state, resumed))
        self.assertEqual("catalog", resumed.action)
        self.assertEqual(state["binding"]["value"], resumed.expected_content_sha256)

    def test_manual_range_and_resume_do_not_mix(self):
        with self.assertRaises(ReadError):
            sessions.prepare(sessions.new_state(FILE, PIN), args(url=FILE, resume=True, file_offset=1))

    def test_sheet_two_dimensional_gaps_and_large_geometry_without_grid_allocation(self):
        self.assertEqual([[3, 3, 3, 4]], sessions.sheet_gaps([1, 1, 3, 4],
                         [[1, 1, 2, 4], [3, 1, 3, 2]]))
        self.assertEqual([[1, 1, 18278, 1000000]], sessions.sheet_gaps([1, 1, 18278, 1000000], []))

    def test_sheet_union_is_range_completion_not_whole_workbook(self):
        options = args(url=SHEET, target_range="A1:C4", range="A1:C2")
        state = sessions.record(sessions.new_state(SHEET, PIN), sheet_result("A1:C2"), options)
        resumed = args(url=SHEET, resume=True)
        sessions.prepare(state, resumed)
        self.assertEqual("A3:C4", resumed.range)
        self.assertEqual("3", resumed.expected_revision)
        self.assertEqual("Sheet1", resumed.sheet_id)
        state = sessions.record(state, sheet_result("A3:C4"), resumed)
        self.assertTrue(sessions.summary(state)["scope_complete"])
        self.assertFalse(sessions.summary(state)["whole_resource_complete"])

    def test_partial_sheet_window_is_split_not_counted(self):
        options = args(url=SHEET, target_range="A1:C4", range="A1:C4")
        state = sessions.record(sessions.new_state(SHEET, PIN), sheet_result("A1:C4", complete=False), options)
        self.assertEqual([], state["segments"])
        self.assertEqual({"action": "read", "range": "A1:C2"}, sessions.summary(state)["next"])
        self.assertFalse(sessions.summary(state)["scope_complete"])

    def test_sheet_missing_revision_never_completes_or_resumes_as_same_snapshot(self):
        options = args(url=SHEET, target_range="A1:C4", range="A1:C4")
        state = sessions.record(sessions.new_state(SHEET, PIN), sheet_result("A1:C4", revision=None), options)
        self.assertFalse(sessions.summary(state)["scope_complete"])
        self.assertIsNone(sessions.summary(state)["next"])

    def test_sheet_plan_change_and_out_of_scope_window_rejected_before_network(self):
        options = args(url=SHEET, target_range="C3:D4", range="C3:D3")
        state = sessions.record(sessions.new_state(SHEET, PIN), sheet_result("C3:D3"), options)
        for attempt in (args(url=SHEET, target_range="A1:C4"), args(url=SHEET, range="A1:C3")):
            with self.assertRaises(ReadError):
                sessions.prepare(state, attempt)

    def test_doc_catalog_covers_preamble_and_heading_and_pins_revision(self):
        options = args(url=DOC, action="catalog")
        state = sessions.record(sessions.new_state(DOC, PIN), doc_result(catalog=True), options)
        for block in ("Preamble", "Heading"):
            resumed = args(url=DOC, resume=True)
            sessions.prepare(state, resumed)
            self.assertEqual(block, resumed.start_block)
            self.assertEqual(block, resumed.end_block)
            self.assertEqual(3, resumed.revision_id)
            state = sessions.record(state, doc_result(block=block), resumed)
        self.assertTrue(sessions.summary(state)["whole_resource_complete"])

    def test_partial_doc_and_unidentified_catalog_cannot_close_or_loop_forever(self):
        options = args(url=DOC, action="catalog")
        state = sessions.record(sessions.new_state(DOC, PIN), doc_result(catalog=True, unidentified=1), options)
        self.assertFalse(sessions.summary(state)["scope_complete"])
        self.assertIsNone(sessions.summary(state)["next"])
        state = sessions.record(sessions.new_state(DOC, PIN), doc_result(catalog=True), options)
        partial_args = args(url=DOC, scope="range", start_block="Preamble", end_block="Preamble")
        for _ in range(3):
            state = sessions.record(state, doc_result(partial=True), partial_args)
        self.assertEqual([], state["segments"])
        self.assertIsNone(sessions.summary(state)["next"])

    def test_document_catalog_detects_unidentified_top_level_text(self):
        data = {"document": {"content": '<document>preamble<p block-id="B1">body</p><p>no id</p></document>'}}
        result = document_coverage(data, "range", "0", "-1", 0)
        self.assertEqual(2, result["top_level_unidentified_count"])

    def test_full_document_with_unidentified_body_never_closes(self):
        data = {"document": {"content": '<document>preamble<p block-id="B1">body</p><p>no id</p></document>'}}
        self.assertFalse(document_coverage(data, "full")["full_document_complete"])
        result = doc_result(unidentified=2)
        result["coverage"]["full_document_complete"] = True
        state = sessions.record(sessions.new_state(DOC, PIN), result, args(url=DOC, scope="full"))
        self.assertFalse(sessions.summary(state)["whole_resource_complete"])

    def test_empty_doc_plan_is_invalid_even_with_revision(self):
        state = sessions.new_state(DOC, PIN)
        state.update(resource={"type": "docx", "token": "Doc1"},
                     binding={"kind": "revision", "value": "3"}, plan={"kind": "docx", "blocks": []})
        for operation in (sessions.validate_state, sessions.summary):
            with self.assertRaises(ReadError):
                operation(state)

    def test_repeated_windows_and_catalog_do_not_reset_stalled_counter(self):
        options = args(url=FILE, file_length=3)
        state = sessions.record(sessions.new_state(FILE, PIN), file_result(options), options)
        for _ in range(3):
            state = sessions.record(state, file_result(options), options)
        self.assertEqual(3, state["failures"])
        self.assertIsNone(sessions.summary(state)["next"])
        catalog = args(url=FILE, action="catalog")
        state = sessions.record(state, file_result(catalog), catalog)
        self.assertEqual(4, state["failures"])

    def test_state_rejects_unknown_body_fields_and_invalid_geometry(self):
        state = sessions.new_state(FILE, PIN)
        for invalid in (dict(state, content="private"), dict(state, sequence=True), dict(state, binding={"kind": "sha256", "value": "bad"})):
            with self.assertRaises(ReadError):
                sessions.validate_state(invalid)

    def test_backend_identity_source_and_version_are_not_replaceable(self):
        options = args(url=DOC, action="catalog")
        state = sessions.record(sessions.new_state(DOC, PIN), doc_result(catalog=True), options)
        with self.assertRaises(ReadError):
            sessions.record(state, doc_result(catalog=True, revision="4"), options)


class SessionStoreTest(unittest.TestCase):
    def make_store(self, root, name="job", url=FILE, pin=PIN, **kwargs):
        return sessions.SessionStore(name, url, pin, root=pathlib.Path(root), **kwargs)

    def test_atomic_metadata_save_status_and_same_resource_restore(self):
        with tempfile.TemporaryDirectory() as root:
            store = self.make_store(root)
            with store:
                options = args(url=FILE, file_length=4)
                state = sessions.record(store.state, file_result(options), options)
                store.save(state)
            raw = store.path.read_text()
            self.assertNotIn("0123456789abcdefghij", raw)
            self.assertNotIn('"content"', raw)
            self.assertEqual(0o600, store.path.stat().st_mode & 0o777)
            before = store.path.stat().st_mtime_ns
            self.assertEqual([[4, 20]], self.make_store(root).status()["missing"])
            self.assertEqual(before, store.path.stat().st_mtime_ns)
            with self.make_store(root, require_existing=True) as restored:
                self.assertEqual(state, restored.state)

    def test_private_root_and_session_lock(self):
        with tempfile.TemporaryDirectory() as root:
            with self.make_store(root):
                with self.assertRaises(ReadError) as error:
                    with self.make_store(root):
                        pass
                self.assertEqual("session_busy", error.exception.kind)
                with self.make_store(root, name="different"):
                    pass

    def test_wrong_backend_resource_missing_resume_and_insecure_file_fail(self):
        with tempfile.TemporaryDirectory() as root:
            store = self.make_store(root)
            with store:
                store.save(store.state)
            for other in (self.make_store(root, pin="b" * 64),
                          self.make_store(root, url="https://example.feishu.cn/file/Other1"),
                          self.make_store(root, name="missing", require_existing=True)):
                with self.assertRaises(ReadError):
                    with other:
                        pass
            store.path.chmod(0o644)
            with self.assertRaises(ReadError):
                store.status()

    def test_invalid_json_unknown_fields_oversize_and_symlink_are_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            store = self.make_store(root)
            with store:
                store.save(store.state)
            for raw in ("{", json.dumps(dict(store.state, content="must-not-be-read")), "x" * (sessions.MAX_STATE + 1)):
                store.path.write_text(raw)
                store.path.chmod(0o600)
                with self.assertRaises(ReadError):
                    store.status()
            store.path.unlink()
            store.path.symlink_to("/etc/hosts")
            with self.assertRaises((ReadError, OSError)):
                store.status()

    def test_fifo_and_hardlink_are_not_read_as_metadata(self):
        with tempfile.TemporaryDirectory() as root:
            store = self.make_store(root)
            os.mkfifo(str(store.path), 0o600)
            with self.assertRaises(ReadError):
                store.status()
            store.path.unlink()
            with store:
                store.save(store.state)
            os.link(str(store.path), str(pathlib.Path(root) / "other.json"))
            with self.assertRaises(ReadError):
                store.status()


class ReadIntegrationTest(unittest.TestCase):
    def run_cli(self, value):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = cli.run(value)
        return code, json.loads(output.getvalue())

    def test_dry_run_does_not_create_session_or_backend(self):
        with mock.patch.object(cli, "SessionStore") as store, mock.patch.object(cli, "Backend") as constructor:
            code, result = self.run_cli(args(url=FILE, session="new", resume=True, dry_run=True))
        self.assertEqual(0, code)
        store.assert_not_called()
        constructor.assert_not_called()

    def test_cli_first_read_status_resume_and_complete_noop(self):
        with tempfile.TemporaryDirectory() as root:
            factory = lambda name, url, pin, **kw: sessions.SessionStore(name, url, pin, root=pathlib.Path(root), **kw)
            def execute(options, _):
                return file_result(options)
            with mock.patch.object(cli, "SessionStore", side_effect=factory), mock.patch.object(cli, "execute_read", side_effect=execute) as transport:
                code, first = self.run_cli(args(url=FILE, session="job", file_length=7))
                self.assertEqual(0, code)
                self.assertFalse(first["session"]["scope_complete"])
                code, status = self.run_cli(args(url=FILE, action="status", session="job"))
                self.assertEqual(0, code)
                self.assertFalse(status["network_requested"])
                self.assertEqual(1, transport.call_count)
                code, resumed = self.run_cli(args(url=FILE, session="job", resume=True))
                self.assertEqual(0, code)
                self.assertTrue(resumed["session"]["scope_complete"])
                code, noop = self.run_cli(args(url=FILE, session="job", resume=True))
                self.assertEqual(0, code)
                self.assertTrue(noop["already_complete"])
                self.assertTrue(noop["snapshot_revalidated"])
                self.assertEqual(3, transport.call_count)

    def test_evidence_and_capabilities_distinguish_metadata_and_content(self):
        value = file_result()
        result = enrich(value)
        self.assertEqual("characters", result["evidence"]["locator"]["kind"])
        self.assertEqual("content-verified", result["capabilities"]["access_status"])
        self.assertEqual(value["data"]["sha256"], result["evidence"]["snapshot"]["sha256"])
        self.assertNotIn("content", result["evidence"])
        value = files.file_metadata({"url": FILE, "type": "file", "token": "File1"}, "x.txt", args(url=FILE, action="inspect"))
        result = enrich(value)
        self.assertTrue(result["capabilities"]["type_supported"])
        self.assertFalse(result["capabilities"]["content_returned"])
        self.assertEqual("metadata-or-structure-only", result["capabilities"]["access_status"])

    def test_permanent_errors_and_long_rate_limits_do_not_auto_retry(self):
        for error in (ReadError("application_scope_missing", "scope"),
                      ReadError("rate_limited", "wait"), ReadError("access_denied", "denied")):
            value = backend()
            value.retries = 2
            with mock.patch.object(value, "invoke", side_effect=error) as invoke, mock.patch.object(cli.time, "sleep") as sleep:
                with self.assertRaises(ReadError):
                    value.read("docs/+fetch", [])
                self.assertEqual(1, invoke.call_count)
                sleep.assert_not_called()

    def test_transient_read_retry_is_bounded_and_keeps_same_bot_command(self):
        value = backend()
        value.retries = 2
        payload = {"ok": True, "identity": "bot", "data": {}}
        with mock.patch.object(value, "invoke", side_effect=[ReadError("timeout", "timeout"), payload]) as invoke, mock.patch.object(cli.time, "sleep") as sleep:
            value.read("docs/+fetch", ["--doc", "Doc1"])
            self.assertEqual(2, invoke.call_count)
            self.assertEqual(invoke.call_args_list[0], invoke.call_args_list[1])
            self.assertEqual("bot", invoke.call_args.args[0][-1])
            sleep.assert_called_once_with(1)

    def test_error_projection_classifies_without_retaining_signed_urls(self):
        for code, kind in ((401, "authentication_failed"), (403, "access_denied"), (404, "not_found"),
                           (429, "rate_limited"), (503, "service_unavailable")):
            error = backend_error({"code": code, "message": "https://secret.example/?access_token=private-value"})
            payload = error_payload(error)
            self.assertEqual(kind, payload["kind"])
            self.assertNotIn("private-value", json.dumps(payload))
            self.assertIn("next_action", payload["recovery"])


if __name__ == "__main__":
    unittest.main()
