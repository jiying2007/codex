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


class CodexAssetError(RuntimeError):
    pass


def fail(message: str) -> None:
    raise CodexAssetError(message)


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
    for skill_md in sorted(plugins_dir.glob("*/*/skills/*/SKILL.md")):
        rel = skill_md.parent.relative_to(source).as_posix()
        if rel not in active_sources:
            patterns.append(f"{rel}/**")
    return patterns


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
    output = build / output_rel
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(parts))


def build_repo(root: str | pathlib.Path, profile_arg: str = "", source_arg: str = "", build_arg: str = "") -> pathlib.Path:
    repo = Repo.from_path(root)
    assets = repo.assets
    policies = repo.policies
    source = pathlib.Path(source_arg).expanduser().resolve() if source_arg else repo.source
    build = pathlib.Path(build_arg).expanduser().resolve() if build_arg else repo.build
    profile = profile_arg or assets.get("default_profile") or "team-collab"
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


def plan_apply(root: str | pathlib.Path, build: str | pathlib.Path, target: str | pathlib.Path, backup_root: str | pathlib.Path, overwrite: bool) -> dict[str, Any]:
    repo = Repo.from_path(root)
    build_path = pathlib.Path(build).expanduser().resolve()
    target_path = pathlib.Path(target).expanduser()
    backup_path = pathlib.Path(backup_root).expanduser()
    if not build_path.is_dir():
        fail(f"构建目录不存在: {build_path}")
    protected = repo.policies.get("protected_paths", [])
    generated = {"skills/registry.csv", "control/state/active-profile.env", "control/state/managed-files.json"}
    actions: list[dict[str, Any]] = [{"action": "mkdir", "path": "."}]
    summary = {"copy": 0, "keep": 0, "overwrite": 0, "mkdir": 1, "skip": 0}

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
        should_overwrite = overwrite or src.is_symlink() or rel in generated
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

    return {
        "schema_version": 2,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "build": build_path.as_posix(),
        "target": target_path.as_posix(),
        "overwrite": overwrite,
        "summary": summary,
        "actions": actions,
    }


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


def apply_plan(plan: dict[str, Any], dry_run: bool) -> None:
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
    return summary


def diff_build_live(build: str | pathlib.Path, target: str | pathlib.Path) -> tuple[int, int, int]:
    build_path = pathlib.Path(build).expanduser().resolve()
    target_path = pathlib.Path(target).expanduser()
    if not build_path.is_dir():
        fail(f"构建目录不存在: {build_path}")
    same = diff = missing = 0
    for src in sorted(p for p in build_path.rglob("*") if p.is_file() or p.is_symlink()):
        rel = src.relative_to(build_path)
        dest = target_path / rel
        if not dest.exists() and not dest.is_symlink():
            print(f"[MISS] {rel.as_posix()}")
            missing += 1
        elif src.is_symlink():
            if dest.is_symlink() and os.readlink(src) == os.readlink(dest):
                same += 1
            else:
                print(f"[DIFF] {rel.as_posix()}")
                diff += 1
        elif dest.is_file() and filecmp.cmp(src, dest, shallow=False):
            same += 1
        else:
            print(f"[DIFF] {rel.as_posix()}")
            diff += 1
    return same, diff, missing


def live_drift(build: str | pathlib.Path, target: str | pathlib.Path) -> dict[str, Any]:
    build_path = pathlib.Path(build).expanduser().resolve()
    target_path = pathlib.Path(target).expanduser()
    state = target_path / "control/state/managed-files.json"
    if not state.is_file():
        return {"schema_version": 2, "status": "missing-live-state", "changed": [], "stale": []}
    managed = read_json(state).get("managed", [])
    changed: list[str] = []
    stale: list[str] = []
    for item in managed:
        rel = item["path"]
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
    return {"schema_version": 2, "status": "ok", "changed": changed, "stale": stale}


def frontmatter_value(path: pathlib.Path, key: str) -> str:
    text = path.read_text(errors="ignore")
    match = re.search(r"^---\n(.*?)\n---", text, re.S)
    if not match:
        return ""
    for line in match.group(1).splitlines():
        if line.startswith(f"{key}:"):
            return line.split(":", 1)[1].strip().strip('"')
    return ""


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
