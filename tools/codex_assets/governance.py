from __future__ import annotations

import pathlib
import re
from urllib.parse import urlparse
from typing import Any

from .core import Repo, matches_any


def governance_report(root: str | pathlib.Path) -> dict[str, Any]:
    repo = Repo.from_path(root)
    profiles = repo.manifest("profiles.json").get("profiles", [])
    skills = repo.manifest("skills.json").get("skills", [])
    agents = repo.manifest("agents.json").get("agents", [])
    workflows = repo.manifest("workflows.json").get("workflows", [])
    templates = repo.manifest("project-templates.json").get("project_templates", [])
    overlays = repo.manifest("overlays.json").get("overlays", [])
    mcp_servers = optional_manifest_items(repo, "mcp_servers.json", "mcp_servers")
    workflow_recipes = optional_manifest_items(repo, "workflow_recipes.json", "workflow_recipes")
    automations = optional_manifest_items(repo, "automations.json", "automations")
    subagent_contracts = optional_manifest_items(repo, "subagent_contracts.json", "subagent_contracts")
    memory_candidates = optional_manifest_items(repo, "memory_candidates.json", "memory_candidates")
    eval_suites = optional_manifest_items(repo, "eval_suites.json", "eval_suites")
    cli_command_contracts = optional_manifest_items(repo, "cli_command_contracts.json", "cli_command_contracts")
    guidance_promotions = optional_manifest_items(repo, "guidance_promotions.json", "guidance_promotions")
    goal_templates = optional_manifest_items(repo, "goal_templates.json", "goal_templates")
    return {
        "schema_version": 1,
        "default_profile": repo.assets.get("default_profile", ""),
        "profiles": sorted(item.get("name", "") for item in profiles if item.get("name")),
        "skills": sorted(item.get("name", "") for item in skills if item.get("name")),
        "agents": sorted(item.get("name", "") for item in agents if item.get("name")),
        "mcp_servers": sorted(item.get("name", "") for item in mcp_servers if item.get("name")),
        "workflow_recipes": sorted(item.get("name", "") for item in workflow_recipes if item.get("name")),
        "automations": sorted(item.get("name", "") for item in automations if item.get("name")),
        "subagent_contracts": sorted(item.get("name", "") for item in subagent_contracts if item.get("name")),
        "memory_candidates": sorted(item.get("name", "") for item in memory_candidates if item.get("name")),
        "eval_suites": sorted(item.get("name", "") for item in eval_suites if item.get("name")),
        "cli_command_contracts": sorted(item.get("name", "") for item in cli_command_contracts if item.get("name")),
        "guidance_promotions": sorted(item.get("name", "") for item in guidance_promotions if item.get("name")),
        "goal_templates": sorted(item.get("name", "") for item in goal_templates if item.get("name")),
        "workflows": sorted(item.get("name", "") for item in workflows if item.get("name")),
        "project_templates": sorted(item.get("name", "") for item in templates if item.get("name")),
        "overlays": sorted(item.get("name", "") for item in overlays if item.get("name")),
        "workflow_links": workflow_links(workflows),
        "workflow_recipe_links": workflow_recipe_links(workflow_recipes),
        "automation_links": automation_links(automations),
        "subagent_contract_links": subagent_contract_links(subagent_contracts),
        "memory_candidate_links": memory_candidate_links(memory_candidates),
        "eval_suite_links": eval_suite_links(eval_suites),
        "cli_command_contract_links": cli_command_contract_links(cli_command_contracts),
        "guidance_promotion_links": guidance_promotion_links(guidance_promotions),
        "goal_template_links": goal_template_links(goal_templates),
        "template_links": template_links(templates),
    }


