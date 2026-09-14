from __future__ import annotations

import csv
import filecmp
import fnmatch
import hashlib
import json
import os
import pathlib
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import yaml

from .archive_governance import build_meta_v2


class CodexAssetError(RuntimeError):
    pass


def fail(message: str) -> None:
    raise CodexAssetError(message)


def knowledge_hub_root() -> pathlib.Path:
    return pathlib.Path(os.environ.get("KNOWLEDGE_HUB_HOME", "~/knowledge-hub")).expanduser().resolve()


def read_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except Exception as exc:
        fail(f"无法读取 JSON: {path}: {exc}")


def write_json(path: pathlib.Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_fingerprint(root: pathlib.Path) -> str:
    """Return a stable digest for files and symlinks below root."""
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file() and not path.is_symlink():
            continue
        rel = path.relative_to(root).as_posix()
        digest.update(rel.encode())
        digest.update(b"\0")
        if path.is_symlink():
            digest.update(b"symlink\0")
            digest.update(os.readlink(path).encode())
        else:
            digest.update(b"file\0")
            digest.update(sha256(path).encode())
        digest.update(b"\0")
    return digest.hexdigest()


def source_fingerprint(repo: "Repo", source: pathlib.Path | None = None) -> str:
    """Hash conservative build inputs so reused builds fail closed when source changes."""
    digest = hashlib.sha256()
    roots = [
        (source or repo.source, "source"),
        (repo.manifests_dir, "manifests"),
        (repo.root / "tools/codex_assets", "tools/codex_assets"),
    ]
    for root, label in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() and not path.is_symlink():
                continue
            if path == repo.manifests_dir / "lock.json" or "__pycache__" in path.parts:
                continue
            rel = f"{label}/{path.relative_to(root).as_posix()}"
            digest.update(rel.encode())
            digest.update(b"\0")
            if path.is_symlink():
                digest.update(b"symlink\0")
                digest.update(os.readlink(path).encode())
            else:
                digest.update(b"file\0")
                digest.update(sha256(path).encode())
            digest.update(b"\0")
    return digest.hexdigest()


def normalize_path(path: str | pathlib.Path) -> str:
    return pathlib.Path(path).as_posix()


def matches_any(rel: str | pathlib.Path, patterns: list[str]) -> bool:
    rel_text = normalize_path(rel)
    for pattern in patterns:
        base = pattern[:-3] if pattern.endswith("/**") else pattern
        if rel_text == base or fnmatch.fnmatch(rel_text, pattern):
            return True
    return False


def split_list(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"[|,]", value) if part.strip()]


def parse_frontmatter(path: pathlib.Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"^---\n(.*?)\n---", text, re.S)
    if not match:
        return {}
    try:
        data = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as exc:
        fail(f"无效 frontmatter YAML: {path}: {exc}")
    if not isinstance(data, dict):
        fail(f"frontmatter 必须是 key/value 映射: {path}")
    return data


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip().lower()).strip("-")
    return slug or "note"


def assert_safe_archive_source(source: pathlib.Path, repo: "Repo") -> None:
    resolved = source.expanduser().resolve()
    source_text = resolved.as_posix()
    forbidden_parts = [
        "/.codex/sessions/",
        "/.codex/log/",
        "/.codex/cache/",
        "/.codex/tmp/",
        "/.codex/mcp/secrets/",
    ]
    if any(part in source_text for part in forbidden_parts):
        fail(f"拒绝归档运行态/敏感目录: {source}")
    rel = ""
    try:
        rel = resolved.relative_to(repo.root).as_posix()
    except ValueError:
        pass
    old_control_roots = [
        "src/codex-home/control/archives",
        "src/codex-home/control/knowledge",
        "src/codex-home/control/roles",
        "src/codex-home/control/workflows",
    ]
    if rel and any(rel == root or rel.startswith(f"{root}/") for root in old_control_roots):
        fail(f"拒绝归档旧 control 知识态目录: {rel}")
    protected = repo.policies.get("protected_paths", [])
    if rel and matches_any(rel, protected):
        fail(f"拒绝归档 protected path: {rel}")
    candidates = [source]
    if source.is_dir():
        candidates = [path for path in source.rglob("*") if path.is_file() or path.is_symlink()]
    for path in candidates:
        name = path.name.lower()
        if any(name.endswith(suffix) for suffix in [".secret", ".key", ".pem"]):
            fail(f"拒绝归档疑似密钥文件: {path}")
        if name in {"auth.json"} or name.startswith(("logs_", "state_")):
            fail(f"拒绝归档运行态文件: {path}")


