from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Sequence

ARCHIVE_SCOPES = {"codex-governance", "codex-knowledge", "project-specific", "session-summary", "legacy-local-runtime"}
ARCHIVE_STATUSES = {"open", "closed", "blocked"}
GOVERNANCE_STATUSES = {"active", "superseded", "quarantine"}
MEMORY_ACTIONS = {"archive-only", "candidate", "promote-to-agents", "write-to-memory", "drop-or-review"}
SECRET_ASSIGNMENT = re.compile(r"(?i)(password|passwd|api[_-]?key|secret|token)\s*[:=]\s*[^\s\]\)>,;]+")
PRIVATE_KEY = re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")
ARCHIVE_FILENAME = re.compile(r"^\d{8}-\d{6}-[a-z0-9][a-z0-9._-]*\.md$")


class ArchiveGovernanceError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProjectMatch:
    project_id: str
    matched_path: str
    source: str
    project: dict[str, Any]


def knowledge_hub_root() -> pathlib.Path:
    return pathlib.Path(os.environ.get("KNOWLEDGE_HUB_HOME", "~/knowledge-hub")).expanduser().resolve()


def archive_root(root: str | pathlib.Path) -> pathlib.Path:
    return knowledge_hub_root() / "domains/codex/archive/codex-archive"


def registry_root(root: str | pathlib.Path) -> pathlib.Path:
    return knowledge_hub_root() / "domains/codex/archive/codex-archive-registry"