def governance_errors(repo: Repo) -> list[str]:
    errors: list[str] = []
    profile_names = names(repo.manifest("profiles.json"), "profiles")
    skill_names = names(repo.manifest("skills.json"), "skills")
    agent_names = names(repo.manifest("agents.json"), "agents")
    workflows = repo.manifest("workflows.json").get("workflows", [])
    templates = repo.manifest("project-templates.json").get("project_templates", [])
    overlays = repo.manifest("overlays.json").get("overlays", [])
    mcp_servers = optional_manifest_items(repo, "mcp_servers.json", "mcp_servers")
    workflow_recipes = optional_manifest_items(repo, "workflow_recipes.json", "workflow_recipes")
    automations = optional_manifest_items(repo, "automations.json", "automations")
    subagent_contracts = optional_manifest_items(repo, "subagent_contracts.json", "subagent_contracts")
    memory_candidates = optional_manifest_items(repo, "memory_candidates.json", "memory_candidates")
    eval_suites = optional_manifest_items(repo, "eval_suites.json", "eval_suites")
    cli_command_contracts = optional_manifest_items(repo, "cli_command_contracts.json", "cli_command_contracts")
    guidance_promotions = optional_manifest_items(repo, "guidance_promotions.json", "guidance_promotions")
    goal_templates = optional_manifest_items(repo, "goal_templates.json", "goal_templates")
    workflow_names = item_names("workflows", workflows, errors)
    workflow_profiles = {item.get("name", ""): set(list_value(item, "profiles")) for item in workflows if item.get("name")}
    item_names("project-templates", templates, errors)
    item_names("overlays", overlays, errors)
    item_names("workflow_recipes", workflow_recipes, errors)
    item_names("automations", automations, errors)
    item_names("subagent_contracts", subagent_contracts, errors)
    item_names("memory_candidates", memory_candidates, errors)
    item_names("eval_suites", eval_suites, errors)
    item_names("cli_command_contracts", cli_command_contracts, errors)
    item_names("guidance_promotions", guidance_promotions, errors)
    item_names("goal_templates", goal_templates, errors)
    validate_workflows(workflows, profile_names, skill_names, agent_names, errors)
    validate_project_templates(templates, profile_names, workflow_names, errors)
    validate_overlays(overlays, repo.policies.get("protected_paths", []), errors)
    validate_mcp_servers(mcp_servers, profile_names, errors)
    validate_workflow_recipes(workflow_recipes, profile_names, workflow_names, workflow_profiles, errors)
    validate_automations(automations, profile_names, workflow_names, workflow_profiles, errors)
    validate_subagent_contracts(subagent_contracts, profile_names, agent_names, errors)
    validate_memory_candidates(memory_candidates, errors)
    validate_eval_suites(eval_suites, profile_names, repo.root, errors)
    validate_cli_command_contracts(cli_command_contracts, profile_names, errors)
    validate_guidance_promotions(guidance_promotions, errors)
    validate_goal_templates(goal_templates, profile_names, workflow_names, workflow_profiles, errors)
    return errors


def names(manifest: dict[str, Any], key: str) -> set[str]:
    return {item.get("name", "") for item in manifest.get(key, []) if item.get("name")}


def optional_manifest_items(repo: Repo, name: str, key: str) -> list[dict[str, Any]]:
    path = repo.manifests_dir / name
    if not path.is_file():
        return []
    value = repo.manifest(name).get(key, [])
    return value if isinstance(value, list) else []


def item_names(label: str, items: list[dict[str, Any]], errors: list[str]) -> set[str]:
    seen: set[str] = set()
    for item in items:
        name = item.get("name")
        if not name:
            errors.append(f"{label} 条目缺少 name")
            continue
        if name in seen:
            errors.append(f"{label} 重复 name: {name}")
        seen.add(name)
    return seen


def validate_workflows(
    workflows: list[dict[str, Any]],
    profile_names: set[str],
    skill_names: set[str],
    agent_names: set[str],
    errors: list[str],
) -> None:
    for item in workflows:
        name = item.get("name", "")
        for field in ["enabled", "profiles", "triggers", "skills", "agents", "commands", "verification"]:
            if field not in item:
                errors.append(f"workflows:{name} 缺少字段 {field}")
        for profile in list_value(item, "profiles"):
            if profile not in profile_names:
                errors.append(f"workflows:{name} 引用未知 profile: {profile}")
        for skill in list_value(item, "skills"):
            if skill not in skill_names:
                errors.append(f"workflows:{name} 引用未知 skill: {skill}")
        for agent in list_value(item, "agents"):
            if agent not in agent_names:
                errors.append(f"workflows:{name} 引用未知 agent: {agent}")


def validate_project_templates(
    templates: list[dict[str, Any]],
    profile_names: set[str],
    workflow_names: set[str],
    errors: list[str],
) -> None:
    for item in templates:
        name = item.get("name", "")
        for field in ["path_patterns", "default_profile", "workflows", "archive_topics"]:
            if field not in item:
                errors.append(f"project-templates:{name} 缺少字段 {field}")
        profile = item.get("default_profile", "")
        if profile and profile not in profile_names:
            errors.append(f"project-templates:{name} 引用未知 default_profile: {profile}")
        for workflow in list_value(item, "workflows"):
            if workflow not in workflow_names:
                errors.append(f"project-templates:{name} 引用未知 workflow: {workflow}")


