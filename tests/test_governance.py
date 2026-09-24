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
    # Reuse the real fixed source contract; do not create a legacy wheel fixture.
    repository = pathlib.Path(__file__).resolve().parents[1]
    for relative in (
        "manifests/execution_policy.json",
        "manifests/provider-locks/agent-dev-kit.json",
        "tools/codex_assets/execution_policy/engine.py",
        "tools/codex_assets/execution_policy/contracts.py",
    ):
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(repository / relative, destination)
    return root


def add_valid_workflow_route(root: pathlib.Path) -> dict:
    manifest = json.loads((root / "manifests/workflows.json").read_text())
    route = {
        "name": "session-closeout",
        "match_any": ["总结本次会话"],
        "exclude_any": ["整理长期记忆"],
        "primary_skill": "session-wrap",
        "supporting_skills": ["memory-curator"],
        "fallback_skill": "",
        "mutually_exclusive_skills": [],
    }
    manifest["workflows"][0]["routes"] = [route]
    write_json(root / "manifests/workflows.json", manifest)
    return manifest


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
                    "name": "review-command",
                    "enabled": True,
                    "profiles": ["team-collab"],
                    "command": "/review",
                    "purpose": "quality review",
                    "input_contract": ["diff"],
                    "allowed_actions": ["review"],
                    "forbidden_actions": ["bypass-verification"],
                    "output_contract": ["evidence"],
                    "review_required": True,
                    "verification": ["rtk bash scripts/runtime-control.sh gate --event final"],
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


def write_p5_controls(root: pathlib.Path) -> None:
    write_json(
        root / "manifests/prompt_experiments.json",
        {
            "schema_version": 1,
            "prompt_experiments": [
                {
                    "name": "agents-guidance-experiment",
                    "enabled": False,
                    "profiles": ["team-collab"],
                    "target": "agents-guidance",
                    "target_paths": ["AGENTS.md", "src/codex-home/AGENTS.md"],
                    "hypothesis": "explicit evidence gate improves guidance promotion",
                    "variants": [
                        {"name": "baseline", "change_summary": "current guidance"},
                        {"name": "evidence-gate", "change_summary": "require evidence"},
                    ],
                    "evaluation_suite": "routing-eval",
                    "sample_cases": ["official docs promotion", "session lesson"],
                    "grader": {"type": "human-plus-tests", "rubric": ["rejects unsourced rules"]},
                    "human_review_required": True,
                    "success_metric": "no governance regression",
                    "rollback": "drop variant",
                    "artifacts": ["review note"],
                }
            ],
        },
    )
    write_json(
        root / "manifests/trace_eval_contracts.json",
        {
            "schema_version": 1,
            "trace_eval_contracts": [
                {
                    "name": "governance-trace-eval",
                    "enabled": True,
                    "profiles": ["team-collab"],
                    "scope": "asset governance",
                    "trace_sources": ["plan", "commands"],
                    "rubric": [
                        {"criterion": "read before edit", "weight": 0.5},
                        {"criterion": "verify before final", "weight": 0.5},
                    ],
                    "min_score": 0.9,
                    "required_events": ["status checked", "tests run"],
                    "forbidden_events": ["completion without verification"],
                    "commands": ["rtk bash scripts/runtime-control.sh gate --event final"],
                    "artifacts": ["runtime-control final decision"],
                    "promotion_gate": "trace evidence reviewed",
                }
            ],
        },
    )
    write_json(
        root / "manifests/context_state_contracts.json",
        {
            "schema_version": 1,
            "context_state_contracts": [
                {
                    "name": "handoff-context-state",
                    "enabled": True,
                    "profiles": ["team-collab"],
                    "scope": "context handoff",
                    "layers": {
                        "stable": {
                            "required_fields": ["rules"],
                            "destinations": ["AGENTS.md"],
                            "promotion_gate": "reviewed",
                        },
                        "dynamic": {
                            "required_fields": ["current goal"],
                            "destinations": ["context-preflight"],
                            "promotion_gate": "expires before promotion",
                        },
                        "evidence": {
                            "required_fields": ["command"],
                            "destinations": ["final evidence"],
                            "promotion_gate": "reproducible",
                        },
                        "excluded": {
                            "required_fields": ["secrets"],
                            "destinations": ["none"],
                            "promotion_gate": "never promote",
                        },
                    },
                    "validation_commands": ["rtk bash scripts/context-preflight.sh"],
                    "forbidden_promotions": ["excluded-to-memory"],
                    "artifacts": ["context-preflight markdown"],
                }
            ],
        },
    )
    write_json(
        root / "manifests/automation_run_records.json",
        {
            "schema_version": 1,
            "automation_run_records": [
                {
                    "name": "health-report-record-template",
                    "enabled": False,
                    "automation": "health-report",
                    "run_id": "template",
                    "run_at": "manual-template",
                    "trigger": "scheduled",
                    "status": "record-template",
                    "triage": {
                        "summary": "record triage",
                        "priority": "review",
                        "allowed_outputs": ["summary"],
                        "forbidden_actions": ["send", "commit", "delete", "publish"],
                    },
                    "cleanup": {"performed": False, "actions": ["discard transient logs"]},
                    "retention": {"policy": "summary-only", "expires_after": "next run"},
                    "human_review": {"required": True, "status": "pending", "reviewer": "human"},
                    "artifacts": ["triage summary"],
                }
            ],
        },
    )


