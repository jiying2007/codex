from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import tempfile
import unittest

from tools.codex_assets.session_bootstrap import BootstrapError, build_envelope, configure_parser, resolve_mode


ROOT = pathlib.Path(__file__).resolve().parents[1]


class SessionBootstrapTests(unittest.TestCase):
    def parse(self, *args: str):
        return configure_parser().parse_args(["--root", str(ROOT), *args])

    def test_resolution_precedence_is_deterministic(self) -> None:
        self.assertEqual(resolve_mode("auto", governed=False, formal=False, engineering_task_package=None), "L0")
        self.assertEqual(resolve_mode("auto", governed=True, formal=False, engineering_task_package=None), "L1")
        self.assertEqual(resolve_mode("auto", governed=False, formal=True, engineering_task_package=None), "L2")
        self.assertEqual(resolve_mode("L2", governed=False, formal=True, engineering_task_package=None), "L2")
        with self.assertRaises(BootstrapError):
            resolve_mode("L0", governed=False, formal=True, engineering_task_package=None)

    def test_l0_is_ready_without_control_planes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = self.parse("--cwd", tmp, "--mode", "L0", "--knowledge-root", f"{tmp}/missing")
            envelope = build_envelope(args)
            self.assertEqual(envelope["status"], "ready")
            self.assertEqual(envelope["mode"], "L0")
            self.assertIn("knowledge_provider_unavailable", envelope["degraded_reasons"])
            self.assertEqual(envelope["agent_assets"]["delivery_mode"], "exact-source-set")
            self.assertEqual(envelope["runtime_binding"]["readiness"], "SOURCE_SET_BOUND")

    def test_l1_requires_digital_worker_and_current_knowledge_provider(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            dw = base / "digital-worker"
            kh = base / "knowledge-hub"
            dw.mkdir()
            kh.mkdir()
            args = self.parse(
                "--cwd", tmp,
                "--governed",
                "--digital-worker-root", str(dw),
                "--knowledge-root", str(kh),
            )
            envelope = build_envelope(args)
            self.assertEqual(envelope["status"], "ready")
            self.assertEqual(envelope["mode"], "L1")
            self.assertEqual(envelope["knowledge"]["mode"], "current-provider")

    def test_l2_fails_closed_without_exact_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = self.parse("--cwd", tmp, "--formal")
            envelope = build_envelope(args)
            self.assertEqual(envelope["status"], "blocked")
            self.assertEqual(envelope["mode"], "L2")
            self.assertTrue(envelope["blocked_reasons"])

    def test_l2_accepts_exact_pinned_knowledge_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            dw = base / "digital-worker"
            kh = base / "knowledge-hub"
            etp = base / "engineering-task-package.json"
            (dw / "config/integrations").mkdir(parents=True)
            (kh / "registry/integrations").mkdir(parents=True)
            etp.write_text("{}\n", encoding="utf-8")

            contract_rel = "registry/integrations/digital-worker.json"
            contract_path = kh / contract_rel
            contract_data = {"contract_version": "1.0", "status": "active"}
            contract_path.write_text(json.dumps(contract_data, indent=2) + "\n", encoding="utf-8")
            canonical = json.dumps(contract_data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            digest = hashlib.sha256(canonical).hexdigest()

            subprocess.run(["git", "init", "-q", str(kh)], check=True)
            subprocess.run(["git", "-C", str(kh), "add", contract_rel], check=True)
            subprocess.run(
                ["git", "-C", str(kh), "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "fixture"],
                check=True,
            )
            commit = subprocess.check_output(["git", "-C", str(kh), "rev-parse", "HEAD"], text=True).strip()

            lock = {
                "providers": {
                    "knowledge_control_plane": {
                        "commit": commit,
                        "contract": contract_rel,
                        "contract_canonical_sha256": digest,
                    }
                }
            }
            (dw / "config/integrations/cross-repo-lock.json").write_text(
                json.dumps(lock, indent=2) + "\n", encoding="utf-8"
            )

            args = self.parse(
                "--cwd", tmp,
                "--formal",
                "--base-commit", "a" * 40,
                "--digital-worker-root", str(dw),
                "--knowledge-root", str(kh),
                "--engineering-task-package", str(etp),
            )
            envelope = build_envelope(args)
            self.assertEqual(envelope["status"], "ready")
            self.assertEqual(envelope["mode"], "L2")
            self.assertEqual(envelope["knowledge"]["commit"], commit)
            self.assertEqual(envelope["knowledge"]["contract_canonical_sha256"], digest)
            rendered = json.dumps(envelope, sort_keys=True)
            for forbidden in ("verification_pass", "domain_gate_pass", "release_ready"):
                self.assertNotIn(f'"{forbidden}"', rendered)


if __name__ == "__main__":
    unittest.main()
