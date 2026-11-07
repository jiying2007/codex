import json
import tempfile
import unittest
from unittest import mock
from tests import test_knowledge_provider_adapter as fixtures
from tools.codex_assets import knowledge_provider_adapter as adapter


class ProviderActivityReportTest(unittest.TestCase):
    def test_no_write_or_abbreviated_arguments_reach_transport(self):
        for flags in (["--apply"], ["--output-dir", "/tmp/a"], ["--out=/tmp/a"], ["--p", "daily"]):
            with self.subTest(flags=flags), mock.patch.object(adapter.subprocess, "run") as call, mock.patch("builtins.print"):
                self.assertEqual(2, adapter.main(["activity-report"] + flags))
                call.assert_not_called()

    def test_report_is_forced_readonly_and_receipt_checked(self):
        for corrupted in (False, True):
            with self.subTest(corrupted=corrupted), tempfile.TemporaryDirectory() as directory:
                native, hub, _ = fixtures.ProviderAdapterTests().fixture(directory)
                payload = {"schema_version": 2, "status": "pass", "mode": "report-only", "written": corrupted,
                           "period": {"start": "2026-11-03", "end": "2026-11-03"},
                           "facts": {"schema_version": 2, "kind": "knowledge-hub.activity-facts-v2", "work_items": [],
                                     "period": {"start": "2026-11-03", "end": "2026-11-03"}},
                           "source_coverage": {}, "privacy": {key: False for key in
                           ("raw_sessions_stored", "raw_logs_stored", "credentials_stored",
                            "identity_inferred_from_git", "memory_write", "external_write")}}
                with mock.patch.object(adapter, "__file__", str(native / "tools/codex_assets/knowledge_provider_adapter.py")), \
                        mock.patch.dict("os.environ", {"KNOWLEDGE_HUB_ROOT": str(hub)}), \
                        mock.patch.object(adapter.subprocess, "run", return_value=mock.Mock(returncode=0, stdout=json.dumps(payload))) as call, \
                        mock.patch("builtins.print"):
                    self.assertEqual(2 if corrupted else 0, adapter.main(["activity-report", "--period", "daily"]))
                    self.assertIn("report", call.call_args.args[0])
                    self.assertIn("--stdout-only", call.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
