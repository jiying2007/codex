from __future__ import annotations

import pathlib
import re
import hashlib
from urllib.parse import urlparse
from typing import Any

from .core import Repo, active, matches_any


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
    runtime_control = repo.manifest("runtime_control.json")
    prompt_experiments = optional_manifest_items(repo, "prompt_experiments.json", "prompt_experiments")
    trace_eval_contracts = optional_manifest_items(repo, "trace_eval_contracts.json", "trace_eval_contracts")
    context_state_contracts = optional_manifest_items(repo, "context_state_contracts.json", "context_state_contracts")
    automation_run_records = optional_manifest_items(repo, "automation_run_records.json", "automation_run_records")
    skill_mcp_dependencies = optional_manifest_items(repo, "skill_mcp_dependencies.json", "skill_mcp_dependencies")
    slash_command_runtime_audits = optional_manifest_items(
        repo, "slash_command_runtime_audits.json", "slash_command_runtime_audits"
    )
    official_docs_freshness_gates = optional_manifest_items(
        repo, "official_docs_freshness_gates.json", "official_docs_freshness_gates"
    )
    permission_profiles = optional_manifest_items(repo, "permission_profiles.json", "permission_profiles")
    exec_rules = optional_manifest_items(repo, "exec_rules.json", "exec_rules")
    hook_contracts = optional_manifest_items(repo, "hook_contracts.json", "hook_contracts")
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
        "runtime_control": {
            "schema_version": runtime_control.get("schema_version"),
            "engine_version": (runtime_control.get("engine") or {}).get("version"),
            "policy_schema": (runtime_control.get("policy") or {}).get("schema_version"),
        },
        "prompt_experiments": sorted(item.get("name", "") for item in prompt_experiments if item.get("name")),
        "trace_eval_contracts": sorted(item.get("name", "") for item in trace_eval_contracts if item.get("name")),
        "context_state_contracts": sorted(item.get("name", "") for item in context_state_contracts if item.get("name")),
        "automation_run_records": sorted(item.get("name", "") for item in automation_run_records if item.get("name")),
        "skill_mcp_dependencies": sorted(item.get("name", "") for item in skill_mcp_dependencies if item.get("name")),
        "slash_command_runtime_audits": sorted(
            item.get("name", "") for item in slash_command_runtime_audits if item.get("name")
        ),
        "official_docs_freshness_gates": sorted(
            item.get("name", "") for item in official_docs_freshness_gates if item.get("name")
        ),
        "permission_profiles": sorted(item.get("name", "") for item in permission_profiles if item.get("name")),
        "exec_rules": sorted(item.get("name", "") for item in exec_rules if item.get("name")),
        "hook_contracts": sorted(item.get("name", "") for item in hook_contracts if item.get("name")),
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
        "prompt_experiment_links": prompt_experiment_links(prompt_experiments),
        "trace_eval_contract_links": trace_eval_contract_links(trace_eval_contracts),
        "context_state_contract_links": context_state_contract_links(context_state_contracts),
        "automation_run_record_links": automation_run_record_links(automation_run_records),
        "skill_mcp_dependency_links": skill_mcp_dependency_links(skill_mcp_dependencies),
        "slash_command_runtime_audit_links": slash_command_runtime_audit_links(slash_command_runtime_audits),
        "official_docs_freshness_gate_links": official_docs_freshness_gate_links(official_docs_freshness_gates),
        "permission_profile_links": permission_profile_links(permission_profiles),
        "exec_rule_links": exec_rule_links(exec_rules),
        "hook_contract_links": hook_contract_links(hook_contracts),
        "template_links": template_links(templates),
    }


def governance_errors(repo: Repo) -> list[str]:
    errors: list[str] = []
    profiles = repo.manifest("profiles.json").get("profiles", [])
    profile_names = {str(item.get("name", "")) for item in profiles if item.get("name")}
    lazy_profile_names = {str(item.get("name", "")) for item in profiles if item.get("name") and item.get("catalog_mode") == "lazy"}
    skills = repo.manifest("skills.json").get("skills", [])
    skill_names = {str(item.get("name", "")) for item in skills if item.get("name")}
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
    runtime_control = repo.manifest("runtime_control.json")
    prompt_experiments = optional_manifest_items(repo, "prompt_experiments.json", "prompt_experiments")
    trace_eval_contracts = optional_manifest_items(repo, "trace_eval_contracts.json", "trace_eval_contracts")
    context_state_contracts = optional_manifest_items(repo, "context_state_contracts.json", "context_state_contracts")
    automation_run_records = optional_manifest_items(repo, "automation_run_records.json", "automation_run_records")
    skill_mcp_dependencies = optional_manifest_items(repo, "skill_mcp_dependencies.json", "skill_mcp_dependencies")
    slash_command_runtime_audits = optional_manifest_items(
        repo, "slash_command_runtime_audits.json", "slash_command_runtime_audits"
    )
    official_docs_freshness_gates = optional_manifest_items(
        repo, "official_docs_freshness_gates.json", "official_docs_freshness_gates"
    )
    permission_profiles = optional_manifest_items(repo, "permission_profiles.json", "permission_profiles")
    exec_rules = optional_manifest_items(repo, "exec_rules.json", "exec_rules")
    hook_contracts = optional_manifest_items(repo, "hook_contracts.json", "hook_contracts")
    workflow_names = item_names("workflows", workflows, errors)
    automation_names = item_names("automations", automations, errors)
    eval_suite_names = item_names("eval_suites", eval_suites, errors)
    mcp_server_names = {item.get("name", "") for item in mcp_servers if item.get("name")}
    workflow_profiles = {item.get("name", ""): set(list_value(item, "profiles")) for item in workflows if item.get("name")}
    item_names("project-templates", templates, errors)
    item_names("overlays", overlays, errors)
    item_names("workflow_recipes", workflow_recipes, errors)
    item_names("subagent_contracts", subagent_contracts, errors)
    item_names("memory_candidates", memory_candidates, errors)
    cli_command_contract_names = item_names("cli_command_contracts", cli_command_contracts, errors)
    item_names("guidance_promotions", guidance_promotions, errors)
    item_names("prompt_experiments", prompt_experiments, errors)
    item_names("trace_eval_contracts", trace_eval_contracts, errors)
    item_names("context_state_contracts", context_state_contracts, errors)
    item_names("automation_run_records", automation_run_records, errors)
    item_names("skill_mcp_dependencies", skill_mcp_dependencies, errors)
    item_names("slash_command_runtime_audits", slash_command_runtime_audits, errors)
    item_names("official_docs_freshness_gates", official_docs_freshness_gates, errors)
    item_names("permission_profiles", permission_profiles, errors)
    item_names("exec_rules", exec_rules, errors)
    item_names("hook_contracts", hook_contracts, errors)
    validate_workflows(workflows, profile_names, lazy_profile_names, skills, skill_names, agent_names, errors)
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
    validate_runtime_control(runtime_control, repo.root, errors)
    validate_prompt_experiments(prompt_experiments, profile_names, eval_suite_names, errors)
    validate_trace_eval_contracts(trace_eval_contracts, profile_names, errors)
    validate_context_state_contracts(context_state_contracts, profile_names, errors)
    validate_automation_run_records(automation_run_records, automation_names, errors)
    validate_skill_mcp_dependencies(skill_mcp_dependencies, profile_names, skill_names, mcp_server_names, errors)
    validate_slash_command_runtime_audits(
        slash_command_runtime_audits,
        profile_names,
        cli_command_contract_names,
        cli_command_contracts,
        errors,
    )
    validate_official_docs_freshness_gates(official_docs_freshness_gates, mcp_server_names, errors)
    validate_permission_profiles(permission_profiles, profile_names, errors)
    validate_exec_rules(exec_rules, profile_names, errors)
    validate_hook_contracts(hook_contracts, profile_names, errors)
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
    lazy_profile_names: set[str],
    skills: list[dict[str, Any]],
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
        validate_context_activation(item, lazy_profile_names, skills, errors)
        validate_workflow_routes(item, skill_names, errors)


