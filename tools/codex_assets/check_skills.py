from __future__ import annotations

import json
import pathlib
import re
import sys

from .core import CodexAssetError, parse_frontmatter


ROOT = pathlib.Path(__file__).resolve().parents[2]
SKILLS_ROOT = ROOT / "src/codex-home/vendor/skills"
MANIFEST = ROOT / "manifests/skills.json"
SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+([+-][A-Za-z0-9.-]+)?$")
DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
LINK = re.compile(r"(?:\]\(|`)((?:scripts|references|reference|examples)/[^)`#\s]+)")


def frontmatter(path: pathlib.Path) -> dict[str, str]:
    return {str(key): str(value) for key, value in parse_frontmatter(path).items()}


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    names: dict[str, pathlib.Path] = {}
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest_items = {item["name"]: item for item in manifest.get("skills", [])}

    for skill_md in sorted(SKILLS_ROOT.glob("*/*/SKILL.md")):
        skill_dir = skill_md.parent
        expected_version = skill_dir.name
        expected_name = skill_dir.parent.name
        try:
            meta = frontmatter(skill_md)
        except CodexAssetError as exc:
            errors.append(str(exc))
            continue

        for field in ["name", "description", "version", "last_updated"]:
            if not meta.get(field):
                errors.append(f"{skill_md}: frontmatter 缺少 {field}")

        name = meta.get("name", expected_name)
        if name in names:
            errors.append(f"重复 skill name: {name} ({names[name]} 与 {skill_md})")
        names[name] = skill_md

        if name != expected_name:
            errors.append(f"{skill_md}: name={name} 与目录名 {expected_name} 不一致")
        if meta.get("version") != expected_version:
            errors.append(f"{skill_md}: version={meta.get('version')} 与目录版本 {expected_version} 不一致")
        if meta.get("version") and not SEMVER.match(meta["version"]):
            errors.append(f"{skill_md}: version 非 semver")
        if meta.get("last_updated") and not DATE.match(meta["last_updated"]):
            errors.append(f"{skill_md}: last_updated 必须是 YYYY-MM-DD")

        if not (skill_dir / "README.md").is_file():
            warnings.append(f"{skill_dir}: 缺少 README.md")
        if not ((skill_dir / "LICENSE").is_file() or (skill_dir / "LICENSE.txt").is_file()):
            warnings.append(f"{skill_dir}: 缺少 LICENSE 或 LICENSE.txt")
        if not (skill_dir / "agents/openai.yaml").is_file():
            warnings.append(f"{skill_dir}: 缺少 agents/openai.yaml")
        if (skill_dir / ".git").exists():
            errors.append(f"{skill_dir}: 不应包含内嵌 .git")

        text = skill_md.read_text(encoding="utf-8")
        for match in LINK.finditer(text):
            rel = match.group(1).strip()
            if not (skill_dir / rel).exists():
                errors.append(f"{skill_md}: 引用文件不存在 {rel}")
        if re.search(r"~/.agents/skills|assets/codex|apply-to-codex|scan-codex-skills", text):
            errors.append(f"{skill_md}: 包含旧路径或旧入口")

    for name, item in manifest_items.items():
        vendor_rel = item.get("vendor_rel", "")
        if vendor_rel.startswith("vendor/skills/"):
            skill_md = ROOT / "src/codex-home" / vendor_rel / "SKILL.md"
            if not skill_md.is_file():
                errors.append(f"manifest:{name} vendor_rel 缺少 SKILL.md")
                continue
            try:
                meta = frontmatter(skill_md)
            except CodexAssetError as exc:
                errors.append(str(exc))
                continue
            if meta.get("name") != name:
                errors.append(f"manifest:{name} 与 SKILL.md name={meta.get('name')} 不一致")
            if meta.get("version") != item.get("version"):
                errors.append(f"manifest:{name} 与 SKILL.md version={meta.get('version')} 不一致")

        provenance = [item.get(field, "") for field in ["source_repo", "source_ref", "source_path", "imported_at"]]
        if any(provenance) and not all(provenance):
            errors.append(f"manifest:{name} 来源元数据不完整")
        if item.get("source_repo") and item.get("review_status") != "accepted":
            errors.append(f"manifest:{name} 第三方来源必须 review_status=accepted")

    for warning in warnings:
        print(f"[WARN ] {warning}")
    for error in errors:
        print(f"[ERROR] {error}")
    print(f"[INFO ] skills={len(names)} errors={len(errors)} warnings={len(warnings)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
