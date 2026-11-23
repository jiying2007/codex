from __future__ import annotations

import json
import pathlib
import re
import os
import hashlib
from typing import Any

import yaml

from .core import Repo, active, parse_frontmatter, CodexAssetError


DEFAULT_LIMIT = 3
MAX_LIMIT = 20
DEFAULT_OUTPUT_BUDGET = 2048
MIN_MATCH_SCORE = 42
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
    "内存泄漏", "内存泄露", "资源泄漏", "无界容器", "FD", "fd",
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
    return "fallback" in {str(tag) for tag in item.get("tags", [])}


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
    if item.get("discovery_path"):
        return pathlib.Path(item["discovery_path"])
    live = codex_home / item["vendor_rel"] / "SKILL.md"
    return live if live.is_file() else repo.source / item["vendor_rel"] / "SKILL.md"


def _allows_implicit_invocation(skill_path: pathlib.Path) -> bool:
    metadata = skill_path.with_name("agents") / "openai.yaml"
    if not metadata.exists():
        return True
    try:
        data = yaml.safe_load(metadata.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise CodexAssetError(f"invalid Skill invocation metadata: {metadata}") from exc
    return isinstance(data, dict) and "policy" not in data


def external_items(repo: Repo) -> tuple[list[dict[str, Any]], list[str]]:
    """Explicit local sources only; never recurse or import executable content."""
    manifest = repo.manifests_dir / "skill_discovery.json"
    if not manifest.is_file():
        return [], []
    config = json.loads(manifest.read_text(encoding="utf-8"))
    if config.get("schema_version") != 1 or not isinstance(config.get("sources"), list):
        raise CodexAssetError("invalid skill discovery manifest")
    items, unavailable = [], []
    seen_names, seen_sources = set(), set()
    for source in config["sources"]:
        sid = source.get("source_id", "")
        names = source.get("allowed_names", [])
        rel = pathlib.PurePosixPath(source.get("skills_rel", ""))
        if (not re.fullmatch(r"[a-z0-9][a-z0-9-]*", sid)
                or not isinstance(names, list) or rel.is_absolute() or ".." in rel.parts
                or not rel.parts):
            raise CodexAssetError("invalid skill discovery source")
        if sid in seen_sources:
            raise CodexAssetError("duplicate skill discovery source")
        seen_sources.add(sid)
        root = pathlib.Path(os.environ.get(source.get("root_env", "")) or source["default_root"]).expanduser().resolve()
        skills = root.joinpath(*rel.parts)
        for name in names:
            if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name):
                raise CodexAssetError("invalid discovery skill name")
            # Manifest source order is explicit precedence for external names;
            # a repeated name never consumes another candidate slot.
            if name in seen_names:
                continue
            path = skills / name / "SKILL.md"
            if not path.is_file():
                continue
            try:
                path.resolve().relative_to(root)
            except ValueError:
                raise CodexAssetError("discovery skill escapes configured root")
            meta = parse_frontmatter(path)
            if meta.get("name") != name:
                raise CodexAssetError("discovery skill identity mismatch")
            seen_names.add(name)
            items.append({"name": name, "enabled": True, "profiles": [],
                          "tags": ["embedded", name], "discovery_path": str(path),
                          "source_id": sid, "review_status": "accepted"})
        if not skills.is_dir():
            unavailable.append(sid)
    return items, unavailable


_OBJECT_PREFIX = re.compile(
    r"(?:[\s`'“”\"‘’，,:：]|the\b|this\b|that\b|my\b|our\b|"
    r"一下|这次的|本次的|此次的|本轮的|这份|我的|这次|本次|此次|本轮|当前)*"
)
_REVIEW_SUFFIX = re.compile(
    r"(?:[\s`'“”\"‘’，,:：]|please\b|改动|差异|补丁|代码|帮我|请|做|进行|作|独立|只读)*"
)
_OBJECT_FIRST = re.compile(r"(?:对|把|将)\s*(?:当前|本轮|这次的)?\s*[`'“\"‘]*$")
_EXPLICIT_REQUEST = re.compile(r"(?:请|帮我|做|进行|please)\s*$")
_NON_REQUEST_PREFIX = re.compile(
    r"(?:如何|怎样|怎么|how\s+to|不要|无需|不必|不需要|do\s+not|don['’]t|no\s+need\s+to)"
    r"(?:\s|独立|只读|去|做|independently\b)*$"
)
_CLAUSE_BOUNDARY = re.compile(
    r"[，。；！？,;!?\n]+|并且|然后|同时|但是|\b(?:and|but|then)\b"
)
_NON_REQUEST_SCOPE = re.compile(
    r"^\s*(?:(?:请|麻烦|先|暂时|please\b)\s*)*"
    r"(?:不要|无需|不必|不需要|别|是否|do\s+not\b|don['’]t\b|no\s+need\s+to\b|should\s+(?:we|i)\b)"
)
_HISTORICAL_REQUEST = re.compile(
    r"^\s*(?:(?:请|麻烦)?\s*(?P<only_zh>只|仅|仅仅)?\s*(?:统计|计数|梳理|归纳|汇总|提炼)\s*(?:一下\s*)?"
    r"(?:历史会话|历史线程|工作记录)|"
    r"(?:please\s+)?(?:(?P<only_en>only|just)\s+)?(?:count|tally|mine|summari[sz]e|analy[sz]e)\s+"
    r"(?:(?:the|our|my)\s+)?(?:session history|prior sessions))"
)