def validate_context_activation(
    item: dict[str, Any], lazy_profile_names: set[str], skills: list[dict[str, Any]], errors: list[str]
) -> None:
    name = str(item.get("name", ""))
    lazy_profiles = set(list_value(item, "profiles")) & lazy_profile_names
    activation = item.get("context_activation")
    if not lazy_profiles:
        if activation is not None:
            errors.append(f"workflows:{name} context_activation 仅允许 lazy catalog profile")
        return
    label = f"workflows:{name} context_activation"
    if not isinstance(activation, dict):
        errors.append(f"{label} 必须是 object")
        return
    if len(lazy_profiles) != 1:
        errors.append(f"{label} 当前要求 workflow 只绑定一个 lazy catalog profile")
        return
    profile = next(iter(lazy_profiles))
    categories: dict[str, set[str]] = {}
    for field in ("resident", "lazy", "fallback"):
        if field not in activation: errors.append(f"{label} 缺少字段 {field}")
        values = list_value(activation, field)
        if len(values) != len(set(values)): errors.append(f"{label}.{field} 包含重复 skill")
        categories[field] = set(values)
    for left, right in (("resident","lazy"),("resident","fallback"),("lazy","fallback")):
        overlap = categories[left] & categories[right]
        if overlap: errors.append(f"{label} {left}/{right} 重叠: {', '.join(sorted(overlap))}")
    workflow_skills = set(list_value(item, "skills"))
    classified = set().union(*categories.values())
    if classified != workflow_skills:
        errors.append(f"{label} 未完整覆盖 workflow.skills: missing={sorted(workflow_skills-classified)} extra={sorted(classified-workflow_skills)}")
    active_names = {str(skill.get("name", "")) for skill in skills if str(skill.get("name", "")) in workflow_skills and active(skill, profile)}
    if categories["resident"] != active_names:
        errors.append(f"{label}.resident 与 {profile} 实际激活不一致: expected={sorted(active_names)} actual={sorted(categories['resident'])}")



