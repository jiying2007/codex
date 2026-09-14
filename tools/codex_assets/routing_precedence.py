from __future__ import annotations

import json
import pathlib
from typing import Any

from .core import Repo, active, read_json


ADK_WORKFLOW_REQUIREMENTS = {
    "adk-delivery-gate": {
        "required": {
            "adk-requirements-triage",
            "adk-task-breakdown",
            "adk-verification-before-completion",
            "adk-commit-pr-quality-gate",
        },
        "forbidden_tags": {"superpowers"},
    },
    "implementation-quality": {
        "required": {
            "adk-requirements-triage",
            "adk-task-breakdown",
            "adk-systematic-debugging",
            "adk-test-strategy",
            "adk-code-review-loop",
            "adk-commit-pr-quality-gate",
            "adk-verification-before-completion",
        },
        "forbidden_tags": {"superpowers"},
    },
    "parallel-collab": {
        "required": {
            "codex-parallel-collab",
            "adk-parallel-agent-governance",
            "adk-worktree-governance",
            "adk-branch-closeout",
            "worktree-closeout",
        },
        "forbidden_tags": {"superpowers"},
    },
}

RETIRED_COMPAT_PROFILE = "superpowers-compat"
RETIRED_COMPAT_WORKFLOW = "superpowers-compat-fallback"


def check(root: str | pathlib.Path) -> tuple[list[str], dict[str, Any]]:
    repo = Repo.from_path(root)
    assets = repo.assets
    default_profile = assets.get("default_profile", "default")
    profiles = {item.get("name") for item in repo.manifest("profiles.json").get("profiles", [])}
    skills = repo.manifest("skills.json").get("skills", [])
    workflows = repo.manifest("workflows.json").get("workflows", [])
    skills_by_name = {item["name"]: item for item in skills if item.get("name")}
    workflows_by_name = {item["name"]: item for item in workflows if item.get("name")}

    errors: list[str] = []
    superpowers = [item for item in skills if "superpowers" in item.get("tags", [])]
    if RETIRED_COMPAT_PROFILE in profiles:
        errors.append(f"retired compatibility profile 仍存在: {RETIRED_COMPAT_PROFILE}")
    if superpowers:
        errors.append("retired compatibility skills 仍存在: " + ", ".join(sorted(item["name"] for item in superpowers)))
    if RETIRED_COMPAT_WORKFLOW in workflows_by_name:
        errors.append(f"retired compatibility workflow 仍存在: {RETIRED_COMPAT_WORKFLOW}")

    for workflow_name, rule in ADK_WORKFLOW_REQUIREMENTS.items():
        workflow = workflows_by_name.get(workflow_name)
        if not workflow:
            errors.append(f"缺少 ADK workflow: {workflow_name}")
            continue
        if default_profile not in workflow.get("profiles", []):
            errors.append(f"{workflow_name} 未绑定 default profile {default_profile}")
        workflow_skills = set(workflow.get("skills", []))
        missing_required = sorted(rule["required"] - workflow_skills)
        if missing_required:
            errors.append(f"{workflow_name} 缺少 ADK primary skill: {', '.join(missing_required)}")
        forbidden = []
        for skill_name in workflow_skills:
            skill = skills_by_name.get(skill_name)
            if skill and set(skill.get("tags", [])) & rule["forbidden_tags"]:
                forbidden.append(skill_name)
        if forbidden:
            errors.append(f"{workflow_name} 包含 forbidden fallback skill: {', '.join(sorted(forbidden))}")

    summary = {
        "schema_version": 1,
        "default_profile": default_profile,
        "retired_compat_profile_present": RETIRED_COMPAT_PROFILE in profiles,
        "retired_compat_skills": sorted(item["name"] for item in superpowers),
        "retired_compat_workflow_present": RETIRED_COMPAT_WORKFLOW in workflows_by_name,
        "checked_workflows": sorted(ADK_WORKFLOW_REQUIREMENTS),
    }
    return errors, summary


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="check-routing-precedence")
    parser.add_argument("--root", default=str(pathlib.Path(__file__).resolve().parents[2]))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    errors, summary = check(args.root)
    if args.json:
        payload = dict(summary)
        payload["status"] = "pass" if not errors else "fail"
        payload["errors"] = errors
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for error in errors:
            print(f"[ERROR] {error}")
        print(
            "[INFO] "
            f"default_profile={summary['default_profile']} "
            f"retired_compat_skills={len(summary['retired_compat_skills'])} "
            f"retired_compat_profile_present={int(summary['retired_compat_profile_present'])}"
        )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