def validate_overlays(overlays: list[dict[str, Any]], protected: list[str], errors: list[str]) -> None:
    for item in overlays:
        name = item.get("name", "")
        for field in ["allowed_live_drift_paths", "blocked_paths"]:
            if field not in item:
                errors.append(f"overlays:{name} 缺少字段 {field}")
        for path in list_value(item, "allowed_live_drift_paths"):
            if unsafe_path(path):
                errors.append(f"overlays:{name} 包含不安全路径: {path}")
            if matches_any(path, protected):
                errors.append(f"overlays:{name} allowed_live_drift_paths 不能包含 protected path: {path}")


def validate_mcp_servers(items: list[dict[str, Any]], profile_names: set[str], errors: list[str]) -> None:
    seen: set[str] = set()
    for item in items:
        name = item.get("name", "")
        if not name:
            errors.append("mcp_servers 条目缺少 name")
            continue
        if name in seen:
            errors.append(f"mcp_servers 重复 name: {name}")
        seen.add(name)
        for field in [
            "enabled",
            "profiles",
            "transport",
            "required",
            "supports_parallel_tool_calls",
            "env",
            "owner",
            "purpose",
            "security_status",
            "rollback",
            "readiness",
        ]:
            if field not in item:
                errors.append(f"mcp_servers:{name} 缺少字段 {field}")
        if not re_match_name(name):
            errors.append(f"mcp_servers:{name} name 只能包含字母、数字、下划线和连字符")
        transport = str(item.get("transport", "stdio"))
        if transport not in {"stdio", "http"}:
            errors.append(f"mcp_servers:{name} transport 非法: {transport}")
        if transport == "stdio":
            for field in ["command", "args"]:
                if field not in item:
                    errors.append(f"mcp_servers:{name} stdio transport 缺少字段 {field}")
        if transport == "http":
            if "url" not in item:
                errors.append(f"mcp_servers:{name} http transport 缺少字段 url")
            if item.get("command") or item.get("args"):
                errors.append(f"mcp_servers:{name} http transport 不应声明 command/args")
        for profile in list_value(item, "profiles"):
            if profile not in profile_names:
                errors.append(f"mcp_servers:{name} 引用未知 profile: {profile}")
        if item.get("command") and pathlib.PurePosixPath(str(item.get("command", ""))).is_absolute():
            errors.append(f"mcp_servers:{name} command 不应使用绝对路径")
        cwd = str(item.get("cwd", ""))
        if cwd and unsafe_path(cwd):
            errors.append(f"mcp_servers:{name} cwd 包含不安全路径: {cwd}")
        env = item.get("env", {})
        if not isinstance(env, dict):
            errors.append(f"mcp_servers:{name} env 必须是 object")
        else:
            for key, value in env.items():
                if not re_match_env_key(str(key)):
                    errors.append(f"mcp_servers:{name} env key 非法: {key}")
                if value:
                    errors.append(f"mcp_servers:{name} env 不得在 manifest 中写入非空值: {key}")
        if transport == "http" and isinstance(env, dict) and env:
            errors.append(f"mcp_servers:{name} http transport 不应在 manifest 中声明 env key")
        readiness = item.get("readiness", {})
        if not isinstance(readiness, dict):
            errors.append(f"mcp_servers:{name} readiness 必须是 object")
            continue
        for field in [
            "scopes",
            "network_targets",
            "tool_inventory",
            "write_actions",
            "destructive_actions",
            "requires_human_confirmation",
            "deny_path_tests",
            "log_redaction",
            "smoke",
        ]:
            if field not in readiness:
                errors.append(f"mcp_servers:{name} readiness 缺少字段 {field}")
        if item.get("enabled") and item.get("security_status") not in {"accepted", "reviewed"}:
            errors.append(f"mcp_servers:{name} 启用前 security_status 必须是 accepted 或 reviewed")
        if item.get("enabled") and "pending-inspector" in list_value(readiness, "tool_inventory"):
            errors.append(f"mcp_servers:{name} 启用前 tool_inventory 不能是 pending-inspector")
        if not list_value(readiness, "tool_inventory"):
            errors.append(f"mcp_servers:{name} readiness.tool_inventory 不能为空")
        if any(target in {"*", "any", "0.0.0.0/0"} for target in list_value(readiness, "network_targets")):
            errors.append(f"mcp_servers:{name} readiness.network_targets 不允许通配")
        if transport == "http":
            validate_mcp_url(name, str(item.get("url", "")), list_value(readiness, "network_targets"), errors)
        if (list_value(readiness, "write_actions") or list_value(readiness, "destructive_actions")) and not readiness.get(
            "requires_human_confirmation"
        ):
            errors.append(f"mcp_servers:{name} 写入或破坏性动作必须 requires_human_confirmation=true")
        deny_tests = list_dict_value(readiness, "deny_path_tests")
        if not deny_tests:
            errors.append(f"mcp_servers:{name} readiness.deny_path_tests 不能为空")
        for test in deny_tests:
            validate_deny_path_test(name, test, errors)
        if not readiness.get("log_redaction"):
            errors.append(f"mcp_servers:{name} readiness.log_redaction 必须启用")


