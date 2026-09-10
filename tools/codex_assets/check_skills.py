from __future__ import annotations

import json
import pathlib
import re
import sys

import yaml

from .core import CodexAssetError, parse_frontmatter


ROOT = pathlib.Path(__file__).resolve().parents[2]
SKILLS_ROOT = ROOT / "src/codex-home/vendor/skills"
MANIFEST = ROOT / "manifests/skills.json"
SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+([+-][A-Za-z0-9.-]+)?$")
DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
LINK = re.compile(r"(?:\]\(|`)((?:scripts|references|reference|examples)/[^)`#\s]+)")
BARE_LOCAL_COMMAND = re.compile(
    r"^\s*(?:\|\s*)?(?:bash|git|rg|find|sed|awk|python|python3|echo|codex)\s+"
)
SCRIPT_REF = re.compile(r"(?<![A-Za-z0-9_.-])((?:\./)?scripts/[A-Za-z0-9._/-]+\.(?:sh|py))")
OPENAI_TOP_LEVEL_FIELDS = {"interface", "policy"}
OPENAI_INTERFACE_REQUIRED_FIELDS = {"display_name", "short_description"}
OPENAI_INTERFACE_OPTIONAL_FIELDS = {
    "default_prompt",
    "icon_small",
    "icon_large",
    "brand_color",
}
OPENAI_INTERFACE_FIELDS = OPENAI_INTERFACE_REQUIRED_FIELDS | OPENAI_INTERFACE_OPTIONAL_FIELDS
OPENAI_POLICY_FIELDS = {"allow_implicit_invocation"}


def frontmatter(path: pathlib.Path) -> dict[str, str]:
    return {str(key): str(value) for key, value in parse_frontmatter(path).items()}


def validate_openai_metadata(path: pathlib.Path, errors: list[str]) -> None:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        errors.append(f"{path}: agents/openai.yaml 无法解析: {exc}")
        return
    if not isinstance(data, dict):
        errors.append(f"{path}: agents/openai.yaml 顶层必须是对象")
        return

    legacy = sorted(set(data) & OPENAI_INTERFACE_FIELDS)
    if legacy:
        errors.append(f"{path}: legacy 顶层 interface 字段已退役: {', '.join(legacy)}")
    unknown_top = sorted(set(data) - OPENAI_TOP_LEVEL_FIELDS - OPENAI_INTERFACE_FIELDS)
    if unknown_top:
        errors.append(f"{path}: agents/openai.yaml 未知顶层字段: {', '.join(unknown_top)}")

    interface = data.get("interface")
    if not isinstance(interface, dict):
        errors.append(f"{path}: interface 必须是对象且不得省略")
    else:
        unknown_interface = sorted(set(interface) - OPENAI_INTERFACE_FIELDS)
        if unknown_interface:
            errors.append(f"{path}: interface 未知字段: {', '.join(unknown_interface)}")
        for field in sorted(OPENAI_INTERFACE_REQUIRED_FIELDS):
            value = interface.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{path}: interface.{field} 必须是非空字符串")
        for field in sorted(OPENAI_INTERFACE_OPTIONAL_FIELDS & set(interface)):
            value = interface[field]
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{path}: interface.{field} 必须是非空字符串")

    if "policy" not in data:
        return
    policy = data["policy"]
    if not isinstance(policy, dict):
        errors.append(f"{path}: policy 必须是对象")
        return
    unknown_policy = sorted(set(policy) - OPENAI_POLICY_FIELDS)
    if unknown_policy:
        errors.append(f"{path}: policy 未知字段: {', '.join(unknown_policy)}")
    if set(policy) != OPENAI_POLICY_FIELDS:
        errors.append(f"{path}: policy 仅允许声明 allow_implicit_invocation")
        return
    if policy["allow_implicit_invocation"] is not False:
        errors.append(
            f"{path}: implicit invocation 必须省略 policy；"
            "仅 explicit-only 可声明 allow_implicit_invocation: false"
        )


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
        openai_metadata = skill_dir / "agents/openai.yaml"
        if not openai_metadata.is_file():
            warnings.append(f"{skill_dir}: 缺少 agents/openai.yaml")
        else:
            validate_openai_metadata(openai_metadata, errors)
        if (skill_dir / ".git").exists():
            errors.append(f"{skill_dir}: 不应包含内嵌 .git")

        text = skill_md.read_text(encoding="utf-8")
        for match in LINK.finditer(text):
            rel = match.group(1).strip()
            if not (skill_dir / rel).exists():
                errors.append(f"{skill_md}: 引用文件不存在 {rel}")
        if re.search(r"~/.agents/skills|assets/codex|apply-to-codex|scan-codex-skills", text):
            errors.append(f"{skill_md}: 包含旧路径或旧入口")

        manifest_item = manifest_items.get(name)
        if manifest_item is None:
            errors.append(f"{skill_md}: source skill 未登记到 manifests/skills.json")
            continue
        if "local" in manifest_item.get("tags", []):
            for doc_path in (skill_md, skill_dir / "README.md"):
                doc_text = doc_path.read_text(encoding="utf-8")
                in_fence = False
                for line_number, line in enumerate(doc_text.splitlines(), 1):
                    if line.lstrip().startswith("```"):
                        in_fence = not in_fence
                        continue
                    if in_fence and BARE_LOCAL_COMMAND.match(line):
                        errors.append(
                            f"{doc_path}:{line_number}: local skill 命令必须通过 rtk 执行"
                        )
                for match in SCRIPT_REF.finditer(doc_text):
                    rel = match.group(1)
                    if rel.startswith("./"):
                        rel = rel[2:]
                    if not (ROOT / rel).exists() and not (skill_dir / rel).exists():
                        errors.append(f"{doc_path}: local skill 引用不可用脚本 {rel}")

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
        if "-dirty-" in str(manifest_item.get("source_ref", "")):
            errors.append(f"manifest:{name} accepted runtime asset 不得使用 dirty source_ref")
        if item.get("enabled") and item.get("source_repo") and item.get("review_status") != "accepted":
            errors.append(f"manifest:{name} 第三方来源必须 review_status=accepted")

    for warning in warnings:
        print(f"[WARN ] {warning}")
    for error in errors:
        print(f"[ERROR] {error}")
    print(f"[INFO ] skills={len(names)} errors={len(errors)} warnings={len(warnings)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
