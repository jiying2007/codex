from __future__ import annotations

import argparse
import pathlib
import sys
from datetime import datetime

from .core import (
    CodexAssetError,
    Repo,
    active,
    apply_plan,
    build_repo,
    diff_build_live,
    fail,
    frontmatter_value,
    live_drift,
    normalize_name,
    plan_apply,
    read_json,
    rollback_plan,
    split_list,
    write_json,
)
from .validate import validate_repo


def default_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[2]


def cmd_build(args: argparse.Namespace) -> int:
    build = build_repo(args.root, args.profile or "", args.source or "", args.build or "")
    state = read_json(build / "control/state/managed-files.json")
    print(f"[DONE] build profile={state['profile']} output={build} managed={len(state['managed'])}")
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    repo = Repo.from_path(args.root)
    build = pathlib.Path(args.build).expanduser().resolve() if args.build else repo.build
    target = pathlib.Path(args.target).expanduser()
    backup_root = pathlib.Path(args.backup_root).expanduser() if args.backup_root else repo.root / ".backups/apply" / datetime.now().strftime("%Y%m%d-%H%M%S")
    plan = plan_apply(repo.root, build, target, backup_root, args.overwrite)
    output = pathlib.Path(args.output).expanduser() if args.output else repo.root / "build/apply-plan.json"
    write_json(output, plan)
    print(f"[DONE] plan output={output} summary={plan['summary']}")
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    repo = Repo.from_path(args.root)
    build = pathlib.Path(args.build).expanduser().resolve() if args.build else repo.build
    if args.run_build and not args.dry_run:
        build = build_repo(repo.root, args.profile or "", "", str(build))
    target = pathlib.Path(args.target).expanduser()
    backup_root = pathlib.Path(args.backup_root).expanduser() if args.backup_root else repo.root / ".backups/apply" / datetime.now().strftime("%Y%m%d-%H%M%S")
    plan = plan_apply(repo.root, build, target, backup_root, args.overwrite)
    if args.plan_out:
        write_json(pathlib.Path(args.plan_out).expanduser(), plan)
    if args.dry_run:
        for action in plan["actions"]:
            if action["action"] in {"copy", "overwrite", "skip"}:
                print(f"[DRY ] {action['action']} {action['path']}")
        print(f"[DONE] apply target={target} summary={plan['summary']} dry_run=1")
        return 0
    apply_plan(plan, dry_run=False)
    print(f"[DONE] apply target={target} summary={plan['summary']} dry_run=0")
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    repo = Repo.from_path(args.root)
    build = pathlib.Path(args.build).expanduser().resolve() if args.build else repo.build
    same, diff, missing = diff_build_live(build, pathlib.Path(args.target).expanduser())
    print(f"[INFO] same={same} diff={diff} missing={missing}")
    return 1 if diff or missing else 0


def cmd_drift(args: argparse.Namespace) -> int:
    repo = Repo.from_path(args.root)
    build = pathlib.Path(args.build).expanduser().resolve() if args.build else repo.build
    drift = live_drift(build, pathlib.Path(args.target).expanduser())
    if args.output:
        write_json(pathlib.Path(args.output).expanduser(), drift)
    for path in drift.get("changed", []):
        print(f"[DRIFT] {path}")
    for path in drift.get("stale", []):
        print(f"[STALE] {path}")
    print(f"[INFO] status={drift['status']} changed={len(drift.get('changed', []))} stale={len(drift.get('stale', []))}")
    return 1 if drift.get("changed") or drift.get("stale") else 0