def validate_workflow_recipes(
    items: list[dict[str, Any]],
    profile_names: set[str],
    workflow_names: set[str],
    workflow_profiles: dict[str, set[str]],
    errors: list[str],
) -> None:
    for item in items:
        name = item.get("name", "")
        for field in [
            "enabled",
            "profiles",
            "workflow",
            "context_inputs",
            "done_criteria",
            "review_artifacts",
            "failure_modes",
            "trigger_examples",
            "negative_examples",
            "verification",
        ]:
            if field not in item:
                errors.append(f"workflow_recipes:{name} 缺少字段 {field}")
        workflow = str(item.get("workflow", ""))
        if workflow and workflow not in workflow_names:
            errors.append(f"workflow_recipes:{name} 引用未知 workflow: {workflow}")
        for profile in list_value(item, "profiles"):
            if profile not in profile_names:
                errors.append(f"workflow_recipes:{name} 引用未知 profile: {profile}")
            elif workflow in workflow_profiles and profile not in workflow_profiles[workflow]:
                errors.append(f"workflow_recipes:{name} profile {profile} 未在 workflow:{workflow} 启用")
        for field in ["context_inputs", "done_criteria", "review_artifacts", "failure_modes", "trigger_examples", "negative_examples"]:
            if not list_value(item, field):
                errors.append(f"workflow_recipes:{name} {field} 不能为空")


