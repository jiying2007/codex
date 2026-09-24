"""Exact first-batch source and disposable installation checks, not model qualification."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest

from tools.codex_assets.adk_skill_audit import _digest, _tree, audit
from tools.codex_assets.core import Repo, apply_plan, build_repo, diff_build_live, plan_apply, rollback_plan, validate_apply_plan
from tools.codex_assets.skill_catalog import search_skills
from tests import test_adk_skill_audit as audit_fixtures

ROOT = Path(__file__).resolve().parents[1]
SOURCE_COMMIT = "7367ef84787de75bb751940b32c9e80009660e47"
# Reviewed upstream identities from the #30 exact-source candidate, not local rehashes.
EXPECTED = {
    "adk-runtime-router": ("2.1.0", "9ba36768b91eb551136604462105a5b836b47119", "460073fcac9ec92763c20d32fde305862e2d6692d557c4d95900ca556d018cd3", 2, "技能路由"),
    "adk-code-review-loop": ("1.7.0", "8b536410b3cb0e656e2d032f071022c37a43b00c", "a9ae8c66af6b8bd1ad250d3dc208fe3082492feb682b028243d2ebf15818364a", 4, "独立代码审查"),
    "adk-verification-before-completion": ("1.7.0", "b5da2c7c73e817dbc38b160380c618ef51f7eac9", "9b8a3333309f2af29ac52af82cedf81a64f33ed50c8dac119b08dba94eca87ab", 2, "准备完成"),
}


class ImportedTreeDigestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = audit_fixtures.AdkSkillAuditTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def bind_support(self) -> Path:
        fixture = self.fixture
        support = fixture.skill.parent / "reference.md"
        fixture.write(support, "original")
        support.chmod(0o644)
        fixture.record["source_tree_sha256"] = audit(fixture.root)["skills"][0]["local_tree_sha256"]
        fixture.save()
        return support

    def test_support_content_tampering_is_reported(self) -> None:
        support = self.bind_support()
        self.assertEqual(audit(self.fixture.root)["status"], "consistent")
        support.write_text("tampered", encoding="utf-8")
        result = audit(self.fixture.root)
        self.assertIn("local_skill_tree_mismatch", result["gap_counts"])
        self.assertNotIn("local_skill_blob_mismatch", result["gap_counts"])

    def test_added_or_missing_support_is_reported(self) -> None:
        support = self.bind_support()
        support.unlink()
        self.assertIn("local_skill_tree_mismatch", audit(self.fixture.root)["gap_counts"])
        self.fixture.write(support, "original")
        self.fixture.write(support.parent / "extra.md", "unbound")
        self.assertIn("local_skill_tree_mismatch", audit(self.fixture.root)["gap_counts"])

    def test_support_execution_mode_drift_is_reported(self) -> None:
        self.bind_support().chmod(0o755)
        self.assertIn("local_skill_tree_mismatch", audit(self.fixture.root)["gap_counts"])

    def test_invalid_declared_tree_digest_is_not_ignored(self) -> None:
        for value in (None, "", "a" * 63, 123, []):
            self.fixture.record["source_tree_sha256"] = value
            self.fixture.save()
            with self.subTest(value=value):
                self.assertIn("invalid_source_tree_sha256", audit(self.fixture.root)["gap_counts"])


class DailyCoreImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.records = {item["name"]: item for item in json.loads((ROOT / "manifests/skills.json").read_text())["skills"]}

    def test_exact_source_and_whole_tree_identities(self) -> None:
        for name, (version, blob, digest, count, _) in EXPECTED.items():
            with self.subTest(skill=name):
                record = self.records[name]
                self.assertEqual(record["version"], version)
                self.assertEqual(record["source_repo"], "jiying2007/agent-dev-kit")
                self.assertEqual(record["source_ref"], SOURCE_COMMIT)
                self.assertEqual(record["source_release"], "v7.0.31")
                self.assertEqual(record["source_path"], f"skills/{name}/SKILL.md")
                self.assertEqual(record["source_blob"], blob)
                self.assertEqual(record["source_tree_sha256"], digest)
                tree = _tree(ROOT / "src/codex-home" / record["vendor_rel"])
                self.assertEqual(len(tree), count)
                self.assertEqual(tree["SKILL.md"]["blob"], blob)
                self.assertEqual(_digest(tree), digest)

    def test_declared_references_are_present_and_versions_match(self) -> None:
        for name, (version, _, _, _, _) in EXPECTED.items():
            directory = ROOT / "src/codex-home" / self.records[name]["vendor_rel"]
            text = (directory / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn(f"version: {version}\n", text)
            refs = re.findall(r"`(references/[^`]+\.md)`", text)
            self.assertTrue(refs, name)
            for ref in refs:
                self.assertTrue((directory / ref).is_file(), ref)

    def test_profiles_targets_and_active_source_are_not_expanded(self) -> None:
        for name, (version, _, _, _, _) in EXPECTED.items():
            record = self.records[name]
            self.assertIs(record["enabled"], True)
            self.assertEqual(record["profiles"], ["team-collab", "default"])
            self.assertEqual(record["target_rel"], f"skills/{name}")
            self.assertEqual(record["vendor_rel"], f"vendor/skills/{name}/{version}")
            self.assertEqual(record["owner"], "agent-dev-kit")
            parent = ROOT / "src/codex-home/vendor/skills" / name
            self.assertEqual(sorted(p.name for p in parent.iterdir()), [version])

    def test_default_catalog_resolves_new_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for name, (_, _, _, _, query) in EXPECTED.items():
                result = search_skills(Repo.from_path(ROOT), query, "default", codex_home=tmp)
                selected = result["candidates"][0]
                self.assertEqual(selected["name"], name)
                self.assertEqual(Path(selected["load_path"]), ROOT / "src/codex-home" / self.records[name]["vendor_rel"] / "SKILL.md")

    def test_audit_has_no_gaps_for_imported_skills_without_promoting_qualification(self) -> None:
        result = audit(ROOT)
        for row in result["skills"]:
            if row["name"] in EXPECTED:
                self.assertEqual(row["gaps"], [])
        for claim in ("release_verified", "installation_verified", "runtime_qualified"):
            self.assertIs(result["claims"][claim], False)

    def test_materializer_is_not_a_permanent_workflow(self) -> None:
        self.assertFalse((ROOT / ".github/workflows/adk-first-batch-materialize.yml").exists())

    def test_disposable_build_install_noop_and_rollback(self) -> None:
        for profile in ("default", "team-collab"):
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
                base = Path(tmp)
                repo = base / "source"
                # build_repo updates its derived lock: only a disposable source copy is writable.
                shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "build", "__pycache__", ".adk-upgrade-source"))
                target = base / "home/.codex"
                protected = {"auth.json": b"fixture-not-a-secret", "sessions/keep": b"private fixture", "skills/.system/keep": b"system fixture"}
                for path, data in protected.items():
                    file = target / path
                    file.parent.mkdir(parents=True, exist_ok=True)
                    file.write_bytes(data)
                build = build_repo(repo, profile, build_arg=str(base / "build"))
                plan = plan_apply(repo, build, target, base / "backup", overwrite=False, prune_stale=True)
                self.assertEqual(validate_apply_plan(plan), "ready")
                apply_plan(plan, dry_run=True)
                self.assertFalse((target / "skills/adk-runtime-router").exists())
                apply_plan(plan, dry_run=False)
                self.assertEqual(diff_build_live(build, target)[1:], (0, 0))
                for name, (_, _, digest, _, _) in EXPECTED.items():
                    installed = target / self.records[name]["target_rel"]
                    self.assertTrue(installed.is_symlink())
                    self.assertEqual(_digest(_tree(installed.resolve())), digest)
                again = plan_apply(repo, build, target, base / "backup-noop", overwrite=False, prune_stale=True)
                self.assertEqual(again["content_changes"], 0)
                plan_path = base / "plan.json"
                plan_path.write_text(json.dumps(plan), encoding="utf-8")
                rollback_plan(plan_path)
                self.assertFalse((target / "skills/adk-runtime-router").exists())
                for path, data in protected.items():
                    self.assertEqual((target / path).read_bytes(), data)


if __name__ == "__main__":
    unittest.main()
