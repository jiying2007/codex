from __future__ import annotations

import json
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_manifest(name: str) -> dict:
    return json.loads((ROOT / "manifests" / name).read_text(encoding="utf-8"))


def active_count(items: list[dict], profile: str) -> int:
    return sum(
        1
        for item in items
        if item.get("enabled", True) and profile in item.get("profiles", [])
    )


class ProfileDocumentationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.readme = (ROOT / "README.md").read_text(encoding="utf-8")
        start = cls.readme.index("## Profile 选择与切换")
        end = cls.readme.index("\n## 目录职责", start)
        cls.section = cls.readme[start:end]

    def test_profile_table_matches_manifests(self) -> None:
        profiles = load_manifest("profiles.json")["profiles"]
        skills = load_manifest("skills.json")["skills"]
        agents = load_manifest("agents.json")["agents"]
        workflows = load_manifest("workflows.json")["workflows"]

        for profile_item in profiles:
            profile = profile_item["name"]
            expected = (
                rf"\| `{re.escape(profile)}` \| "
                rf"{active_count(skills, profile)} \| "
                rf"{active_count(agents, profile)} \| "
                rf"{active_count(workflows, profile)} \|"
            )
            self.assertRegex(self.section, expected, profile)

    def test_switch_contract_is_documented(self) -> None:
        required = [
            "scripts/doctor.sh --scope live",
            "--profile team-collab",
            "--prune-stale",
            "--plan-out build/apply-plan.switch.json",
            "scripts/apply.sh --plan build/apply-plan.switch.json --dry-run",
            "scripts/rollback.sh --plan build/apply-plan.switch.json --dry-run",
            "新开 Codex 线程",
        ]
        for text in required:
            self.assertIn(text, self.section)

    def test_build_only_boundary_and_default_profile_are_documented(self) -> None:
        default_profile = load_manifest("assets.json")["default_profile"]
        self.assertIn(f"当前默认 profile 是 `{default_profile}`", self.section)
        self.assertIn("只更新 `build/codex-home`，不会切换 `~/.codex`", self.section)

    def test_live_skill_readme_has_quick_switch_contract(self) -> None:
        readme = (ROOT / "src/codex-home/skills/README.md").read_text(encoding="utf-8")
        self.assertIn("## Profile 切换", readme)
        self.assertIn("--profile team-collab", readme)
        self.assertIn("--prune-stale", readme)
        self.assertIn("--plan ~/codex/build/apply-plan.json --dry-run", readme)

    def test_skill_registry_versions_match_manifest(self) -> None:
        manifest_versions = {
            item["name"]: item["version"]
            for item in load_manifest("skills.json")["skills"]
        }
        registry = ROOT / "src/codex-home/skills/registry.csv"
        rows = [
            line.split(",")
            for line in registry.read_text(encoding="utf-8").splitlines()[1:]
            if line.strip()
        ]

        for name, version, _status, _source in rows:
            self.assertIn(name, manifest_versions)
            self.assertEqual(manifest_versions[name], version, name)

    def test_asset_manual_reuses_the_reviewed_plan(self) -> None:
        manual = (ROOT / "docs/codex-asset-management.md").read_text(encoding="utf-8")
        self.assertIn("--prune-stale --output build/apply-plan.json", manual)
        self.assertIn("--plan build/apply-plan.json --dry-run", manual)
        self.assertIn("--plan build/apply-plan.json`", manual)


if __name__ == "__main__":
    unittest.main()