def validate_automations(
    items: list[dict[str, Any]],
    profile_names: set[str],
    workflow_names: set[str],
    workflow_profiles: dict[str, set[str]],
    errors: list[str],
) -> None:
    allowed_modes = {"report-only", "manual-review", "assist"}
    allowed_types = {"scheduled", "thread"}
    allowed_sandboxes = {"read-only", "workspace-write"}
    allowed_approval = {"on-request", "on-failure", "manual"}
    allowed_risk = {"read-only", "draft-write", "external-write"}
    for item in items:
        name = item.get("name", "")
        for field in [
            "enabled",
            "mode",
            "type",
            "profiles",
            "workflow",
            "cadence",
            "scope",
            "sandbox",
            "approval_policy",
            "worktree_policy",
            "first_run_review",
            "stop_condition",
            "output_artifacts",
            "risk_class",
            "triage_contract",
            "requires_worktree_for_write",
            "run_lifecycle",
        ]:
            if field not in item:
                errors.append(f"automations:{name} 缺少字段 {field}")
        workflow = str(item.get("workflow", ""))
        if workflow and workflow not in workflow_names:
            errors.append(f"automations:{name} 引用未知 workflow: {workflow}")
        for profile in list_value(item, "profiles"):
            if profile not in profile_names:
                errors.append(f"automations:{name} 引用未知 profile: {profile}")
            elif workflow in workflow_profiles and profile not in workflow_profiles[workflow]:
                errors.append(f"automations:{name} profile {profile} 未在 workflow:{workflow} 启用")
        mode = str(item.get("mode", ""))
        if mode and mode not in allowed_modes:
            errors.append(f"automations:{name} mode 非法: {mode}")
        auto_type = str(item.get("type", ""))
        if auto_type and auto_type not in allowed_types:
            errors.append(f"automations:{name} type 非法: {auto_type}")
        sandbox = str(item.get("sandbox", ""))
        if sandbox and sandbox not in allowed_sandboxes:
            errors.append(f"automations:{name} sandbox 非法或过宽: {sandbox}")
        approval_policy = str(item.get("approval_policy", ""))
        if approval_policy == "never":
            errors.append(f"automations:{name} approval_policy 不允许 never")
        elif approval_policy and approval_policy not in allowed_approval:
            errors.append(f"automations:{name} approval_policy 非法: {approval_policy}")
        if item.get("enabled") and mode != "report-only":
            errors.append(f"automations:{name} 启用时必须保持 mode=report-only")
        risk = str(item.get("risk_class", ""))
        if risk and risk not in allowed_risk:
            errors.append(f"automations:{name} risk_class 非法: {risk}")
        if risk in {"draft-write", "external-write"} and item.get("requires_worktree_for_write") is not True:
            errors.append(f"automations:{name} 写入类风险必须 requires_worktree_for_write=true")
        if item.get("first_run_review") is not True:
            errors.append(f"automations:{name} first_run_review 必须为 true")
        scope = item.get("scope", {})
        if not isinstance(scope, dict):
            errors.append(f"automations:{name} scope 必须是 object")
        elif not list_value(scope, "data_sources"):
            errors.append(f"automations:{name} scope.data_sources 不能为空")
        if not str(item.get("stop_condition", "")).strip():
            errors.append(f"automations:{name} stop_condition 不能为空")
        if not list_value(item, "output_artifacts"):
            errors.append(f"automations:{name} output_artifacts 不能为空")
        triage_contract = item.get("triage_contract", {})
        if not isinstance(triage_contract, dict):
            errors.append(f"automations:{name} triage_contract 必须是 object")
        else:
            for field in ["destination", "allowed_outputs", "forbidden_actions"]:
                if field not in triage_contract:
                    errors.append(f"automations:{name} triage_contract 缺少字段 {field}")
            if not str(triage_contract.get("destination", "")).strip():
                errors.append(f"automations:{name} triage_contract.destination 不能为空")
            if not list_value(triage_contract, "allowed_outputs"):
                errors.append(f"automations:{name} triage_contract.allowed_outputs 不能为空")
            if not list_value(triage_contract, "forbidden_actions"):
                errors.append(f"automations:{name} triage_contract.forbidden_actions 不能为空")
        lifecycle = item.get("run_lifecycle", {})
        if not isinstance(lifecycle, dict):
            errors.append(f"automations:{name} run_lifecycle 必须是 object")
        else:
            for field in ["first_run", "steady_state", "stale_after", "retry_budget", "cleanup", "retention"]:
                if field not in lifecycle:
                    errors.append(f"automations:{name} run_lifecycle 缺少字段 {field}")
            for field in ["first_run", "steady_state", "stale_after", "retention"]:
                if not str(lifecycle.get(field, "")).strip():
                    errors.append(f"automations:{name} run_lifecycle.{field} 不能为空")
            retry_budget = lifecycle.get("retry_budget", 0)
            if not isinstance(retry_budget, int) or retry_budget < 0 or retry_budget > 5:
                errors.append(f"automations:{name} run_lifecycle.retry_budget 必须在 0..5")
            if not list_value(lifecycle, "cleanup"):
                errors.append(f"automations:{name} run_lifecycle.cleanup 不能为空")


def validate_subagent_contracts(
    items: list[dict[str, Any]],
    profile_names: set[str],
    agent_names: set[str],
    errors: list[str],
) -> None:
    allowed_sandboxes = {"read-only", "workspace-write"}
    for item in items:
        name = item.get("name", "")
        for field in [
            "enabled",
            "profiles",
            "agent",
            "scope_read",
            "scope_write",
            "must_not_touch",
            "output_contract",
            "sandbox",
            "max_parallel",
            "verification",
        ]:
            if field not in item:
                errors.append(f"subagent_contracts:{name} 缺少字段 {field}")
        for profile in list_value(item, "profiles"):
            if profile not in profile_names:
                errors.append(f"subagent_contracts:{name} 引用未知 profile: {profile}")
        agent = str(item.get("agent", ""))
        if agent and agent not in agent_names:
            errors.append(f"subagent_contracts:{name} 引用未知 agent: {agent}")
        if str(item.get("sandbox", "")) not in allowed_sandboxes:
            errors.append(f"subagent_contracts:{name} sandbox 非法: {item.get('sandbox', '')}")
        for field in ["scope_read", "must_not_touch", "output_contract"]:
            if not list_value(item, field):
                errors.append(f"subagent_contracts:{name} {field} 不能为空")
        for path in list_value(item, "scope_write") + list_value(item, "must_not_touch"):
            if unsafe_path(path):
                errors.append(f"subagent_contracts:{name} 包含不安全路径: {path}")
        max_parallel = item.get("max_parallel", 0)
        if not isinstance(max_parallel, int) or max_parallel < 1 or max_parallel > 6:
            errors.append(f"subagent_contracts:{name} max_parallel 必须在 1..6")


