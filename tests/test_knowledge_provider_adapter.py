import hashlib
import json
import pathlib
import tempfile
import unittest
from unittest import mock

from tools.codex_assets import knowledge_provider_adapter as adapter


class ProviderAdapterTests(unittest.TestCase):
    def test_content_maintenance_receipts_are_exact_and_never_approve(self):
        for corrupt in (None, "persisted", "owner_review_performed", "manifest_ref", "write_count"):
            with self.subTest(corrupt=corrupt), tempfile.TemporaryDirectory() as directory:
                native, hub, _ = self.fixture(directory)
                expected = "a" * 64
                receipt = {"schema_version": "knowledge-provider.content-maintenance/v1", "status": "MAINTAINED",
                           "persisted": True, "write_performed": True, "read_only": False,
                           "expected_hash": expected, "item_count": 2, "write_count": 3, "delete_count": 1,
                           "active_promoted": False, "owner_review_performed": False,
                           "transaction_id": "content-maintenance-" + expected[:24],
                           "manifest_ref": "artifacts/manifests/content-maintenance-" + expected + ".json"}
                if corrupt:
                    receipt[corrupt] = {"persisted": False, "owner_review_performed": True,
                                        "manifest_ref": "wrong.json", "write_count": True}[corrupt]
                with mock.patch.object(adapter, "__file__", str(native / "tools/codex_assets/knowledge_provider_adapter.py")), \
                        mock.patch.dict("os.environ", {"KNOWLEDGE_HUB_ROOT": str(hub)}), \
                        mock.patch.object(adapter.subprocess, "run", return_value=mock.Mock(returncode=0, stdout=json.dumps(receipt))), \
                        mock.patch("builtins.print"):
                    self.assertEqual(adapter.main(["maintain-content", "--apply"]), 2 if corrupt else 0)

    def test_repository_registration_is_an_explicit_public_operation(self):
        self.assertIn("register-repository", adapter.OPERATIONS)
        with tempfile.TemporaryDirectory() as directory:
            native, hub, _ = self.fixture(directory)
            with mock.patch.object(adapter, "__file__", str(native / "tools/codex_assets/knowledge_provider_adapter.py")), \
                    mock.patch.dict("os.environ", {"KNOWLEDGE_HUB_ROOT": str(hub)}), \
                    mock.patch.object(adapter.subprocess, "run", return_value=mock.Mock(returncode=0, stdout='{"status":"PLANNED","persisted":false}')) as call, \
                    mock.patch("builtins.print"):
                self.assertEqual(adapter.main(["register-repository", "--project", "test", "--repository-id", "sample",
                                               "--remote-url", "ssh://git@example.test/group/sample.git", "--dry-run"]), 0)
                forwarded = call.call_args.args[0]
                self.assertIn("register-repository", forwarded)
                self.assertNotIn("--apply", forwarded)

    def test_extended_deadline_keeps_timeout_write_uncertainty(self):
        for arguments, expected_status, expected_persisted in (
                (["archive", "--apply"], "UNKNOWN", None),
                (["reconcile"], "BLOCKED", False)):
            with self.subTest(arguments=arguments), tempfile.TemporaryDirectory() as directory:
                native, hub, _ = self.fixture(directory)
                with mock.patch.object(adapter, "__file__", str(native / "tools/codex_assets/knowledge_provider_adapter.py")), \
                        mock.patch.dict("os.environ", {"KNOWLEDGE_HUB_ROOT": str(hub)}), \
                        mock.patch.object(adapter.subprocess, "run", side_effect=adapter.subprocess.TimeoutExpired("provider", 180)) as transport, \
                        mock.patch("builtins.print") as output:
                    self.assertEqual(adapter.main(arguments), 2)
                    self.assertEqual(transport.call_args.kwargs["timeout"], 180)
                    receipt = json.loads(output.call_args.args[0])
                    self.assertEqual(receipt["status"], expected_status)
                    self.assertIs(receipt["persisted"], expected_persisted)
                    self.assertEqual(receipt["reason_codes"], ["PROVIDER_TIMEOUT"])

    def test_root_help_lists_auxiliary_operations_as_well(self):
        with tempfile.TemporaryDirectory() as directory:
            native, hub, _ = self.fixture(directory)
            payload = {"schema_version": "knowledge-provider.help/v4", "status": "HELP", "operation": "status",
                       "read_only": True, "persisted": False, "write_performed": False, "operations": ["status"]}
            with mock.patch.object(adapter, "__file__", str(native / "tools/codex_assets/knowledge_provider_adapter.py")), \
                    mock.patch.dict("os.environ", {"KNOWLEDGE_HUB_ROOT": str(hub)}), \
                    mock.patch.object(adapter.subprocess, "run", return_value=mock.Mock(returncode=0, stdout=json.dumps(payload))), \
                    mock.patch("builtins.print") as output:
                self.assertEqual(adapter.main(["--help"]), 0)
                result = json.loads(output.call_args.args[0])
                self.assertIsNone(result["operation"])
                self.assertEqual(set(result["operations"]), adapter.OPERATIONS)
                self.assertIn("activity-capture", result["operations"])

    def test_operation_help_is_readonly_and_never_forwards_write_flags(self):
        for operation in ("context", "archive", "activity-capture"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as directory:
                native, hub, _ = self.fixture(directory)
                payload = {"schema_version": "knowledge-provider.help/v4", "status": "HELP",
                           "operation": operation, "read_only": True, "persisted": False, "write_performed": False}
                stdout = "usage: activity capture [--input INPUT]\n" if operation == "activity-capture" else json.dumps(payload)
                with mock.patch.object(adapter, "__file__", str(native / "tools/codex_assets/knowledge_provider_adapter.py")), \
                        mock.patch.dict("os.environ", {"KNOWLEDGE_HUB_ROOT": str(hub)}), \
                        mock.patch.object(adapter.subprocess, "run", return_value=mock.Mock(returncode=0, stdout=stdout)) as transport, \
                        mock.patch("builtins.print") as output:
                    self.assertEqual(adapter.main([operation, "--apply", "--help"]), 0)
                    self.assertNotIn("--apply", transport.call_args.args[0])
                    self.assertEqual(transport.call_args.args[0][-1], "--help")
                    self.assertEqual(json.loads(output.call_args.args[0])["status"], "HELP")

    def test_help_rejects_malformed_payload_and_source_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            native, hub, source = self.fixture(directory)
            with mock.patch.object(adapter, "__file__", str(native / "tools/codex_assets/knowledge_provider_adapter.py")), \
                    mock.patch.dict("os.environ", {"KNOWLEDGE_HUB_ROOT": str(hub)}), \
                    mock.patch.object(adapter.subprocess, "run", return_value=mock.Mock(returncode=0, stdout="{}")), \
                    mock.patch("builtins.print") as output:
                self.assertEqual(adapter.main(["context", "--help"]), 2)
                self.assertEqual(json.loads(output.call_args.args[0])["reason_codes"], ["PROVIDER_RESPONSE_INVALID"])
            source.write_text("changed source")
            with mock.patch.object(adapter, "__file__", str(native / "tools/codex_assets/knowledge_provider_adapter.py")), \
                    mock.patch.dict("os.environ", {"KNOWLEDGE_HUB_ROOT": str(hub)}), \
                    mock.patch.object(adapter.subprocess, "run") as transport, mock.patch("builtins.print"):
                self.assertEqual(adapter.main(["context", "--help"]), 2)
                transport.assert_not_called()

    def test_project_migration_validates_persistence_and_current_manifest(self):
        expected = "c" * 64
        base = {"schema_version": "knowledge-provider.project-migration/v1", "status": "MIGRATED",
                "subject_ref": {"type": "project", "id": "target"}, "expected_hash": expected,
                "source_file_count": 3, "source_item_count": 2, "write_count": 4, "delete_count": 3,
                "provider_proofs": 1, "active_promoted": False, "owner_review_performed": False,
                "persisted": True, "write_performed": True, "read_only": False,
                "manifest_ref": "artifacts/manifests/project-migration-" + expected + ".json",
                "transaction_id": "project-migration-" + expected[:24]}
        for change, valid in (({}, True), ({"persisted": False}, False),
                              ({"subject_ref": {"type": "project"}}, False),
                              ({"manifest_ref": "/tmp/untrusted.json"}, False),
                              ({"provider_proofs": True}, False), ({"active_promoted": True}, False)):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                native, hub, _ = self.fixture(directory)
                with mock.patch.object(adapter, "__file__", str(native / "tools/codex_assets/knowledge_provider_adapter.py")), \
                        mock.patch.dict("os.environ", {"KNOWLEDGE_HUB_ROOT": str(hub)}), \
                        mock.patch.object(adapter.subprocess, "run", return_value=mock.Mock(returncode=0, stdout=json.dumps(dict(base, **change)))), \
                        mock.patch("builtins.print") as output:
                    self.assertEqual(adapter.main(["migrate-project", "--apply"]), 0 if valid else 2)
                    if not valid:
                        self.assertEqual(json.loads(output.call_args.args[0])["status"], "UNKNOWN")

    def fixture(self, directory):
        native, hub = pathlib.Path(directory) / "native", pathlib.Path(directory) / "hub"
        (native / "manifests/provider-locks").mkdir(parents=True)
        (hub / "registry").mkdir(parents=True)
        (hub / "tools").mkdir()
        source = hub / "tools/knowledge-provider.sh"
        source.write_text("approved source\n")
        manifest = hub / "registry/provider-runtime-files.json"
        manifest.write_text(json.dumps({"schema_version": 1, "inventory_roots": ["tools"], "files": {
            "tools/knowledge-provider.sh": hashlib.sha256(source.read_bytes()).hexdigest()}}))
        (native / "manifests/provider-locks/knowledge-hub.json").write_text(json.dumps({
            "repository": "jiying2007/knowledge-hub", "protocol_version": 4,
            "provider_commit": "a" * 40, "source_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest()}))
        return native, hub, source

    def test_unlisted_root_import_sources_block_before_transport(self):
        for relative in ("json.py", "sitecustomize.py", "json.pyc", "yaml/__init__.py", "tools/unlisted.pyc", "tools/unlisted"):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as directory:
                native, hub, _ = self.fixture(directory)
                path = hub / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("unapproved executable")
                if relative == "tools/unlisted":
                    path.chmod(0o755)
                with self.assertRaisesRegex(adapter.ProviderAdapterError, "SOURCE_DRIFT"):
                    adapter.verify_source(native, hub)

    def test_real_transport_cannot_execute_shell_startup_hook(self):
        with tempfile.TemporaryDirectory() as directory:
            native, hub, source = self.fixture(directory)
            source.write_text("#!/usr/bin/env bash\nprintf '%s\\n' '{\"status\":\"READY\"}'\n")
            manifest = hub / "registry/provider-runtime-files.json"
            value = json.loads(manifest.read_text())
            value["files"]["tools/knowledge-provider.sh"] = hashlib.sha256(source.read_bytes()).hexdigest()
            manifest.write_text(json.dumps(value))
            lock_path = native / "manifests/provider-locks/knowledge-hub.json"
            lock = json.loads(lock_path.read_text())
            lock["source_manifest_sha256"] = hashlib.sha256(manifest.read_bytes()).hexdigest()
            lock_path.write_text(json.dumps(lock))
            marker = pathlib.Path(directory) / "executed"
            hook = pathlib.Path(directory) / "hook.sh"
            hook.write_text(f"touch {marker}\nprintf 'forged'\nexit 0\n")
            with mock.patch.object(adapter, "__file__", str(native / "tools/codex_assets/knowledge_provider_adapter.py")), \
                    mock.patch.dict("os.environ", {"KNOWLEDGE_HUB_ROOT": str(hub), "BASH_ENV": str(hook), "ENV": str(hook)}), \
                    mock.patch("builtins.print") as output:
                self.assertEqual(adapter.main(["status"]), 0)
                self.assertEqual(json.loads(output.call_args.args[0])["status"], "READY")
                self.assertFalse(marker.exists())

    def test_source_drift_blocks_before_transport(self):
        with tempfile.TemporaryDirectory() as directory:
            native, hub, source = self.fixture(directory)
            source.write_text("changed source")
            with self.assertRaisesRegex(adapter.ProviderAdapterError, "SOURCE_DRIFT"):
                adapter.verify_source(native, hub)

    def test_symlink_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            native, hub, source = self.fixture(directory)
            original = source.with_suffix(".original")
            source.rename(original)
            source.symlink_to(original)
            with self.assertRaisesRegex(adapter.ProviderAdapterError, "SOURCE_DRIFT"):
                adapter.verify_source(native, hub)

    def test_post_apply_source_drift_is_unknown_with_operation_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            native, hub, source = self.fixture(directory)
            def transport(*args, **kwargs):
                source.write_text("drift after invoked apply")
                return mock.Mock(returncode=0, stdout=json.dumps({"status": "ARCHIVED", "persisted": True,
                    "operation_id": "b" * 64}), stderr="")
            with mock.patch.object(adapter, "__file__", str(native / "tools/codex_assets/knowledge_provider_adapter.py")), \
                    mock.patch.dict("os.environ", {"KNOWLEDGE_HUB_ROOT": str(hub)}), \
                    mock.patch.object(adapter.subprocess, "run", side_effect=transport), \
                    mock.patch("builtins.print") as output:
                self.assertEqual(adapter.main(["archive", "--apply"]), 2)
                result = json.loads(output.call_args.args[0])
                self.assertEqual(result["status"], "UNKNOWN")
                self.assertIsNone(result["persisted"])
                self.assertEqual(result["operation_id"], "b" * 64)

    def test_preflight_failure_never_invokes_apply(self):
        with tempfile.TemporaryDirectory() as directory:
            native, hub, source = self.fixture(directory)
            source.write_text("drift before apply")
            with mock.patch.object(adapter, "__file__", str(native / "tools/codex_assets/knowledge_provider_adapter.py")), \
                    mock.patch.dict("os.environ", {"KNOWLEDGE_HUB_ROOT": str(hub)}), \
                    mock.patch.object(adapter.subprocess, "run") as transport, \
                    mock.patch("builtins.print") as output:
                self.assertEqual(adapter.main(["archive", "--apply"]), 2)
                self.assertEqual(json.loads(output.call_args.args[0])["status"], "BLOCKED")
                transport.assert_not_called()


    def test_invalid_responses_after_apply_are_unknown(self):
        for payload in ("", "not-json", "[]", "{}", '{"unexpected":true}', '{"status":"ARCHIVED"}'):
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as directory:
                native, hub, _ = self.fixture(directory)
                with mock.patch.object(adapter, "__file__", str(native / "tools/codex_assets/knowledge_provider_adapter.py")), \
                        mock.patch.dict("os.environ", {"KNOWLEDGE_HUB_ROOT": str(hub)}), \
                        mock.patch.object(adapter.subprocess, "run", return_value=mock.Mock(returncode=0, stdout=payload, stderr="")), \
                        mock.patch("builtins.print") as output:
                    self.assertEqual(adapter.main(["archive", "--apply"]), 2)
                    result = json.loads(output.call_args.args[0])
                    self.assertEqual(result["status"], "UNKNOWN")
                    self.assertIsNone(result["persisted"])

    def test_internal_root_and_write_abbreviations_are_rejected_before_transport(self):
        for flag in ("--root", "--root=/tmp/other", "--app"):
            with self.subTest(flag=flag), mock.patch.object(adapter.subprocess, "run") as transport, \
                    mock.patch("builtins.print") as output:
                self.assertEqual(adapter.main(["activity-capture", flag]), 2)
                self.assertEqual(json.loads(output.call_args.args[0])["status"], "BLOCKED")
                transport.assert_not_called()


if __name__ == "__main__":
    unittest.main()