def archive_note(
    root: str | pathlib.Path,
    source_arg: str | pathlib.Path,
    topic_arg: str = "",
    dest_arg: str = "",
    title_arg: str = "",
    description: str = "",
    project_arg: str = "",
    source_repo_arg: str = "",
    workstream_arg: str = "",
    session_arg: str = "",
    status_arg: str = "closed",
    scope_arg: str = "",
    kind_arg: str = "",
    owner_arg: str = "",
    next_action_arg: str = "",
    memory_action_arg: str = "archive-only",
    tags_arg: list[str] | None = None,
    no_project_detect: bool = False,
    move: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    repo = Repo.from_path(root)
    source = pathlib.Path(source_arg).expanduser()
    if not source.exists() and not source.is_symlink():
        fail(f"归档来源不存在: {source}")
    assert_safe_archive_source(source, repo)
    topic = slugify(topic_arg or source.stem or source.name)
    hub_root = knowledge_hub_root()
    archive_root = pathlib.Path(dest_arg).expanduser() if dest_arg else hub_root / "domains/codex/archive/codex-archive" / topic
    archive_root = archive_root.resolve()
    allowed_roots = [repo.root, hub_root]
    if not any(allowed in [archive_root, *archive_root.parents] for allowed in allowed_roots):
        fail(f"归档目标必须位于 Codex 仓或 Knowledge Hub 内: {archive_root}")
    if source.is_dir() and source.resolve() in [archive_root, *archive_root.parents]:
        fail(f"归档目标不能位于来源目录内部: {archive_root}")
    timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    source_slug = slugify(source.stem if source.is_file() else source.name)
    item_name = f"{timestamp}-{source_slug}"
    dest = archive_root / f"{item_name}{source.suffix}" if source.is_file() else archive_root / item_name
    meta_path = archive_root / f"{dest.name}.meta.json"
    meta_kwargs = {
        "title": title_arg,
        "description": description,
        "mode": "move" if move else "copy",
        "explicit_project": project_arg,
        "source_repo": source_repo_arg,
        "workstream_id": workstream_arg,
        "session_id": session_arg,
        "status": status_arg,
        "scope": scope_arg,
        "kind": kind_arg,
        "owner": owner_arg,
        "next_action": next_action_arg,
        "memory_action": memory_action_arg,
        "tags": tags_arg or [],
        "no_project_detect": no_project_detect,
    }
    meta: dict[str, Any] = {}
    if not dry_run:
        build_meta_v2(repo.root, source, dest, meta_path, topic, **meta_kwargs)
        archive_root.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            if move:
                shutil.move(str(source), str(dest))
            else:
                shutil.copytree(source, dest, symlinks=True)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            if move:
                shutil.move(str(source), str(dest))
            else:
                shutil.copy2(source, dest)
        meta = build_meta_v2(repo.root, source, dest, meta_path, topic, **meta_kwargs)
        write_json(meta_path, meta)
        update_archive_index(archive_root, topic)
    else:
        meta = {
            "schema_version": 2,
            "source": source.expanduser().resolve(strict=False).as_posix(),
            "destination": dest.as_posix(),
            "metadata": meta_path.as_posix(),
            "topic": topic,
            "title": title_arg or topic,
            "description": description,
            "mode": "move" if move else "copy",
            "dry_run": True,
        }
    return meta


ARCHIVE_TOPIC_TITLES = {
    "archive-governance": "Archive Governance",
    "control-archives": "Legacy Control Archives",
    "daily-summary": "Daily Summary Archive",
    "debug-notes": "Debug Notes Archive",
    "diag-architecture": "Diagnostic Architecture Archive",
    "memory-curation": "Memory Curation Archive",
    "release-governance": "Release Governance Archive",
    "research-notes": "Research Notes Archive",
    "session-wrap": "Session Wrap Archive",
    "tools": "Tools Archive",
}


def archive_topic_title(topic: str) -> str:
    return ARCHIVE_TOPIC_TITLES.get(topic, topic.replace("-", " ").title())


def update_archive_index(archive_root: pathlib.Path, topic: str) -> None:
    rows = []
    for path in sorted(archive_root.iterdir(), key=lambda p: p.name):
        if path.name == "index.md" or path.name.endswith(".meta.json"):
            continue
        rows.append(f"| `{path.name}` | `{path.relative_to(archive_root).as_posix()}` |")
    content = [
        f"# {archive_topic_title(topic)}",
        "",
        "本目录由 `rtk bash ~/codex/scripts/archive-note.sh` 维护，用于沉淀已脱敏、可追溯的长期知识材料；新增归档默认写入 Knowledge Hub。",
        "",
        f"- Topic: `{topic}`",
        "- Index title is topic-level and must not be replaced by a single archived item title.",
        "",
        "| Item | Path |",
        "| --- | --- |",
        *rows,
        "",
    ]
    archive_root.joinpath("index.md").write_text("\n".join(content))


@dataclass
class Repo:
    root: pathlib.Path

    @classmethod
    def from_path(cls, root: str | pathlib.Path) -> "Repo":
        return cls(pathlib.Path(root).expanduser().resolve())

    @property
    def manifests_dir(self) -> pathlib.Path:
        return self.root / "manifests"

    def manifest(self, name: str) -> dict[str, Any]:
        return read_json(self.manifests_dir / name)

    @property
    def assets(self) -> dict[str, Any]:
        return self.manifest("assets.json")

    @property
    def policies(self) -> dict[str, Any]:
        return self.manifest("policies.json")

    @property
    def source(self) -> pathlib.Path:
        return self.root / self.assets.get("source_root", "src/codex-home")

    @property
    def build(self) -> pathlib.Path:
        return self.root / self.assets.get("build_root", "build/codex-home")


def active(item: dict[str, Any], profile: str) -> bool:
    return bool(item.get("enabled", True)) and profile in item.get("profiles", [])


def inactive_plugin_skill_patterns(source: pathlib.Path, skills: list[dict[str, Any]], profile: str) -> list[str]:
    active_sources = {item["vendor_rel"] for item in skills if active(item, profile)}
    patterns: list[str] = []
    plugins_dir = source / "vendor/plugins"
    if not plugins_dir.is_dir():
        return patterns
    for orphan_dir in sorted(plugins_dir.iterdir()):
        if orphan_dir.is_dir() and not any(child.is_dir() for child in orphan_dir.iterdir()):
            orphan_rel = orphan_dir.relative_to(source).as_posix()
            patterns.extend([orphan_rel, f"{orphan_rel}/**"])
    for plugin_dir in sorted(plugins_dir.glob("*/*")):
        if not plugin_dir.is_dir():
            continue
        plugin_skills = sorted(plugin_dir.glob("skills/*/SKILL.md"))
        if not plugin_skills or not any(
            skill_md.parent.relative_to(source).as_posix() in active_sources
            for skill_md in plugin_skills
        ):
            plugin_rel = plugin_dir.relative_to(source).as_posix()
            patterns.extend([plugin_rel, f"{plugin_rel}/**"])
            continue
        for skill_md in plugin_skills:
            rel = skill_md.parent.relative_to(source).as_posix()
            if rel not in active_sources:
                patterns.append(f"{rel}/**")
    return patterns


def unmanaged_live_assets(
    build: str | pathlib.Path,
    target: str | pathlib.Path,
    managed_paths: set[str] | None = None,
) -> list[str]:
    build_path = pathlib.Path(build).expanduser().resolve()
    target_path = pathlib.Path(target).expanduser()
    if not target_path.is_dir():
        return []

    def is_managed(rel: str) -> bool:
        if managed_paths is not None:
            return rel in managed_paths
        return (build_path / rel).exists()

    unmanaged: list[str] = []
    for pattern in ["vendor/skills/*/*/SKILL.md", "vendor/plugins/*/*/skills/*/SKILL.md"]:
        for skill_md in sorted(target_path.glob(pattern)):
            rel = skill_md.parent.relative_to(target_path).as_posix()
            if not is_managed(rel):
                unmanaged.append(rel)
    skills_dir = target_path / "skills"
    if skills_dir.is_dir():
        ignored = {".system", "scripts", "README.md", "registry.csv"}
        for path in sorted(skills_dir.iterdir(), key=lambda p: p.name):
            if path.name in ignored:
                continue
            rel = path.relative_to(target_path).as_posix()
            if not is_managed(rel) and (path.is_symlink() or path.is_dir()):
                unmanaged.append(rel)
    return sorted(set(unmanaged))


def live_drift(build: str | pathlib.Path, target: str | pathlib.Path, ignored: list[str] | None = None) -> dict[str, Any]:
    build_path = pathlib.Path(build).expanduser().resolve()
    target_path = pathlib.Path(target).expanduser()
    ignored = ignored or []
    state = target_path / "control/state/managed-files.json"
    if not state.is_file():
        return {"schema_version": 2, "status": "missing-live-state", "changed": [], "stale": [], "unmanaged": []}
    managed = read_json(state).get("managed", [])
    managed_paths = {
        item["path"]
        for item in managed
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    changed: list[str] = []
    stale: list[str] = []
    for item in managed:
        rel = item["path"]
        if matches_any(rel, ignored):
            continue
        if item["type"] == "dir":
            continue
        live = target_path / rel
        built = build_path / rel
        if not built.exists() and not built.is_symlink():
            stale.append(rel)
            continue
        if not live.exists() and not live.is_symlink():
            changed.append(rel)
            continue
        if item["type"] == "symlink":
            if not live.is_symlink() or os.readlink(live) != item.get("target"):
                changed.append(rel)
        elif item["type"] == "file":
            if not live.is_file() or sha256(live) != item.get("sha256"):
                changed.append(rel)
    return {
        "schema_version": 2,
        "status": "ok",
        "changed": changed,
        "stale": stale,
        "unmanaged": unmanaged_live_assets(build_path, target_path, managed_paths),
    }


def copy_entry(src: pathlib.Path, dst: pathlib.Path, rel: pathlib.Path, protected: list[str], skip_source: list[str]) -> None:
    if matches_any(rel, protected) or matches_any(rel, skip_source):
        return
    if src.is_symlink():
        return
    if src.is_dir():
        dst.mkdir(parents=True, exist_ok=True)
        for child in sorted(src.iterdir(), key=lambda p: p.name):
            copy_entry(child, dst / child.name, rel / child.name, protected, skip_source)
    elif src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def replace_with_symlink(link: pathlib.Path, target: pathlib.Path) -> None:
    if link.exists() or link.is_symlink():
        if link.is_dir() and not link.is_symlink():
            shutil.rmtree(link)
        else:
            link.unlink()
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(os.path.relpath(target, start=link.parent))


def collect_managed(build: pathlib.Path, protected: list[str]) -> list[dict[str, Any]]:
    managed: list[dict[str, Any]] = []
    for path in sorted(build.rglob("*")):
        rel = path.relative_to(build).as_posix()
        if matches_any(rel, protected):
            continue
        if path.is_symlink():
            managed.append({"path": rel, "type": "symlink", "target": os.readlink(path)})
        elif path.is_file():
            managed.append({"path": rel, "type": "file", "sha256": sha256(path)})
        elif path.is_dir():
            managed.append({"path": rel, "type": "dir"})
    return managed


def build_lock(repo: Repo, profile: str, managed: list[dict[str, Any]]) -> dict[str, Any]:
    lock_items = []
    for item in repo.manifest("skills.json").get("skills", []):
        if not active(item, profile):
            continue
        source = repo.source / item["vendor_rel"]
        files = sorted(p for p in source.rglob("*") if p.is_file() and not p.is_symlink())
        digest = hashlib.sha256()
        for path in files:
            rel = path.relative_to(source).as_posix()
            digest.update(rel.encode())
            digest.update(b"\0")
            digest.update(sha256(path).encode())
            digest.update(b"\0")
        lock_items.append({
            "kind": "skill",
            "name": item["name"],
            "version": item.get("version", ""),
            "source": item["vendor_rel"],
            "sha256": digest.hexdigest(),
        })
    return {
        "schema_version": 2,
        "profile": profile,
        "managed_count": len(managed),
        "items": lock_items,
    }


def render_config(repo: Repo, build: pathlib.Path, profile: str) -> None:
    config_spec = repo.assets.get("config", {})
    base_rel = config_spec.get("base", "config/base.toml")
    profile_rel = config_spec.get("profiles", {}).get(profile)
    output_rel = config_spec.get("output", "config.toml")
    parts: list[str] = []
    for rel in [base_rel, profile_rel]:
        if not rel:
            continue
        path = repo.source / rel
        if not path.is_file():
            fail(f"config 模板不存在: {rel}")
        parts.append(path.read_text().rstrip() + "\n")
    if not parts:
        return
    mcp_config = render_mcp_config(repo, profile)
    if mcp_config:
        parts.append(mcp_config)
    output = build / output_rel
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(parts))


def toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(item) for item in value) + "]"
    return json.dumps("" if value is None else str(value), ensure_ascii=False)