def validate_memory_candidates(items: list[dict[str, Any]], errors: list[str]) -> None:
    allowed_status = {"candidate", "accepted", "rejected", "superseded"}
    allowed_action = {"promote-to-agents", "promote-to-archive", "promote-to-memory", "reject"}
    for item in items:
        name = item.get("name", "")
        for field in [
            "enabled",
            "status",
            "source",
            "proposed_action",
            "review_required",
            "secret_scan_required",
            "promotion_gate",
            "summary",
        ]:
            if field not in item:
                errors.append(f"memory_candidates:{name} 缺少字段 {field}")
        status = str(item.get("status", ""))
        if status and status not in allowed_status:
            errors.append(f"memory_candidates:{name} status 非法: {status}")
        action = str(item.get("proposed_action", ""))
        if action and action not in allowed_action:
            errors.append(f"memory_candidates:{name} proposed_action 非法: {action}")
        if item.get("enabled"):
            errors.append(f"memory_candidates:{name} 候选不得 enabled=true")
        if item.get("review_required") is not True:
            errors.append(f"memory_candidates:{name} review_required 必须为 true")
        if item.get("secret_scan_required") is not True:
            errors.append(f"memory_candidates:{name} secret_scan_required 必须为 true")
        if not str(item.get("promotion_gate", "")).strip():
            errors.append(f"memory_candidates:{name} promotion_gate 不能为空")
        source = str(item.get("source", ""))
        if source and unsafe_path(source):
            errors.append(f"memory_candidates:{name} source 包含不安全路径: {source}")


def validate_eval_suites(
    items: list[dict[str, Any]],
    profile_names: set[str],
    root: pathlib.Path,
    errors: list[str],
) -> None:
    allowed_kinds = {"routing", "governance", "completion", "prompt"}
    for item in items:
        name = item.get("name", "")
        for field in [
            "enabled",
            "profiles",
            "kind",
            "owner",
            "cases_path",
            "success_metric",
            "min_pass_rate",
            "negative_cases_required",
            "commands",
            "artifacts",
            "promotion_gate",
        ]:
            if field not in item:
                errors.append(f"eval_suites:{name} 缺少字段 {field}")
        for profile in list_value(item, "profiles"):
            if profile not in profile_names:
                errors.append(f"eval_suites:{name} 引用未知 profile: {profile}")
        kind = str(item.get("kind", ""))
        if kind and kind not in allowed_kinds:
            errors.append(f"eval_suites:{name} kind 非法: {kind}")
        cases_path = str(item.get("cases_path", ""))
        if not cases_path:
            errors.append(f"eval_suites:{name} cases_path 不能为空")
        elif unsafe_path(cases_path):
            errors.append(f"eval_suites:{name} cases_path 包含不安全路径: {cases_path}")
        elif not (root / cases_path).exists():
            errors.append(f"eval_suites:{name} cases_path 不存在: {cases_path}")
        rate = item.get("min_pass_rate", 0)
        if not isinstance(rate, (int, float)) or rate < 0 or rate > 1:
            errors.append(f"eval_suites:{name} min_pass_rate 必须在 0..1")
        if item.get("negative_cases_required") is not True:
            errors.append(f"eval_suites:{name} negative_cases_required 必须为 true")
        for field in ["commands", "artifacts"]:
            if not list_value(item, field):
                errors.append(f"eval_suites:{name} {field} 不能为空")
        if not str(item.get("success_metric", "")).strip():
            errors.append(f"eval_suites:{name} success_metric 不能为空")
        if not str(item.get("promotion_gate", "")).strip():
            errors.append(f"eval_suites:{name} promotion_gate 不能为空")