def validate_workflow_routes(item: dict[str, Any], skill_names: set[str], errors: list[str]) -> None:
    workflow_name = str(item.get("name", ""))
    routes = item.get("routes", [])
    if routes is None:
        return
    if not isinstance(routes, list):
        errors.append(f"workflows:{workflow_name} routes 必须是 array")
        return

    workflow_skills = set(list_value(item, "skills"))
    route_names: set[str] = set()
    match_terms: dict[str, str] = {}
    required_fields = [
        "name",
        "match_any",
        "exclude_any",
        "primary_skill",
        "supporting_skills",
        "fallback_skill",
        "mutually_exclusive_skills",
    ]

    for route in routes:
        if not isinstance(route, dict):
            errors.append(f"workflows:{workflow_name} route 必须是 object")
            continue
        route_name = str(route.get("name", ""))
        label = f"workflows:{workflow_name} route:{route_name or '<unnamed>'}"
        for field in required_fields:
            if field not in route:
                errors.append(f"{label} 缺少字段 {field}")
        if not route_name or not re_match_name(route_name):
            errors.append(f"{label} name 非法")
        elif route_name in route_names:
            errors.append(f"workflows:{workflow_name} 重复 route name: {route_name}")
        route_names.add(route_name)

        match_any = list_value(route, "match_any")
        exclude_any = list_value(route, "exclude_any")
        if not match_any:
            errors.append(f"{label} match_any 不能为空")
        normalized_excludes = {term.strip().casefold() for term in exclude_any if term.strip()}
        for term in match_any:
            normalized = term.strip().casefold()
            if not normalized:
                errors.append(f"{label} match_any 包含空值")
                continue
            if normalized in normalized_excludes:
                errors.append(f"{label} match_any 与 exclude_any 重叠: {term}")
            previous = match_terms.get(normalized)
            if previous and previous != route_name:
                errors.append(
                    f"workflows:{workflow_name} route 匹配词重复: {term} ({previous} 与 {route_name})"
                )
            match_terms[normalized] = route_name

        primary = str(route.get("primary_skill", ""))
        supporting = set(list_value(route, "supporting_skills"))
        fallback = str(route.get("fallback_skill", ""))
        mutually_exclusive = set(list_value(route, "mutually_exclusive_skills"))
        if not primary:
            errors.append(f"{label} primary_skill 不能为空")
        elif primary not in skill_names:
            errors.append(f"{label} 引用未知 primary skill: {primary}")
        elif primary not in workflow_skills:
            errors.append(f"{label} primary skill 未列入 workflow.skills: {primary}")

        for role, values in [
            ("supporting", supporting),
            ("mutually_exclusive", mutually_exclusive),
        ]:
            for skill in values:
                if skill not in skill_names:
                    errors.append(f"{label} 引用未知 {role} skill: {skill}")
                if role == "supporting" and skill not in workflow_skills:
                    errors.append(f"{label} supporting skill 未列入 workflow.skills: {skill}")
        if fallback:
            if fallback not in skill_names:
                errors.append(f"{label} 引用未知 fallback skill: {fallback}")
            elif fallback not in workflow_skills:
                errors.append(f"{label} fallback skill 未列入 workflow.skills: {fallback}")

        if primary in supporting:
            errors.append(f"{label} primary_skill 不得同时是 supporting skill: {primary}")
        if primary in mutually_exclusive:
            errors.append(f"{label} primary_skill 不得与自身互斥: {primary}")
        if fallback and fallback == primary:
            errors.append(f"{label} fallback_skill 不得等于 primary_skill: {primary}")


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


def validate_runtime_control(value: dict[str, Any], root: pathlib.Path, errors: list[str]) -> None:
    if set(value) != {"schema_version", "engine", "sources", "policy"}:
        errors.append("runtime_control.json 顶层字段必须唯一且完整")
        return
    if value.get("schema_version") != 1:
        errors.append("runtime_control.json schema_version 必须为 1")
    engine = value.get("engine")
    if not isinstance(engine, dict) or set(engine) != {"package", "version", "wheel", "sha256"}:
        errors.append("runtime_control.json engine 字段非法")
        return
    if engine.get("package") != "agent-dev-kit" or engine.get("version") != "4.0.0":
        errors.append("runtime_control.json 必须固定 agent-dev-kit 4.0.0")
    wheel_rel = str(engine.get("wheel", ""))
    wheel = (root / wheel_rel).resolve()
    if root not in wheel.parents or not wheel.is_file():
        errors.append("runtime_control.json wheel 缺失或越界")
    else:
        digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
        if digest != engine.get("sha256"):
            errors.append("runtime_control.json wheel SHA-256 不匹配")
    sources = value.get("sources")
    if not isinstance(sources, dict) or set(sources) != {"state_db", "sessions_root", "journal_dir"}:
        errors.append("runtime_control.json sources 字段非法")
    policy = value.get("policy")
    if not isinstance(policy, dict) or set(policy) != {
        "schema_version", "token", "context", "progress", "gate_policy", "retention"
    }:
        errors.append("runtime_control.json policy 字段非法")
    elif policy.get("schema_version") != "runtime_control.policy/v1":
        errors.append("runtime_control.json policy schema 非法")
    retention = policy.get("retention") if isinstance(policy, dict) else None
    if not isinstance(retention, dict) or retention.get("raw_content_stored") is not False:
        errors.append("runtime_control.json 必须禁止 raw content")


def validate_prompt_experiments(
    items: list[dict[str, Any]],
    profile_names: set[str],
    eval_suite_names: set[str],
    errors: list[str],
) -> None:
    allowed_targets = {"agents-guidance", "skill", "workflow", "slash-command", "system-prompt", "docs"}
    for item in items:
        name = item.get("name", "")
        for field in [
            "enabled",
            "profiles",
            "target",
            "target_paths",
            "hypothesis",
            "variants",
            "evaluation_suite",
            "sample_cases",
            "grader",
            "human_review_required",
            "success_metric",
            "rollback",
            "artifacts",
        ]:
            if field not in item:
                errors.append(f"prompt_experiments:{name} 缺少字段 {field}")
        for profile in list_value(item, "profiles"):
            if profile not in profile_names:
                errors.append(f"prompt_experiments:{name} 引用未知 profile: {profile}")
        target = str(item.get("target", ""))
        if target and target not in allowed_targets:
            errors.append(f"prompt_experiments:{name} target 非法: {target}")
        for path in list_value(item, "target_paths"):
            if unsafe_path(path):
                errors.append(f"prompt_experiments:{name} target_paths 包含不安全路径: {path}")
        if not list_value(item, "target_paths"):
            errors.append(f"prompt_experiments:{name} target_paths 不能为空")
        if not str(item.get("hypothesis", "")).strip():
            errors.append(f"prompt_experiments:{name} hypothesis 不能为空")
        variants = list_dict_value(item, "variants")
        if len(variants) < 2:
            errors.append(f"prompt_experiments:{name} variants 至少需要 2 个")
        for variant in variants:
            if not str(variant.get("name", "")).strip():
                errors.append(f"prompt_experiments:{name} variants 条目缺少 name")
            if not str(variant.get("change_summary", "")).strip():
                errors.append(f"prompt_experiments:{name} variants 条目缺少 change_summary")
        suite = str(item.get("evaluation_suite", ""))
        if suite and suite not in eval_suite_names:
            errors.append(f"prompt_experiments:{name} 引用未知 evaluation_suite: {suite}")
        if not list_value(item, "sample_cases"):
            errors.append(f"prompt_experiments:{name} sample_cases 不能为空")
        grader = item.get("grader", {})
        if not isinstance(grader, dict):
            errors.append(f"prompt_experiments:{name} grader 必须是 object")
        elif not str(grader.get("type", "")).strip() or not list_value(grader, "rubric"):
            errors.append(f"prompt_experiments:{name} grader 必须包含 type 和 rubric")
        if item.get("human_review_required") is not True:
            errors.append(f"prompt_experiments:{name} human_review_required 必须为 true")
        for field in ["success_metric", "rollback"]:
            if not str(item.get(field, "")).strip():
                errors.append(f"prompt_experiments:{name} {field} 不能为空")
        if not list_value(item, "artifacts"):
            errors.append(f"prompt_experiments:{name} artifacts 不能为空")