def cmd_doctor(args: argparse.Namespace) -> int:
    repo = Repo.from_path(args.root)
    errors: list[str] = []
    warnings: list[str] = []
    if args.scope in {"repo", "all"}:
        print("[INFO ] scope=repo")
        errors.extend(validate_repo(repo.root))
        if (repo.root / "assets").exists():
            errors.append("旧 assets/ 入口仍存在")
        for path in ["skills/.system", "auth.json", "sessions", "cache", "tmp", "log"]:
            if (repo.source / path).exists():
                errors.append(f"源资产包含受保护运行态路径: {path}")
    if args.scope in {"build", "all"}:
        print("[INFO ] scope=build")
        build = pathlib.Path(args.build).expanduser().resolve() if args.build else repo.build
        if not build.is_dir():
            errors.append(f"构建目录不存在: {build}")
        elif not (build / "control/state/managed-files.json").is_file():
            errors.append("build 缺少 managed-files.json")
        else:
            state = read_json(build / "control/state/managed-files.json")
            profile = state.get("profile", repo.assets.get("default_profile", ""))
            active_sources = {item["vendor_rel"] for item in repo.manifest("skills.json").get("skills", []) if active(item, profile)}
            for skill_md in sorted((build / "vendor/plugins").glob("*/*/skills/*/SKILL.md")):
                rel = skill_md.parent.relative_to(build).as_posix()
                if rel not in active_sources:
                    errors.append(f"build 包含未激活 plugin skill: {rel}")
    if args.scope in {"live", "all"}:
        print("[INFO ] scope=live")
        target = pathlib.Path(args.target).expanduser()
        if not target.is_dir():
            errors.append(f"运行目录不存在: {target}")
        else:
            if not (target / "skills/.system").is_dir():
                warnings.append("live 缺少 skills/.system")
            if not (target / "control/state/managed-files.json").is_file():
                warnings.append("live 缺少 managed-files.json")
            profile_file = target / "control/state/active-profile.env"
            if profile_file.is_file():
                print(f"[INFO ] {profile_file.read_text().strip()}")
            for path in [
                "control/scripts",
                "control/catalog",
                "control/generated",
                "control/archives",
                "control/knowledge",
                "control/roles",
                "control/workflows",
            ]:
                if (target / path).exists():
                    errors.append(f"live 包含 v1 control 残留: {path}")
    for error in errors:
        print(f"[ERROR] {error}")
    for warning in warnings:
        print(f"[WARN ] {warning}")
    print(f"[INFO ] errors={len(errors)} warnings={len(warnings)}")
    return 1 if errors else 0


def cmd_scan_skills(args: argparse.Namespace) -> int:
    repo = Repo.from_path(args.root)
    codex_home = pathlib.Path(args.codex_home).expanduser()
    inbox = pathlib.Path(args.inbox).expanduser() if args.inbox else repo.root / "inbox/skills"
    skills_dir = codex_home / "skills"
    if not skills_dir.is_dir():
        fail(f"skills 目录不存在: {skills_dir}")
    registered = {item["name"] for item in repo.manifest("skills.json").get("skills", [])}
    found = copied = 0
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    for skill in sorted(skills_dir.iterdir(), key=lambda p: p.name):
        if skill.name in {".system", "scripts"} or skill.is_symlink() or not skill.is_dir():
            continue
        if not (skill / "SKILL.md").is_file():
            continue
        found += 1
        name = frontmatter_value(skill / "SKILL.md", "name") or skill.name
        if name in registered:
            print(f"[KEEP] {name} (registered)")
            continue
        dest = inbox / name / timestamp
        print(f"[NEW ] {name} -> {dest}")
        if not args.dry_run:
            import shutil
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(skill, dest)
        copied += 1
    print(f"[INFO] scanned={found} intake={copied} inbox={inbox}")
    return 0


