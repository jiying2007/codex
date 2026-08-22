from __future__ import annotations

import json
import pathlib
import re
from typing import Any

from .core import Repo, active, parse_frontmatter


DEFAULT_LIMIT = 3
MAX_LIMIT = 20
DEFAULT_OUTPUT_BUDGET = 2048
MIN_MATCH_SCORE = 42
FALLBACK_TAGS = {"superpowers"}
EMBEDDED_QUERY_MARKERS = {
    "adb",
    "amp",
    "bootloader",
    "bsp",
    "core dump",
    "dma",
    "dmesg",
    "firmware",
    "kernel",
    "mcu",
    "pcr02",
    "rtos",
    "sigmastar",
    "soc",
    "串口",
    "固件",
    "嵌入式",
    "板级",
    "烧录",
    "芯片",
    "设备",
    "驱动",
}
ROUTE_ROLE_SCORES = {
    "primary": 320,
    "supporting": 32,
    "fallback": 12,
    "mutually_exclusive": -96,
}
STOP_TERMS = {
    "skill",
    "skills",
    "任务",
    "使用",
    "需要",
    "帮我",
    "处理",
    "分析",
    "问题",
    "优化",
}


def _text(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(str(item) for item in value)
    return str(value or "")


def _list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)] if value else []


def _compact(value: str, limit: int = 160) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: max(limit - 1, 0)].rstrip() + "…"


def query_terms(query: str) -> list[str]:
    normalized = query.casefold()
    terms = set(re.findall(r"[a-z0-9][a-z0-9_.+-]*", normalized))
    for run in re.findall(r"[\u3400-\u9fff]+", normalized):
        if 2 <= len(run) <= 12:
            terms.add(run)
        for width in (2, 3, 4):
            for start in range(max(len(run) - width + 1, 0)):
                terms.add(run[start : start + width])
    return sorted(
        (term for term in terms if len(term) >= 2 and term not in STOP_TERMS),
        key=lambda item: (-len(item), item),
    )


def _score(query: str, fields: dict[str, str]) -> tuple[int, list[str], list[str]]:
    query_normalized = " ".join(query.casefold().split())
    score = 0
    matched_fields: set[str] = set()
    matched_terms: set[str] = set()
    if len(query_normalized) >= 2 and query_normalized in " ".join(fields.values()):
        score += 160
        matched_fields.add("phrase")
    for term in query_terms(query):
        term_score = 0
        if term == fields["name"]:
            term_score += 160
            matched_fields.add("name")
        elif term in fields["name"]:
            term_score += 48
            matched_fields.add("name")
        if term in fields["tags"]:
            term_score += 30
            matched_fields.add("tags")
        if term in fields["triggers"]:
            term_score += 26
            matched_fields.add("triggers")
        if term in fields["description"]:
            term_score += 14
            matched_fields.add("description")
        if term_score:
            score += term_score
            matched_terms.add(term)
    return score, sorted(matched_fields), sorted(matched_terms, key=lambda item: (-len(item), item))[:6]


def _is_fallback(item: dict[str, Any]) -> bool:
    return bool(set(item.get("tags", [])) & FALLBACK_TAGS) or item.get("profiles", []) == ["superpowers-compat"]


def _embedded_only(item: dict[str, Any], description: str) -> bool:
    name = str(item.get("name", "")).casefold()
    tags = {str(tag).casefold() for tag in item.get("tags", [])}
    folded_description = description.casefold()
    return (
        "embedded" in tags
        or "embedded" in name
        or "嵌入式" in folded_description
    )


def _query_has_embedded_context(query: str) -> bool:
    folded = query.casefold()
    return any(marker in folded for marker in EMBEDDED_QUERY_MARKERS)


def _load_path(repo: Repo, codex_home: pathlib.Path, item: dict[str, Any]) -> pathlib.Path:
    live = codex_home / item["vendor_rel"] / "SKILL.md"
    return live if live.is_file() else repo.source / item["vendor_rel"] / "SKILL.md"


def _route_hints(repo: Repo, query: str) -> dict[str, dict[str, Any]]:
    manifest_path = repo.manifests_dir / "workflows.json"
    if not manifest_path.is_file():
        return {}
    folded_query = query.casefold()
    candidates: list[tuple[int, str, dict[str, Any], list[str]]] = []
    workflows = json.loads(manifest_path.read_text(encoding="utf-8")).get("workflows", [])
    for workflow in workflows:
        for route in workflow.get("routes", []):
            excludes = [str(term).casefold() for term in route.get("exclude_any", [])]
            if any(term and term in folded_query for term in excludes):
                continue
            matches = [
                str(term)
                for term in route.get("match_any", [])
                if str(term) and str(term).casefold() in folded_query
            ]
            if matches:
                candidates.append((len(matches), str(workflow.get("name", "")), route, matches))
    if not candidates:
        return {}
    best_score = max(item[0] for item in candidates)
    best = [item for item in candidates if item[0] == best_score]
    if len(best) != 1:
        return {}

    _, workflow_name, route, matches = best[0]
    roles: list[tuple[str, str]] = [(str(route.get("primary_skill", "")), "primary")]
    roles.extend((str(skill), "supporting") for skill in route.get("supporting_skills", []))
    fallback = str(route.get("fallback_skill", ""))
    if fallback:
        roles.append((fallback, "fallback"))
    roles.extend((str(skill), "mutually_exclusive") for skill in route.get("mutually_exclusive_skills", []))
    hints: dict[str, dict[str, Any]] = {}
    for skill, role in roles:
        if not skill:
            continue
        score = ROUTE_ROLE_SCORES[role]
        if skill in hints and int(hints[skill]["score"]) >= score:
            continue
        hints[skill] = {
            "score": score,
            "workflow": workflow_name,
            "route": str(route.get("name", "")),
            "role": role,
            "terms": matches,
        }
    return hints


