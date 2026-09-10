import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).parents[1] / "tools" / "codex_assets" / "public_knowledge_archive.py"
SPEC = importlib.util.spec_from_file_location("public_knowledge_archive", MODULE_PATH)
archive = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = archive
SPEC.loader.exec_module(archive)

RENDERED_MODULE_PATH = Path(__file__).parents[1] / "tools" / "codex_assets" / "rendered_public_knowledge_archive.py"
RENDERED_SPEC = importlib.util.spec_from_file_location("rendered_public_knowledge_archive", RENDERED_MODULE_PATH)
rendered = importlib.util.module_from_spec(RENDERED_SPEC)
assert RENDERED_SPEC and RENDERED_SPEC.loader
sys.modules[RENDERED_SPEC.name] = rendered
RENDERED_SPEC.loader.exec_module(rendered)


class PublicKnowledgeArchiveTest(unittest.TestCase):
    def test_canonicalize_and_allowlist(self):
        self.assertEqual(archive.canonicalize("HTTPS://WWW.YUQUE.COM/a#x"), "https://www.yuque.com/a")
        self.assertTrue(archive.host_allowed("https://sub.yuque.com/a", ("yuque.com",)))
        self.assertFalse(archive.host_allowed("https://yuque.example.com/a", ("yuque.com",)))

    def test_archives_public_html_and_skips_unchanged_body(self):
        html = ("<html><title>Public Doc</title><body><p>" + ("Useful public content. " * 40) + "</p><a href='/next'>Next</a></body></html>").encode("utf-8")
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "archive"
            args = [
                "archive", "--source", "https://www.yuque.com/aiui/zzoolv", "--allow-domain", "yuque.com",
                "--output-dir", str(output), "--max-pages", "1", "--max-depth", "0",
            ]
            with mock.patch.object(archive, "robots_allowed", return_value=True), \
                 mock.patch.object(archive, "request_bytes", return_value=(200, "https://www.yuque.com/aiui/zzoolv", html, "text/html")), \
                 mock.patch.object(sys, "argv", args):
                self.assertEqual(archive.main(), 0)
            pages = list((output / "pages").glob("*.md"))
            self.assertEqual(len(pages), 1)
            self.assertIn("Useful public content.", pages[0].read_text(encoding="utf-8"))
            first_index_count = len((output / "index.jsonl").read_text(encoding="utf-8").splitlines())
            with mock.patch.object(archive, "robots_allowed", return_value=True), \
                 mock.patch.object(archive, "request_bytes", return_value=(200, "https://www.yuque.com/aiui/zzoolv", html, "text/html")), \
                 mock.patch.object(sys, "argv", args):
                self.assertEqual(archive.main(), 0)
            self.assertEqual(len(list((output / "pages").glob("*.md"))), 1)
            records = [json.loads(line) for line in (output / "index.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(records), first_index_count + 1)
            self.assertEqual(records[-1]["status"], "unchanged")

    def test_access_gate_does_not_store_body(self):
        gate = b"<html><title>\xe7\x99\xbb\xe5\xbd\x95</title><body>\xe8\xaf\xb7\xe7\x99\xbb\xe5\xbd\x95\xe5\x90\x8e\xe7\xbb\xa7\xe7\xbb\xad</body></html>"
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "archive"
            args = [
                "archive", "--source", "https://www.yuque.com/aiui/zzoolv", "--allow-domain", "yuque.com",
                "--output-dir", str(output), "--max-pages", "1", "--max-depth", "0",
            ]
            with mock.patch.object(archive, "robots_allowed", return_value=True), \
                 mock.patch.object(archive, "request_bytes", return_value=(200, "https://www.yuque.com/login", gate, "text/html")), \
                 mock.patch.object(sys, "argv", args):
                self.assertEqual(archive.main(), 0)
            records = [json.loads(line) for line in (output / "index.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(records[-1]["status"], "access-gated")
            self.assertFalse((output / "pages").exists())

    def test_dynamic_shell_does_not_store_body(self):
        shell = b"<html><title>Public Shell</title><body>Public Shell</body></html>"
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "archive"
            args = [
                "archive", "--source", "https://www.yuque.com/aiui/zzoolv", "--allow-domain", "yuque.com",
                "--output-dir", str(output), "--max-pages", "1", "--max-depth", "0",
            ]
            with mock.patch.object(archive, "robots_allowed", return_value=True), \
                 mock.patch.object(archive, "request_bytes", return_value=(200, "https://www.yuque.com/aiui/zzoolv", shell, "text/html")), \
                 mock.patch.object(sys, "argv", args):
                self.assertEqual(archive.main(), 0)
            records = [json.loads(line) for line in (output / "index.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(records[-1]["status"], "dynamic-shell")
            self.assertFalse((output / "pages").exists())

    def test_rendered_toc_urls_collects_nested_document_routes(self):
        toc = [
            {"type": "DOC", "url": "first-doc"},
            {"type": "TITLE", "children": [{"type": "DOC", "url": "nested-doc"}]},
            {"type": "DOC", "url": ""},
        ]
        self.assertEqual(rendered.toc_urls(toc), ["first-doc", "nested-doc"])

    def test_rendered_toc_route_stays_under_book_root(self):
        self.assertEqual(
            rendered.resolve_child("https://www.yuque.com/caixueyang/kb", "first-doc", from_toc=True),
            "https://www.yuque.com/caixueyang/kb/first-doc",
        )
        self.assertEqual(
            rendered.resolve_child("https://www.yuque.com/caixueyang/kb", "/caixueyang/kb/first-doc", from_toc=False),
            "https://www.yuque.com/caixueyang/kb/first-doc",
        )


if __name__ == "__main__":
    unittest.main()
