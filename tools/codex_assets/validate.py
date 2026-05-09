from __future__ import annotations

import pathlib
import re
from typing import Any

from .core import Repo, fail, read_json


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
    profile_names = {item.get("name") for item in repo.manifest("profiles.json").get("profiles", [])}
    if assets.get("default_profile") not in profile_names:
        errors.append(f"default_profile 未定义: {assets.get('default_profile')}")

    for collection_name, key in [("skills.json", "skills"), ("agents.json", "agents")]:
        seen: set[str] = set()
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
            for profile in item.get("profiles", []):
                if profile not in profile_names:
                    errors.append(f"{collection_name}:{name} 引用未知 profile: {profile}")
            for field in ["vendor_rel", "target_rel"]:
                value = item.get(field, "")
                if value.startswith("/") or ".." in pathlib.PurePosixPath(value).parts:
                    errors.append(f"{collection_name}:{name} 不安全路径 {field}={value}")
    return errors


def schema_doc(name: str, required: list[str]) -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": name,
        "type": "object",
        "required": required,
        "additionalProperties": True,
    }