def write_p6_controls(root: pathlib.Path) -> None:
    mcp_manifest = json.loads((root / "manifests/mcp_servers.json").read_text())
    docs_server = dict(mcp_manifest["mcp_servers"][0])
    docs_server["name"] = "openaiDeveloperDocs"
    docs_server["transport"] = "http"
    docs_server.pop("command", None)
    docs_server.pop("args", None)
    docs_server["url"] = "https://developers.openai.com/mcp"
    docs_server["env"] = {}
    docs_server["readiness"]["network_targets"] = ["developers.openai.com"]
    docs_server["readiness"]["tool_inventory"] = [
        "search_openai_docs",
        "fetch_openai_doc",
        "list_openai_docs",
    ]
    docs_server["readiness"]["write_actions"] = []
    docs_server["readiness"]["destructive_actions"] = []
    mcp_manifest["mcp_servers"].append(docs_server)
    write_json(root / "manifests/mcp_servers.json", mcp_manifest)
    write_json(
        root / "manifests/skill_mcp_dependencies.json",
        {
            "schema_version": 1,
            "skill_mcp_dependencies": [
                {
                    "name": "docs-skill-dependency",
                    "enabled": True,
                    "profiles": ["team-collab"],
                    "skill": "session-wrap",
                    "mcp_servers": ["openaiDeveloperDocs"],
                    "access_mode": "read-only",
                    "required_tools": ["search_openai_docs", "fetch_openai_doc"],
                    "allowed_actions": ["search docs", "fetch docs"],
                    "forbidden_actions": [
                        "external-write",
                        "credential-access",
                        "destructive-action",
                        "silent-enable-mcp",
                    ],
                    "approval_required": True,
                    "fallback": "official-domain fallback",
                    "verification": ["rtk codex mcp list"],
                    "artifacts": ["source URL list"],
                }
            ],
        },
    )
    write_json(
        root / "manifests/slash_command_runtime_audits.json",
        {
            "schema_version": 1,
            "slash_command_runtime_audits": [
                {
                    "name": "review-runtime-audit",
                    "enabled": True,
                    "profiles": ["team-collab"],
                    "command_contract": "review-command",
                    "command": "/review",
                    "risk_class": "review-control",
                    "audit_events": ["command invoked", "verification checked"],
                    "runtime_controls": ["keep scope explicit"],
                    "required_evidence": ["review summary"],
                    "forbidden_actions": ["bypass-verification", "silent-memory-write"],
                    "retention": "audit summary only",
                    "review_required": True,
                    "verification": ["rtk bash scripts/runtime-control.sh gate --event final"],
                    "artifacts": ["audit summary"],
                }
            ],
        },
    )
    write_json(
        root / "manifests/official_docs_freshness_gates.json",
        {
            "schema_version": 1,
            "official_docs_freshness_gates": [
                {
                    "name": "openai-docs-freshness",
                    "enabled": True,
                    "source": "openai-developer-docs",
                    "mcp_server": "openaiDeveloperDocs",
                    "source_domains": ["developers.openai.com"],
                    "source_urls": ["https://developers.openai.com/learn/docs-mcp"],
                    "retrieval_required": True,
                    "max_age_days": 45,
                    "required_metadata": ["source_url", "retrieved_at", "review_status", "expires_at"],
                    "review_status": "review-required",
                    "stale_action": "re-fetch before promotion",
                    "promotion_targets": ["AGENTS.md"],
                    "verification": ["rtk bash scripts/doctor.sh --scope governance"],
                    "rollback": "remove promoted rule",
                    "artifacts": ["review note"],
                }
            ],
        },
    )