def _token_lean_activation_modes(repo: Repo) -> dict[str, str]:
    priority = {"lazy": 1, "fallback": 2, "resident": 3}
    modes: dict[str, str] = {}
    manifest_path = repo.manifests_dir / "workflows.json"
    if not manifest_path.is_file():
        return modes
    workflows = json.loads(manifest_path.read_text(encoding="utf-8")).get("workflows", [])
    for workflow in workflows:
        activation = workflow.get("token_lean_activation")
        if not isinstance(activation, dict):
            continue
        for mode in ("resident", "lazy", "fallback"):
            for skill in _list(activation.get(mode, [])):
                previous = modes.get(skill, "")
                if priority[mode] > priority.get(previous, 0):
                    modes[skill] = mode
    return modes


def catalog_metrics(repo: Repo, profile: str, display_root: str = "~/.codex") -> dict[str, int | str]:
    count = 0
    catalog_bytes = 0
    description_bytes = 0
    for item in repo.manifest("skills.json").get("skills", []):
        if not active(item, profile):
            continue
        skill_path = repo.source / item["vendor_rel"] / "SKILL.md"
        description = _text(parse_frontmatter(skill_path).get("description", ""))
        shown_path = f"{display_root.rstrip('/')}/{item['vendor_rel']}/SKILL.md"
        line = f"- {item['name']}: {description} (file: {shown_path})\n"
        count += 1
        catalog_bytes += len(line.encode("utf-8"))
        description_bytes += len(description.encode("utf-8"))
    return {
        "profile": profile,
        "active_count": count,
        "catalog_bytes": catalog_bytes,
        "description_bytes": description_bytes,
    }


def search_skills(
    repo: Repo,
    query: str,
    profile: str,
    codex_home: str | pathlib.Path = "~/.codex",
    limit: int = DEFAULT_LIMIT,
    include_fallback: bool = False,
    active_only: bool = False,
    max_output_bytes: int = DEFAULT_OUTPUT_BUDGET,
) -> dict[str, Any]:
    home = pathlib.Path(codex_home).expanduser()
    candidates: list[dict[str, Any]] = []
    fallback_excluded = 0
    route_hints = _route_hints(repo, query)
    activation_modes = _token_lean_activation_modes(repo) if profile == "token-lean" else {}
    for item in repo.manifest("skills.json").get("skills", []):
        if not item.get("enabled", True) or item.get("review_status") in {"pending", "rejected"}:
            continue
        fallback = _is_fallback(item)
        is_active = active(item, profile)
        if active_only and not is_active:
            continue
        skill_path = repo.source / item["vendor_rel"] / "SKILL.md"
        meta = parse_frontmatter(skill_path)
        description = _text(meta.get("description", ""))
        triggers = _list(meta.get("triggers", []))
        if (
            _embedded_only(item, description)
            and not _query_has_embedded_context(query)
            and item["name"] not in route_hints
        ):
            continue
        fields = {
            "name": item["name"].casefold(),
            "tags": _text(item.get("tags", [])).casefold(),
            "description": description.casefold(),
            "triggers": _text(triggers).casefold(),
        }
        score, matched_fields, matched_terms = _score(query, fields)
        route_hint = route_hints.get(item["name"])
        if route_hint:
            score += int(route_hint["score"])
            matched_fields = sorted(set(matched_fields) | {"workflow-route"})
            matched_terms = sorted(
                set(matched_terms) | set(route_hint["terms"]),
                key=lambda term: (-len(term), term),
            )[:6]
        if score <= 0:
            continue
        if not route_hint and score < MIN_MATCH_SCORE:
            continue
        if not route_hint:
            raw_ascii_terms = re.findall(r"[a-z0-9][a-z0-9_.+-]*", query.casefold())
            raw_ascii_hits = sum(
                1
                for term in raw_ascii_terms
                if any(term in value for value in fields.values())
            )
            if len(raw_ascii_terms) >= 2 and raw_ascii_hits < 2:
                continue
        if fallback and not include_fallback:
            fallback_excluded += 1
            continue
        score += 2 if is_active else 0
        candidates.append(
            {
                "name": item["name"],
                "score": score,
                "activation": "active" if is_active else "deferred",
                "activation_mode": activation_modes.get(
                    item["name"], "resident" if is_active else "deferred"
                ),
                "description": _compact(description),
                "triggers": [_compact(trigger, 72) for trigger in triggers[:2]],
                "load_path": str(_load_path(repo, home, item)),
                "profiles": item.get("profiles", []),
                "why_selected": {"fields": matched_fields, "terms": matched_terms},
                "route": (
                    {
                        "workflow": route_hint["workflow"],
                        "name": route_hint["route"],
                        "role": route_hint["role"],
                    }
                    if route_hint
                    else None
                ),
                "fallback": fallback,
            }
        )
    candidates.sort(key=lambda item: (-item["score"], item["activation"] != "active", item["name"]))
    total_matches = len(candidates)
    selected = candidates[:limit]
    payload: dict[str, Any] = {
        "schema_version": 1,
        "projection": "skill-catalog-summary-v1",
        "status": "pass" if selected else "zero-hit",
        "query": _compact(query, 160),
        "profile": profile,
        "total_matches": total_matches,
        "returned": len(selected),
        "fallback_candidates_excluded": fallback_excluded,
        "candidates": selected,
        "context_contract": {
            "initial_surface": "name, short description, triggers, boundary",
            "deferred_surface": "full SKILL.md, references, scripts, assets",
            "permission_boundary": "deferred loading does not grant write, network, credential, or approval authority",
            "fallback_condition": "routing ambiguity, high-risk conclusion, or explicit Superpowers compatibility request",
            "no_skill_allowed": True,
        },
        "no_skill_reason": (
            ""
            if selected
            else "no high-confidence match; direct execution is allowed for micro tasks"
        ),
        "output_truncated": total_matches > len(selected),
    }
    compact_payload(payload, max_output_bytes)
    return payload


