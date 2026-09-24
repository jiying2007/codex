"""Pinned upstream source and native packaging stay independently verifiable."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

import yaml

from tests import test_adk_skill_audit as fixtures
from tools.codex_assets.adk_skill_audit import _digest, _source_tree, _tree, audit
from tools.codex_assets.check_skills import validate_openai_metadata
from tools.codex_assets.core import Repo, parse_frontmatter
from tools.codex_assets.skill_catalog import search_skills

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "7367ef84787de75bb751940b32c9e80009660e47"


class DistributionMetadataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = fixtures.AdkSkillAuditTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        directory = self.fixture.skill.parent
        source = _tree(directory)
        self.metadata = directory / "README.md"
        self.fixture.write(self.metadata, "Distribution-only metadata\n")
        self.metadata.chmod(0o644)
        self.fixture.record["source_tree_sha256"] = _digest(source)
        self.fixture.record["distribution_metadata"] = {
            "README.md": {"source": None, "installed": _tree(directory)["README.md"]}}
        self.fixture.save()

    def gaps(self):
        return audit(self.fixture.root)["gap_counts"]

    def test_packaging_does_not_change_upstream_identity_or_qualification(self) -> None:
        report = audit(self.fixture.root)
        self.assertEqual("consistent", report["status"])
        self.assertEqual(["README.md"], report["skills"][0]["distribution_metadata_paths"])
        self.assertFalse(report["claims"]["runtime_qualified"])
        self.assertFalse(report["claims"]["installation_verified"])

    def test_changed_missing_or_executable_metadata_is_rejected(self) -> None:
        self.metadata.write_text("tampered")
        self.assertIn("distribution_metadata_mismatch", self.gaps())
        self.metadata.write_text("Distribution-only metadata\n")
        self.metadata.chmod(0o755)
        self.assertIn("distribution_metadata_mismatch", self.gaps())
        self.metadata.unlink()
        self.assertIn("distribution_metadata_mismatch", self.gaps())

    def test_capability_files_cannot_be_excluded_as_packaging(self) -> None:
        binding = copy.deepcopy(self.fixture.record["distribution_metadata"]["README.md"])
        for path in ("SKILL.md", "references/guard.md", "scripts/run.py", "../README.md"):
            with self.subTest(path=path):
                self.fixture.record["distribution_metadata"] = {path: binding}
                self.fixture.save()
                self.assertIn("distribution_metadata_invalid", self.gaps())

    def test_entrypoint_and_extra_support_changes_still_fail(self) -> None:
        self.fixture.skill.write_text("changed entrypoint")
        self.assertIn("local_skill_blob_mismatch", self.gaps())
        self.assertIn("local_skill_tree_mismatch", self.gaps())
        self.fixture.write(self.fixture.skill.parent / "references/unbound.md", "extra")
        self.assertIn("local_skill_tree_mismatch", self.gaps())

    def test_source_override_is_restricted_to_display_metadata(self) -> None:
        self.fixture.record["distribution_metadata"]["README.md"]["source"] = {
            "blob": "a" * 40, "mode": "100644"}
        self.fixture.save()
        self.assertIn("distribution_source_override_forbidden", self.gaps())

    def test_invalid_metadata_is_a_diagnostic_not_an_unhandled_error(self) -> None:
        for value in (None, [], 42, "invalid", {"README.md": []}, {"README.md": {}}):
            with self.subTest(value=value):
                self.fixture.record["distribution_metadata"] = value
                self.fixture.save()
                self.assertIn("distribution_metadata_invalid", self.gaps())

    def test_invalid_identity_shape_mode_and_digest_are_rejected(self) -> None:
        binding = copy.deepcopy(self.fixture.record["distribution_metadata"])
        for value in (None, [], {}, {"blob": "a" * 39, "mode": "100644"},
                      {"blob": "a" * 40, "mode": "100755"}, {"blob": 42, "mode": "100644"}):
            with self.subTest(value=value):
                self.fixture.record["distribution_metadata"] = copy.deepcopy(binding)
                self.fixture.record["distribution_metadata"]["README.md"]["installed"] = value
                self.fixture.save()
                self.assertIn("distribution_metadata_invalid", self.gaps())

    def test_packaging_requires_the_original_tree_digest(self) -> None:
        del self.fixture.record["source_tree_sha256"]
        self.fixture.save()
        self.assertIn("distribution_source_tree_required", self.gaps())


class CompleteAdkImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Static evidence captured from the exact provider Git tree, not a lock
        # generated from the currently installed consumer files during testing.
        cls.golden = json.loads((ROOT / "tests/fixtures/adk-skill-sources-7.0.31.json").read_text())
        cls.records = {r["name"]: r for r in json.loads((ROOT / "manifests/skills.json").read_text())["skills"]
                       if r["enabled"] and r["name"].startswith("adk-")}

    def test_all_42_sources_match_exact_upstream_files_and_modes(self) -> None:
        self.assertEqual(COMMIT, self.golden["provider_commit"])
        self.assertEqual(42, len(self.records))
        self.assertEqual(set(self.records), set(self.golden["skills"]))
        for name, record in self.records.items():
            expected = self.golden["skills"][name]
            with self.subTest(skill=name):
                directory = ROOT / "src/codex-home" / record["vendor_rel"]
                actual = _tree(directory)
                self.assertEqual("jiying2007/agent-dev-kit", record["source_repo"])
                self.assertEqual(COMMIT, record["source_ref"])
                self.assertEqual("v7.0.31", record["source_release"])
                self.assertEqual(expected["source_path"], record["source_path"])
                self.assertEqual(expected["tree"], _source_tree(record, actual))
                self.assertEqual(_digest(expected["tree"]), record["source_tree_sha256"])
                self.assertEqual(expected["tree"]["SKILL.md"]["blob"], record["source_blob"])
                self.assertEqual(expected["version"], record["version"])
                self.assertEqual(record["version"], parse_frontmatter(directory / "SKILL.md")["version"])
                self.assertEqual(expected["profiles"], record["profiles"])
                self.assertEqual(expected["target_rel"], record["target_rel"])
                self.assertEqual([record["version"]], sorted(p.name for p in directory.parent.iterdir()))

    def test_every_distribution_has_native_metadata_and_preserved_license(self) -> None:
        for name, record in self.records.items():
            expected = self.golden["skills"][name]
            directory = ROOT / "src/codex-home" / record["vendor_rel"]
            with self.subTest(skill=name):
                self.assertTrue((directory / "README.md").is_file())
                self.assertEqual(expected["installed_license_blob"], _tree(directory)["LICENSE"]["blob"])
                errors = []
                validate_openai_metadata(directory / "agents/openai.yaml", errors)
                self.assertEqual([], errors)
                original = expected["openai_source"]
                if original is not None:
                    native = yaml.safe_load((directory / "agents/openai.yaml").read_text())
                    self.assertEqual(original if "interface" in original else {"interface": original}, native)

    def test_remaining_sources_have_no_gaps_without_promoting_runtime_identity(self) -> None:
        report = audit(ROOT)
        self.assertEqual({}, report["gap_counts"])
        self.assertEqual("consistent", report["status"])
        self.assertEqual("7.0.4", report["provider_lock_version"])
        self.assertEqual(0, report["skills_matching_provider_lock_commit"])
        self.assertFalse(report["claims"]["runtime_qualified"])

    def test_moved_handoff_is_the_same_named_skill_not_a_guessed_replacement(self) -> None:
        record = self.records["adk-cross-team-handoff"]
        self.assertEqual("skills/adk-cross-team-handoff/SKILL.md", record["source_path"])
        self.assertEqual(["team-collab"], record["profiles"])

    def test_revised_natural_language_triggers_resolve_without_extra_profiles(self) -> None:
        cases = {"跨会话恢复": "adk-context-engineering", "编写驱动": "adk-driver-implementation",
                 "嵌入式发布编排": "adk-embedded-release-orchestration", "第三方引入": "adk-security-supply-chain"}
        with tempfile.TemporaryDirectory() as home:
            for query, name in cases.items():
                with self.subTest(query=query):
                    result = search_skills(Repo.from_path(ROOT), query, "team-collab", codex_home=home)
                    self.assertEqual(name, result["candidates"][0]["name"])


if __name__ == "__main__":
    unittest.main()
