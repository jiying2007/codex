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
    write_json(
        root / "manifests/session_coach.json",
        {
            "schema_version": 1,
            "defaults": {"top": 3},
            "events": {},
        },
    )
    return root


def write_optional_controls(root: pathlib.Path) -> None:
    write_json(
        root / "manifests/workflow_recipes.json",
        {
            "schema_version": 1,
            "workflow_recipes": [
                {
                    "name": "context-handoff-recipe",
                    "enabled": True,
                    "profiles": ["team-collab"],
                    "workflow": "context-handoff",
                    "context_inputs": ["thread role", "goal"],
                    "done_criteria": ["handoff artifact exists"],
                    "review_artifacts": ["preflight note"],
                    "failure_modes": ["missing verification"],
                    "trigger_examples": ["请生成会话接力模板"],
                    "negative_examples": ["只修一个 Python 单元测试"],
                    "verification": ["rtk bash scripts/context-preflight.sh"],
                }
            ],
        },
    )
    write_json(
        root / "manifests/automations.json",
        {
            "schema_version": 1,
            "automations": [
                {
                    "name": "health-report",
                    "enabled": False,
                    "mode": "report-only",
                    "type": "scheduled",
                    "profiles": ["team-collab"],
                    "workflow": "context-handoff",
                    "cadence": "daily",
                    "scope": {"data_sources": ["local manifests"]},
                    "sandbox": "read-only",
                    "approval_policy": "manual",
                    "worktree_policy": "read-current-only",
                    "first_run_review": True,
                    "risk_class": "read-only",
                    "requires_worktree_for_write": False,
                    "stop_condition": "after report",
                    "triage_contract": {
                        "destination": "test summary",
                        "allowed_outputs": ["summary"],
                        "forbidden_actions": ["commit"],
                    },
                    "run_lifecycle": {
                        "first_run": "manual review",
                        "steady_state": "report and stop",
                        "stale_after": "one day",
                        "retry_budget": 1,
                        "cleanup": ["discard transient logs"],
                        "retention": "summary only",
                    },
                    "output_artifacts": ["summary"],
                }
            ],
        },
    )
    write_json(
        root / "manifests/mcp_servers.json",
        {
            "schema_version": 2,
            "mcp_servers": [
                {
                    "name": "docs",
                    "enabled": False,
                    "transport": "stdio",
                    "profiles": ["team-collab"],
                    "command": "npx",
                    "args": ["-y", "@openai/docs-mcp"],
                    "required": False,
                    "supports_parallel_tool_calls": True,
                    "env": {"OPENAI_API_KEY": ""},
                    "owner": "local",
                    "purpose": "official docs lookup",
                    "security_status": "declared-disabled",
                    "rollback": "disable and rebuild",
                    "readiness": {
                        "scopes": ["docs lookup"],
                        "network_targets": ["developers.openai.com"],
                        "tool_inventory": ["pending-inspector"],
                        "write_actions": [],
                        "destructive_actions": [],
                        "requires_human_confirmation": True,
                        "deny_path_tests": [
                            {"name": "reject-auth", "path": "auth.json", "expected_decision": "deny"}
                        ],
                        "log_redaction": True,
                        "smoke": "rtk codex mcp list",
                    },
                }
            ],
        },
    )


def write_p2_controls(root: pathlib.Path) -> None:
    write_json(
        root / "manifests/subagent_contracts.json",
        {
            "schema_version": 1,
            "subagent_contracts": [
                {
                    "name": "context-curator-readonly",
                    "enabled": True,
                    "profiles": ["team-collab"],
                    "agent": "local-context-curator",
                    "scope_read": ["docs/**", "manifests/**"],
                    "scope_write": [],
                    "must_not_touch": ["auth.json", "sessions/**"],
                    "output_contract": ["summary", "next actions"],
                    "sandbox": "read-only",
                    "max_parallel": 1,
                    "verification": ["rtk bash scripts/doctor.sh --scope governance"],
                }
            ],
        },
    )
    write_json(
        root / "manifests/memory_candidates.json",
        {
            "schema_version": 1,
            "memory_candidates": [
                {
                    "name": "candidate-rule",
                    "enabled": False,
                    "status": "candidate",
                    "source": "docs/example.md",
                    "proposed_action": "promote-to-archive",
                    "review_required": True,
                    "secret_scan_required": True,
                    "promotion_gate": "reviewed and scanned",
                    "summary": "test candidate",
                }
            ],
        },
    )