def compact_payload(payload: dict[str, Any], max_output_bytes: int) -> None:
    def size() -> int:
        return len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

    if size() <= max_output_bytes:
        return
    payload["output_truncated"] = True
    for candidate in payload["candidates"]:
        candidate["description"] = _compact(candidate["description"], 80)
        candidate["triggers"] = candidate["triggers"][:1]
    while len(payload["candidates"]) > 1 and size() > max_output_bytes:
        payload["candidates"].pop()
    if size() > max_output_bytes and payload["candidates"]:
        payload["candidates"][0].pop("triggers", None)
        payload["candidates"][0]["why_selected"].pop("terms", None)
    if size() > max_output_bytes:
        payload["context_contract"] = {
            "no_skill_allowed": True,
            "fallback_condition": "ambiguity or high risk requires targeted raw evidence",
        }
    if size() > max_output_bytes and payload["candidates"]:
        payload["candidates"][0].pop("description", None)
        payload["candidates"][0].pop("profiles", None)
    payload["returned"] = len(payload["candidates"])


def validate_context_budgets(repo: Repo) -> list[str]:
    budget = repo.manifest("profiles.json").get("context_budget", {})
    if not budget:
        return []
    errors: list[str] = []
    root_agents = repo.root / "AGENTS.md"
    source_agents = repo.source / "AGENTS.md"
    agents_limit = int(budget.get("agents_max_bytes", 0) or 0)
    if agents_limit > 0:
        for path in (root_agents, source_agents):
            if not path.is_file():
                errors.append(f"context budget 缺少 AGENTS: {path}")
            elif path.stat().st_size > agents_limit:
                errors.append(f"AGENTS 超出预算: {path} bytes={path.stat().st_size} limit={agents_limit}")
        if root_agents.is_file() and source_agents.is_file() and root_agents.read_bytes() != source_agents.read_bytes():
            errors.append("AGENTS 与 src/codex-home/AGENTS.md 不一致")
    profile = repo.assets.get("default_profile", "")
    metrics = catalog_metrics(repo, profile)
    count_limit = int(budget.get("default_profile_max_active_skills", 0) or 0)
    byte_limit = int(budget.get("default_profile_max_catalog_bytes", 0) or 0)
    if count_limit > 0 and int(metrics["active_count"]) > count_limit:
        errors.append(
            f"default skill catalog 条目超出预算: profile={profile} count={metrics['active_count']} limit={count_limit}"
        )
    if byte_limit > 0 and int(metrics["catalog_bytes"]) > byte_limit:
        errors.append(
            f"default skill catalog 字节超出预算: profile={profile} bytes={metrics['catalog_bytes']} limit={byte_limit}"
        )
    return errors


def render_human(payload: dict[str, Any]) -> str:
    lines = [
        f"[INFO] status={payload['status']} profile={payload['profile']} total={payload['total_matches']} returned={payload['returned']}"
    ]
    for item in payload["candidates"]:
        lines.append(f"[{item['activation'].upper()}] {item['name']} score={item['score']} {item['description']}")
        lines.append(f"  path={item['load_path']}")
    if not payload["candidates"]:
        lines.append("[INFO] no matching skill; refine the query or use --include-fallback only for explicit compatibility")
    return "\n".join(lines)
