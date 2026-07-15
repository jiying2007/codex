from __future__ import annotations

import json
import pathlib
import shutil
import tempfile
import unittest

from tools.codex_assets.core import Repo
from tools.codex_assets.skill_catalog import (
    catalog_metrics,
    search_skills,
    validate_context_budgets,
)


def write_json(path: pathlib.Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def write_skill(path: pathlib.Path, name: str, description: str, triggers: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    trigger_lines = "\n".join(f"  - {trigger}" for trigger in triggers)
    path.write_text(
        f"---\nname: {name}\ndescription: {description}\ntriggers:\n{trigger_lines}\n---\n\n# {name}\n"
    )


class SkillCatalogTest(unittest.TestCase):
    def make_repo(self, long_description: bool = False) -> Repo:
        root = pathlib.Path(tempfile.mkdtemp(prefix="codex-skill-catalog-test-"))
        self.addCleanup(shutil.rmtree, root)
        write_json(
            root / "manifests/assets.json",
            {
                "schema_version": 2,
                "source_root": "src/codex-home",
                "build_root": "build/codex-home",
                "default_profile": "token-lean",
                "copy_roots": [],
            },
        )
        write_json(
            root / "manifests/profiles.json",
            {
                "schema_version": 2,
                "context_budget": {
                    "agents_max_bytes": 1000,
                    "default_profile_max_active_skills": 1,
                    "default_profile_max_catalog_bytes": 2000,
                    "skill_search_max_output_bytes": 4096,
                },
                "profiles": [
                    {"name": "token-lean"},
                    {"name": "team-collab"},
                    {"name": "superpowers-compat"},
                ],
            },
        )
        description = "嵌入式串口、boot、dmesg 与设备日志异常分析" + ("日志证据" * 300 if long_description else "")
        skills = [
            {
                "name": "adk-runtime-router",
                "enabled": True,
                "version": "1.0.0",
                "vendor_rel": "vendor/skills/adk-runtime-router/1.0.0",
                "target_rel": "skills/adk-runtime-router",
                "profiles": ["token-lean", "team-collab"],
                "tags": ["adk", "routing"],
            },
            {
                "name": "embedded-log-triage",
                "enabled": True,
                "version": "0.1.0",
                "vendor_rel": "vendor/skills/embedded-log-triage/0.1.0",
                "target_rel": "skills/embedded-log-triage",
                "profiles": ["team-collab"],
                "tags": ["embedded", "logs"],
            },
            {
                "name": "adk-embedded-remote-debug-log-triage",
                "enabled": True,
                "version": "1.0.0",
                "vendor_rel": "vendor/skills/adk-embedded-remote-debug-log-triage/1.0.0",
                "target_rel": "skills/adk-embedded-remote-debug-log-triage",
                "profiles": ["team-collab"],
                "tags": ["adk", "embedded", "logs"],
            },
            {
                "name": "writing-plans",
                "enabled": True,
                "version": "1.0.0",
                "vendor_rel": "vendor/plugins/superpowers/1.0.0/skills/writing-plans",
                "target_rel": "skills/writing-plans",
                "profiles": ["superpowers-compat"],
                "tags": ["superpowers"],
            },
            {
                "name": "skill-asset-manager",
                "enabled": True,
                "version": "0.2.0",
                "vendor_rel": "vendor/skills/skill-asset-manager/0.2.0",
                "target_rel": "skills/skill-asset-manager",
                "profiles": ["team-collab"],
                "tags": ["local", "asset-management"],
            },
        ]
        write_json(root / "manifests/skills.json", {"schema_version": 2, "skills": skills})
        write_json(
            root / "manifests/workflows.json",
            {
                "schema_version": 1,
                "workflows": [
                    {
                        "name": "embedded-diagnostic-validation",
                        "routes": [
                            {
                                "name": "device-remote-log-triage",
                                "match_any": ["SSH 设备日志", "现场日志"],
                                "exclude_any": ["仅分析日志文本"],
                                "primary_skill": "adk-embedded-remote-debug-log-triage",
                                "supporting_skills": [],
                                "fallback_skill": "",
                                "mutually_exclusive_skills": ["embedded-log-triage"],
                            },
                            {
                                "name": "offline-pasted-log-triage",
                                "match_any": ["粘贴串口日志", "仅分析日志文本"],
                                "exclude_any": ["SSH"],
                                "primary_skill": "embedded-log-triage",
                                "supporting_skills": [],
                                "fallback_skill": "adk-embedded-remote-debug-log-triage",
                                "mutually_exclusive_skills": [],
                            },
                        ],
                    },
                    {
                        "name": "asset-governance",
                        "routes": [
                            {
                                "name": "skill-asset-lifecycle",
                                "match_any": ["skill 资产", "技能资产"],
                                "exclude_any": ["技能组合"],
                                "primary_skill": "skill-asset-manager",
                                "supporting_skills": [],
                                "fallback_skill": "",
                                "mutually_exclusive_skills": [],
                            }
                        ],
                    },
                ],
            },
        )
        source = root / "src/codex-home"
        write_skill(
            source / "vendor/skills/adk-runtime-router/1.0.0/SKILL.md",
            "adk-runtime-router",
            "adk-first 运行时技能路由入口",
            ["技能路由"],
        )
        write_skill(
            source / "vendor/skills/embedded-log-triage/0.1.0/SKILL.md",
            "embedded-log-triage",
            description,
            ["嵌入式日志异常", "分析串口日志"],
        )
        write_skill(
            source / "vendor/skills/adk-embedded-remote-debug-log-triage/1.0.0/SKILL.md",
            "adk-embedded-remote-debug-log-triage",
            "设备端远程日志、SSH、ADB 与现场日志取证",
            ["远程日志", "现场日志"],
        )
        write_skill(
            source / "vendor/plugins/superpowers/1.0.0/skills/writing-plans/SKILL.md",
            "writing-plans",
            "Write an implementation plan",
            ["writing plans"],
        )
        write_skill(
            source / "vendor/skills/skill-asset-manager/0.2.0/SKILL.md",
            "skill-asset-manager",
            "Codex skill asset governance, version promotion, manifest update and rollback",
            ["技能资产治理", "版本提升"],
        )
        (root / "AGENTS.md").write_text("# rules\n")
        (source / "AGENTS.md").write_text("# rules\n")
        return Repo.from_path(root)

    def test_deferred_skill_is_discovered_without_fallback_catalog(self) -> None:
        repo = self.make_repo()
        payload = search_skills(repo, "请分析嵌入式日志异常", "token-lean", codex_home=repo.root / "live")
        self.assertEqual("embedded-log-triage", payload["candidates"][0]["name"])
        self.assertEqual("deferred", payload["candidates"][0]["activation"])
        self.assertFalse(payload["candidates"][0]["fallback"])

    def test_superpowers_fallback_requires_explicit_flag(self) -> None:
        repo = self.make_repo()
        hidden = search_skills(repo, "writing plans", "token-lean")
        shown = search_skills(repo, "writing plans", "token-lean", include_fallback=True)
        self.assertEqual("zero-hit", hidden["status"])
        self.assertEqual(1, hidden["fallback_candidates_excluded"])
        self.assertEqual("writing-plans", shown["candidates"][0]["name"])

    def test_workflow_route_selects_skill_asset_manager(self) -> None:
        repo = self.make_repo()
        payload = search_skills(repo, "skill 资产版本治理", "token-lean")
        candidate = payload["candidates"][0]
        self.assertEqual("skill-asset-manager", candidate["name"])
        self.assertEqual("skill-asset-lifecycle", candidate["route"]["name"])

    def test_workflow_route_boosts_remote_log_primary(self) -> None:
        repo = self.make_repo()
        payload = search_skills(repo, "通过 SSH 设备日志排查现场日志", "token-lean")
        candidate = payload["candidates"][0]
        self.assertEqual("adk-embedded-remote-debug-log-triage", candidate["name"])
        self.assertEqual("primary", candidate["route"]["role"])

    def test_workflow_route_boosts_offline_log_primary(self) -> None:
        repo = self.make_repo()
        payload = search_skills(repo, "仅分析日志文本：这是粘贴串口日志", "token-lean")
        candidate = payload["candidates"][0]
        self.assertEqual("embedded-log-triage", candidate["name"])
        self.assertEqual("offline-pasted-log-triage", candidate["route"]["name"])

    def test_catalog_and_summary_obey_budgets(self) -> None:
        repo = self.make_repo(long_description=True)
        metrics = catalog_metrics(repo, "token-lean")
        payload = search_skills(repo, "嵌入式日志异常", "token-lean", limit=20, max_output_bytes=4096)
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.assertEqual(1, metrics["active_count"])
        self.assertLessEqual(len(encoded), 4096)
        self.assertEqual([], validate_context_budgets(repo))

    def test_agents_budget_detects_drift(self) -> None:
        repo = self.make_repo()
        (repo.root / "AGENTS.md").write_text("x" * 1001)
        errors = validate_context_budgets(repo)
        self.assertTrue(any("AGENTS 超出预算" in error for error in errors))
        self.assertTrue(any("AGENTS 与" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