def validate_trace_eval_contracts(
    items: list[dict[str, Any]],
    profile_names: set[str],
    errors: list[str],
) -> None:
    for item in items:
        name = item.get("name", "")
        for field in [
            "enabled",
            "profiles",
            "scope",
            "trace_sources",
            "rubric",
            "min_score",
            "required_events",
            "forbidden_events",
            "commands",
            "artifacts",
            "promotion_gate",
        ]:
            if field not in item:
                errors.append(f"trace_eval_contracts:{name} 缺少字段 {field}")
        for profile in list_value(item, "profiles"):
            if profile not in profile_names:
                errors.append(f"trace_eval_contracts:{name} 引用未知 profile: {profile}")
        if not str(item.get("scope", "")).strip():
            errors.append(f"trace_eval_contracts:{name} scope 不能为空")
        for field in ["trace_sources", "required_events", "forbidden_events", "commands", "artifacts"]:
            if not list_value(item, field):
                errors.append(f"trace_eval_contracts:{name} {field} 不能为空")
        rubric = list_dict_value(item, "rubric")
        if not rubric:
            errors.append(f"trace_eval_contracts:{name} rubric 不能为空")
        total_weight = 0.0
        for rule in rubric:
            if not str(rule.get("criterion", "")).strip():
                errors.append(f"trace_eval_contracts:{name} rubric 条目缺少 criterion")
            weight = rule.get("weight", 0)
            if not isinstance(weight, (int, float)) or weight <= 0:
                errors.append(f"trace_eval_contracts:{name} rubric.weight 必须大于 0")
            else:
                total_weight += float(weight)
        if rubric and abs(total_weight - 1.0) > 0.001:
            errors.append(f"trace_eval_contracts:{name} rubric.weight 总和必须为 1")
        score = item.get("min_score", 0)
        if not isinstance(score, (int, float)) or score < 0 or score > 1:
            errors.append(f"trace_eval_contracts:{name} min_score 必须在 0..1")
        if not str(item.get("promotion_gate", "")).strip():
            errors.append(f"trace_eval_contracts:{name} promotion_gate 不能为空")


def validate_context_state_contracts(
    items: list[dict[str, Any]],
    profile_names: set[str],
    errors: list[str],
) -> None:
    required_layers = ["stable", "dynamic", "evidence", "excluded"]
    for item in items:
        name = item.get("name", "")
        for field in [
            "enabled",
            "profiles",
            "scope",
            "layers",
            "validation_commands",
            "forbidden_promotions",
            "artifacts",
        ]:
            if field not in item:
                errors.append(f"context_state_contracts:{name} 缺少字段 {field}")
        for profile in list_value(item, "profiles"):
            if profile not in profile_names:
                errors.append(f"context_state_contracts:{name} 引用未知 profile: {profile}")
        if not str(item.get("scope", "")).strip():
            errors.append(f"context_state_contracts:{name} scope 不能为空")
        layers = item.get("layers", {})
        if not isinstance(layers, dict):
            errors.append(f"context_state_contracts:{name} layers 必须是 object")
        else:
            for layer_name in required_layers:
                layer = layers.get(layer_name)
                if not isinstance(layer, dict):
                    errors.append(f"context_state_contracts:{name} layers 缺少 {layer_name}")
                    continue
                for field in ["required_fields", "destinations", "promotion_gate"]:
                    if field not in layer:
                        errors.append(f"context_state_contracts:{name} layers.{layer_name} 缺少字段 {field}")
                if not list_value(layer, "required_fields"):
                    errors.append(f"context_state_contracts:{name} layers.{layer_name}.required_fields 不能为空")
                if not list_value(layer, "destinations"):
                    errors.append(f"context_state_contracts:{name} layers.{layer_name}.destinations 不能为空")
                if not str(layer.get("promotion_gate", "")).strip():
                    errors.append(f"context_state_contracts:{name} layers.{layer_name}.promotion_gate 不能为空")
            excluded = layers.get("excluded", {})
            if isinstance(excluded, dict) and "never" not in str(excluded.get("promotion_gate", "")).lower():
                errors.append(f"context_state_contracts:{name} excluded promotion_gate 必须包含 never")
        for field in ["validation_commands", "forbidden_promotions", "artifacts"]:
            if not list_value(item, field):
                errors.append(f"context_state_contracts:{name} {field} 不能为空")