def validate_cli_command_contracts(
    items: list[dict[str, Any]],
    profile_names: set[str],
    errors: list[str],
) -> None:
    for item in items:
        name = item.get("name", "")
        for field in [
            "enabled",
            "profiles",
            "command",
            "purpose",
            "input_contract",
            "allowed_actions",
            "forbidden_actions",
            "output_contract",
            "review_required",
            "verification",
        ]:
            if field not in item:
                errors.append(f"cli_command_contracts:{name} 缺少字段 {field}")
        for profile in list_value(item, "profiles"):
            if profile not in profile_names:
                errors.append(f"cli_command_contracts:{name} 引用未知 profile: {profile}")
        command = str(item.get("command", ""))
        if not command.startswith("/"):
            errors.append(f"cli_command_contracts:{name} command 必须以 / 开头")
        for field in ["input_contract", "allowed_actions", "forbidden_actions", "output_contract", "verification"]:
            if not list_value(item, field):
                errors.append(f"cli_command_contracts:{name} {field} 不能为空")
        if item.get("review_required") is not True:
            errors.append(f"cli_command_contracts:{name} review_required 必须为 true")
        forbidden = set(list_value(item, "forbidden_actions"))
        if "bypass-verification" not in forbidden:
            errors.append(f"cli_command_contracts:{name} forbidden_actions 必须包含 bypass-verification")


def validate_guidance_promotions(items: list[dict[str, Any]], errors: list[str]) -> None:
    allowed_source = {"conversation", "docs-archive", "manifest", "test", "external-docs"}
    allowed_destination = {"agents", "skill", "archive", "memory", "reject"}
    for item in items:
        name = item.get("name", "")
        for field in [
            "enabled",
            "source_kind",
            "source_patterns",
            "destination",
            "review_required",
            "secret_scan_required",
            "min_evidence",
            "verification",
            "rollback",
        ]:
            if field not in item:
                errors.append(f"guidance_promotions:{name} 缺少字段 {field}")
        source_kind = str(item.get("source_kind", ""))
        if source_kind and source_kind not in allowed_source:
            errors.append(f"guidance_promotions:{name} source_kind 非法: {source_kind}")
        destination = str(item.get("destination", ""))
        if destination and destination not in allowed_destination:
            errors.append(f"guidance_promotions:{name} destination 非法: {destination}")
        for path in list_value(item, "source_patterns"):
            if unsafe_path(path):
                errors.append(f"guidance_promotions:{name} source_patterns 包含不安全路径: {path}")
        for field in ["source_patterns", "min_evidence", "verification"]:
            if not list_value(item, field):
                errors.append(f"guidance_promotions:{name} {field} 不能为空")
        if item.get("review_required") is not True:
            errors.append(f"guidance_promotions:{name} review_required 必须为 true")
        if item.get("secret_scan_required") is not True:
            errors.append(f"guidance_promotions:{name} secret_scan_required 必须为 true")
        if not str(item.get("rollback", "")).strip():
            errors.append(f"guidance_promotions:{name} rollback 不能为空")


def validate_goal_templates(
    items: list[dict[str, Any]],
    profile_names: set[str],
    workflow_names: set[str],
    workflow_profiles: dict[str, set[str]],
    errors: list[str],
) -> None:
    allowed_strengths = {"weak", "strong", "continuous"}
    required_goal_fields = {"goal", "scope", "success_criteria", "verification_commands", "review_artifacts"}
    for item in items:
        name = item.get("name", "")
        for field in [
            "enabled",
            "profiles",
            "workflow",
            "goal_strength",
            "required_fields",
            "verification_contract",
            "artifact_contract",
            "stop_conditions",
            "negative_examples",
        ]:
            if field not in item:
                errors.append(f"goal_templates:{name} 缺少字段 {field}")
        workflow = str(item.get("workflow", ""))
        if workflow and workflow not in workflow_names:
            errors.append(f"goal_templates:{name} 引用未知 workflow: {workflow}")
        for profile in list_value(item, "profiles"):
            if profile not in profile_names:
                errors.append(f"goal_templates:{name} 引用未知 profile: {profile}")
            elif workflow in workflow_profiles and profile not in workflow_profiles[workflow]:
                errors.append(f"goal_templates:{name} profile {profile} 未在 workflow:{workflow} 启用")
        strength = str(item.get("goal_strength", ""))
        if strength and strength not in allowed_strengths:
            errors.append(f"goal_templates:{name} goal_strength 非法: {strength}")
        fields = set(list_value(item, "required_fields"))
        missing = sorted(required_goal_fields - fields)
        if missing:
            errors.append(f"goal_templates:{name} required_fields 缺少: {', '.join(missing)}")
        for field in ["verification_contract", "artifact_contract", "stop_conditions", "negative_examples"]:
            if not list_value(item, field):
                errors.append(f"goal_templates:{name} {field} 不能为空")


def list_value(item: dict[str, Any], key: str) -> list[str]:
    value = item.get(key, [])
    if not isinstance(value, list):
        return []
    return [str(part) for part in value]


