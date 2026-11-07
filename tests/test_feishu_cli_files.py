from __future__ import annotations

import hashlib
import json
import os
import pathlib
import signal
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

from tools.codex_assets import feishu_cli_files as files
from tools.codex_assets import feishu_cli_read as read
from tools.codex_assets.feishu_documents import parse_document_url, DocumentReadError
from tests.test_feishu_cli_read import args, backend

WIKI = "https://example.feishu.cn/wiki/Node1"
DIRECT = "https://example.feishu.cn/file/File1"
SOURCE = {"url": DIRECT, "type": "file", "token": "File1"}


class FileReadTest(unittest.TestCase):
    def make_backend(self, raw=b"# Title\nbody\n"):
        value = mock.Mock()
        value.download.return_value = raw
        value.secrets = []
        value.read.return_value = {"obj_type": "file", "obj_token": "File1", "title": "需求.md"}
        return value

    def test_direct_file_routes_are_opt_in_without_expanding_legacy_bot_reader(self):
        for path in ("file/File1", "drive/file/File1"):
            url = "https://example.feishu.cn/" + path
            self.assertEqual("file", parse_document_url(url, allow_files=True).kind)
            with self.assertRaises(DocumentReadError):
                parse_document_url(url)
        for path in ("file/../secret", "file/%2Fsecret", "file/File1/extra"):
            with self.assertRaises(DocumentReadError):
                parse_document_url("https://example.feishu.cn/" + path, allow_files=True)

    def test_invalid_file_options_fail_before_credentials(self):
        for changes in ({"file_offset": -1}, {"file_length": files.MAX_FILE_BYTES + 1},
                        {"expected_content_sha256": "bad"}, {"url": "https://example.feishu.cn/docx/Doc1", "file_offset": 1}):
            value = args(url=DIRECT)
            for key, item in changes.items():
                setattr(value, key, item)
            with mock.patch.object(read, "Backend") as constructor, mock.patch("builtins.print"):
                self.assertEqual(2, read.run(value))
            constructor.assert_not_called()

    def test_inspect_is_metadata_only_and_never_downloads(self):
        value = self.make_backend()
        result = read.fetch(value, args(url=WIKI, action="inspect"))
        self.assertEqual("需求.md", result["data"]["title"])
        self.assertTrue(result["data"]["content_read_supported"])
        self.assertFalse(result["coverage"]["whole_resource_complete"])
        value.download.assert_not_called()

    def test_catalog_returns_hash_without_content_or_whole_resource_claim(self):
        value = self.make_backend()
        result = read.fetch(value, args(url=WIKI, action="catalog"))
        self.assertEqual(hashlib.sha256(value.download.return_value).hexdigest(), result["data"]["sha256"])
        self.assertNotIn("content", result["data"])
        self.assertFalse(result["receipt"]["whole_resource_complete"])

    def test_small_text_file_has_complete_receipt_and_no_native_revision_claim(self):
        value = self.make_backend()
        result = read.fetch(value, args(url=DIRECT))
        self.assertEqual("# Title\nbody\n", result["data"]["content"])
        self.assertTrue(result["coverage"]["whole_resource_complete"])
        self.assertTrue(result["receipt"]["whole_resource_complete"])
        self.assertIsNone(result["receipt"]["revision"])
        self.assertTrue(result["receipt"]["resume_requires_content_sha256"])

    def test_long_line_unicode_and_escaping_resume_without_gaps_under_same_hash(self):
        raw = ('行一\n' + '中"\\' * 3000 + '\n最后一行').encode()
        value = self.make_backend(raw)
        sha = hashlib.sha256(raw).hexdigest()
        chunks, offset = [], 0
        while True:
            result = files.read_file(value, SOURCE, "需求.md", args(
                url=DIRECT, max_chars=1000, file_offset=offset, expected_content_sha256=sha))
            self.assertLessEqual(len(json.dumps(result["data"], ensure_ascii=False)), 1000)
            self.assertEqual(offset, result["coverage"]["actual_start_char"])
            chunks.append(result["data"]["content"])
            end = result["coverage"]["actual_end_char"]
            self.assertGreater(end, offset)
            if "next_offset" not in result["coverage"]:
                break
            self.assertFalse(result["receipt"]["whole_resource_complete"])
            offset = result["coverage"]["next_offset"]
        self.assertEqual(raw.decode(), "".join(chunks))

    def test_explicit_file_window_does_not_claim_whole_file(self):
        result = files.read_file(self.make_backend(b"abcdef"), SOURCE, "x.txt",
                                 args(url=DIRECT, file_offset=2, file_length=2))
        self.assertEqual("cd", result["data"]["content"])
        self.assertTrue(result["coverage"]["window_complete"])
        self.assertFalse(result["receipt"]["whole_resource_complete"])
        self.assertEqual(4, result["coverage"]["next_offset"])

    def test_changed_content_is_rejected_before_output(self):
        with self.assertRaises(read.ReadError) as raised:
            files.read_file(self.make_backend(), SOURCE, "x.md", args(
                url=DIRECT, expected_content_sha256="0" * 64))
        self.assertEqual("content_mismatch", raised.exception.kind)

    def test_bom_empty_file_and_control_characters(self):
        self.assertEqual("a\nb\nc", files.decode_text(b"a\r\nb\rc"))
        self.assertEqual("中文", files.decode_text("中文".encode("utf-16")))
        self.assertEqual("中文", files.decode_text(b"\xef\xbb\xbf" + "中文".encode()))
        result = files.read_file(self.make_backend(b""), SOURCE, "empty.txt", args(url=DIRECT))
        self.assertTrue(result["receipt"]["whole_resource_complete"])
        for raw in (b"\xffbad", b"a\x00b", b"PK\x03\x04zip", b"%PDF-1.4 ASCII-only PDF"):
            with self.assertRaises(read.ReadError):
                files.decode_text(raw)

    def test_auto_source_preview_only_for_typed_denial_and_same_token(self):
        value = self.make_backend()
        value.download.side_effect = [read.ReadError("backend_error", "denied", {"type": "permission_denied"}), b"ok"]
        result = files.read_file(value, SOURCE, "x.md", args(url=DIRECT))
        self.assertEqual("source-preview", result["data"]["representation"])
        self.assertEqual([mock.call("File1", "download"), mock.call("File1", "source-preview")],
                         value.download.call_args_list)
        for error in (read.ReadError("backend_error", "scope", {"type": "scope_missing"}),
                      read.ReadError("timeout", "timeout"), read.ReadError("policy_invalid", "bad")):
            value = self.make_backend()
            value.download.side_effect = error
            with self.assertRaises(read.ReadError):
                files.read_file(value, SOURCE, "x.md", args(url=DIRECT))
            self.assertEqual(1, value.download.call_count)

    def test_binary_uses_only_available_text_preview_without_claiming_original_complete(self):
        value = self.make_backend()
        value.download.side_effect = [b"%PDF\x00binary", b"converted text"]
        value.read.return_value = {"candidates": [{"type": "text", "downloadable": True}]}
        result = files.read_file(value, SOURCE, "x.pdf", args(url=DIRECT))
        self.assertEqual("converted text", result["data"]["content"])
        self.assertEqual("text-preview", result["receipt"]["representation"])
        self.assertFalse(result["receipt"]["whole_resource_complete"])
        self.assertTrue(result["coverage"]["original_file_unread"])
        value.read.assert_called_once_with("drive/+preview", ["--file-token", "File1", "--list-only"])

    def test_missing_preview_is_not_guessed_and_explicit_modes_do_not_fallback(self):
        value = self.make_backend(b"%PDF\x00binary")
        value.read.return_value = {"candidates": []}
        with self.assertRaises(read.ReadError):
            files.read_file(value, SOURCE, "x.pdf", args(url=DIRECT))
        self.assertEqual(1, value.download.call_count)
        value = self.make_backend()
        value.download.side_effect = read.ReadError("backend_error", "denied", {"code": 403})
        with self.assertRaises(read.ReadError):
            files.read_file(value, SOURCE, "x.md", args(url=DIRECT, file_mode="download"))
        self.assertEqual(1, value.download.call_count)

    def test_html_error_page_and_out_of_bounds_offsets_are_rejected(self):
        for raw, changes in ((b"<!doctype html><html>login</html>", {}),
                             (b"abc", {"file_offset": 4}), (b"abc", {"file_offset": 3})):
            with self.assertRaises(read.ReadError):
                files.read_file(self.make_backend(raw), SOURCE, "x.md", args(url=DIRECT, **changes))

    def test_line_counts_use_lf_consistently_for_form_feed_and_unicode_separator(self):
        raw = "a\fb\u2028c".encode()
        result = files.read_file(self.make_backend(raw), SOURCE, "x.txt", args(url=DIRECT))
        self.assertEqual(1, result["data"]["total_lines"])
        self.assertEqual(1, result["data"]["end_line"])
        self.assertTrue(result["receipt"]["whole_resource_complete"])

    def test_html_requires_wiki_filename_and_direct_limit_is_actionable(self):
        raw = b"<!doctype html><html>source</html>"
        value = self.make_backend(raw)
        result = files.read_file(value, SOURCE, "page.html", args(url=DIRECT))
        self.assertTrue(result["receipt"]["whole_resource_complete"])
        with self.assertRaises(read.ReadError) as raised:
            files.read_file(value, SOURCE, "", args(url=DIRECT))
        self.assertEqual("unsupported_file_format", raised.exception.kind)
        self.assertIn("Wiki", str(raised.exception))

    def test_download_path_is_private_separate_from_config_and_removed(self):
        value = backend()
        seen = []
        def download(command, flags):
            self.assertEqual("drive/+download", command)
            target = pathlib.Path(flags[flags.index("--output") + 1])
            self.assertTrue(target.is_absolute())
            self.assertEqual(0o700, target.parent.stat().st_mode & 0o777)
            self.assertNotEqual(value.runtime, target.parent)
            target.write_bytes(b"content")
            seen.append(target)
            return {}
        value.read = mock.Mock(side_effect=download)
        self.assertEqual(b"content", value.download("File1", "download"))
        self.assertFalse(seen[0].exists())

    def test_download_rejects_symlink_and_partial_oversized_file_and_cleans_up(self):
        for scenario in ("symlink", "oversize", "missing"):
            value = backend()
            targets = []
            def download(command, flags):
                target = pathlib.Path(flags[flags.index("--output") + 1])
                targets.append(target)
                if scenario == "symlink":
                    target.symlink_to("/etc/hosts")
                elif scenario == "oversize":
                    with target.open("wb") as stream:
                        stream.truncate(files.MAX_FILE_BYTES + 1)
                return {}
            value.read = mock.Mock(side_effect=download)
            with self.assertRaises(read.ReadError):
                value.download("File1", "download")
            self.assertFalse(targets[0].parent.exists())

    def test_cli_download_has_os_file_size_limit_and_signal_is_stable_error(self):
        value = backend()
        result = types.SimpleNamespace(returncode=-signal.SIGXFSZ, stdout="", stderr="")
        with mock.patch.object(read.subprocess, "run", return_value=result) as run:
            with self.assertRaises(read.ReadError) as raised:
                value.invoke(["drive", "+download", "--output", "/tmp/test.bin"])
        self.assertEqual("file_too_large", raised.exception.kind)
        self.assertIs(read.limit_download_size, run.call_args.kwargs["preexec_fn"])
        with mock.patch.object(read.resource, "setrlimit") as limit:
            read.limit_download_size()
        limit.assert_called_once_with(read.resource.RLIMIT_FSIZE, (files.MAX_FILE_BYTES, files.MAX_FILE_BYTES))

    def test_os_limit_really_prevents_oversized_download_file(self):
        with tempfile.TemporaryDirectory() as directory:
            target = pathlib.Path(directory) / "large.bin"
            child = subprocess.run([sys.executable, "-c",
                "import sys; f=open(sys.argv[1], 'wb'); f.write(b'x' * (int(sys.argv[2]) + 1)); f.close()",
                str(target), str(files.MAX_FILE_BYTES)], capture_output=True,
                preexec_fn=read.limit_download_size, timeout=10)
            self.assertNotEqual(0, child.returncode)
            self.assertLessEqual(target.stat().st_size, files.MAX_FILE_BYTES)

    def test_app_scope_error_can_use_existing_authorized_source_preview(self):
        value = self.make_backend()
        value.download.side_effect = [read.ReadError("application_scope_missing", "scope", {}), b"ok"]
        result = files.read_file(value, SOURCE, "x.md", args(url=DIRECT))
        self.assertEqual(["application_scope_missing"], result["data"]["fallbacks"])
        self.assertEqual("source-preview", result["data"]["representation"])

    def test_cli_warning_then_json_error_preserves_typed_scope_without_auth_urls(self):
        value = backend()
        inner = {"code": 99991672, "msg": "private-url-secret-value", "error": {"permission_violations": [
            {"type": "action_scope_required", "subject": "drive:file:download"}]}}
        error = {"ok": False, "error": {"message": "HTTP 400: " + json.dumps(inner)}}
        result = types.SimpleNamespace(returncode=4, stdout="", stderr="warning: preflight failed\n" + json.dumps(error))
        with mock.patch.object(read.subprocess, "run", return_value=result), self.assertRaises(read.ReadError) as raised:
            value.invoke(["drive", "+download"])
        self.assertEqual("application_scope_missing", raised.exception.kind)
        self.assertEqual(["drive:file:download"], raised.exception.details["required_scopes_any_of"])
        self.assertNotIn("private-url", json.dumps(raised.exception.details))
        for raw in ('prefix\n{"ok":true}', '{"ok":true}\ntrailing'):
            with self.assertRaises(ValueError):
                read.cli_json(raw)

    def test_redacted_text_does_not_claim_original_full_content(self):
        value = self.make_backend(b"do not expose runtime-secret")
        value.secrets = ["runtime-secret"]
        result = read.fetch(value, args(url=DIRECT))
        self.assertNotIn("runtime-secret", result["data"]["content"])
        self.assertTrue(result["data"]["content_redacted"])
        self.assertFalse(result["receipt"]["whole_resource_complete"])


if __name__ == "__main__":
    unittest.main()
