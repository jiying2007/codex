from __future__ import annotations

import pathlib
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
    return {
        "schema_version": 1,
        "default_profile": repo.assets.get("default_profile", ""),
        "profiles": sorted(item.get("name", "") for item in profiles if item.get("name")),
        "skills": sorted(item.get("name", "") for item in skills if item.get("name")),
        "agents": sorted(item.get("name", "") for item in agents if item.get("name")),
        "workflows": sorted(item.get("name", "") for item in workflows if item.get("name")),
        "project_templates": sorted(item.get("name", "") for item in templates if item.get("name")),
        "overlays": sorted(item.get("name", "") for item in overlays if item.get("name")),
        "workflow_links": workflow_links(workflows),
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
    workflow_names = item_names("workflows", workflows, errors)
    item_names("project-templates", templates, errors)
    item_names("overlays", overlays, errors)
    validate_workflows(workflows, profile_names, skill_names, agent_names, errors)
    validate_project_templates(templates, profile_names, workflow_names, errors)
    validate_overlays(overlays, repo.policies.get("protected_paths", []), errors)
    return errors


def names(manifest: dict[str, Any], key: str) -> set[str]:
    return {item.get("name", "") for item in manifest.get(key, []) if item.get("name")}


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


def list_value(item: dict[str, Any], key: str) -> list[str]:
    value = item.get(key, [])
    if not isinstance(value, list):
        return []
    return [str(part) for part in value]


def unsafe_path(path: str) -> bool:
    return path.startswith("/") or ".." in pathlib.PurePosixPath(path).parts


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
