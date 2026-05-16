from __future__ import annotations

import json
import pathlib
import shutil
import tempfile
import unittest

from tools.codex_assets.governance import governance_report
from tools.codex_assets.validate import validate_repo


def write_json(path: pathlib.Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def make_repo(test_case: unittest.TestCase) -> pathlib.Path:
    root = pathlib.Path(tempfile.mkdtemp(prefix="codex-governance-test-"))
    test_case.addCleanup(shutil.rmtree, root)
    source = root / "src/codex-home"
    (source / "AGENTS.md").parent.mkdir(parents=True, exist_ok=True)
    (source / "AGENTS.md").write_text("# Agent Rules\n")
    for path in [
        "vendor/skills/session-wrap/1.0.0/SKILL.md",
        "vendor/skills/memory-curator/1.0.0/SKILL.md",
        "control/agents-local/local-context-curator.toml",
    ]:
        file_path = source / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("name = test\n")
    write_json(
        root / "manifests/assets.json",
        {
            "schema_version": 2,
            "source_root": "src/codex-home",
            "build_root": "build/codex-home",
            "default_profile": "team-collab",
            "copy_roots": ["AGENTS.md"],
        },
    )
    write_json(
        root / "manifests/policies.json",
        {
            "schema_version": 2,
            "protected_paths": ["skills/.system/**", "auth.json", "sessions/**", "mcp/secrets/**"],
            "skip_source_paths": [".git/**"],
            "allowed_live_drift_paths": ["config.toml"],
        },
    )
    write_json(
        root / "manifests/profiles.json",
        {
            "schema_version": 2,
            "profiles": [
                {"name": "solo-dev", "description": "个人开发"},
                {"name": "team-collab", "description": "团队协作"},
            ],
        },
    )
    write_json(
        root / "manifests/skills.json",
        {
            "schema_version": 2,
            "skills": [
                {
                    "name": "session-wrap",
                    "enabled": True,
                    "version": "1.0.0",
                    "vendor_rel": "vendor/skills/session-wrap/1.0.0",
                    "target_rel": "skills/session-wrap",
                    "profiles": ["team-collab"],
                },
                {
                    "name": "memory-curator",
                    "enabled": True,
                    "version": "1.0.0",
                    "vendor_rel": "vendor/skills/memory-curator/1.0.0",
                    "target_rel": "skills/memory-curator",
                    "profiles": ["team-collab"],
                },
            ],
        },
    )
    write_json(
        root / "manifests/agents.json",
        {
            "schema_version": 2,
            "agents": [
                {
                    "name": "local-context-curator",
                    "enabled": True,
                    "version": "1.0.0",
                    "vendor_rel": "control/agents-local/local-context-curator.toml",
                    "target_rel": "agents/local-context-curator.toml",
                    "profiles": ["team-collab"],
                }
            ],
        },
    )
    write_json(
        root / "manifests/workflows.json",
        {
            "schema_version": 1,
            "workflows": [
                {
                    "name": "context-handoff",
                    "enabled": True,
                    "profiles": ["team-collab"],
                    "triggers": ["会话接力"],
                    "skills": ["session-wrap", "memory-curator"],
                    "agents": ["local-context-curator"],
                    "commands": ["rtk bash scripts/context-preflight.sh"],
                    "verification": ["rtk bash scripts/check-skills.sh"],
                }
            ],
        },
    )
    write_json(
        root / "manifests/project-templates.json",
        {
            "schema_version": 1,
            "project_templates": [
                {
                    "name": "asset-repo",
                    "path_patterns": ["*/codex"],
                    "default_profile": "team-collab",
                    "workflows": ["context-handoff"],
                    "archive_topics": ["session-wrap"],
                }
            ],
        },
    )
    write_json(
        root / "manifests/overlays.json",
        {
            "schema_version": 1,
            "overlays": [
                {
                    "name": "personal-local",
                    "allowed_live_drift_paths": ["config.toml"],
                    "blocked_paths": ["auth.json", "sessions/**"],
                }
            ],
        },
    )
    return root


class GovernanceValidationTest(unittest.TestCase):
    def test_valid_governance_manifests_pass(self) -> None:
        root = make_repo(self)
        self.assertEqual([], validate_repo(root))

    def test_workflow_rejects_unknown_skill(self) -> None:
        root = make_repo(self)
        manifest = json.loads((root / "manifests/workflows.json").read_text())
        manifest["workflows"][0]["skills"].append("missing-skill")
        write_json(root / "manifests/workflows.json", manifest)
        errors = validate_repo(root)
        self.assertIn("workflows:context-handoff 引用未知 skill: missing-skill", errors)

    def test_project_template_rejects_unknown_workflow(self) -> None:
        root = make_repo(self)
        manifest = json.loads((root / "manifests/project-templates.json").read_text())
        manifest["project_templates"][0]["workflows"].append("missing-workflow")
        write_json(root / "manifests/project-templates.json", manifest)
        errors = validate_repo(root)
        self.assertIn("project-templates:asset-repo 引用未知 workflow: missing-workflow", errors)

    def test_overlay_rejects_allowed_protected_path(self) -> None:
        root = make_repo(self)
        manifest = json.loads((root / "manifests/overlays.json").read_text())
        manifest["overlays"][0]["allowed_live_drift_paths"].append("auth.json")
        write_json(root / "manifests/overlays.json", manifest)
        errors = validate_repo(root)
        self.assertIn("overlays:personal-local allowed_live_drift_paths 不能包含 protected path: auth.json", errors)

    def test_governance_report_summarizes_links(self) -> None:
        root = make_repo(self)
        report = governance_report(root)
        self.assertEqual("team-collab", report["default_profile"])
        self.assertEqual(["context-handoff"], report["workflows"])
        self.assertEqual(["asset-repo"], report["project_templates"])
        self.assertEqual(["personal-local"], report["overlays"])


if __name__ == "__main__":
    unittest.main()