def render_mcp_config(repo: Repo, profile: str) -> str:
    manifest_path = repo.manifests_dir / "mcp_servers.json"
    if not manifest_path.is_file():
        return ""
    servers = read_json(manifest_path).get("mcp_servers", [])
    lines: list[str] = []
    for item in servers:
        profiles = item.get("profiles", [])
        if profiles and profile not in profiles:
            continue
        name = item.get("name", "")
        if not name:
            continue
        if not lines:
            lines.extend([
                "# >>> CODEX-MANAGED MCP START",
                "# generated_from = manifests/mcp_servers.json",
            ])
        lines.append("")
        lines.append(f"[mcp_servers.{name}]")
        for key in ["url", "command", "args", "cwd", "enabled", "required", "supports_parallel_tool_calls"]:
            if key in item:
                lines.append(f"{key} = {toml_value(item[key])}")
        env = item.get("env", {})
        if isinstance(env, dict) and env:
            lines.append("")
            lines.append(f"[mcp_servers.{name}.env]")
            for env_key in sorted(env):
                lines.append(f"{env_key} = {toml_value(env[env_key])}")
    if lines:
        lines.extend(["", "# <<< CODEX-MANAGED MCP END", ""])
    return "\n".join(lines)


def build_repo(root: str | pathlib.Path, profile_arg: str = "", source_arg: str = "", build_arg: str = "") -> pathlib.Path:
    repo = Repo.from_path(root)
    assets = repo.assets
    policies = repo.policies
    source = pathlib.Path(source_arg).expanduser().resolve() if source_arg else repo.source
    build = pathlib.Path(build_arg).expanduser().resolve() if build_arg else repo.build
    profile = profile_arg or assets.get("default_profile") or "default"
    profiles = {item["name"] for item in repo.manifest("profiles.json").get("profiles", [])}
    if profile not in profiles:
        fail(f"profile 未定义: {profile}")
    if not source.is_dir():
        fail(f"源资产目录不存在: {source}")

    tmp_build = build.with_name(f".{build.name}.tmp-{os.getpid()}")
    if tmp_build.exists() or tmp_build.is_symlink():
        shutil.rmtree(tmp_build)
    tmp_build.mkdir(parents=True)

    skills = repo.manifest("skills.json").get("skills", [])
    protected = policies.get("protected_paths", [])
    skip_source = policies.get("skip_source_paths", []) + inactive_plugin_skill_patterns(source, skills, profile)
    for rel_text in assets.get("copy_roots", []):
        if rel_text == "config.toml":
            continue
        rel = pathlib.Path(rel_text)
        copy_entry(source / rel, tmp_build / rel, rel, protected, skip_source)

    render_config(repo, tmp_build, profile)

    for item in skills:
        if active(item, profile):
            src_path = tmp_build / item["vendor_rel"]
            if not src_path.exists():
                fail(f"skill 源不存在: {item['vendor_rel']}")
            replace_with_symlink(tmp_build / item["target_rel"], src_path)

    for item in repo.manifest("agents.json").get("agents", []):
        if active(item, profile):
            src_path = tmp_build / item["vendor_rel"]
            if not src_path.exists():
                fail(f"agent 源不存在: {item['vendor_rel']}")
            replace_with_symlink(tmp_build / item["target_rel"], src_path)

    registry_path = tmp_build / "skills/registry.csv"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    with registry_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "version", "status", "owner"])
        for item in repo.manifest("skills.json").get("skills", []):
            if active(item, profile):
                writer.writerow([item["name"], item.get("version", ""), "active", item.get("owner", item.get("source_kind", "managed"))])

    state_dir = tmp_build / "control/state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "active-profile.env").write_text(f"PROFILE={profile}\n")
    managed = collect_managed(tmp_build, protected)
    write_json(state_dir / "managed-files.json", {
        "schema_version": 2,
        "profile": profile,
        "source": str(source),
        "source_fingerprint": source_fingerprint(repo, source),
        "managed": managed,
    })
    if build.exists() or build.is_symlink():
        old_build = build.with_name(f".{build.name}.old-{os.getpid()}")
        if old_build.exists():
            shutil.rmtree(old_build)
        build.rename(old_build)
        tmp_build.rename(build)
        shutil.rmtree(old_build)
    else:
        build.parent.mkdir(parents=True, exist_ok=True)
        tmp_build.rename(build)
    write_json(repo.root / "manifests/lock.json", build_lock(repo, profile, managed))
    return build