def validate_automation_run_records(
    items: list[dict[str, Any]],
    automation_names: set[str],
    errors: list[str],
) -> None:
    allowed_status = {"record-template", "pending-review", "reviewed", "archived", "discarded"}
    allowed_priorities = {"low", "review", "high", "urgent"}
    for item in items:
        name = item.get("name", "")
        for field in [
            "enabled",
            "automation",
            "run_id",
            "run_at",
            "trigger",
            "status",
            "triage",
            "cleanup",
            "retention",
            "human_review",
            "artifacts",
        ]:
            if field not in item:
                errors.append(f"automation_run_records:{name} 缺少字段 {field}")
        if item.get("enabled"):
            errors.append(f"automation_run_records:{name} 运行记录不得 enabled=true")
        automation = str(item.get("automation", ""))
        if automation and automation not in automation_names:
            errors.append(f"automation_run_records:{name} 引用未知 automation: {automation}")
        for field in ["run_id", "run_at", "trigger"]:
            if not str(item.get(field, "")).strip():
                errors.append(f"automation_run_records:{name} {field} 不能为空")
        status = str(item.get("status", ""))
        if status and status not in allowed_status:
            errors.append(f"automation_run_records:{name} status 非法: {status}")
        triage = item.get("triage", {})
        if not isinstance(triage, dict):
            errors.append(f"automation_run_records:{name} triage 必须是 object")
        else:
            for field in ["summary", "priority", "allowed_outputs", "forbidden_actions"]:
                if field not in triage:
                    errors.append(f"automation_run_records:{name} triage 缺少字段 {field}")
            if not str(triage.get("summary", "")).strip():
                errors.append(f"automation_run_records:{name} triage.summary 不能为空")
            priority = str(triage.get("priority", ""))
            if priority and priority not in allowed_priorities:
                errors.append(f"automation_run_records:{name} triage.priority 非法: {priority}")
            if not list_value(triage, "allowed_outputs"):
                errors.append(f"automation_run_records:{name} triage.allowed_outputs 不能为空")
            forbidden = set(list_value(triage, "forbidden_actions"))
            for action in ["send", "commit", "delete", "publish"]:
                if action not in forbidden:
                    errors.append(f"automation_run_records:{name} triage.forbidden_actions 必须包含 {action}")
        cleanup = item.get("cleanup", {})
        if not isinstance(cleanup, dict):
            errors.append(f"automation_run_records:{name} cleanup 必须是 object")
        else:
            if "performed" not in cleanup:
                errors.append(f"automation_run_records:{name} cleanup 缺少字段 performed")
            if not list_value(cleanup, "actions"):
                errors.append(f"automation_run_records:{name} cleanup.actions 不能为空")
        retention = item.get("retention", {})
        if not isinstance(retention, dict):
            errors.append(f"automation_run_records:{name} retention 必须是 object")
        else:
            for field in ["policy", "expires_after"]:
                if not str(retention.get(field, "")).strip():
                    errors.append(f"automation_run_records:{name} retention.{field} 不能为空")
        human_review = item.get("human_review", {})
        if not isinstance(human_review, dict):
            errors.append(f"automation_run_records:{name} human_review 必须是 object")
        else:
            if human_review.get("required") is not True:
                errors.append(f"automation_run_records:{name} human_review.required 必须为 true")
            if not str(human_review.get("status", "")).strip():
                errors.append(f"automation_run_records:{name} human_review.status 不能为空")
            if not str(human_review.get("reviewer", "")).strip():
                errors.append(f"automation_run_records:{name} human_review.reviewer 不能为空")
        if not list_value(item, "artifacts"):
            errors.append(f"automation_run_records:{name} artifacts 不能为空")


def validate_skill_mcp_dependencies(
    items: list[dict[str, Any]],
    profile_names: set[str],
    skill_names: set[str],
    mcp_server_names: set[str],
    errors: list[str],
) -> None:
    allowed_modes = {"read-only", "draft-write", "external-write"}
    required_forbidden = {"credential-access", "destructive-action", "silent-enable-mcp"}
    for item in items:
        name = item.get("name", "")
        for field in [
            "enabled",
            "profiles",
            "skill",
            "mcp_servers",
            "access_mode",
            "required_tools",
            "allowed_actions",
            "forbidden_actions",
            "approval_required",
            "fallback",
            "verification",
            "artifacts",
        ]:
            if field not in item:
                errors.append(f"skill_mcp_dependencies:{name} 缺少字段 {field}")
        for profile in list_value(item, "profiles"):
            if profile not in profile_names:
                errors.append(f"skill_mcp_dependencies:{name} 引用未知 profile: {profile}")
        skill = str(item.get("skill", ""))
        if skill and skill not in skill_names:
            errors.append(f"skill_mcp_dependencies:{name} 引用未知 skill: {skill}")
        for server in list_value(item, "mcp_servers"):
            if server not in mcp_server_names:
                errors.append(f"skill_mcp_dependencies:{name} 引用未知 mcp_server: {server}")
        mode = str(item.get("access_mode", ""))
        if mode and mode not in allowed_modes:
            errors.append(f"skill_mcp_dependencies:{name} access_mode 非法: {mode}")
        for field in ["mcp_servers", "required_tools", "allowed_actions", "forbidden_actions", "verification", "artifacts"]:
            if not list_value(item, field):
                errors.append(f"skill_mcp_dependencies:{name} {field} 不能为空")
        if item.get("approval_required") is not True:
            errors.append(f"skill_mcp_dependencies:{name} approval_required 必须为 true")
        forbidden = set(list_value(item, "forbidden_actions"))
        missing_forbidden = sorted(required_forbidden - forbidden)
        if missing_forbidden:
            errors.append(f"skill_mcp_dependencies:{name} forbidden_actions 缺少: {', '.join(missing_forbidden)}")
        if mode in {"draft-write", "external-write"} and "external-write" not in forbidden:
            errors.append(f"skill_mcp_dependencies:{name} 写入类依赖必须禁止 external-write，除非单独建受审契约")
        if not str(item.get("fallback", "")).strip():
            errors.append(f"skill_mcp_dependencies:{name} fallback 不能为空")


