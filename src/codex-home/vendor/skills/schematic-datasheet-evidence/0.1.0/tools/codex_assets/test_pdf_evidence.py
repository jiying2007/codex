import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import pdf_evidence as tool
from pdf_evidence import extract_locations


VALID_XML = b'<doc><page width="100" height="100"><word xMin="1" yMin="2" xMax="3" yMax="4">PB6</word></page></doc>'


class LocationTests(unittest.TestCase):
    def test_reading_order_does_not_create_pin_pairs(self):
        xml = b'<doc><page width="100" height="100"><word xMin="20" yMin="1" xMax="22" yMax="9">NET_B</word><word xMin="10" yMin="1" xMax="12" yMax="9">NET_A</word></page></doc>'
        result = extract_locations(xml, ["NET_A", "NET_B"])
        self.assertEqual(result["results"][0]["matches"][0]["bbox"], [10, 1, 12, 9])
        self.assertFalse(result["connectivity_verified"])
        self.assertNotIn("connections", result)

    def test_missing_word_is_not_filled_in(self):
        xml = b'<doc><page width="1" height="1"/></doc>'
        item = extract_locations(xml, ["PB6"])["results"][0]
        self.assertEqual(item["status"], "not-found")
        self.assertEqual(item["matches"], [])

    def test_duplicates_are_kept_and_truncation_is_explicit(self):
        word = '<word xMin="1" yMin="2" xMax="3" yMax="4">PB6</word>'
        xml = ('<doc><page width="10" height="10">' + word * 3 + '</page></doc>').encode()
        item = extract_locations(xml, ["PB6"], limit=2)["results"][0]
        self.assertEqual(item["count"], 3)
        self.assertTrue(item["truncated"])
        self.assertEqual(len(item["matches"]), 2)

    def test_multiple_pages_rejected(self):
        with self.assertRaises(ValueError):
            extract_locations(b'<doc><page/><page/></doc>', ["PB6"])

    def test_namespace_and_case_sensitivity(self):
        xml = b'<doc xmlns="urn:test"><page width="1" height="1"><word xMin="0" yMin="0" xMax="1" yMax="1">PB6</word></page></doc>'
        result = extract_locations(xml, ["PB6", "pb6", "PB"])
        self.assertEqual([r["count"] for r in result["results"]], [1, 0, 0])

    def test_missing_nonfinite_reversed_and_invalid_dimensions_rejected(self):
        for xml in [VALID_XML.replace(b' xMin="1"', b''),
                    VALID_XML.replace(b'xMin="1"', b'xMin="nan"'),
                    VALID_XML.replace(b'xMax="3"', b'xMax="inf"'),
                    VALID_XML.replace(b'xMin="1"', b'xMin="5"'),
                    VALID_XML.replace(b'yMin="2"', b'yMin="7"'),
                    VALID_XML.replace(b'width="100"', b'width="0"'),
                    VALID_XML.replace(b' height="100"', b'')]:
            with self.subTest(xml=xml), self.assertRaises(tool.EvidenceError):
                extract_locations(xml, ["PB6"])

    def test_limits_and_entity_declarations_rejected(self):
        for queries, limit in [([], 40), ([""], 40), (["x"] * 33, 40),
                               (["x" * 257], 40), (["x"], 201)]:
            with self.subTest(queries=queries, limit=limit), self.assertRaises(tool.EvidenceError):
                extract_locations(VALID_XML, queries, limit)
        with self.assertRaises(tool.EvidenceError):
            extract_locations(b'<!DOCTYPE doc [<!ENTITY x "secret">]>' + VALID_XML, ["PB6"])
        with patch.object(tool, "MAX_XML_BYTES", 10), self.assertRaises(tool.EvidenceError):
            extract_locations(VALID_XML, ["PB6"])


class CliTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="pdf-evidence-tests-")
        self.addCleanup(self.directory.cleanup)
        self.pdf = Path(self.directory.name) / "input.pdf"
        self.pdf.write_bytes(b"%PDF-1.4\nfixture for mocked backend\n")

    def invoke(self, xml=VALID_XML, diagnostics=b"", code=0, extra=None,
               version="24.02.0", backend_error=None):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(tool, "backend_identity", return_value={"name": "pdftotext", "version": version}), \
                patch.object(tool, "run_backend", return_value=tool.BackendResult(code, xml, diagnostics), side_effect=backend_error), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = tool.main(["--pdf", str(self.pdf), "--page", "1", "--text", "PB6"] + (extra or []))
        self.assertEqual(stderr.getvalue(), "")
        payload = json.loads(stdout.getvalue())
        self.assertFalse(payload["connectivity_verified"])
        self.assertNotIn("connections", payload)
        return result, payload

    def test_clean_extraction_records_backend_identity(self):
        code, payload = self.invoke()
        self.assertEqual(code, 0)
        self.assertEqual(payload["backend"]["version"], "24.02.0")
        self.assertEqual(payload["extraction_status"], "no-diagnostics")
        self.assertEqual(payload["backend_warnings"], [])
        self.assertEqual(len(payload["source_sha256"]), 64)

    def test_success_with_warning_requires_review_and_redacts_raw_text(self):
        for raw, category in [
            (b"Syntax Warning: font mapping at /private/file.pdf token=secret", "font-or-text-mapping"),
            (b"Syntax Error: malformed path", "pdf-syntax"),
            (b"other message with private PDF content", "unclassified-backend-diagnostic"),
        ]:
            with self.subTest(category=category):
                code, payload = self.invoke(diagnostics=raw)
                self.assertEqual(code, 2)
                self.assertEqual(payload["status"], "needs-review")
                self.assertEqual(payload["backend_warnings"][0]["category"], category)
                self.assertFalse(payload["raw_diagnostics_included"])
                rendered = json.dumps(payload)
                self.assertNotIn("secret", rendered)
                self.assertNotIn("/private/", rendered)

    def test_unknown_version_requires_review(self):
        code, payload = self.invoke(version="unknown")
        self.assertEqual(code, 2)
        self.assertEqual(payload["backend_warnings"][0]["category"], "backend-version-unknown")

    def test_missing_field_and_bad_xml_are_structured_errors(self):
        for xml, expected in [(VALID_XML.replace(b' xMin="1"', b''), "invalid-bbox"),
                              (b"<not-closed>", "invalid-xml")]:
            with self.subTest(expected=expected):
                code, payload = self.invoke(xml=xml)
                self.assertEqual(code, 1)
                self.assertEqual(payload["error_code"], expected)
                self.assertEqual(payload["status"], "error")

    def test_backend_failure_preserves_redacted_diagnostics(self):
        code, payload = self.invoke(code=1, diagnostics=b"Syntax Error: invalid PDF")
        self.assertEqual(code, 1)
        self.assertEqual(payload["error_code"], "backend-failed")
        self.assertTrue(payload["backend_warnings"])

    def test_missing_and_truncated_matches_are_not_complete(self):
        for xml, extra in [(VALID_XML.replace(b"PB6", b"OTHER"), []),
                           (VALID_XML.replace(b'</page>', VALID_XML.split(b'<page width="100" height="100">')[1].split(b'</page>')[0] + b'</page>'),
                            ["--max-matches", "1"])]:
            with self.subTest(extra=extra):
                code, payload = self.invoke(xml=xml, extra=extra)
                self.assertEqual(code, 2)
                self.assertEqual(payload["status"], "needs-review")

    def test_argument_errors_are_json_without_echoing_input(self):
        for extra in [["--page", "0"], ["--page", "private-invalid-value"], ["--max-matches", "201"]]:
            with self.subTest(extra=extra):
                code, payload = self.invoke(extra=extra)
                self.assertEqual(code, 1)
                self.assertEqual(payload["error_code"], "invalid-arguments")
                self.assertNotIn("private-invalid-value", json.dumps(payload))

    def test_missing_backend_and_timeout_are_structured(self):
        for error in [FileNotFoundError("/private/backend"),
                      tool.EvidenceError("backend-timeout", "PDF backend exceeded its time limit")]:
            with self.subTest(error=error):
                code, payload = self.invoke(backend_error=error)
                self.assertEqual(code, 1)
                self.assertNotIn("/private/", json.dumps(payload))

    def test_changed_pdf_is_not_attested(self):
        with patch.object(tool, "file_digest", side_effect=["a" * 64, "b" * 64]):
            code, payload = self.invoke()
        self.assertEqual(code, 1)
        self.assertEqual(payload["error_code"], "source-changed")

    def test_invalid_header_is_rejected_before_backend(self):
        self.pdf.write_bytes(b"not a PDF")
        code, payload = self.invoke()
        self.assertEqual(code, 1)
        self.assertEqual(payload["error_code"], "invalid-pdf")

    def test_input_limit_is_enforced_during_hashing(self):
        with patch.object(tool, "MAX_PDF_BYTES", 10), self.assertRaises(tool.EvidenceError):
            tool.file_digest(self.pdf)

    def test_version_probe_parses_only_expected_banner(self):
        for banner, expected in [(b"pdftotext version 24.02.0\nCopyright", "24.02.0"),
                                 (b"unexpected banner", "unknown")]:
            with self.subTest(expected=expected), patch.object(tool, "run_backend", return_value=tool.BackendResult(0, b"", banner)):
                self.assertEqual(tool.backend_identity()["version"], expected)


class BackendProcessTests(unittest.TestCase):
    def test_both_streams_are_drained(self):
        command = [sys.executable, "-c", "import os; os.write(1,b'a'*200000); os.write(2,b'b'*1000)"]
        result = tool.run_backend(command, stdout_limit=200000, stderr_limit=1000, timeout=5)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(result.stdout), 200000)
        self.assertEqual(len(result.stderr), 1000)

    def test_stdout_and_stderr_overflow_terminate(self):
        for descriptor in [1, 2]:
            with self.subTest(descriptor=descriptor), self.assertRaises(tool.EvidenceError) as raised:
                tool.run_backend([sys.executable, "-c", "import os; os.write(%d,b'x'*20000)" % descriptor],
                                 stdout_limit=100, stderr_limit=100, timeout=5)
            self.assertEqual(raised.exception.code, "backend-output-limit")

    def test_timeout_terminates_backend(self):
        with self.assertRaises(tool.EvidenceError) as raised:
            tool.run_backend([sys.executable, "-c", "import time; time.sleep(2)"], timeout=0.05)
        self.assertEqual(raised.exception.code, "backend-timeout")


if __name__ == "__main__":
    unittest.main()
