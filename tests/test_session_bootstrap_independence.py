from __future__ import annotations

import contextlib
import io
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tools.codex_assets.session_bootstrap import BootstrapError, build_envelope, configure_parser, main


ROOT = pathlib.Path(__file__).resolve().parents[1]
BINDING = "manifests/integrations/digital-worker-runtime-binding.json"
CORE = (
    "manifests/session_bootstrap.json",
    "manifests/provider-locks/agent-dev-kit.json",
    "scripts/knowledge-provider.sh",
)


class DailyBootstrapIndependenceTests(unittest.TestCase):
    """Unit conformance only; these fixtures do not qualify a live provider."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name) / "runtime"
        self.knowledge = pathlib.Path(self.temp.name) / "knowledge-hub"
        self.knowledge.mkdir()
        self.missing_dw = pathlib.Path(self.temp.name) / "not-installed-digital-worker"
        for relative in CORE[:2]:
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, destination)
        adapter = self.root / CORE[2]
        adapter.parent.mkdir(parents=True)
        adapter.write_text("# Unit fixture: provider adapter is not executed.\n", encoding="utf-8")

    def argv(self, mode: str, *extra: str) -> list[str]:
        return [
            "--root", str(self.root), "--cwd", self.temp.name,
            "--mode", mode, "--digital-worker-root", str(self.missing_dw),
            "--knowledge-root", str(self.knowledge), *extra,
        ]

    def envelope(self, mode: str, *extra: str):
        return build_envelope(configure_parser().parse_args(self.argv(mode, *extra)))

    def write_binding(self, value: str) -> None:
        path = self.root / BINDING
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")

    def assert_daily(self, result, mode: str) -> None:
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["mode"], mode)
        self.assertFalse(result["digital_worker"]["required"])
        self.assertIsNone(result["digital_worker"]["root"])
        self.assertIsNone(result["digital_worker"]["governance_identity"])
        self.assertIsNone(result["execution_source_set"])
        self.assertIsNone(result["work_identity"])
        self.assertFalse(result["claims"]["domain_verification_owned_by_digital_worker"])
        self.assertTrue(result["claims"]["runtime_local_only"])
        self.assertTrue(result["claims"]["project_acceptance_owned_by_project"])
        for key in ("verification_pass", "domain_gate_pass", "release_ready"):
            self.assertNotIn(f'"{key}"', json.dumps(result))
        self.assertFalse(self.missing_dw.exists())

    def test_daily_modes_work_without_digital_worker_or_integration_file(self) -> None:
        for mode in ("L0", "L1"):
            with self.subTest(mode=mode):
                self.assert_daily(self.envelope(mode), mode)
                self.assertFalse((self.root / BINDING).exists())

    def test_daily_modes_ignore_malformed_or_disabled_optional_integration(self) -> None:
        for value in ("not-json", "[]", '{"status":"disabled"}'):
            self.write_binding(value)
            for mode in ("L0", "L1"):
                with self.subTest(value=value, mode=mode):
                    self.assert_daily(self.envelope(mode), mode)

    def test_daily_identity_is_derived_from_the_existing_adk_lock(self) -> None:
        lock = json.loads((self.root / CORE[1]).read_text(encoding="utf-8"))
        expected = {
            "provider_repository": lock["repository"],
            "release_version": lock["version"],
            "provider_commit": lock["provider_commit"],
            "asset_profile": lock["asset_profile"],
            "identity_mode": lock["source_set"]["identity"],
        }
        self.assertEqual(self.envelope("L1")["runtime_binding"]["source_binding"], expected)

    def test_missing_knowledge_is_degraded_only_for_l0_and_blocks_l1(self) -> None:
        self.knowledge.rmdir()
        result = self.envelope("L0")
        self.assert_daily(result, "L0")
        self.assertIn("knowledge_provider_unavailable", result["degraded_reasons"])
        result = self.envelope("L1")
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["blocked_reasons"], ["knowledge_provider_unavailable"])

    def test_invalid_adk_delivery_still_blocks_daily_modes(self) -> None:
        path = self.root / CORE[1]
        lock = json.loads(path.read_text(encoding="utf-8"))
        lock["binding_status"] = "unverified"
        path.write_text(json.dumps(lock), encoding="utf-8")
        for mode in ("L0", "L1"):
            with self.subTest(mode=mode), self.assertRaisesRegex(BootstrapError, "ADK provider lock"):
                self.envelope(mode)

    def test_core_assets_are_still_required(self) -> None:
        for relative in CORE:
            path = self.root / relative
            data = path.read_bytes()
            path.unlink()
            with self.subTest(path=relative), self.assertRaisesRegex(BootstrapError, "required Runtime Binding asset"):
                self.envelope("L1")
            path.write_bytes(data)

    def test_formal_mode_still_requires_its_integration(self) -> None:
        with self.assertRaisesRegex(BootstrapError, "required formal Runtime Binding asset"):
            self.envelope("L2")

    def test_formal_mode_rejects_malformed_and_disabled_integration(self) -> None:
        for value in ("not-json", "[]", '{"status":"disabled"}'):
            self.write_binding(value)
            with self.subTest(value=value), self.assertRaises(BootstrapError):
                self.envelope("L2")

    def test_formal_mode_never_falls_back_when_materials_are_missing(self) -> None:
        self.write_binding('{"status":"active","readiness":"SOURCE_SET_BOUND"}')
        result = self.envelope("L2")
        self.assertEqual(result["mode"], "L2")
        self.assertEqual(result["status"], "blocked")
        self.assertIn("digital_worker_root_unavailable", result["blocked_reasons"])
        self.assertIn("engineering_task_package_missing", result["blocked_reasons"])
        self.assertIsNone(result["execution_source_set"])

    def test_formal_signal_cannot_be_downgraded_to_daily_mode(self) -> None:
        for mode in ("L0", "L1"):
            with self.subTest(mode=mode), self.assertRaisesRegex(BootstrapError, "conflicts"):
                self.envelope(mode, "--formal")

    def test_cli_returns_machine_readable_blocked_for_bad_formal_json(self) -> None:
        self.write_binding("not-json")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = main(self.argv("L2", "--summary-json"))
        self.assertEqual(result, 2)
        self.assertEqual(json.loads(output.getvalue())["status"], "blocked")

    def test_manifest_declares_only_l2_as_digital_worker_dependent(self) -> None:
        contract = json.loads((self.root / CORE[0]).read_text(encoding="utf-8"))
        self.assertEqual(contract["contract_version"], "1.3")
        self.assertEqual(contract["runtime_binding_contract_modes"], ["L2"])
        for mode in ("L0", "L1", "L2"):
            self.assertEqual(contract["modes"][mode]["digital_worker_contract_required"], mode == "L2")

    def test_daily_cli_works_from_external_cwd_with_empty_home(self) -> None:
        home = pathlib.Path(self.temp.name) / "empty-home"
        home.mkdir()
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools/codex_assets/session_bootstrap.py"), *self.argv("L1", "--summary-json")],
            cwd=self.temp.name,
            env={**os.environ, "HOME": str(home), "DIGITAL_WORKER_ROOT": str(self.missing_dw)},
            text=True, capture_output=True, check=False, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_daily(json.loads(result.stdout), "L1")
        self.assertEqual(list(home.iterdir()), [])

    def test_daily_does_not_probe_digital_worker_root(self) -> None:
        from tools.codex_assets import session_bootstrap

        original = session_bootstrap._path_or_default

        def only_knowledge(value, env_key, default):
            self.assertNotEqual(env_key, "DIGITAL_WORKER_ROOT")
            return original(value, env_key, default)

        with mock.patch.object(session_bootstrap, "_path_or_default", side_effect=only_knowledge):
            self.assert_daily(self.envelope("L1"), "L1")


if __name__ == "__main__":
    unittest.main()