def list_dict_value(item: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = item.get(key, [])
    if not isinstance(value, list):
        return []
    return [part for part in value if isinstance(part, dict)]


def validate_mcp_url(name: str, url: str, network_targets: list[str], errors: list[str]) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        errors.append(f"mcp_servers:{name} http url 必须是 https URL")
        return
    host = parsed.hostname or ""
    if host not in network_targets:
        errors.append(f"mcp_servers:{name} url host 必须列入 readiness.network_targets: {host}")
    if name == "openaiDeveloperDocs" and host != "developers.openai.com":
        errors.append("mcp_servers:openaiDeveloperDocs 必须使用官方 developers.openai.com MCP")


def validate_deny_path_test(name: str, test: dict[str, Any], errors: list[str]) -> None:
    for field in ["name", "path", "expected_decision"]:
        if field not in test:
            errors.append(f"mcp_servers:{name} deny_path_tests 条目缺少字段 {field}")
    path = str(test.get("path", ""))
    if not path:
        errors.append(f"mcp_servers:{name} deny_path_tests.path 不能为空")
    elif unsafe_path(path):
        errors.append(f"mcp_servers:{name} deny_path_tests.path 包含不安全路径: {path}")
    if test.get("expected_decision") != "deny":
        errors.append(f"mcp_servers:{name} deny_path_tests.expected_decision 必须是 deny")


def unsafe_path(path: str) -> bool:
    return path.startswith("/") or ".." in pathlib.PurePosixPath(path).parts


def re_match_name(value: str) -> bool:
    return bool(re.match(r"^[A-Za-z0-9_-]+$", value))


def re_match_env_key(value: str) -> bool:
    return bool(re.match(r"^[A-Z_][A-Z0-9_]*$", value))


def workflow_links(workflows: list[dict[str, Any]]) -> dict[str, dict[str, list[str]]]:
    return {
        item["name"]: {
            "profiles": list_value(item, "profiles"),
            "skills": list_value(item, "skills"),
            "agents": list_value(item, "agents"),
        }
        for item in workflows
        if item.get("name")
    }


def template_links(templates: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        item["name"]: {
            "default_profile": item.get("default_profile", ""),
            "workflows": list_value(item, "workflows"),
            "archive_topics": list_value(item, "archive_topics"),
        }
        for item in templates
        if item.get("name")
    }


def workflow_recipe_links(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        item["name"]: {
            "workflow": item.get("workflow", ""),
            "profiles": list_value(item, "profiles"),
            "review_artifacts": list_value(item, "review_artifacts"),
        }
        for item in items
        if item.get("name")
    }


def automation_links(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        item["name"]: {
            "workflow": item.get("workflow", ""),
            "profiles": list_value(item, "profiles"),
            "mode": item.get("mode", ""),
            "type": item.get("type", ""),
        }
        for item in items
        if item.get("name")
    }


def subagent_contract_links(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        item["name"]: {
            "agent": item.get("agent", ""),
            "profiles": list_value(item, "profiles"),
            "sandbox": item.get("sandbox", ""),
            "max_parallel": item.get("max_parallel", 0),
        }
        for item in items
        if item.get("name")
    }


def memory_candidate_links(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        item["name"]: {
            "status": item.get("status", ""),
            "proposed_action": item.get("proposed_action", ""),
            "source": item.get("source", ""),
        }
        for item in items
        if item.get("name")
    }


def eval_suite_links(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        item["name"]: {
            "kind": item.get("kind", ""),
            "profiles": list_value(item, "profiles"),
            "cases_path": item.get("cases_path", ""),
            "min_pass_rate": item.get("min_pass_rate", 0),
        }
        for item in items
        if item.get("name")
    }


def cli_command_contract_links(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        item["name"]: {
            "command": item.get("command", ""),
            "profiles": list_value(item, "profiles"),
            "review_required": item.get("review_required", False),
        }
        for item in items
        if item.get("name")
    }


def guidance_promotion_links(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        item["name"]: {
            "source_kind": item.get("source_kind", ""),
            "destination": item.get("destination", ""),
            "review_required": item.get("review_required", False),
        }
        for item in items
        if item.get("name")
    }


def goal_template_links(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        item["name"]: {
            "workflow": item.get("workflow", ""),
            "goal_strength": item.get("goal_strength", ""),
            "profiles": list_value(item, "profiles"),
        }
        for item in items
        if item.get("name")
    }
