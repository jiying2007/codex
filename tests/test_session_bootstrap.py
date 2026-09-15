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

    def commit_repo(self, root: pathlib.Path) -> str:
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "add", "."], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.com",
                "commit",
                "-qm",
                "fixture",
            ],
            check=True,
        )
        return subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()

    def formal_fixture(self, base: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path, pathlib.Path, str, str, str]:
        dw = base / "digital-worker"
        kh = base / "knowledge-hub"
        etp = base / "engineering-task-package.json"
        (kh / "registry/integrations").mkdir(parents=True)
        etp.write_text("{}\n", encoding="utf-8")

        knowledge_contract_rel = "registry/integrations/digital-worker.json"
        knowledge_contract_path = kh / knowledge_contract_rel
        knowledge_contract_data = {"contract_version": "1.0", "status": "active"}
        knowledge_contract_path.write_text(json.dumps(knowledge_contract_data, indent=2) + "\n", encoding="utf-8")
        knowledge_commit = self.commit_repo(kh)
        canonical = json.dumps(
            knowledge_contract_data,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        knowledge_digest = hashlib.sha256(canonical).hexdigest()

        domain_ref = "domains/edge-foundation/domain.yaml"
        routing_ref = "config/routing/edge.yaml"
        skill_ref = "domains/edge-foundation/skills/debug/SKILL.md"
        (dw / "contracts").mkdir(parents=True)
        (dw / pathlib.Path(domain_ref).parent).mkdir(parents=True)
        (dw / pathlib.Path(routing_ref).parent).mkdir(parents=True)
        (dw / pathlib.Path(skill_ref).parent).mkdir(parents=True)
        (dw / "config/integrations").mkdir(parents=True)
        (dw / "contracts/catalog.json").write_text(
            json.dumps({"schema_version": 1, "contracts": []}, indent=2) + "\n",
            encoding="utf-8",
        )
        (dw / domain_ref).write_text("domain: edge-foundation\n", encoding="utf-8")
        (dw / routing_ref).write_text("route: embedded\n", encoding="utf-8")
        (dw / skill_ref).write_text("---\nname: debug\n---\n", encoding="utf-8")
        lock = {
            "providers": {
                "knowledge_control_plane": {
                    "commit": knowledge_commit,
                    "contract": knowledge_contract_rel,
                    "contract_canonical_sha256": knowledge_digest,
                }
            }
        }
        (dw / "config/integrations/cross-repo-lock.json").write_text(
            json.dumps(lock, indent=2) + "\n",
            encoding="utf-8",
        )
        self.commit_repo(dw)
        return dw, kh, etp, domain_ref, routing_ref, skill_ref

    def formal_args(
        self,
        base: pathlib.Path,
        dw: pathlib.Path,
        kh: pathlib.Path,
        etp: pathlib.Path,
        domain_ref: str,
        routing_ref: str,
        skill_ref: str,
        *extra: str,
    ):
        return self.parse(
            "--cwd",
            str(base),
            "--formal",
            "--base-commit",
            "a" * 40,
            "--digital-worker-root",
            str(dw),
            "--digital-worker-domain-ref",
            domain_ref,
            "--digital-worker-routing-ref",
            routing_ref,
            "--digital-worker-skill-ref",
            skill_ref,
            "--knowledge-root",
            str(kh),
            "--engineering-task-package",
            str(etp),
            *extra,
        )

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
            self.assertIsNone(envelope["execution_source_set"])
            self.assertTrue(envelope["session_bootstrap_identity"].startswith("sha256:"))

    def test_l1_requires_digital_worker_and_current_knowledge_provider(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            dw = base / "digital-worker"
            kh = base / "knowledge-hub"
            dw.mkdir()
            kh.mkdir()
            args = self.parse(
                "--cwd",
                tmp,
                "--governed",
                "--digital-worker-root",
                str(dw),
                "--knowledge-root",
                str(kh),
            )
            envelope = build_envelope(args)
            self.assertEqual(envelope["status"], "ready")
            self.assertEqual(envelope["mode"], "L1")
            self.assertEqual(envelope["knowledge"]["mode"], "current-provider")
            self.assertIsNone(envelope["digital_worker"]["governance_identity"])
            self.assertIsNone(envelope["execution_source_set"])

    def test_l2_fails_closed_without_exact_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = self.parse("--cwd", tmp, "--formal")
            envelope = build_envelope(args)
            self.assertEqual(envelope["status"], "blocked")
            self.assertEqual(envelope["mode"], "L2")
            self.assertTrue(envelope["blocked_reasons"])
            self.assertIsNone(envelope["execution_source_set"])

    def test_l2_blocks_missing_digital_worker_selection_even_with_provider_checkouts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            dw, kh, etp, _, _, _ = self.formal_fixture(base)
            args = self.parse(
                "--cwd",
                tmp,
                "--formal",
                "--base-commit",
                "a" * 40,
                "--digital-worker-root",
                str(dw),
                "--knowledge-root",
                str(kh),
                "--engineering-task-package",
                str(etp),
            )
            envelope = build_envelope(args)
            self.assertEqual(envelope["status"], "blocked")
            self.assertTrue(
                any("requires at least one explicit digital-worker domain ref" in item for item in envelope["blocked_reasons"])
            )
            self.assertIsNone(envelope["execution_source_set"])

    def test_l2_accepts_exact_governance_and_knowledge_identity_and_freezes_source_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            dw, kh, etp, domain_ref, routing_ref, skill_ref = self.formal_fixture(base)
            args = self.formal_args(base, dw, kh, etp, domain_ref, routing_ref, skill_ref)
            envelope = build_envelope(args)
            self.assertEqual(envelope["status"], "ready")
            self.assertEqual(envelope["mode"], "L2")

            governance = envelope["digital_worker"]["governance_identity"]
            self.assertEqual(governance["provider"], "digital-worker")
            self.assertEqual(governance["provider_commit"], subprocess.check_output(["git", "-C", str(dw), "rev-parse", "HEAD"], text=True).strip())
            self.assertEqual(governance["selected_domain_refs"], [domain_ref])
            self.assertEqual(governance["selected_routing_refs"], [routing_ref])
            self.assertEqual(governance["materially_used_domain_skills"], [skill_ref])
            self.assertEqual(len(governance["contract_catalog_digest"]), 64)
            self.assertEqual(len(governance["identity_digest"]), 64)

            self.assertTrue(envelope["knowledge"]["commit"])
            self.assertTrue(envelope["execution_source_set"]["identity"].startswith("sha256:"))
            self.assertTrue(envelope["session_bootstrap_identity"].startswith("sha256:"))
            rendered = json.dumps(envelope, sort_keys=True)
            for forbidden in ("verification_pass", "domain_gate_pass", "release_ready"):
                self.assertNotIn(f'"{forbidden}"', rendered)

    def test_l1_to_l2_escalation_refreezes_and_never_promotes_prior_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            dw, kh, etp, domain_ref, routing_ref, skill_ref = self.formal_fixture(base)

            l1 = build_envelope(
                self.parse(
                    "--cwd",
                    tmp,
                    "--governed",
                    "--digital-worker-root",
                    str(dw),
                    "--knowledge-root",
                    str(kh),
                    "--task",
                    "same work item",
                )
            )
            self.assertEqual(l1["status"], "ready")
            self.assertIsNone(l1["execution_source_set"])
            prior = base / "l1-bootstrap.json"
            prior.write_text(json.dumps(l1, indent=2) + "\n", encoding="utf-8")

            l2 = build_envelope(
                self.formal_args(
                    base,
                    dw,
                    kh,
                    etp,
                    domain_ref,
                    routing_ref,
                    skill_ref,
                    "--task",
                    "same work item",
                    "--escalate-from-l1",
                    "--prior-session-bootstrap",
                    str(prior),
                )
            )
            self.assertEqual(l2["status"], "ready")
            self.assertNotEqual(l1["session_bootstrap_identity"], l2["session_bootstrap_identity"])
            self.assertTrue(l2["execution_source_set"]["identity"].startswith("sha256:"))
            escalation = l2["governance_escalation"]
            self.assertEqual(escalation["from_level"], "L1")
            self.assertEqual(escalation["to_level"], "L2")
            self.assertEqual(escalation["prior_context_disposition"], "provisional-not-promoted")
            self.assertEqual(escalation["prior_session_bootstrap_identity"], l1["session_bootstrap_identity"])
            self.assertEqual(escalation["new_execution_source_set_ref"], l2["execution_source_set"]["identity"])
            self.assertEqual(escalation["new_session_bootstrap_ref"], l2["session_bootstrap_identity"])

    def test_l1_to_l2_escalation_requires_prior_bootstrap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            dw, kh, etp, domain_ref, routing_ref, skill_ref = self.formal_fixture(base)
            envelope = build_envelope(
                self.formal_args(
                    base,
                    dw,
                    kh,
                    etp,
                    domain_ref,
                    routing_ref,
                    skill_ref,
                    "--escalate-from-l1",
                )
            )
            self.assertEqual(envelope["status"], "blocked")
            self.assertIn("L1 to L2 escalation requires --prior-session-bootstrap", envelope["blocked_reasons"])
            self.assertIsNone(envelope["execution_source_set"])


if __name__ == "__main__":
    unittest.main()