def read_json(path: pathlib.Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def write_json(path: pathlib.Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_jsonl(path: pathlib.Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ArchiveGovernanceError(f"{path}:{line_no} JSONL 无效: {exc}") from exc
        if not isinstance(item, dict):
            raise ArchiveGovernanceError(f"{path}:{line_no} JSONL 条目必须是 object")
        rows.append(item)
    return rows


def write_jsonl(path: pathlib.Path, rows: Sequence[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def normalize_id(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip().lower()).strip("-")
    return text or "general"


def load_projects(root: str | pathlib.Path) -> list[dict[str, Any]]:
    data = read_json(registry_root(root) / "projects.json", {"projects": []})
    projects = data.get("projects", []) if isinstance(data, dict) else []
    return [item for item in projects if isinstance(item, dict)]


def project_ids(root: str | pathlib.Path) -> set[str]:
    return {str(item.get("project_id")) for item in load_projects(root) if item.get("project_id")}


def project_by_id_or_alias(root: str | pathlib.Path, value: str) -> dict[str, Any] | None:
    needle = value.strip()
    if not needle:
        return None
    for project in load_projects(root):
        if project.get("project_id") == needle or needle in project.get("aliases", []):
            return project
    return None


def resolve_path(value: str | pathlib.Path) -> pathlib.Path:
    return pathlib.Path(value).expanduser().resolve(strict=False)


def is_under(candidate: pathlib.Path, base: pathlib.Path) -> bool:
    try:
        candidate.relative_to(base)
        return True
    except ValueError:
        return False


def match_project_for_path(root: str | pathlib.Path, candidate: str | pathlib.Path, source: str) -> ProjectMatch | None:
    path = resolve_path(candidate)
    matches: list[tuple[int, str, dict[str, Any], str]] = []
    for project in load_projects(root):
        project_id = str(project.get("project_id") or "")
        if not project_id:
            continue
        for repo_path in project.get("repo_paths", []) or []:
            base = resolve_path(str(repo_path))
            if path == base or is_under(path, base):
                matches.append((len(base.as_posix()), base.as_posix(), project, project_id))
    if not matches:
        return None
    matches.sort(key=lambda item: item[0], reverse=True)
    best_len = matches[0][0]
    best = [item for item in matches if item[0] == best_len]
    best_ids = {item[3] for item in best}
    if len(best_ids) > 1:
        raise ArchiveGovernanceError(f"项目路径匹配并列，需显式 --project: {path} -> {', '.join(sorted(best_ids))}")
    _, matched_path, project, project_id = best[0]
    return ProjectMatch(project_id=project_id, matched_path=matched_path, source=source, project=project)


def resolve_project(
    root: str | pathlib.Path,
    explicit_project: str = "",
    source_repo: str = "",
    source_path: str | pathlib.Path = "",
    cwd: str | pathlib.Path = "",
    scope: str = "",
    no_project_detect: bool = False,
) -> ProjectMatch | None:
    if explicit_project.strip():
        project = project_by_id_or_alias(root, explicit_project)
        if not project:
            raise ArchiveGovernanceError(f"未知 project: {explicit_project}")
        repo_paths = project.get("repo_paths") or [""]
        return ProjectMatch(str(project["project_id"]), str(repo_paths[0]), "explicit", project)
    if no_project_detect:
        if scope == "project-specific":
            raise ArchiveGovernanceError("scope=project-specific 时必须提供 --project 或允许自动项目识别")
        return None
    candidates: list[tuple[str, str | pathlib.Path]] = []
    if source_repo:
        candidates.append(("source_repo", source_repo))
    if source_path:
        candidates.append(("source", source_path))
    if cwd:
        candidates.append(("cwd", cwd))
    for source, candidate in candidates:
        match = match_project_for_path(root, candidate, source)
        if match:
            return match
    if scope == "project-specific":
        raise ArchiveGovernanceError("scope=project-specific 但无法匹配 project registry")
    return None


def infer_kind(topic: str, path_rel: str = "") -> str:
    if topic == "session-wrap" or "/session-wrap/" in f"/{path_rel}/":
        return "session-wrap"
    if topic == "memory-curation" or "/memory-curation/" in f"/{path_rel}/":
        return "memory-curation-report"
    if topic == "archive-governance":
        return "archive-governance-report"
    if topic == "daily-summary":
        return "daily-summary"
    if topic == "control-archives":
        return "legacy-runtime-snapshot"
    return "knowledge-note"


def infer_scope(topic: str, kind: str, project_id: str = "") -> str:
    if project_id:
        return "project-specific"
    if topic in {"memory-curation", "archive-governance"}:
        return "codex-governance"
    if topic == "control-archives":
        return "legacy-local-runtime"
    if kind == "session-wrap":
        return "session-summary"
    return "codex-knowledge"


def content_digest(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    if path.is_dir():
        for item in sorted(p for p in path.rglob("*") if p.is_file() and not p.is_symlink()):
            rel = item.relative_to(path).as_posix()
            h.update(rel.encode())
            h.update(b"\0")
            h.update(content_digest(item).encode())
            h.update(b"\0")
        return h.hexdigest()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def title_from_markdown(path: pathlib.Path) -> str:
    if path.is_file() and path.suffix == ".md":
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith("# "):
                return line[2:].strip()
            if line.startswith("## "):
                return line[3:].strip()
    return path.stem


def build_meta_v2(
    root: str | pathlib.Path,
    source: str | pathlib.Path,
    dest: pathlib.Path,
    meta_path: pathlib.Path,
    topic: str,
    title: str = "",
    description: str = "",
    mode: str = "copy",
    explicit_project: str = "",
    source_repo: str = "",
    workstream_id: str = "",
    session_id: str = "",
    status: str = "closed",
    scope: str = "",
    kind: str = "",
    owner: str = "",
    next_action: str = "",
    memory_action: str = "archive-only",
    tags: Sequence[str] | None = None,
    no_project_detect: bool = False,
    cwd: str | pathlib.Path = "",
) -> dict[str, Any]:
    repo_root = pathlib.Path(root).expanduser().resolve()
    topic = normalize_id(topic)
    try:
        rel = dest.relative_to(archive_root(root)).as_posix()
    except ValueError:
        rel = dest.name
    kind = kind or infer_kind(topic, rel)
    project_match = resolve_project(root, explicit_project, source_repo, source, cwd or os.getcwd(), scope, no_project_detect)
    project_id = project_match.project_id if project_match else ""
    scope = scope or infer_scope(topic, kind, project_id)
    if scope not in ARCHIVE_SCOPES:
        raise ArchiveGovernanceError(f"非法 scope: {scope}")
    if scope == "project-specific" and not project_id:
        raise ArchiveGovernanceError("project-specific 归档必须有 project_id")
    archive_id = normalize_id(dest.stem)
    if kind == "session-wrap" and not session_id:
        session_id = archive_id
    if not workstream_id:
        workstream_id = "general" if project_id else ""
    if not owner:
        owner = os.environ.get("USER") or "unknown"
    if status not in ARCHIVE_STATUSES:
        raise ArchiveGovernanceError(f"非法 status: {status}")
    if memory_action not in MEMORY_ACTIONS:
        raise ArchiveGovernanceError(f"非法 memory_action: {memory_action}")
    if status == "open" and not next_action.strip():
        raise ArchiveGovernanceError("status=open 时必须提供 next_action")
    tag_values = sorted({normalize_id(str(item)) for item in (tags or []) if str(item).strip()})
    if project_id:
        tag_values = sorted(set(tag_values + [project_id]))
    try:
        dest_rel = dest.relative_to(repo_root).as_posix()
    except ValueError:
        dest_rel = dest.as_posix()
    try:
        meta_rel = meta_path.relative_to(repo_root).as_posix()
    except ValueError:
        meta_rel = meta_path.as_posix()
    return {
        "schema_version": 2,
        "archive_id": archive_id,
        "archived_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": pathlib.Path(source).expanduser().resolve(strict=False).as_posix(),
        "source_repo": source_repo or (project_match.matched_path if project_match else ""),
        "destination": dest_rel,
        "metadata": meta_rel,
        "topic": topic,
        "kind": kind,
        "scope": scope,
        "project_id": project_id,
        "workstream_id": workstream_id,
        "session_id": session_id,
        "title": title or title_from_markdown(dest) or topic,
        "summary": description or title or topic,
        "description": description,
        "status": status,
        "governance_status": "active",
        "memory_action": memory_action,
        "owner": owner,
        "next_action": next_action,
        "mode": mode,
        "tags": tag_values,
        "content_sha256": content_digest(dest) if dest.exists() else "",
        "sensitivity": "sanitized-no-secret-pattern-detected",
    }


def archive_entries(root: str | pathlib.Path) -> list[pathlib.Path]:
    base = archive_root(root)
    entries: list[pathlib.Path] = []
    for path in base.rglob("*"):
        if not path.is_file():
            continue
        try:
            rel = path.relative_to(base)
        except ValueError:
            continue
        if rel.parts and rel.parts[0] == "_registry":
            continue
        if path.name in {"index.md", "README.md"} or path.name.endswith(".meta.json"):
            continue
        entries.append(path)
    return sorted(entries)


def validate_archive(root: str | pathlib.Path) -> tuple[list[str], list[str]]:
    repo_root = pathlib.Path(root).expanduser().resolve()
    base = archive_root(repo_root)
    errors: list[str] = []
    warnings: list[str] = []
    if not base.is_dir():
        return ["Knowledge Hub Codex archive 不存在"], warnings
    reg = registry_root(repo_root)
    for name in ["projects.json", "workstreams.jsonl", "sessions.jsonl", "topics.json", "schema.md"]:
        if not (reg / name).is_file():
            errors.append(f"缺少 archive registry: {name}")
    projects = project_ids(repo_root)
    topics_data = read_json(reg / "topics.json", {"topics": []})
    topics = {
        str(row.get("topic"))
        for row in (topics_data.get("topics", []) if isinstance(topics_data, dict) else [])
        if isinstance(row, dict) and row.get("topic")
    }
    try:
        session_rows = read_jsonl(reg / "sessions.jsonl")
    except ArchiveGovernanceError as exc:
        errors.append(str(exc))
        session_rows = []
    session_ids = {str(row.get("session_id")) for row in session_rows if row.get("session_id")}
    for path in archive_entries(repo_root):
        rel = path.relative_to(base)
        rel_text = path.relative_to(repo_root).as_posix()
        if len(rel.parts) != 2:
            errors.append(f"归档条目必须位于 topic 一层目录: {rel_text}")
        elif topics and rel.parts[0] not in topics:
            errors.append(f"归档条目 topic 未登记: {rel_text}")
        if path.suffix != ".md":
            errors.append(f"归档条目必须是 Markdown 文档: {rel_text}")
        if not ARCHIVE_FILENAME.match(path.name):
            errors.append(f"归档文件名不符合 YYYYMMDD-HHMMSS-slug.md: {rel_text}")
        if re.search(r"\d{4}-\d{2}-\d{2}", path.name):
            errors.append(f"归档文件名不得在 slug 中重复 ISO 日期: {rel_text}")
        stem = path.stem
        slug = ""
        if re.match(r"^\d{8}-\d{6}-", stem):
            slug = stem[16:]
        elif re.match(r"^\d{8}-", stem):
            slug = stem[9:]
        if re.match(r"^(?:\d{8}|\d{6}|\d{4})-", slug):
            errors.append(f"归档文件名 slug 不得以重复日期或时间开头: {rel_text}")
        if not pathlib.Path(str(path) + ".meta.json").is_file():
            errors.append(f"归档条目缺少 meta: {rel_text}")
    for meta_path in sorted(base.rglob("*.meta.json")):
        source_path = pathlib.Path(str(meta_path)[:-10])
        if not source_path.exists():
            errors.append(f"孤儿 archive meta: {meta_path.relative_to(repo_root).as_posix()}")
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"无效 archive meta JSON: {meta_path.relative_to(repo_root).as_posix()}: {exc}")
            continue
        rel = meta_path.relative_to(repo_root).as_posix()
        if meta.get("schema_version") != 2:
            errors.append(f"archive meta 不是 schema_version=2: {rel}")
            continue
        for field in ["archive_id", "topic", "kind", "scope", "status", "governance_status", "memory_action", "content_sha256"]:
            if not str(meta.get(field, "")).strip():
                errors.append(f"archive meta 缺少字段 {field}: {rel}")
        try:
            body_rel = source_path.relative_to(repo_root).as_posix()
            meta_rel = meta_path.relative_to(repo_root).as_posix()
        except ValueError:
            body_rel = source_path.as_posix()
            meta_rel = meta_path.as_posix()
        if meta.get("archive_id") != source_path.stem:
            errors.append(f"archive_id 必须等于文件 stem: {rel}")
        if meta.get("destination") != body_rel:
            errors.append(f"archive destination 必须使用仓库相对路径: {rel}")
        if meta.get("metadata") != meta_rel:
            errors.append(f"archive metadata 必须使用仓库相对路径: {rel}")
        if meta.get("scope") not in ARCHIVE_SCOPES:
            errors.append(f"archive meta scope 非法: {rel}: {meta.get('scope')}")
        if meta.get("status") not in ARCHIVE_STATUSES:
            errors.append(f"archive meta status 非法: {rel}: {meta.get('status')}")
        if meta.get("governance_status") not in GOVERNANCE_STATUSES:
            errors.append(f"archive meta governance_status 非法: {rel}: {meta.get('governance_status')}")
        if meta.get("memory_action") not in MEMORY_ACTIONS:
            errors.append(f"archive meta memory_action 非法: {rel}: {meta.get('memory_action')}")
        if meta.get("scope") == "project-specific":
            project_id = str(meta.get("project_id") or "")
            if not project_id:
                errors.append(f"project-specific archive 缺少 project_id: {rel}")
            elif project_id not in projects:
                errors.append(f"archive meta 引用未知 project_id: {rel}: {project_id}")
        if meta.get("kind") == "session-wrap":
            session_id = str(meta.get("session_id") or "")
            if not session_id:
                errors.append(f"session-wrap archive 缺少 session_id: {rel}")
            elif session_ids and session_id not in session_ids:
                errors.append(f"session-wrap archive 未登记到 sessions.jsonl: {rel}: {session_id}")
        if meta.get("status") == "open" and (not meta.get("next_action") or not meta.get("owner")):
            errors.append(f"open archive 必须有 owner 和 next_action: {rel}")
        if meta.get("governance_status") == "superseded" and not meta.get("superseded_by"):
            errors.append(f"superseded archive 必须有 superseded_by: {rel}")
        if meta.get("content_sha256") != content_digest(source_path):
            errors.append(f"archive content_sha256 不匹配: {rel}")
        if source_path.is_file() and source_path.suffix in {".md", ".txt", ".json"}:
            text = source_path.read_text(encoding="utf-8", errors="ignore")
            if SECRET_ASSIGNMENT.search(text):
                errors.append(f"archive 命中疑似凭证赋值: {source_path.relative_to(repo_root).as_posix()}")
            if PRIVATE_KEY.search(text):
                errors.append(f"archive 命中 private key marker: {source_path.relative_to(repo_root).as_posix()}")
    for row in session_rows:
        session_id = str(row.get("session_id") or "")
        if not session_id:
            errors.append("sessions.jsonl 条目缺少 session_id")
        archive_path = str(row.get("archive_path") or "")
        if archive_path and not (repo_root / archive_path).is_file():
            errors.append(f"sessions.jsonl archive_path 不存在: {session_id}: {archive_path}")
        if row.get("status") == "open" and not row.get("next_action"):
            errors.append(f"sessions.jsonl open session 缺少 next_action: {session_id}")
    return errors, warnings


def run_check(root: str | pathlib.Path, json_output: bool = False) -> int:
    errors, warnings = validate_archive(root)
    if json_output:
        print(json.dumps({"errors": errors, "warnings": warnings, "error_count": len(errors), "warning_count": len(warnings)}, ensure_ascii=False, indent=2))
    else:
        for item in warnings:
            print(f"[WARN] {item}")
        for item in errors:
            print(f"[ERROR] {item}")
        print(f"[INFO] archive_errors={len(errors)} archive_warnings={len(warnings)}")
    return 1 if errors else 0