def validate_slash_command_runtime_audits(
    items: list[dict[str, Any]],
    profile_names: set[str],
    cli_command_contract_names: set[str],
    cli_command_contracts: list[dict[str, Any]],
    errors: list[str],
) -> None:
    allowed_risk = {"context-control", "review-control", "goal-control", "permission-control", "model-control"}
    contracts_by_name = {item.get("name", ""): item for item in cli_command_contracts if item.get("name")}
    for item in items:
        name = item.get("name", "")
        for field in [
            "enabled",
            "profiles",
            "command_contract",
            "command",
            "risk_class",
            "audit_events",
            "runtime_controls",
            "required_evidence",
            "forbidden_actions",
            "retention",
            "review_required",
            "verification",
            "artifacts",
        ]:
            if field not in item:
                errors.append(f"slash_command_runtime_audits:{name} 缺少字段 {field}")
        for profile in list_value(item, "profiles"):
            if profile not in profile_names:
                errors.append(f"slash_command_runtime_audits:{name} 引用未知 profile: {profile}")
        contract_name = str(item.get("command_contract", ""))
        if contract_name and contract_name not in cli_command_contract_names:
            errors.append(f"slash_command_runtime_audits:{name} 引用未知 command_contract: {contract_name}")
        command = str(item.get("command", ""))
        if not command.startswith("/"):
            errors.append(f"slash_command_runtime_audits:{name} command 必须以 / 开头")
        contract = contracts_by_name.get(contract_name, {})
        if contract and command != str(contract.get("command", "")):
            errors.append(f"slash_command_runtime_audits:{name} command 必须匹配 command_contract: {contract.get('command', '')}")
        risk = str(item.get("risk_class", ""))
        if risk and risk not in allowed_risk:
            errors.append(f"slash_command_runtime_audits:{name} risk_class 非法: {risk}")
        for field in ["audit_events", "runtime_controls", "required_evidence", "forbidden_actions", "verification", "artifacts"]:
            if not list_value(item, field):
                errors.append(f"slash_command_runtime_audits:{name} {field} 不能为空")
        if item.get("review_required") is not True:
            errors.append(f"slash_command_runtime_audits:{name} review_required 必须为 true")
        forbidden = set(list_value(item, "forbidden_actions"))
        if "bypass-verification" not in forbidden:
            errors.append(f"slash_command_runtime_audits:{name} forbidden_actions 必须包含 bypass-verification")
        retention = str(item.get("retention", "")).lower()
        if not retention.strip():
            errors.append(f"slash_command_runtime_audits:{name} retention 不能为空")
        elif "raw session" in retention or "raw-session" in retention:
            errors.append(f"slash_command_runtime_audits:{name} retention 不得保留 raw session")


def validate_official_docs_freshness_gates(
    items: list[dict[str, Any]],
    mcp_server_names: set[str],
    errors: list[str],
) -> None:
    required_metadata = {"source_url", "retrieved_at", "review_status", "expires_at"}
    allowed_review_status = {"review-required", "reviewed", "stale", "rejected"}
    for item in items:
        name = item.get("name", "")
        for field in [
            "enabled",
            "source",
            "mcp_server",
            "source_domains",
            "source_urls",
            "retrieval_required",
            "max_age_days",
            "required_metadata",
            "review_status",
            "stale_action",
            "promotion_targets",
            "verification",
            "rollback",
            "artifacts",
        ]:
            if field not in item:
                errors.append(f"official_docs_freshness_gates:{name} 缺少字段 {field}")
        server = str(item.get("mcp_server", ""))
        if server and server not in mcp_server_names:
            errors.append(f"official_docs_freshness_gates:{name} 引用未知 mcp_server: {server}")
        if server and server != "openaiDeveloperDocs":
            errors.append(f"official_docs_freshness_gates:{name} mcp_server 必须是 openaiDeveloperDocs")
        if item.get("retrieval_required") is not True:
            errors.append(f"official_docs_freshness_gates:{name} retrieval_required 必须为 true")
        max_age = item.get("max_age_days", 0)
        if not isinstance(max_age, int) or max_age < 1 or max_age > 365:
            errors.append(f"official_docs_freshness_gates:{name} max_age_days 必须在 1..365")
        domains = set(list_value(item, "source_domains"))
        if not domains:
            errors.append(f"official_docs_freshness_gates:{name} source_domains 不能为空")
        if not any(domain in {"developers.openai.com", "platform.openai.com", "openai.com"} for domain in domains):
            errors.append(f"official_docs_freshness_gates:{name} source_domains 必须包含 OpenAI 官方域名")
        for url in list_value(item, "source_urls"):
            validate_official_docs_url(name, url, domains, errors)
        if not list_value(item, "source_urls"):
            errors.append(f"official_docs_freshness_gates:{name} source_urls 不能为空")
        metadata = set(list_value(item, "required_metadata"))
        missing_metadata = sorted(required_metadata - metadata)
        if missing_metadata:
            errors.append(f"official_docs_freshness_gates:{name} required_metadata 缺少: {', '.join(missing_metadata)}")
        review_status = str(item.get("review_status", ""))
        if review_status and review_status not in allowed_review_status:
            errors.append(f"official_docs_freshness_gates:{name} review_status 非法: {review_status}")
        for field in ["stale_action", "rollback"]:
            if not str(item.get(field, "")).strip():
                errors.append(f"official_docs_freshness_gates:{name} {field} 不能为空")
        for field in ["promotion_targets", "verification", "artifacts"]:
            if not list_value(item, field):
                errors.append(f"official_docs_freshness_gates:{name} {field} 不能为空")