def cmd_promote_skill(args: argparse.Namespace) -> int:
    import re
    import shutil

    repo = Repo.from_path(args.root)
    skill_path = pathlib.Path(args.skill_path).expanduser().resolve()
    if "/skills/.system" in str(skill_path):
        fail(f"拒绝归档系统 skill: {skill_path}")
    if not (skill_path / "SKILL.md").is_file():
        fail(f"缺少 SKILL.md: {skill_path}")
    if not re.match(r"^[0-9]+\.[0-9]+\.[0-9]+([+-][A-Za-z0-9.-]+)?$", args.version):
        fail(f"version 必须是语义化版本: {args.version}")
    name = normalize_name(args.name or frontmatter_value(skill_path / "SKILL.md", "name") or skill_path.name)
    vendor_rel = f"vendor/skills/{name}/{args.version}"
    dest = repo.source / vendor_rel
    manifest_path = repo.manifests_dir / "skills.json"
    manifest = read_json(manifest_path)
    items = manifest.setdefault("skills", [])
    if any(item.get("name") == name for item in items) and not args.replace:
        fail(f"manifest 已存在 skill: {name}（如需替换，加 --replace）")
    if dest.exists():
        fail(f"目标版本目录已存在: {dest}")
    entry = {
        "name": name,
        "enabled": True,
        "source_kind": "vendor",
        "version": args.version,
        "vendor_rel": vendor_rel,
        "target_rel": f"skills/{name}",
        "profiles": split_list(args.profiles),
        "tags": split_list(args.tags),
        "owner": args.owner,
    }
    for key, value in {
        "source_repo": args.source_repo,
        "source_ref": args.source_ref,
        "source_path": args.source_path,
        "imported_at": args.imported_at,
        "review_status": args.review_status,
    }.items():
        if value:
            entry[key] = value
    print(f"[INFO] promote name={name} version={args.version}")
    if not args.dry_run:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(skill_path, dest)
        items[:] = [item for item in items if item.get("name") != name]
        items.append(entry)
        items.sort(key=lambda item: item["name"])
        write_json(manifest_path, manifest)
    print(f"[DONE] promoted {name}@{args.version}")
    return 0


def cmd_rollback(args: argparse.Namespace) -> int:
    summary = rollback_plan(args.plan, dry_run=args.dry_run, remove_copies=not args.keep_copies)
    print(f"[DONE] rollback summary={summary} dry_run={int(args.dry_run)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="codex-assets")
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", default=str(default_root()))

    p = sub.add_parser("build", parents=[common])
    p.add_argument("--profile", default="")
    p.add_argument("--source", default="")
    p.add_argument("--build", default="")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("plan", parents=[common])
    p.add_argument("--build", default="")
    p.add_argument("--target", default="~/.codex")
    p.add_argument("--backup-root", default="")
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--output", default="")
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser("apply", parents=[common])
    p.add_argument("--build", default="")
    p.add_argument("--target", default="~/.codex")
    p.add_argument("--profile", default="")
    p.add_argument("--no-build", dest="run_build", action="store_false", default=True)
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--backup-root", default="")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--plan-out", default="")
    p.set_defaults(func=cmd_apply)

    p = sub.add_parser("diff", parents=[common])
    p.add_argument("--build", default="")
    p.add_argument("--target", default="~/.codex")
    p.set_defaults(func=cmd_diff)

    p = sub.add_parser("drift", parents=[common])
    p.add_argument("--build", default="")
    p.add_argument("--target", default="~/.codex")
    p.add_argument("--output", default="")
    p.set_defaults(func=cmd_drift)

    p = sub.add_parser("doctor", parents=[common])
    p.add_argument("--scope", default="all", choices=["repo", "build", "live", "all"])
    p.add_argument("--build", default="")
    p.add_argument("--target", default="~/.codex")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("scan-skills", parents=[common])
    p.add_argument("--codex-home", default="~/.codex")
    p.add_argument("--inbox", default="")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_scan_skills)

    p = sub.add_parser("promote-skill", parents=[common])
    p.add_argument("skill_path")
    p.add_argument("--name", default="")
    p.add_argument("--version", required=True)
    p.add_argument("--profiles", default="solo-dev,team-collab")
    p.add_argument("--tags", default="custom")
    p.add_argument("--owner", default="global")
    p.add_argument("--source-repo", default="")
    p.add_argument("--source-ref", default="")
    p.add_argument("--source-path", default="")
    p.add_argument("--imported-at", default="")
    p.add_argument("--review-status", default="")
    p.add_argument("--replace", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_promote_skill)

    p = sub.add_parser("rollback", parents=[common])
    p.add_argument("--plan", required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--keep-copies", action="store_true")
    p.set_defaults(func=cmd_rollback)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        raise SystemExit(args.func(args))
    except CodexAssetError as exc:
        print(f"[FATAL] {exc}", file=sys.stderr)
        raise SystemExit(2)