def write_p3_p4_controls(root: pathlib.Path) -> None:
    write_json(
        root / "tests/fixtures/routing_eval/workflow_cases.json",
        {"cases": [{"name": "case", "prompt": "请生成会话接力模板", "expected_recipe": "context-handoff-recipe"}]},
    )
    write_json(
        root / "manifests/eval_suites.json",
        {
            "schema_version": 1,
            "eval_suites": [
                {
                    "name": "routing-eval",
                    "enabled": True,
                    "profiles": ["team-collab"],
                    "kind": "routing",
                    "owner": "test",
                    "cases_path": "tests/fixtures/routing_eval/workflow_cases.json",
                    "success_metric": "all cases pass",
                    "min_pass_rate": 1.0,
                    "negative_cases_required": True,
                    "commands": ["rtk python3 -m unittest tests.test_agent_routing_eval"],
                    "artifacts": ["routing fixture"],
                    "promotion_gate": "examples reviewed",
                }
            ],
        },
    )
    write_json(
        root / "manifests/cli_command_contracts.json",
        {
            "schema_version": 1,
            "cli_command_contracts": [
                {
                    "name": "goal-command",
                    "enabled": True,
                    "profiles": ["team-collab"],
                    "command": "/goal",
                    "purpose": "strong goal",
                    "input_contract": ["goal"],
                    "allowed_actions": ["plan"],
                    "forbidden_actions": ["bypass-verification"],
                    "output_contract": ["evidence"],
                    "review_required": True,
                    "verification": ["rtk bash scripts/final-ready.sh"],
                }
            ],
        },
    )
    write_json(
        root / "manifests/guidance_promotions.json",
        {
            "schema_version": 1,
            "guidance_promotions": [
                {
                    "name": "docs-to-agents",
                    "enabled": True,
                    "source_kind": "external-docs",
                    "source_patterns": ["docs/**"],
                    "destination": "agents",
                    "review_required": True,
                    "secret_scan_required": True,
                    "min_evidence": ["source", "verification"],
                    "verification": ["rtk bash scripts/check.sh"],
                    "rollback": "remove promoted rule",
                }
            ],
        },
    )
    write_json(
        root / "manifests/goal_templates.json",
        {
            "schema_version": 1,
            "goal_templates": [
                {
                    "name": "handoff-strong-goal",
                    "enabled": True,
                    "profiles": ["team-collab"],
                    "workflow": "context-handoff",
                    "goal_strength": "strong",
                    "required_fields": [
                        "goal",
                        "scope",
                        "success_criteria",
                        "verification_commands",
                        "review_artifacts",
                    ],
                    "verification_contract": ["rtk bash scripts/context-preflight.sh"],
                    "artifact_contract": ["preflight note"],
                    "stop_conditions": ["pass", "blocked"],
                    "negative_examples": ["no verification"],
                }
            ],
        },
    )


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

    def test_optional_openai_developer_controls_pass_and_report(self) -> None:
        root = make_repo(self)
        write_optional_controls(root)

        self.assertEqual([], validate_repo(root))
        report = governance_report(root)
        self.assertEqual(["context-handoff-recipe"], report["workflow_recipes"])
        self.assertEqual(["health-report"], report["automations"])
        self.assertEqual(["docs"], report["mcp_servers"])
        self.assertEqual("context-handoff", report["workflow_recipe_links"]["context-handoff-recipe"]["workflow"])
        self.assertEqual("report-only", report["automation_links"]["health-report"]["mode"])

    def test_workflow_recipe_rejects_unknown_workflow(self) -> None:
        root = make_repo(self)
        write_optional_controls(root)
        manifest = json.loads((root / "manifests/workflow_recipes.json").read_text())
        manifest["workflow_recipes"][0]["workflow"] = "missing-workflow"
        write_json(root / "manifests/workflow_recipes.json", manifest)

        errors = validate_repo(root)
        self.assertIn("workflow_recipes:context-handoff-recipe 引用未知 workflow: missing-workflow", errors)

    def test_automation_rejects_unsafe_policy(self) -> None:
        root = make_repo(self)
        write_optional_controls(root)
        manifest = json.loads((root / "manifests/automations.json").read_text())
        manifest["automations"][0]["approval_policy"] = "never"
        manifest["automations"][0]["sandbox"] = "danger-full-access"
        manifest["automations"][0]["first_run_review"] = False
        write_json(root / "manifests/automations.json", manifest)

        errors = validate_repo(root)
        self.assertIn("automations:health-report approval_policy 不允许 never", errors)
        self.assertIn("automations:health-report sandbox 非法或过宽: danger-full-access", errors)
        self.assertIn("automations:health-report first_run_review 必须为 true", errors)

    def test_mcp_rejects_secret_env_and_missing_confirmation(self) -> None:
        root = make_repo(self)
        write_optional_controls(root)
        manifest = json.loads((root / "manifests/mcp_servers.json").read_text())
        server = manifest["mcp_servers"][0]
        server["env"]["OPENAI_API_KEY"] = "secret"
        server["readiness"]["write_actions"] = ["remote_write"]
        server["readiness"]["requires_human_confirmation"] = False
        write_json(root / "manifests/mcp_servers.json", manifest)

        errors = validate_repo(root)
        self.assertIn("mcp_servers:docs env 不得在 manifest 中写入非空值: OPENAI_API_KEY", errors)
        self.assertIn("mcp_servers:docs 写入或破坏性动作必须 requires_human_confirmation=true", errors)

    def test_p2_controls_pass_and_report(self) -> None:
        root = make_repo(self)
        write_p2_controls(root)

        self.assertEqual([], validate_repo(root))
        report = governance_report(root)
        self.assertEqual(["context-curator-readonly"], report["subagent_contracts"])
        self.assertEqual(["candidate-rule"], report["memory_candidates"])
        self.assertEqual(
            "local-context-curator",
            report["subagent_contract_links"]["context-curator-readonly"]["agent"],
        )
        self.assertEqual(
            "promote-to-archive",
            report["memory_candidate_links"]["candidate-rule"]["proposed_action"],
        )

    def test_subagent_contract_rejects_unknown_agent(self) -> None:
        root = make_repo(self)
        write_p2_controls(root)
        manifest = json.loads((root / "manifests/subagent_contracts.json").read_text())
        manifest["subagent_contracts"][0]["agent"] = "missing-agent"
        write_json(root / "manifests/subagent_contracts.json", manifest)

        errors = validate_repo(root)
        self.assertIn("subagent_contracts:context-curator-readonly 引用未知 agent: missing-agent", errors)

    def test_memory_candidate_rejects_enabled_candidate(self) -> None:
        root = make_repo(self)
        write_p2_controls(root)
        manifest = json.loads((root / "manifests/memory_candidates.json").read_text())
        manifest["memory_candidates"][0]["enabled"] = True
        write_json(root / "manifests/memory_candidates.json", manifest)

        errors = validate_repo(root)
        self.assertIn("memory_candidates:candidate-rule 候选不得 enabled=true", errors)

    def test_remote_mcp_requires_https_url_and_declared_host(self) -> None:
        root = make_repo(self)
        write_optional_controls(root)
        manifest = json.loads((root / "manifests/mcp_servers.json").read_text())
        server = manifest["mcp_servers"][0]
        server["name"] = "openaiDeveloperDocs"
        server["transport"] = "http"
        server.pop("command")
        server.pop("args")
        server["url"] = "http://example.com/mcp"
        server["env"] = {}
        server["readiness"]["network_targets"] = ["developers.openai.com"]
        write_json(root / "manifests/mcp_servers.json", manifest)

        errors = validate_repo(root)
        self.assertIn("mcp_servers:openaiDeveloperDocs http url 必须是 https URL", errors)

    def test_automation_rejects_write_risk_without_worktree(self) -> None:
        root = make_repo(self)
        write_optional_controls(root)
        manifest = json.loads((root / "manifests/automations.json").read_text())
        manifest["automations"][0]["risk_class"] = "draft-write"
        manifest["automations"][0]["requires_worktree_for_write"] = False
        write_json(root / "manifests/automations.json", manifest)

        errors = validate_repo(root)
        self.assertIn("automations:health-report 写入类风险必须 requires_worktree_for_write=true", errors)

    def test_p3_p4_controls_pass_and_report(self) -> None:
        root = make_repo(self)
        write_optional_controls(root)
        write_p3_p4_controls(root)

        self.assertEqual([], validate_repo(root))
        report = governance_report(root)
        self.assertEqual(["routing-eval"], report["eval_suites"])
        self.assertEqual(["goal-command"], report["cli_command_contracts"])
        self.assertEqual(["docs-to-agents"], report["guidance_promotions"])
        self.assertEqual(["handoff-strong-goal"], report["goal_templates"])
        self.assertEqual("routing", report["eval_suite_links"]["routing-eval"]["kind"])
        self.assertEqual("/goal", report["cli_command_contract_links"]["goal-command"]["command"])
        self.assertEqual("agents", report["guidance_promotion_links"]["docs-to-agents"]["destination"])
        self.assertEqual("context-handoff", report["goal_template_links"]["handoff-strong-goal"]["workflow"])

    def test_eval_suite_rejects_missing_cases_path(self) -> None:
        root = make_repo(self)
        write_p3_p4_controls(root)
        manifest = json.loads((root / "manifests/eval_suites.json").read_text())
        manifest["eval_suites"][0]["cases_path"] = "tests/missing.json"
        write_json(root / "manifests/eval_suites.json", manifest)

        errors = validate_repo(root)
        self.assertIn("eval_suites:routing-eval cases_path 不存在: tests/missing.json", errors)

    def test_cli_command_contract_requires_slash_and_verification_denial(self) -> None:
        root = make_repo(self)
        write_p3_p4_controls(root)
        manifest = json.loads((root / "manifests/cli_command_contracts.json").read_text())
        contract = manifest["cli_command_contracts"][0]
        contract["command"] = "goal"
        contract["forbidden_actions"] = ["skip-review"]
        write_json(root / "manifests/cli_command_contracts.json", manifest)

        errors = validate_repo(root)
        self.assertIn("cli_command_contracts:goal-command command 必须以 / 开头", errors)
        self.assertIn("cli_command_contracts:goal-command forbidden_actions 必须包含 bypass-verification", errors)

    def test_guidance_promotion_requires_review_and_secret_scan(self) -> None:
        root = make_repo(self)
        write_p3_p4_controls(root)
        manifest = json.loads((root / "manifests/guidance_promotions.json").read_text())
        promotion = manifest["guidance_promotions"][0]
        promotion["review_required"] = False
        promotion["secret_scan_required"] = False
        write_json(root / "manifests/guidance_promotions.json", manifest)

        errors = validate_repo(root)
        self.assertIn("guidance_promotions:docs-to-agents review_required 必须为 true", errors)
        self.assertIn("guidance_promotions:docs-to-agents secret_scan_required 必须为 true", errors)

    def test_goal_template_requires_core_goal_fields(self) -> None:
        root = make_repo(self)
        write_p3_p4_controls(root)
        manifest = json.loads((root / "manifests/goal_templates.json").read_text())
        manifest["goal_templates"][0]["required_fields"] = ["goal"]
        write_json(root / "manifests/goal_templates.json", manifest)

        errors = validate_repo(root)
        self.assertIn(
            "goal_templates:handoff-strong-goal required_fields 缺少: review_artifacts, scope, success_criteria, verification_commands",
            errors,
        )

    def test_automation_requires_run_lifecycle(self) -> None:
        root = make_repo(self)
        write_optional_controls(root)
        manifest = json.loads((root / "manifests/automations.json").read_text())
        del manifest["automations"][0]["run_lifecycle"]
        write_json(root / "manifests/automations.json", manifest)

        errors = validate_repo(root)
        self.assertIn("automations:health-report 缺少字段 run_lifecycle", errors)


if __name__ == "__main__":
    unittest.main()