def plan_apply(
    root: str | pathlib.Path,
    build: str | pathlib.Path,
    target: str | pathlib.Path,
    backup_root: str | pathlib.Path,
    overwrite: bool,
    prune_stale: bool = False,
) -> dict[str, Any]:
    repo = Repo.from_path(root)
    build_path = pathlib.Path(build).expanduser().resolve()
    target_path = pathlib.Path(target).expanduser()
    backup_path = pathlib.Path(backup_root).expanduser()
    if not build_path.is_dir():
        fail(f"构建目录不存在: {build_path}")
    state_path = build_path / "control/state/managed-files.json"
    if not state_path.is_file():
        fail(f"构建目录缺少 managed-files.json: {build_path}")
    protected = repo.policies.get("protected_paths", [])
    always_generated = {"skills/registry.csv", "control/state/active-profile.env", "control/state/managed-files.json"}
    previous_managed = managed_items(target_path)
    actions: list[dict[str, Any]] = [{"action": "mkdir", "path": "."}]
    summary = {"copy": 0, "keep": 0, "overwrite": 0, "delete": 0, "mkdir": 1, "skip": 0}

    for src in sorted(build_path.rglob("*")):
        rel = src.relative_to(build_path).as_posix()
        if matches_any(rel, protected):
            actions.append({"action": "skip", "path": rel, "reason": "protected"})
            summary["skip"] += 1
            continue
        dest = target_path / rel
        if src.is_dir() and not src.is_symlink():
            actions.append({"action": "mkdir", "path": rel})
            summary["mkdir"] += 1
            continue
        src_kind = "symlink" if src.is_symlink() else "file"
        if not dest.exists() and not dest.is_symlink():
            actions.append({"action": "copy", "path": rel, "kind": src_kind})
            summary["copy"] += 1
            continue
        if src.is_symlink() and dest.is_symlink() and os.readlink(src) == os.readlink(dest):
            actions.append({"action": "keep", "path": rel, "reason": "same-symlink"})
            summary["keep"] += 1
            continue
        if not src.is_symlink() and src.is_file() and dest.is_file() and filecmp.cmp(src, dest, shallow=False):
            actions.append({"action": "keep", "path": rel, "reason": "same-file"})
            summary["keep"] += 1
            continue
        previous = previous_managed.get(rel)
        should_overwrite = (
            overwrite
            or src.is_symlink()
            or rel in always_generated
            or unchanged_from_managed(dest, previous)
        )
        if should_overwrite:
            actions.append({
                "action": "overwrite",
                "path": rel,
                "kind": src_kind,
                "backup": (backup_path / rel).as_posix(),
            })
            summary["overwrite"] += 1
        else:
            actions.append({"action": "keep", "path": rel, "reason": "exists"})
            summary["keep"] += 1

    if prune_stale:
        built_paths = {path.relative_to(build_path).as_posix() for path in build_path.rglob("*")}
        stale_items = [
            item
            for rel, item in previous_managed.items()
            if rel not in built_paths and not matches_any(rel, protected)
        ]
        stale_items.sort(key=lambda item: (item["path"].count("/"), item["path"]), reverse=True)
        for item in stale_items:
            rel = item["path"]
            actions.append({
                "action": "delete",
                "path": rel,
                "kind": item.get("type", "unknown"),
                "backup": (backup_path / rel).as_posix(),
            })
            summary["delete"] += 1

        for rel in repo.policies.get("retired_live_paths", []):
            if not isinstance(rel, str) or not rel:
                fail("retired_live_paths 必须是非空字符串数组")
            if matches_any(rel, protected):
                fail(f"retired live path 不能匹配 protected path: {rel}")
            already_scheduled = any(
                action.get("action") == "delete" and action.get("path") == rel
                for action in actions
            )
            if not already_scheduled and ((target_path / rel).exists() or (target_path / rel).is_symlink()):
                actions.append({
                    "action": "delete",
                    "path": rel,
                    "kind": "retired-path",
                    "backup": (backup_path / rel).as_posix(),
                    "reason": "retired-live-path",
                })
                summary["delete"] += 1

    content_changes = summary["copy"] + summary["overwrite"] + summary["delete"]
    target_preconditions = target_precondition_rows(target_path, actions)
    return {
        "schema_version": 3,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "build": build_path.as_posix(),
        "target": target_path.as_posix(),
        "overwrite": overwrite,
        "build_receipt": {
            "tree_sha256": tree_fingerprint(build_path),
            "managed_state_sha256": sha256(state_path),
        },
        "target_receipt": {
            "precondition_paths_sha256": target_precondition_fingerprint(target_preconditions),
            "precondition_paths": len(target_preconditions),
            "mutation_paths": content_changes,
            "keep_paths": [
                row for row in target_preconditions if row.get("action") == "keep"
            ],
        },
        "content_changes": content_changes,
        "content_noop": content_changes == 0,
        "summary": summary,
        "actions": actions,
    }