def write_p7_runtime_boundary_controls(root: pathlib.Path) -> None:
    write_json(
        root / "manifests/permission_profiles.json",
        {
            "schema_version": 1,
            "permission_profiles": [
                {
                    "name": "local-workspace-boundary",
                    "enabled": True,
                    "profiles": ["team-collab"],
                    "mode": "workspace-write",
                    "active_config_mode": "legacy-sandbox",
                    "approval_policy": "on-request",
                    "filesystem": {
                        "write_roots": ["<workspace>", "/home/leiwenjun/.codex/memories"],
                        "deny_paths": ["auth.json", "sessions/**", "mcp/secrets/**"],
                    },
                    "network": {
                        "default": "deny",
                        "allowed_domains": ["developers.openai.com"],
                        "approval_required_for_unlisted": True,
                    },
                    "allowed_sandbox_modes": ["read-only", "workspace-write"],
                    "forbidden_modes": ["danger-full-access"],
                    "source_urls": ["https://developers.openai.com/codex/permissions"],
                    "verification": ["rtk codex --strict-config doctor --summary --ascii"],
                    "rollback": "restore legacy sandbox config and keep default_permissions disabled",
                    "artifacts": ["config audit summary"],
                }
            ],
        },
    )
    write_json(
        root / "manifests/exec_rules.json",
        {
            "schema_version": 1,
            "exec_rules": [
                {
                    "name": "default-local-command-rules",
                    "enabled": True,
                    "profiles": ["team-collab"],
                    "source_path": "src/codex-home/rules/default.rules",
                    "rules": [
                        {
                            "name": "allow-rtk-wrapper",
                            "pattern": ["rtk"],
                            "decision": "allow",
                            "justification": "repo policy requires all shell commands to go through rtk",
                            "match": ["rtk bash scripts/check.sh"],
                            "not_match": ["bash scripts/check.sh"],
                        }
                    ],
                    "verification": ["rtk bash scripts/doctor.sh --scope governance"],
                    "rollback": "remove the matching prefix_rule and rebuild Codex home",
                    "artifacts": ["rules/default.rules"],
                }
            ],
        },
    )
    write_json(
        root / "manifests/hook_contracts.json",
        {
            "schema_version": 1,
            "hook_contracts": [
                {
                    "name": "pretooluse-rtk-guard-contract",
                    "enabled": False,
                    "profiles": ["team-collab"],
                    "event": "PreToolUse",
                    "matcher": "Bash",
                    "mode": "report-only",
                    "input_contract": ["tool_name", "command", "cwd"],
                    "output_contract": ["systemMessage", "stopReason"],
                    "allowed_actions": ["warn about non-rtk shell commands"],
                    "forbidden_actions": ["bypass-sandbox", "claim-complete-enforcement"],
                    "review_required": True,
                    "retention": "sanitized hook summary only",
                    "source_urls": ["https://developers.openai.com/codex/hooks"],
                    "verification": ["rtk bash scripts/doctor.sh --scope governance"],
                    "rollback": "keep hook disabled and remove contract entry",
                    "artifacts": ["hook contract summary"],
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

    def test_workflow_route_rejects_unknown_primary_skill(self) -> None:
        root = make_repo(self)
        manifest = add_valid_workflow_route(root)
        manifest["workflows"][0]["routes"][0]["primary_skill"] = "missing-skill"
        write_json(root / "manifests/workflows.json", manifest)

        errors = validate_repo(root)
        self.assertIn(
            "workflows:context-handoff route:session-closeout 引用未知 primary skill: missing-skill",
            errors,
        )

    def test_workflow_route_rejects_primary_supporting_overlap(self) -> None:
        root = make_repo(self)
        manifest = add_valid_workflow_route(root)
        manifest["workflows"][0]["routes"][0]["supporting_skills"].append("session-wrap")
        write_json(root / "manifests/workflows.json", manifest)

        errors = validate_repo(root)
        self.assertIn(
            "workflows:context-handoff route:session-closeout primary_skill 不得同时是 supporting skill: session-wrap",
            errors,
        )

    def test_workflow_route_rejects_duplicate_match_term(self) -> None:
        root = make_repo(self)
        manifest = add_valid_workflow_route(root)
        manifest["workflows"][0]["routes"].append(
            {
                "name": "memory-closeout",
                "match_any": ["总结本次会话"],
                "exclude_any": [],
                "primary_skill": "memory-curator",
                "supporting_skills": [],
                "fallback_skill": "session-wrap",
                "mutually_exclusive_skills": [],
            }
        )
        write_json(root / "manifests/workflows.json", manifest)

        errors = validate_repo(root)
        self.assertIn(
            "workflows:context-handoff route 匹配词重复: 总结本次会话 (session-closeout 与 memory-closeout)",
            errors,
        )

    def test_governance_report_exposes_workflow_route_roles(self) -> None:
        root = make_repo(self)
        add_valid_workflow_route(root)

        report = governance_report(root)
        route = report["workflow_links"]["context-handoff"]["routes"][0]
        self.assertEqual("session-wrap", route["primary_skill"])
        self.assertEqual(["memory-curator"], route["supporting_skills"])

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
        self.assertEqual(["review-command"], report["cli_command_contracts"])
        self.assertEqual(["docs-to-agents"], report["guidance_promotions"])
        self.assertEqual(2, report["schema_version"])
        self.assertNotIn("runtime_control", report)
        self.assertEqual("7.0.4", report["execution_policy"]["engine_version"])
        self.assertEqual("routing", report["eval_suite_links"]["routing-eval"]["kind"])
        self.assertEqual("/review", report["cli_command_contract_links"]["review-command"]["command"])
        self.assertEqual("agents", report["guidance_promotion_links"]["docs-to-agents"]["destination"])

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
        contract["command"] = "review"
        contract["forbidden_actions"] = ["skip-review"]
        write_json(root / "manifests/cli_command_contracts.json", manifest)

        errors = validate_repo(root)
        self.assertIn("cli_command_contracts:review-command command 必须以 / 开头", errors)
        self.assertIn("cli_command_contracts:review-command forbidden_actions 必须包含 bypass-verification", errors)

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

    def test_execution_policy_requires_exact_source_blob(self) -> None:
        root = make_repo(self)
        source = root / "tools/codex_assets/execution_policy/engine.py"
        source.write_bytes(source.read_bytes() + b"\n# source drift\n")

        errors = validate_repo(root)
        self.assertIn("execution_policy.json: Execution Policy source blob drift: engine.py", errors)

    def test_automation_requires_run_lifecycle(self) -> None:
        root = make_repo(self)
        write_optional_controls(root)
        manifest = json.loads((root / "manifests/automations.json").read_text())
        del manifest["automations"][0]["run_lifecycle"]
        write_json(root / "manifests/automations.json", manifest)

        errors = validate_repo(root)
        self.assertIn("automations:health-report 缺少字段 run_lifecycle", errors)

    def test_p5_controls_pass_and_report(self) -> None:
        root = make_repo(self)
        write_optional_controls(root)
        write_p3_p4_controls(root)
        write_p5_controls(root)

        self.assertEqual([], validate_repo(root))
        report = governance_report(root)
        self.assertEqual(["agents-guidance-experiment"], report["prompt_experiments"])
        self.assertEqual(["governance-trace-eval"], report["trace_eval_contracts"])
        self.assertEqual(["handoff-context-state"], report["context_state_contracts"])
        self.assertEqual(["health-report-record-template"], report["automation_run_records"])
        self.assertEqual(
            "routing-eval",
            report["prompt_experiment_links"]["agents-guidance-experiment"]["evaluation_suite"],
        )
        self.assertEqual(
            0.9,
            report["trace_eval_contract_links"]["governance-trace-eval"]["min_score"],
        )
        self.assertEqual(
            ["dynamic", "evidence", "excluded", "stable"],
            report["context_state_contract_links"]["handoff-context-state"]["layers"],
        )
        self.assertEqual(
            "health-report",
            report["automation_run_record_links"]["health-report-record-template"]["automation"],
        )

    def test_prompt_experiment_rejects_unknown_eval_suite_and_missing_review(self) -> None:
        root = make_repo(self)
        write_optional_controls(root)
        write_p3_p4_controls(root)
        write_p5_controls(root)
        manifest = json.loads((root / "manifests/prompt_experiments.json").read_text())
        experiment = manifest["prompt_experiments"][0]
        experiment["evaluation_suite"] = "missing-eval"
        experiment["human_review_required"] = False
        write_json(root / "manifests/prompt_experiments.json", manifest)

        errors = validate_repo(root)
        self.assertIn("prompt_experiments:agents-guidance-experiment 引用未知 evaluation_suite: missing-eval", errors)
        self.assertIn("prompt_experiments:agents-guidance-experiment human_review_required 必须为 true", errors)

    def test_trace_eval_rejects_bad_weight_and_score(self) -> None:
        root = make_repo(self)
        write_optional_controls(root)
        write_p3_p4_controls(root)
        write_p5_controls(root)
        manifest = json.loads((root / "manifests/trace_eval_contracts.json").read_text())
        contract = manifest["trace_eval_contracts"][0]
        contract["rubric"][0]["weight"] = 0.2
        contract["min_score"] = 1.5
        write_json(root / "manifests/trace_eval_contracts.json", manifest)

        errors = validate_repo(root)
        self.assertIn("trace_eval_contracts:governance-trace-eval rubric.weight 总和必须为 1", errors)
        self.assertIn("trace_eval_contracts:governance-trace-eval min_score 必须在 0..1", errors)

    def test_context_state_requires_excluded_never_gate(self) -> None:
        root = make_repo(self)
        write_optional_controls(root)
        write_p3_p4_controls(root)
        write_p5_controls(root)
        manifest = json.loads((root / "manifests/context_state_contracts.json").read_text())
        manifest["context_state_contracts"][0]["layers"]["excluded"]["promotion_gate"] = "review first"
        write_json(root / "manifests/context_state_contracts.json", manifest)

        errors = validate_repo(root)
        self.assertIn("context_state_contracts:handoff-context-state excluded promotion_gate 必须包含 never", errors)

    def test_automation_run_record_rejects_enabled_and_missing_forbidden_action(self) -> None:
        root = make_repo(self)
        write_optional_controls(root)
        write_p5_controls(root)
        manifest = json.loads((root / "manifests/automation_run_records.json").read_text())
        record = manifest["automation_run_records"][0]
        record["enabled"] = True
        record["triage"]["forbidden_actions"] = ["send", "commit", "delete"]
        write_json(root / "manifests/automation_run_records.json", manifest)

        errors = validate_repo(root)
        self.assertIn("automation_run_records:health-report-record-template 运行记录不得 enabled=true", errors)
        self.assertIn("automation_run_records:health-report-record-template triage.forbidden_actions 必须包含 publish", errors)

    def test_p6_controls_pass_and_report(self) -> None:
        root = make_repo(self)
        write_optional_controls(root)
        write_p3_p4_controls(root)
        write_p6_controls(root)

        self.assertEqual([], validate_repo(root))
        report = governance_report(root)
        self.assertEqual(["docs-skill-dependency"], report["skill_mcp_dependencies"])
        self.assertEqual(["review-runtime-audit"], report["slash_command_runtime_audits"])
        self.assertEqual(["openai-docs-freshness"], report["official_docs_freshness_gates"])
        self.assertEqual(
            "session-wrap",
            report["skill_mcp_dependency_links"]["docs-skill-dependency"]["skill"],
        )
        self.assertEqual(
            "/review",
            report["slash_command_runtime_audit_links"]["review-runtime-audit"]["command"],
        )
        self.assertEqual(
            "openaiDeveloperDocs",
            report["official_docs_freshness_gate_links"]["openai-docs-freshness"]["mcp_server"],
        )

    def test_skill_mcp_dependency_rejects_unknown_skill_and_missing_approval(self) -> None:
        root = make_repo(self)
        write_optional_controls(root)
        write_p6_controls(root)
        manifest = json.loads((root / "manifests/skill_mcp_dependencies.json").read_text())
        dependency = manifest["skill_mcp_dependencies"][0]
        dependency["skill"] = "missing-skill"
        dependency["approval_required"] = False
        dependency["forbidden_actions"] = ["external-write"]
        write_json(root / "manifests/skill_mcp_dependencies.json", manifest)

        errors = validate_repo(root)
        self.assertIn("skill_mcp_dependencies:docs-skill-dependency 引用未知 skill: missing-skill", errors)
        self.assertIn("skill_mcp_dependencies:docs-skill-dependency approval_required 必须为 true", errors)
        self.assertIn(
            "skill_mcp_dependencies:docs-skill-dependency forbidden_actions 缺少: credential-access, destructive-action, silent-enable-mcp",
            errors,
        )

    def test_slash_command_runtime_audit_rejects_mismatched_command(self) -> None:
        root = make_repo(self)
        write_optional_controls(root)
        write_p3_p4_controls(root)
        write_p6_controls(root)
        manifest = json.loads((root / "manifests/slash_command_runtime_audits.json").read_text())
        audit = manifest["slash_command_runtime_audits"][0]
        audit["command"] = "/goal"
        audit["forbidden_actions"] = ["silent-memory-write"]
        write_json(root / "manifests/slash_command_runtime_audits.json", manifest)

        errors = validate_repo(root)
        self.assertIn("slash_command_runtime_audits:review-runtime-audit command 必须匹配 command_contract: /review", errors)
        self.assertIn("slash_command_runtime_audits:review-runtime-audit forbidden_actions 必须包含 bypass-verification", errors)

    def test_official_docs_freshness_gate_rejects_unofficial_source(self) -> None:
        root = make_repo(self)
        write_optional_controls(root)
        write_p6_controls(root)
        manifest = json.loads((root / "manifests/official_docs_freshness_gates.json").read_text())
        gate = manifest["official_docs_freshness_gates"][0]
        gate["source_domains"] = ["example.com"]
        gate["source_urls"] = ["https://example.com/docs"]
        gate["required_metadata"] = ["source_url"]
        gate["retrieval_required"] = False
        write_json(root / "manifests/official_docs_freshness_gates.json", manifest)

        errors = validate_repo(root)
        self.assertIn("official_docs_freshness_gates:openai-docs-freshness retrieval_required 必须为 true", errors)
        self.assertIn("official_docs_freshness_gates:openai-docs-freshness source_domains 必须包含 OpenAI 官方域名", errors)
        self.assertIn("official_docs_freshness_gates:openai-docs-freshness source_urls 必须使用 OpenAI 官方域名: example.com", errors)
        self.assertIn(
            "official_docs_freshness_gates:openai-docs-freshness required_metadata 缺少: expires_at, retrieved_at, review_status",
            errors,
        )

    def test_p7_runtime_boundary_controls_pass_and_report(self) -> None:
        root = make_repo(self)
        write_p7_runtime_boundary_controls(root)

        self.assertEqual([], validate_repo(root))
        report = governance_report(root)
        self.assertEqual(["local-workspace-boundary"], report["permission_profiles"])
        self.assertEqual(["default-local-command-rules"], report["exec_rules"])
        self.assertEqual(["pretooluse-rtk-guard-contract"], report["hook_contracts"])
        self.assertEqual(
            "legacy-sandbox",
            report["permission_profile_links"]["local-workspace-boundary"]["active_config_mode"],
        )
        self.assertEqual(1, report["exec_rule_links"]["default-local-command-rules"]["rule_count"])
        self.assertEqual("PreToolUse", report["hook_contract_links"]["pretooluse-rtk-guard-contract"]["event"])

    def test_permission_profile_rejects_broad_access(self) -> None:
        root = make_repo(self)
        write_p7_runtime_boundary_controls(root)
        manifest = json.loads((root / "manifests/permission_profiles.json").read_text())
        profile = manifest["permission_profiles"][0]
        profile["approval_policy"] = "never"
        profile["allowed_sandbox_modes"] = ["danger-full-access"]
        profile["network"]["default"] = "allow"
        write_json(root / "manifests/permission_profiles.json", manifest)

        errors = validate_repo(root)
        self.assertIn("permission_profiles:local-workspace-boundary approval_policy 不允许 never", errors)
        self.assertIn(
            "permission_profiles:local-workspace-boundary allowed_sandbox_modes 不允许 danger-full-access",
            errors,
        )
        self.assertIn("permission_profiles:local-workspace-boundary network.default 不允许 allow", errors)

    def test_exec_rules_reject_broad_allow_prefix(self) -> None:
        root = make_repo(self)
        write_p7_runtime_boundary_controls(root)
        manifest = json.loads((root / "manifests/exec_rules.json").read_text())
        rule = manifest["exec_rules"][0]["rules"][0]
        rule["pattern"] = ["bash"]
        write_json(root / "manifests/exec_rules.json", manifest)

        errors = validate_repo(root)
        self.assertIn("exec_rules:default-local-command-rules:allow-rtk-wrapper 不允许 broad allow prefix: bash", errors)

    def test_hook_contract_rejects_unenforceable_pretooluse_claim(self) -> None:
        root = make_repo(self)
        write_p7_runtime_boundary_controls(root)
        manifest = json.loads((root / "manifests/hook_contracts.json").read_text())
        contract = manifest["hook_contracts"][0]
        contract["forbidden_actions"] = ["bypass-sandbox"]
        write_json(root / "manifests/hook_contracts.json", manifest)

        errors = validate_repo(root)
        self.assertIn(
            "hook_contracts:pretooluse-rtk-guard-contract PreToolUse 必须禁止 claim-complete-enforcement",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
