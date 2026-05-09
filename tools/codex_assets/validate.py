from __future__ import annotations

import pathlib
import re
from typing import Any

from .core import Repo, active, build_lock, matches_any, read_json


REQUIRED = {
    "assets.json": ["schema_version", "source_root", "build_root", "default_profile", "copy_roots"],
    "policies.json": ["schema_version", "protected_paths", "skip_source_paths"],
    "profiles.json": ["schema_version", "profiles"],
    "skills.json": ["schema_version", "skills"],
    "agents.json": ["schema_version", "agents"],
}


def validate_repo(root: str | pathlib.Path) -> list[str]:
    repo = Repo.from_path(root)
    errors: list[str] = []
    for name, fields in REQUIRED.items():
        path = repo.manifests_dir / name
        if not path.is_file():
            errors.append(f"缺少 manifest: {name}")
            continue
        data = read_json(path)
        for field in fields:
            if field not in data:
                errors.append(f"{name} 缺少字段: {field}")

    if errors:
        return errors

    assets = repo.assets
    source = repo.source
    policies = repo.policies
    profile_names = {item.get("name") for item in repo.manifest("profiles.json").get("profiles", [])}
    if assets.get("default_profile") not in profile_names:
        errors.append(f"default_profile 未定义: {assets.get('default_profile')}")
    if not source.is_dir():
        errors.append(f"source_root 不存在: {source}")
    if pathlib.PurePosixPath(assets.get("build_root", "")).is_absolute():
        errors.append("build_root 必须是仓库相对路径")
    protected = policies.get("protected_paths", [])
    copy_roots = assets.get("copy_roots", [])
    for root_name in copy_roots:
        if root_name.startswith("/") or ".." in pathlib.PurePosixPath(root_name).parts:
            errors.append(f"copy_roots 包含不安全路径: {root_name}")
        if matches_any(root_name, protected):
            errors.append(f"copy_roots 不能包含 protected path: {root_name}")
        if source.is_dir() and not (source / root_name).exists():
            errors.append(f"copy_roots 指向不存在路径: {root_name}")

    for collection_name, key in [("skills.json", "skills"), ("agents.json", "agents")]:
        seen: set[str] = set()
        targets_by_profile: dict[str, dict[str, str]] = {}
        for item in repo.manifest(collection_name).get(key, []):
            name = item.get("name")
            if not name:
                errors.append(f"{collection_name} 条目缺少 name")
                continue
            if name in seen:
                errors.append(f"{collection_name} 重复 name: {name}")
            seen.add(name)
            for field in ["enabled", "version", "vendor_rel", "target_rel", "profiles"]:
                if field not in item:
                    errors.append(f"{collection_name}:{name} 缺少字段 {field}")
            version = item.get("version", "")
            if version and not re.match(r"^[0-9]+\.[0-9]+\.[0-9]+([+-][A-Za-z0-9.-]+)?$", version):
                errors.append(f"{collection_name}:{name} version 非 semver: {version}")
            if collection_name == "skills.json":
                provenance = [item.get(field, "") for field in ["source_repo", "source_ref", "source_path", "imported_at"]]
                if any(provenance) and not all(provenance):
                    errors.append(f"{collection_name}:{name} 来源元数据不完整")
                if item.get("imported_at") and not re.match(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$", item["imported_at"]):
                    errors.append(f"{collection_name}:{name} imported_at 必须是 YYYY-MM-DD")
                if item.get("review_status") and item["review_status"] not in {"accepted", "pending", "rejected"}:
                    errors.append(f"{collection_name}:{name} review_status 非法: {item['review_status']}")
                if item.get("enabled") and item.get("review_status") in {"pending", "rejected"}:
                    errors.append(f"{collection_name}:{name} 未 accepted 不能启用")
            for profile in item.get("profiles", []):
                if profile not in profile_names:
                    errors.append(f"{collection_name}:{name} 引用未知 profile: {profile}")
            for field in ["vendor_rel", "target_rel"]:
                value = item.get(field, "")
                if value.startswith("/") or ".." in pathlib.PurePosixPath(value).parts:
                    errors.append(f"{collection_name}:{name} 不安全路径 {field}={value}")
            vendor_rel = item.get("vendor_rel", "")
            target_rel = item.get("target_rel", "")
            if vendor_rel and source.is_dir() and not (source / vendor_rel).exists():
                errors.append(f"{collection_name}:{name} vendor_rel 不存在: {vendor_rel}")
            if target_rel and matches_any(target_rel, protected):
                errors.append(f"{collection_name}:{name} target_rel 不能指向 protected path: {target_rel}")
            for profile in item.get("profiles", []):
                profile_targets = targets_by_profile.setdefault(profile, {})
                if target_rel in profile_targets:
                    errors.append(
                        f"{collection_name}:{name} 与 {profile_targets[target_rel]} 在 profile {profile} 写入同一路径: {target_rel}"
                    )
                profile_targets[target_rel] = name

    lock_path = repo.manifests_dir / "lock.json"
    build_state = repo.build / "control/state/managed-files.json"
    if lock_path.is_file() and build_state.is_file():
        lock = read_json(lock_path)
        state = read_json(build_state)
        expected = build_lock(repo, state.get("profile", assets.get("default_profile", "")), state.get("managed", []))
        if lock.get("profile") != expected.get("profile"):
            errors.append("lock profile 与 build state 不一致")
        lock_items = {(item.get("kind"), item.get("name")): item for item in lock.get("items", [])}
        for item in expected.get("items", []):
            locked = lock_items.get((item.get("kind"), item.get("name")))
            if not locked:
                errors.append(f"lock 缺少条目: {item.get('kind')}:{item.get('name')}")
            elif locked.get("version") != item.get("version") or locked.get("sha256") != item.get("sha256"):
                errors.append(f"lock 条目过期: {item.get('kind')}:{item.get('name')}")
    return errors


def schema_doc(name: str, required: list[str]) -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": name,
        "type": "object",
        "required": required,
        "additionalProperties": True,
    }
