import hashlib
import json
import pathlib
import tempfile
import unittest
from unittest import mock

from tools.codex_assets import knowledge_provider_adapter as adapter


class ProviderAdapterTests(unittest.TestCase):
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