def path_identity(path: pathlib.Path) -> str:
    if not path.exists() and not path.is_symlink():
        return "absent"
    if path.is_symlink():
        return f"symlink:{os.readlink(path)}"
    if path.is_file():
        return f"file:{sha256(path)}"
    if path.is_dir():
        return f"dir:{tree_fingerprint(path)}"
    return "special"


def target_precondition_rows(
    target: pathlib.Path, actions: list[dict[str, Any]]
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for action in actions:
        action_name = str(action.get("action", ""))
        if action_name not in {"copy", "overwrite", "delete", "keep"}:
            continue
        rel = str(action.get("path", ""))
        rows.append(
            {
                "action": action_name,
                "path": rel,
                "identity": path_identity(target / rel),
            }
        )
    return rows


def target_precondition_fingerprint(rows: list[dict[str, str]]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(row["action"].encode())
        digest.update(b"\0")
        digest.update(row["path"].encode())
        digest.update(b"\0")
        digest.update(row["identity"].encode())
        digest.update(b"\0")
    return digest.hexdigest()


def target_matches_plan_output(plan: dict[str, Any]) -> bool:
    build = pathlib.Path(plan["build"])
    target = pathlib.Path(plan["target"]).expanduser()
    mutations = [
        action
        for action in plan.get("actions", [])
        if action.get("action") in {"copy", "overwrite", "delete"}
    ]
    if not mutations:
        return True
    for action in mutations:
        rel = str(action["path"])
        dest = target / rel
        if action["action"] == "delete":
            if dest.exists() or dest.is_symlink():
                return False
            continue
        src = build / rel
        if path_identity(src) != path_identity(dest):
            return False
    return True


def target_keeps_match_receipt(plan: dict[str, Any]) -> bool:
    target = pathlib.Path(plan["target"]).expanduser()
    receipt = plan.get("target_receipt") or {}
    keep_rows = receipt.get("keep_paths")
    if not isinstance(keep_rows, list):
        return False
    expected = {
        (str(row.get("path", "")), str(row.get("identity", "")))
        for row in keep_rows
        if isinstance(row, dict)
    }
    actual = {
        (str(action.get("path", "")), path_identity(target / str(action.get("path", ""))))
        for action in plan.get("actions", [])
        if action.get("action") == "keep"
    }
    return actual == expected


def target_directories_ready(plan: dict[str, Any]) -> bool:
    target = pathlib.Path(plan["target"]).expanduser()
    return all(
        (target / str(action.get("path", ""))).is_dir()
        for action in plan.get("actions", [])
        if action.get("action") == "mkdir"
    )


def validate_apply_plan(
    plan: dict[str, Any], expected_target: str | pathlib.Path | None = None
) -> str:
    if plan.get("schema_version") != 3:
        fail("apply plan schema_version 非 3，请重新生成 plan")
    build = pathlib.Path(str(plan.get("build", ""))).expanduser().resolve()
    if not build.is_dir():
        fail(f"apply plan 构建目录不存在: {build}")
    receipt = plan.get("build_receipt")
    if not isinstance(receipt, dict):
        fail("apply plan 缺少 build_receipt，请重新生成 plan")
    state_path = build / "control/state/managed-files.json"
    if not state_path.is_file():
        fail(f"apply plan 构建状态不存在: {state_path}")
    if receipt.get("managed_state_sha256") != sha256(state_path):
        fail("apply plan 已失效: managed state 已变化")
    if receipt.get("tree_sha256") != tree_fingerprint(build):
        fail("apply plan 已失效: build tree 已变化")
    if expected_target is not None:
        planned = pathlib.Path(str(plan.get("target", ""))).expanduser().resolve()
        expected = pathlib.Path(expected_target).expanduser().resolve()
        if planned != expected:
            fail(f"apply plan target 不匹配: plan={planned} expected={expected}")
    target = pathlib.Path(str(plan.get("target", ""))).expanduser()
    target_receipt = plan.get("target_receipt")
    if not isinstance(target_receipt, dict):
        fail("apply plan 缺少 target_receipt，请重新生成 plan")
    if not isinstance(target_receipt.get("keep_paths"), list):
        fail("apply plan target_receipt 缺少 keep_paths，请重新生成 plan")
    if plan.get("content_noop") and target_directories_ready(plan) and target_keeps_match_receipt(plan):
        return "already-applied"
    current_rows = target_precondition_rows(target, plan.get("actions", []))
    current = target_precondition_fingerprint(current_rows)
    if current == target_receipt.get("precondition_paths_sha256"):
        return "ready"
    if target_matches_plan_output(plan) and target_keeps_match_receipt(plan):
        return "already-applied"
    fail("apply plan 已失效: target precondition paths 已变化")


def managed_items(target: pathlib.Path) -> dict[str, dict[str, Any]]:
    state = target / "control/state/managed-files.json"
    if not state.is_file():
        return {}
    return {item["path"]: item for item in read_json(state).get("managed", [])}


def unchanged_from_managed(path: pathlib.Path, item: dict[str, Any] | None) -> bool:
    if not item:
        return False
    if item.get("type") == "symlink":
        return path.is_symlink() and os.readlink(path) == item.get("target")
    if item.get("type") == "file":
        return path.is_file() and sha256(path) == item.get("sha256")
    return False


def backup_existing(dest: pathlib.Path, backup_dest: pathlib.Path, dry_run: bool) -> None:
    if not dest.exists() and not dest.is_symlink():
        return
    if dry_run:
        return
    backup_dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_symlink():
        if backup_dest.exists() or backup_dest.is_symlink():
            backup_dest.unlink()
        backup_dest.symlink_to(os.readlink(dest))
    elif dest.is_dir():
        if backup_dest.exists():
            shutil.rmtree(backup_dest)
        shutil.copytree(dest, backup_dest, symlinks=True)
    else:
        shutil.copy2(dest, backup_dest)


def copy_one(src: pathlib.Path, dest: pathlib.Path, dry_run: bool) -> None:
    if dry_run:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.is_symlink():
        if dest.exists() or dest.is_symlink():
            if dest.is_dir() and not dest.is_symlink():
                shutil.rmtree(dest)
            else:
                dest.unlink()
        dest.symlink_to(os.readlink(src))
    elif src.is_file():
        shutil.copy2(src, dest)


def apply_plan(plan: dict[str, Any], dry_run: bool) -> str:
    plan_state = validate_apply_plan(plan)
    if plan_state == "already-applied":
        return "already-applied"
    build = pathlib.Path(plan["build"])
    target = pathlib.Path(plan["target"]).expanduser()
    if not dry_run:
        target.mkdir(parents=True, exist_ok=True)
    for action in plan["actions"]:
        rel = action["path"]
        if action["action"] == "mkdir":
            if not dry_run:
                (target / rel).mkdir(parents=True, exist_ok=True)
        elif action["action"] in {"copy", "overwrite"}:
            if action["action"] == "overwrite":
                backup_existing(target / rel, pathlib.Path(action["backup"]), dry_run)
            copy_one(build / rel, target / rel, dry_run)
        elif action["action"] == "delete":
            dest = target / rel
            if dest.exists() or dest.is_symlink():
                backup_existing(dest, pathlib.Path(action["backup"]), dry_run)
                if not dry_run:
                    remove_path(dest)
    return "applied"


def remove_path(path: pathlib.Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def restore_path(backup: pathlib.Path, dest: pathlib.Path, dry_run: bool) -> None:
    if dry_run:
        return
    if dest.exists() or dest.is_symlink():
        remove_path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if backup.is_symlink():
        dest.symlink_to(os.readlink(backup))
    elif backup.is_dir():
        shutil.copytree(backup, dest, symlinks=True)
    elif backup.is_file():
        shutil.copy2(backup, dest)
    else:
        fail(f"备份路径不存在: {backup}")


def rollback_plan(plan_path: str | pathlib.Path, dry_run: bool = False, remove_copies: bool = True) -> dict[str, int]:
    plan = read_json(pathlib.Path(plan_path).expanduser())
    target = pathlib.Path(plan["target"]).expanduser()
    summary = {"restored": 0, "removed": 0, "skipped": 0}
    for action in reversed(plan.get("actions", [])):
        rel = action.get("path", "")
        if not rel or rel == ".":
            continue
        dest = target / rel
        if action.get("action") == "overwrite":
            backup = pathlib.Path(action.get("backup", "")).expanduser()
            if backup.exists() or backup.is_symlink():
                print(f"[ROLLBACK] restore {rel}")
                restore_path(backup, dest, dry_run)
                summary["restored"] += 1
            else:
                print(f"[SKIP] {rel} (backup missing)")
                summary["skipped"] += 1
        elif action.get("action") == "copy" and remove_copies:
            if dest.exists() or dest.is_symlink():
                print(f"[ROLLBACK] remove {rel}")
                if not dry_run:
                    remove_path(dest)
                summary["removed"] += 1
        elif action.get("action") == "delete":
            backup = pathlib.Path(action.get("backup", "")).expanduser()
            if backup.exists() or backup.is_symlink():
                print(f"[ROLLBACK] restore {rel}")
                restore_path(backup, dest, dry_run)
                summary["restored"] += 1
            else:
                print(f"[SKIP] {rel} (backup missing)")
                summary["skipped"] += 1
    return summary


def diff_build_live(build: str | pathlib.Path, target: str | pathlib.Path, ignored: list[str] | None = None) -> tuple[int, int, int]:
    build_path = pathlib.Path(build).expanduser().resolve()
    target_path = pathlib.Path(target).expanduser()
    if not build_path.is_dir():
        fail(f"构建目录不存在: {build_path}")
    ignored = ignored or []
    same = diff = missing = 0
    for src in sorted(p for p in build_path.rglob("*") if p.is_file() or p.is_symlink()):
        rel = src.relative_to(build_path)
        rel_text = rel.as_posix()
        if matches_any(rel_text, ignored):
            continue
        dest = target_path / rel
        if not dest.exists() and not dest.is_symlink():
            print(f"[MISS] {rel_text}")
            missing += 1
        elif src.is_symlink():
            if dest.is_symlink() and os.readlink(src) == os.readlink(dest):
                same += 1
            else:
                print(f"[DIFF] {rel_text}")
                diff += 1
        elif dest.is_file() and filecmp.cmp(src, dest, shallow=False):
            same += 1
        else:
            print(f"[DIFF] {rel_text}")
            diff += 1
    return same, diff, missing




def frontmatter_value(path: pathlib.Path, key: str) -> str:
    value = parse_frontmatter(path).get(key, "")
    return value if isinstance(value, str) else str(value)


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
