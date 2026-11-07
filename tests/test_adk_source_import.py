"""Disposable source-import regressions; trust/Git doubles are not signed evidence."""
from __future__ import annotations

import contextlib
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.codex_assets import adk_source_import as importer
from tools.codex_assets.adk_skill_audit import AuditError, _blob, _digest, _source_tree, _tree


class AdkSourceImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "consumer"
        self.provider = Path(self.temp.name) / "provider"
        self.manifest = self.root / "manifests/skills.json"
        self.old_commit = "a" * 40
        self.record = {
            "name": "adk-example", "enabled": True, "owner": "agent-dev-kit",
            "version": "1.0.0", "source_ref": self.old_commit,
            "source_repo": importer.REPOSITORY, "source_path": "skills/adk-example/SKILL.md",
            "vendor_rel": "vendor/skills/adk-example/1.0.0", "distribution_metadata": {},
            "local_tree_sha256": "",
        }
        directory = self.root / "src/codex-home" / self.record["vendor_rel"]
        self.write(directory / "SKILL.md", "---\nversion: 1.0.0\n---\n# Example\n")
        self.write(directory / "README.md", self.readme("1.0.0", self.old_commit))
        tree = _tree(directory)
        self.record["distribution_metadata"]["README.md"] = {"source": None, "installed": tree["README.md"]}
        self.record["source_blob"] = tree["SKILL.md"]["blob"]
        self.record["source_tree_sha256"] = _digest(_source_tree(self.record, tree))
        self.record["local_tree_sha256"] = _digest(tree)
        self.save()
        self.write(self.root / "manifests/agents.json", '{"agents":[]}')
        self.write(self.root / "manifests/execution_policy.json", '{"engine":{"behavior_baseline":{}}}')
        self.write(self.root / "manifests/provider-locks/agent-dev-kit.json", '{}')
        self.write(self.root / "src/codex-home/skills/registry.csv",
                   "name,version,status,owner\nadk-example,1.0.0,active,agent-dev-kit\n")
        (self.root / "tools/codex_assets/execution_policy").mkdir(parents=True)
        for filename in importer.POLICY_FILES:
            self.write(self.provider / "src/agent_dev_kit/execution_policy" / filename, "# upstream fixture\n")
        self.trusted_root = Path(self.temp.name) / "trusted-root.json"
        self.write(self.trusted_root, "unit-test trust double\n")
        self.trust_digest = hashlib.sha256(self.trusted_root.read_bytes()).hexdigest()
        self.provider_state = self.upgrade_provider("1.1.0", "7.13.0", "b" * 40)

    def write(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        path.chmod(0o644)

    def readme(self, version: str, commit: str) -> str:
        return f"# Example\n- Skill version: `{version}`\n- Source commit: `{commit}`\n"

    def save(self) -> None:
        self.write(self.manifest, json.dumps({"skills": [self.record]}))

    def current(self):
        return json.loads(self.manifest.read_text())["skills"][0]

    def upgrade_provider(self, skill_version, version, commit):
        self.write(self.provider / "manifest.json", json.dumps({"version": version}))
        self.write(self.provider / "skills/adk-example/SKILL.md",
                   f"---\nversion: {skill_version}\n---\n# Example\n")
        tracked = {path.relative_to(self.provider).as_posix():
                   {"kind": "blob", "mode": "100644", "blob": _blob(path.read_bytes())}
                   for path in self.provider.rglob("*") if path.is_file()}
        return {"commit": commit, "version": version, "tracked": tracked}

    def report(self, *_arguments):
        item = self.current()
        current = _source_tree(item, _tree(self.root / "src/codex-home" / item["vendor_rel"]))
        upstream = _tree(self.provider / "skills/adk-example")
        return {"status": "consistent", "candidate": {"blocked_skills": 0}, "skills": [{
            "name": item["name"], "target": {"removed": sorted(set(current) - set(upstream)),
                "changed": sorted(k for k in current.keys() & upstream.keys() if current[k] != upstream[k]),
                "added": sorted(set(upstream) - set(current)), "tree_sha256": _digest(upstream),
                "entrypoint_blob": upstream["SKILL.md"]["blob"]}}]}

    @contextlib.contextmanager
    def boundaries(self):
        # Test doubles isolate external verification; no signature or release is created.
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(importer, "_provider", side_effect=lambda *_: dict(self.provider_state)))
            stack.enter_context(patch.object(importer, "_git", return_value="c" * 40))
            stack.enter_context(patch.object(importer, "_check_target_clean"))
            stack.enter_context(patch.object(importer, "_promotion"))
            stack.enter_context(patch.object(importer, "audit", side_effect=self.report))
            stack.enter_context(patch.object(importer, "TRUSTED_ROOT_SHA256", self.trust_digest))
            verifier = stack.enter_context(patch.object(importer.subprocess, "run", return_value=
                subprocess.CompletedProcess([], 0, stdout="Verified OK", stderr="")))
            yield verifier

    def make_plan(self):
        return importer.plan(self.root, self.provider, self.provider_state["commit"],
                             Path(self.temp.name) / "unused-evidence", Path(self.temp.name) / "unused-attestation",
                             self.trusted_root, "d" * 64)

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in self.root.rglob("*") if p.is_file()}

    def _v2_promotion_receipt(self) -> dict:
        provider = self.provider_state
        manifest = (self.provider / "manifest.json").read_bytes()
        return {
            "schema": "adk-promotion-evidence/v2",
            "source": {
                "repository": importer.REPOSITORY,
                "ref": "refs/heads/main",
                "event": "push",
                "version": provider["version"],
                "commit": provider["commit"],
                "tree": "c" * 40,
                "manifest_blob": provider["tracked"]["manifest.json"]["blob"],
                "manifest_sha256": hashlib.sha256(manifest).hexdigest(),
                "workflow": "agent-dev-kit-ci",
                "workflow_ref": importer.REPOSITORY + "/.github/workflows/ci.yml@refs/heads/main",
                "workflow_sha": provider["commit"],
                "run_id": 421234,
                "run_attempt": 1,
            },
            "release": {"release_eligible": True, "artifact_sha256": "d" * 64},
            "ci": {
                "contract_matrix": {"status": "success", "python": ["3.11", "3.12"]},
                "regression_matrix": {"status": "success", "python": ["3.11", "3.12"]},
                "deterministic_eval_package": "success",
                "static_security": "success",
            },
            "provenance": {"format": "sigstore-bundle/v1", "subject": "promotion-evidence.json"},
        }

    def test_exact_promotion_v2_claims_accept_clean_fixture(self) -> None:
        provider = dict(self.provider_state, root=self.provider)
        receipt = self._v2_promotion_receipt()
        path = Path(self.temp.name) / "promotion.json"
        self.write(path, json.dumps(receipt))
        with patch.object(importer, "_git", return_value="c" * 40):
            importer._promotion(path, provider, "d" * 64)

    def test_v2_promotion_fails_closed_on_identity_ci_and_attestation_drift(self) -> None:
        import copy
        provider = dict(self.provider_state, root=self.provider)
        baseline = self._v2_promotion_receipt()
        mutants = {
            "historical-v1": lambda d: d.update(schema="adk-promotion-evidence/v1"),
            "wrong-source": lambda d: d["source"].update(commit="a" * 40),
            "wrong-tree": lambda d: d["source"].update(tree="b" * 40),
            "wrong-manifest-blob": lambda d: d["source"].update(manifest_blob="a" * 40),
            "wrong-manifest-bytes": lambda d: d["source"].update(manifest_sha256="a" * 64),
            "wrong-workflow": lambda d: d["source"].update(workflow_sha="e" * 40),
            "missing-run": lambda d: d["source"].pop("run_id"),
            "bool-run": lambda d: d["source"].update(run_id=True),
            "missing-attempt": lambda d: d["source"].update(run_attempt=0),
            "wrong-ref": lambda d: d["source"].update(ref="refs/heads/develop"),
            "ci-failed": lambda d: d["ci"]["regression_matrix"].update(status="failure"),
            "ci-not-matched": lambda d: d["ci"]["contract_matrix"].update(python=["3.12"]),
            "release-unqualified": lambda d: d["release"].update(release_eligible=False),
            "wrong-artifact": lambda d: d["release"].update(artifact_sha256="e" * 64),
            "unsigned-subject": lambda d: d["provenance"].update(subject="other.json"),
        }
        path = Path(self.temp.name) / "promotion.json"
        with patch.object(importer, "_git", return_value="c" * 40):
            for label, mutate in mutants.items():
                with self.subTest(label=label):
                    receipt = copy.deepcopy(baseline)
                    mutate(receipt)
                    self.write(path, json.dumps(receipt))
                    with self.assertRaisesRegex(importer.ImportError, "promotion"):
                        importer._promotion(path, provider, "d" * 64)

    def _add_format_only_native_metadata(self, *, semantic_change: bool = False) -> None:
        """Build a disposable source-set with display metadata that was reflowed upstream."""
        item = self.current()
        vendor = self.root / "src/codex-home" / item["vendor_rel"]
        old_yaml = ("interface:\n"
                    "  display_name: Example\n"
                    "  short_description: A concise description\n"
                    "    of a single behavior.\n")
        new_yaml = ("interface:\n"
                    "  display_name: Example\n"
                    "  short_description: A concise description of a single behavior.\n")
        if semantic_change:
            new_yaml = new_yaml.replace("single behavior", "privileged destructive behavior")
        self.write(vendor / "agents/openai.yaml", old_yaml)
        item = self.current()
        item["distribution_metadata"]["agents/openai.yaml"] = {
            "source": {"blob": "a" * 40, "mode": "100644"},
            "installed": _tree(vendor)["agents/openai.yaml"],
        }
        item["source_tree_sha256"] = _digest(_source_tree(item, _tree(vendor)))
        item["local_tree_sha256"] = _digest(_tree(vendor))
        self.record = item
        self.save()
        source = self.provider / "skills/adk-example/agents/openai.yaml"
        self.write(source, new_yaml)
        self.provider_state["tracked"]["skills/adk-example/agents/openai.yaml"] = {
            "kind": "blob", "mode": "100644", "blob": _blob(source.read_bytes()),
        }

    def test_format_only_native_metadata_is_rebound_to_exact_source_blob(self) -> None:
        self._add_format_only_native_metadata()
        with self.boundaries():
            result = self.make_plan()
            renewal = result["skills"][0]["format_only_metadata_rebindings"]
            self.assertEqual(["agents/openai.yaml"], list(renewal))
            prior_yaml = (self.root / "src/codex-home" / self.record["vendor_rel"] /
                          "agents/openai.yaml").read_bytes()
            importer.apply(self.root, self.provider, result)
        updated = self.current()
        target_dir = self.root / "src/codex-home" / updated["vendor_rel"]
        self.assertEqual(
            updated["distribution_metadata"]["agents/openai.yaml"]["source"],
            renewal["agents/openai.yaml"],
        )
        self.assertEqual((target_dir / "agents/openai.yaml").read_bytes(), prior_yaml)
        self.assertEqual(
            _source_tree(updated, _tree(target_dir)),
            _tree(self.provider / "skills/adk-example"),
        )

    def test_semantically_changed_native_metadata_requires_review_without_writes(self) -> None:
        self._add_format_only_native_metadata(semantic_change=True)
        before = self.snapshot()
        with self.boundaries():
            with self.assertRaisesRegex(importer.ImportError, "distribution metadata needs review"):
                self.make_plan()
        self.assertEqual(self.snapshot(), before)

    def test_two_successive_upgrades_bind_each_managed_predecessor(self) -> None:
        previous = self.old_commit
        with self.boundaries():
            for skill_version, version, commit in (("1.1.0", "7.13.0", "b" * 40),
                                                   ("1.2.0", "7.14.0", "e" * 40)):
                self.provider_state = self.upgrade_provider(skill_version, version, commit)
                result = self.make_plan()
                self.assertEqual(result["skills"][0]["old_source_ref"], previous)
                importer.apply(self.root, self.provider, result)
                item = self.current()
                directory = self.root / "src/codex-home" / item["vendor_rel"]
                self.assertEqual((directory / "README.md").read_text(), self.readme(skill_version, commit))
                tree = _tree(directory)
                self.assertEqual(_source_tree(item, tree), _tree(self.provider / "skills/adk-example"))
                self.assertEqual(item["distribution_metadata"]["README.md"]["installed"], tree["README.md"])
                self.assertEqual(item["local_tree_sha256"], _digest(tree))
                self.assertEqual(item["source_ref"], commit)
                previous = commit
        self.assertFalse((self.root / "tests/fixtures/adk-skill-sources-7.0.31.json").exists())

    def test_plan_rejects_readme_self_claim_even_with_updated_metadata(self) -> None:
        directory = self.root / "src/codex-home" / self.record["vendor_rel"]
        self.write(directory / "README.md", self.readme("9.9.9", "f" * 40))
        self.record["distribution_metadata"]["README.md"]["installed"] = _tree(directory)["README.md"]
        self.save()
        before = self.snapshot()
        with self.boundaries(), self.assertRaisesRegex(importer.ImportError, "manual review"):
            self.make_plan()
        self.assertEqual(self.snapshot(), before)

    def test_apply_rejects_stale_managed_identity_before_writes(self) -> None:
        with self.boundaries():
            result = self.make_plan()
            self.record["source_ref"] = "f" * 40
            directory = self.root / "src/codex-home" / self.record["vendor_rel"]
            self.write(directory / "README.md", self.readme("1.0.0", "f" * 40))
            self.record["distribution_metadata"]["README.md"]["installed"] = _tree(directory)["README.md"]
            self.save()
            before = self.snapshot()
            with self.assertRaisesRegex(importer.ImportError, "changed since plan"):
                importer.apply(self.root, self.provider, result)
            self.assertEqual(self.snapshot(), before)

    def test_apply_preflights_readme_drift_before_any_import_write(self) -> None:
        with self.boundaries():
            result = self.make_plan()
            directory = self.root / "src/codex-home" / self.record["vendor_rel"]
            self.write(directory / "README.md", "unreviewed change\n")
            before = self.snapshot()
            with self.assertRaisesRegex(AuditError, "distribution_metadata_mismatch"):
                importer.apply(self.root, self.provider, result)
            self.assertEqual(self.snapshot(), before)

    def test_standalone_refresh_uses_current_identity(self) -> None:
        self.provider_state = self.upgrade_provider("1.0.0", "7.12.4", self.old_commit)
        with self.boundaries():
            self.assertEqual(importer.refresh_local_readmes(self.root, self.provider, self.old_commit), 1)

    def test_standalone_refresh_rejects_unmanaged_target_commit_without_writes(self) -> None:
        self.provider_state = self.upgrade_provider("1.0.0", "7.13.0", "b" * 40)
        before = self.snapshot()
        with self.boundaries(), self.assertRaisesRegex(importer.ImportError, "differs from managed identity"):
            importer.refresh_local_readmes(self.root, self.provider, self.provider_state["commit"])
        self.assertEqual(self.snapshot(), before)

    def test_unchanged_skill_version_still_refreshes_managed_commit(self) -> None:
        self.provider_state = self.upgrade_provider("1.0.0", "7.13.0", "b" * 40)
        with self.boundaries():
            result = self.make_plan()
            importer.apply(self.root, self.provider, result)
        item = self.current()
        self.assertEqual(item["vendor_rel"], self.record["vendor_rel"])
        directory = self.root / "src/codex-home" / item["vendor_rel"]
        self.assertEqual((directory / "README.md").read_text(), self.readme("1.0.0", "b" * 40))

    def test_changed_skill_without_version_advance_still_rejected(self) -> None:
        self.provider_state = self.upgrade_provider("1.0.0", "7.13.0", "b" * 40)
        path = self.provider / "skills/adk-example/SKILL.md"
        self.write(path, path.read_text() + "changed\n")
        self.provider_state["tracked"]["skills/adk-example/SKILL.md"]["blob"] = _blob(path.read_bytes())
        with self.boundaries(), self.assertRaisesRegex(importer.ImportError, "did not advance"):
            self.make_plan()

    def test_provider_source_blob_check_remains_active(self) -> None:
        self.provider_state["tracked"]["skills/adk-example/SKILL.md"]["blob"] = "f" * 40
        with self.boundaries(), self.assertRaisesRegex(AuditError, "not_exact"):
            self.make_plan()

    def test_failed_verifier_still_blocks_plan_without_writes(self) -> None:
        before = self.snapshot()
        with self.boundaries() as verifier:
            verifier.return_value = subprocess.CompletedProcess([], 1, stdout="", stderr="rejected")
            with self.assertRaisesRegex(importer.ImportError, "verification failed"):
                self.make_plan()
        self.assertEqual(self.snapshot(), before)

    def test_unreviewed_trusted_root_still_blocks_before_verifier(self) -> None:
        with self.boundaries() as verifier:
            self.write(self.trusted_root, "different\n")
            with self.assertRaisesRegex(importer.ImportError, "reviewed exact file"):
                self.make_plan()
            verifier.assert_not_called()

    def test_protected_dirty_target_still_rejected(self) -> None:
        with patch.object(importer, "_git", side_effect=["candidate", " M manifests/skills.json"]):
            with self.assertRaisesRegex(importer.ImportError, "pre-existing changes"):
                importer._check_target_clean(self.root)


if __name__ == "__main__":
    unittest.main()