def _qualified_route_terms(query: str, route: dict[str, Any]) -> list[str]:
    historical = _HISTORICAL_REQUEST.match(query)
    if historical and (historical["only_zh"] or historical["only_en"]):
        return []
    required = route["requires_any"]
    if (not isinstance(required, list) or not required
            or any(not isinstance(term, str) or not term.strip() for term in required)):
        return []
    include = {term.strip().casefold() for term in required}
    intents = {term.strip().casefold() for term in route.get("match_any", []) if term.strip()}
    targets = [
        (match, term)
        for term in sorted(include)
        for match in re.finditer(re.escape(term), query)
    ]
    matches = set()
    for intent in sorted(intents):
        pattern = re.escape(intent)
        if intent.isascii():
            pattern = rf"(?<![a-z0-9_]){pattern}(?![a-z0-9_])"
        for action in re.finditer(pattern, query):
            prefix = query[:action.start()]
            clause_prefix = _CLAUSE_BOUNDARY.split(prefix)[-1]
            if (_NON_REQUEST_PREFIX.search(prefix)
                    or _NON_REQUEST_SCOPE.match(clause_prefix)
                    or _HISTORICAL_REQUEST.match(clause_prefix)):
                continue
            for target, term in targets:
                if action.end() <= target.start() and _OBJECT_PREFIX.fullmatch(query[action.end():target.start()]):
                    matches.update((intent, term))
                elif target.end() <= action.start():
                    between = query[target.end():action.start()]
                    if (_REVIEW_SUFFIX.fullmatch(between)
                            and (_OBJECT_FIRST.search(query[:target.start()])
                                 or re.search(r"please\b|帮我|请", between))):
                        matches.update((intent, term))
                elif (action.start() <= target.start() and target.end() <= action.end()
                      and _EXPLICIT_REQUEST.search(query[:action.start()])):
                    matches.update((intent, term))
    return sorted(matches)


def _route_hints(repo: Repo, query: str) -> dict[str, dict[str, Any]]:
    manifest_path = repo.manifests_dir / "workflows.json"
    if not manifest_path.is_file():
        return {}
    folded_query = query.casefold()
    candidates: list[tuple[tuple[bool, int], str, dict[str, Any], list[str]]] = []
    workflows = json.loads(manifest_path.read_text(encoding="utf-8")).get("workflows", [])
    for workflow in workflows:
        for route in workflow.get("routes", []):
            excludes = [str(term).casefold() for term in route.get("exclude_any", [])]
            if any(term and term in folded_query for term in excludes):
                continue
            if "requires_any" in route:
                matches = _qualified_route_terms(folded_query, route)
                if matches:
                    candidates.append(((True, len(matches)), str(workflow.get("name", "")), route, matches))
                continue
            matches = [
                str(term)
                for term in route.get("match_any", [])
                if str(term) and str(term).casefold() in folded_query
            ]
            if matches:
                candidates.append(((False, len(matches)), str(workflow.get("name", "")), route, matches))
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


def _profile_catalog_mode(repo: Repo, profile: str) -> str:
    for item in repo.manifest("profiles.json").get("profiles", []):
        if item.get("name") == profile:
            return str(item.get("catalog_mode", "eager"))
    return "eager"


def _context_activation_modes(repo: Repo) -> dict[str, str]:
    priority = {"lazy": 1, "fallback": 2, "resident": 3}
    modes: dict[str, str] = {}
    manifest_path = repo.manifests_dir / "workflows.json"
    if not manifest_path.is_file():
        return modes
    workflows = json.loads(manifest_path.read_text(encoding="utf-8")).get("workflows", [])
    for workflow in workflows:
        activation = workflow.get("context_activation")
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
    named_skills = set(re.findall(r"[a-z0-9_-]+", query.casefold()))
    route_hints = _route_hints(repo, query)
    activation_modes = _context_activation_modes(repo) if _profile_catalog_mode(repo, profile) == "lazy" else {}
    managed = repo.manifest("skills.json").get("skills", [])
    extras, unavailable = external_items(repo)
    managed_names = {x["name"] for x in managed}
    shadowed = sorted({x["name"] for x in extras if x["name"] in managed_names})
    inventory = managed + [x for x in extras if x["name"] not in managed_names]
    for item in inventory:
        if not item.get("enabled", True) or item.get("review_status") in {"pending", "rejected"}:
            continue
        fallback = _is_fallback(item)
        is_active = active(item, profile)
        if active_only and not is_active:
            continue
        skill_path = (pathlib.Path(item["discovery_path"]) if item.get("discovery_path")
                      else repo.source / item["vendor_rel"] / "SKILL.md")
        load_path = _load_path(repo, home, item)
        explicitly_named = item["name"].casefold() in named_skills
        if not explicitly_named and (
            not _allows_implicit_invocation(skill_path)
            or (load_path != skill_path and not _allows_implicit_invocation(load_path))
        ):
            continue
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
        if explicitly_named and "name" not in matched_fields:
            score += 160
            matched_fields.append("name")
            matched_terms.append(item["name"])
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
        if not route_hint and not explicitly_named:
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
                "load_path": str(load_path),
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
                "source_id": item.get("source_id", "managed"),
                "content_sha256": hashlib.sha256(load_path.read_bytes()).hexdigest(),
            }
        )
    candidates.sort(key=lambda item: (
        item["name"] not in named_skills,
        item["name"] not in named_skills and (item["route"] or {}).get("role") == "mutually_exclusive",
        -item["score"], item["activation"] != "active", item["name"],
    ))
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
            "fallback_condition": "routing ambiguity, high-risk conclusion, or a project-declared internal fallback",
            "no_skill_allowed": True,
        },
        "no_skill_reason": (
            ""
            if selected
            else "no high-confidence match; direct execution is allowed for micro tasks"
        ),
        "output_truncated": total_matches > len(selected),
        "discovery": {"managed_precedence": True, "shadowed_names": shadowed,
                      "unavailable_sources": unavailable,
                      "zero_hit_proves_absence": False},
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
        payload.pop("discovery", None)
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