def validate_permission_profiles(items: list[dict[str, Any]], profile_names: set[str], errors: list[str]) -> None:
    allowed_modes = {"read-only", "workspace-write"}
    allowed_config_modes = {"legacy-sandbox", "permission-profile"}
    allowed_approval = {"on-request", "on-failure", "manual"}
    for item in items:
        name = item.get("name", "")
        for field in [
            "enabled",
            "profiles",
            "mode",
            "active_config_mode",
            "approval_policy",
            "filesystem",
            "network",
            "allowed_sandbox_modes",
            "forbidden_modes",
            "source_urls",
            "verification",
            "rollback",
            "artifacts",
        ]:
            if field not in item:
                errors.append(f"permission_profiles:{name} 缺少字段 {field}")
        for profile in list_value(item, "profiles"):
            if profile not in profile_names:
                errors.append(f"permission_profiles:{name} 引用未知 profile: {profile}")
        mode = str(item.get("mode", ""))
        if mode and mode not in allowed_modes:
            errors.append(f"permission_profiles:{name} mode 非法或过宽: {mode}")
        active_config_mode = str(item.get("active_config_mode", ""))
        if active_config_mode and active_config_mode not in allowed_config_modes:
            errors.append(f"permission_profiles:{name} active_config_mode 非法: {active_config_mode}")
        approval_policy = str(item.get("approval_policy", ""))
        if approval_policy == "never":
            errors.append(f"permission_profiles:{name} approval_policy 不允许 never")
        elif approval_policy and approval_policy not in allowed_approval:
            errors.append(f"permission_profiles:{name} approval_policy 非法: {approval_policy}")
        filesystem = item.get("filesystem", {})
        if not isinstance(filesystem, dict):
            errors.append(f"permission_profiles:{name} filesystem 必须是 object")
        else:
            if not list_value(filesystem, "write_roots"):
                errors.append(f"permission_profiles:{name} filesystem.write_roots 不能为空")
            if not list_value(filesystem, "deny_paths"):
                errors.append(f"permission_profiles:{name} filesystem.deny_paths 不能为空")
        network = item.get("network", {})
        if not isinstance(network, dict):
            errors.append(f"permission_profiles:{name} network 必须是 object")
        else:
            if str(network.get("default", "")) == "allow":
                errors.append(f"permission_profiles:{name} network.default 不允许 allow")
            if "*" in list_value(network, "allowed_domains"):
                errors.append(f"permission_profiles:{name} network.allowed_domains 不允许通配符")
        allowed_sandboxes = set(list_value(item, "allowed_sandbox_modes"))
        if not allowed_sandboxes:
            errors.append(f"permission_profiles:{name} allowed_sandbox_modes 不能为空")
        elif "danger-full-access" in allowed_sandboxes:
            errors.append(f"permission_profiles:{name} allowed_sandbox_modes 不允许 danger-full-access")
        if "danger-full-access" not in set(list_value(item, "forbidden_modes")):
            errors.append(f"permission_profiles:{name} forbidden_modes 必须包含 danger-full-access")
        for url in list_value(item, "source_urls"):
            validate_openai_source_url("permission_profiles", name, url, errors)
        for field in ["source_urls", "verification", "artifacts"]:
            if not list_value(item, field):
                errors.append(f"permission_profiles:{name} {field} 不能为空")
        if not str(item.get("rollback", "")).strip():
            errors.append(f"permission_profiles:{name} rollback 不能为空")


def validate_exec_rules(items: list[dict[str, Any]], profile_names: set[str], errors: list[str]) -> None:
    allowed_decisions = {"allow", "prompt", "deny"}
    broad_allow_prefixes = {"bash", "sh", "python", "python3", "node", "npx", "git", "rm", "curl", "wget"}
    for item in items:
        name = item.get("name", "")
        for field in ["enabled", "profiles", "source_path", "rules", "verification", "rollback", "artifacts"]:
            if field not in item:
                errors.append(f"exec_rules:{name} 缺少字段 {field}")
        for profile in list_value(item, "profiles"):
            if profile not in profile_names:
                errors.append(f"exec_rules:{name} 引用未知 profile: {profile}")
        source_path = str(item.get("source_path", ""))
        if unsafe_path(source_path) or not source_path.startswith("src/codex-home/rules/"):
            errors.append(f"exec_rules:{name} source_path 必须位于 src/codex-home/rules/")
        rules = list_dict_value(item, "rules")
        if not rules:
            errors.append(f"exec_rules:{name} rules 不能为空")
        for rule in rules:
            rule_name = str(rule.get("name", ""))
            pattern = list_value(rule, "pattern")
            decision = str(rule.get("decision", ""))
            if not rule_name:
                errors.append(f"exec_rules:{name} rules 条目缺少 name")
            if not pattern:
                errors.append(f"exec_rules:{name}:{rule_name} pattern 不能为空")
            if decision and decision not in allowed_decisions:
                errors.append(f"exec_rules:{name}:{rule_name} decision 非法: {decision}")
            if decision == "allow" and len(pattern) == 1 and pattern[0] in broad_allow_prefixes:
                errors.append(f"exec_rules:{name}:{rule_name} 不允许 broad allow prefix: {pattern[0]}")
            if not str(rule.get("justification", "")).strip():
                errors.append(f"exec_rules:{name}:{rule_name} justification 不能为空")
            for field in ["match", "not_match"]:
                if not list_value(rule, field):
                    errors.append(f"exec_rules:{name}:{rule_name} {field} 不能为空")
        for field in ["verification", "artifacts"]:
            if not list_value(item, field):
                errors.append(f"exec_rules:{name} {field} 不能为空")
        if not str(item.get("rollback", "")).strip():
            errors.append(f"exec_rules:{name} rollback 不能为空")


