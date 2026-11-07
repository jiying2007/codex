import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests import test_skill_catalog as fixtures
from tools.codex_assets.skill_catalog import search_skills
from tools.codex_assets.core import CodexAssetError


class ExplicitDiscoveryTest(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.SkillCatalogTest()
        self.repo = self.fixture.make_repo()
        self.addCleanup(self.fixture.doCleanups)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.team = Path(self.directory.name)

    def configure(self, names):
        (self.repo.manifests_dir / "skill_discovery.json").write_text(json.dumps({
            "schema_version": 1, "sources": [{"source_id": "team", "root_env": "TEST_SKILL_ROOT",
            "default_root": str(self.team), "skills_rel": ".agents/skills", "allowed_names": names}]}))

    def add_skill(self, name, description):
        p = self.team / ".agents/skills" / name / "SKILL.md"
        p.parent.mkdir(parents=True)
        p.write_text("---\nname: " + name + "\ndescription: " + description + "\n---\n")
        return p

    def test_team_resource_skill_is_discoverable_without_copy_or_activation(self):
        self.configure(["resource-leak-triage"])
        p = self.add_skill("resource-leak-triage", "检查内存泄漏和资源泄漏")
        with patch.dict("os.environ", {"TEST_SKILL_ROOT": str(self.team)}):
            result = search_skills(self.repo, "内存泄漏", "default")
        self.assertEqual("resource-leak-triage", result["candidates"][0]["name"])
        self.assertEqual(str(p), result["candidates"][0]["load_path"])
        self.assertEqual("team", result["candidates"][0]["source_id"])
        self.assertEqual("deferred", result["candidates"][0]["activation"])

    def test_same_name_keeps_managed_precedence_and_reports_alternative(self):
        self.configure(["embedded-log-triage"])
        self.add_skill("embedded-log-triage", "嵌入式日志异常")
        result = search_skills(self.repo, "嵌入式日志异常", "default")
        self.assertEqual("managed", result["candidates"][0]["source_id"])
        self.assertIn("embedded-log-triage", result["discovery"]["shadowed_names"])

    def test_duplicate_external_names_do_not_consume_result_slots(self):
        self.configure(["resource-leak-triage", "resource-leak-triage"])
        self.add_skill("resource-leak-triage", "内存泄漏")
        result = search_skills(self.repo, "内存泄漏", "default")
        self.assertEqual(1, result["total_matches"])

    def test_escaping_symlink_is_rejected_and_unregistered_files_not_scanned(self):
        self.configure(["resource-leak-triage"])
        p = self.add_skill("resource-leak-triage", "内存泄漏")
        target = self.team.parent / (self.team.name + "-outside.md")
        target.write_text(p.read_text())
        self.addCleanup(target.unlink)
        p.unlink()
        p.symlink_to(target)
        with self.assertRaises(CodexAssetError):
            search_skills(self.repo, "内存泄漏", "default")


if __name__ == "__main__":
    unittest.main()