def validate_hook_contracts(items: list[dict[str, Any]], profile_names: set[str], errors: list[str]) -> None:
    allowed_events = {
        "SessionStart",
        "PreCompact",
        "PostCompact",
        "UserPromptSubmit",
        "SubagentStart",
        "SubagentStop",
        "PreToolUse",
        "PostToolUse",
        "PermissionRequest",
        "Stop",
    }
    allowed_modes = {"disabled", "report-only", "blocking", "context-injection"}
    for item in items:
        name = item.get("name", "")
        for field in [
            "enabled",
            "profiles",
            "event",
            "matcher",
            "mode",
            "input_contract",
            "output_contract",
            "allowed_actions",
            "forbidden_actions",
            "review_required",
            "retention",
            "source_urls",
            "verification",
            "rollback",
            "artifacts",
        ]:
            if field not in item:
                errors.append(f"hook_contracts:{name} 缺少字段 {field}")
        for profile in list_value(item, "profiles"):
            if profile not in profile_names:
                errors.append(f"hook_contracts:{name} 引用未知 profile: {profile}")
        event = str(item.get("event", ""))
        if event and event not in allowed_events:
            errors.append(f"hook_contracts:{name} event 非法: {event}")
        mode = str(item.get("mode", ""))
        if mode and mode not in allowed_modes:
            errors.append(f"hook_contracts:{name} mode 非法: {mode}")
        for field in ["input_contract", "output_contract", "allowed_actions", "forbidden_actions", "source_urls", "verification", "artifacts"]:
            if not list_value(item, field):
                errors.append(f"hook_contracts:{name} {field} 不能为空")
        if item.get("review_required") is not True:
            errors.append(f"hook_contracts:{name} review_required 必须为 true")
        forbidden = set(list_value(item, "forbidden_actions"))
        if "bypass-sandbox" not in forbidden:
            errors.append(f"hook_contracts:{name} forbidden_actions 必须包含 bypass-sandbox")
        if event == "PreToolUse" and "claim-complete-enforcement" not in forbidden:
            errors.append(f"hook_contracts:{name} PreToolUse 必须禁止 claim-complete-enforcement")
        retention = str(item.get("retention", "")).lower()
        if not retention.strip():
            errors.append(f"hook_contracts:{name} retention 不能为空")
        elif "raw session" in retention or "raw-session" in retention:
            errors.append(f"hook_contracts:{name} retention 不得保留 raw session")
        for url in list_value(item, "source_urls"):
            validate_openai_source_url("hook_contracts", name, url, errors)
        if not str(item.get("rollback", "")).strip():
            errors.append(f"hook_contracts:{name} rollback 不能为空")


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


def validate_official_docs_url(name: str, url: str, allowed_domains: set[str], errors: list[str]) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        errors.append(f"official_docs_freshness_gates:{name} source_urls 必须是 https URL: {url}")
        return
    host = parsed.hostname or ""
    if host not in allowed_domains:
        errors.append(f"official_docs_freshness_gates:{name} source_urls host 未列入 source_domains: {host}")
    if host not in {"developers.openai.com", "platform.openai.com", "openai.com"}:
        errors.append(f"official_docs_freshness_gates:{name} source_urls 必须使用 OpenAI 官方域名: {host}")


def validate_openai_source_url(label: str, name: str, url: str, errors: list[str]) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        errors.append(f"{label}:{name} source_urls 必须是 https URL: {url}")
        return
    host = parsed.hostname or ""
    if host not in {"developers.openai.com", "platform.openai.com", "openai.com"}:
        errors.append(f"{label}:{name} source_urls 必须使用 OpenAI 官方域名: {host}")


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


def workflow_links(workflows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        item["name"]: {
            "profiles": list_value(item, "profiles"),
            "skills": list_value(item, "skills"),
            "context_activation": item.get("context_activation", {}),
            "agents": list_value(item, "agents"),
            "routes": [
                {
                    "name": route.get("name", ""),
                    "primary_skill": route.get("primary_skill", ""),
                    "supporting_skills": list_value(route, "supporting_skills"),
                    "fallback_skill": route.get("fallback_skill", ""),
                    "mutually_exclusive_skills": list_value(route, "mutually_exclusive_skills"),
                }
                for route in item.get("routes", [])
                if isinstance(route, dict)
            ],
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


def prompt_experiment_links(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        item["name"]: {
            "target": item.get("target", ""),
            "profiles": list_value(item, "profiles"),
            "evaluation_suite": item.get("evaluation_suite", ""),
            "human_review_required": item.get("human_review_required", False),
        }
        for item in items
        if item.get("name")
    }


def trace_eval_contract_links(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        item["name"]: {
            "profiles": list_value(item, "profiles"),
            "min_score": item.get("min_score", 0),
            "required_events": list_value(item, "required_events"),
        }
        for item in items
        if item.get("name")
    }


def context_state_contract_links(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        item["name"]: {
            "profiles": list_value(item, "profiles"),
            "scope": item.get("scope", ""),
            "layers": sorted((item.get("layers", {}) or {}).keys()) if isinstance(item.get("layers", {}), dict) else [],
        }
        for item in items
        if item.get("name")
    }


def automation_run_record_links(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        item["name"]: {
            "automation": item.get("automation", ""),
            "run_id": item.get("run_id", ""),
            "status": item.get("status", ""),
        }
        for item in items
        if item.get("name")
    }


def skill_mcp_dependency_links(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        item["name"]: {
            "skill": item.get("skill", ""),
            "mcp_servers": list_value(item, "mcp_servers"),
            "access_mode": item.get("access_mode", ""),
            "approval_required": item.get("approval_required", False),
        }
        for item in items
        if item.get("name")
    }


def slash_command_runtime_audit_links(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        item["name"]: {
            "command_contract": item.get("command_contract", ""),
            "command": item.get("command", ""),
            "risk_class": item.get("risk_class", ""),
            "review_required": item.get("review_required", False),
        }
        for item in items
        if item.get("name")
    }


def official_docs_freshness_gate_links(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        item["name"]: {
            "mcp_server": item.get("mcp_server", ""),
            "max_age_days": item.get("max_age_days", 0),
            "review_status": item.get("review_status", ""),
            "source_domains": list_value(item, "source_domains"),
        }
        for item in items
        if item.get("name")
    }


def permission_profile_links(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        item["name"]: {
            "profiles": list_value(item, "profiles"),
            "mode": item.get("mode", ""),
            "active_config_mode": item.get("active_config_mode", ""),
            "approval_policy": item.get("approval_policy", ""),
        }
        for item in items
        if item.get("name")
    }


def exec_rule_links(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        item["name"]: {
            "profiles": list_value(item, "profiles"),
            "source_path": item.get("source_path", ""),
            "rule_count": len(list_dict_value(item, "rules")),
        }
        for item in items
        if item.get("name")
    }


def hook_contract_links(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        item["name"]: {
            "profiles": list_value(item, "profiles"),
            "event": item.get("event", ""),
            "mode": item.get("mode", ""),
            "review_required": item.get("review_required", False),
        }
        for item in items
        if item.get("name")
    }
