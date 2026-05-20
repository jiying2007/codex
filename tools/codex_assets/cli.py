from __future__ import annotations

import argparse
import json
import pathlib
import sys
from datetime import datetime

from .core import (
    CodexAssetError,
    Repo,
    active,
    archive_note,
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
from .archive_search import run as run_archive_search
from .archive_governance import ArchiveGovernanceError, run_check as run_archive_check
from .governance import governance_errors, governance_report
from .memory_curator import run as run_memory_curator
from .session_coach import run as run_session_coach
from .usage_dashboard import main as usage_dashboard_main
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
    plan = plan_apply(repo.root, build, target, backup_root, args.overwrite, args.prune_stale)
    output = pathlib.Path(args.output).expanduser() if args.output else repo.root / "build/apply-plan.json"
    write_json(output, plan)
    print(f"[DONE] plan output={output} summary={plan['summary']}")
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    repo = Repo.from_path(args.root)
    if args.plan:
        plan = read_json(pathlib.Path(args.plan).expanduser())
        target = pathlib.Path(plan["target"]).expanduser()
    else:
        build = pathlib.Path(args.build).expanduser().resolve() if args.build else repo.build
        if args.run_build and not args.dry_run:
            build = build_repo(repo.root, args.profile or "", "", str(build))
        target = pathlib.Path(args.target).expanduser()
        backup_root = pathlib.Path(args.backup_root).expanduser() if args.backup_root else repo.root / ".backups/apply" / datetime.now().strftime("%Y%m%d-%H%M%S")
        plan = plan_apply(repo.root, build, target, backup_root, args.overwrite, args.prune_stale)
    if args.plan_out:
        write_json(pathlib.Path(args.plan_out).expanduser(), plan)
    if args.dry_run:
        for action in plan["actions"]:
            if action["action"] in {"copy", "overwrite", "delete", "skip"}:
                print(f"[DRY ] {action['action']} {action['path']}")
        print(f"[DONE] apply target={target} summary={plan['summary']} dry_run=1")
        return 0
    apply_plan(plan, dry_run=False)
    print(f"[DONE] apply target={target} summary={plan['summary']} dry_run=0")
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    repo = Repo.from_path(args.root)
    build = pathlib.Path(args.build).expanduser().resolve() if args.build else repo.build
    ignored = repo.policies.get("allowed_live_drift_paths", [])
    same, diff, missing = diff_build_live(build, pathlib.Path(args.target).expanduser(), ignored)
    print(f"[INFO] same={same} diff={diff} missing={missing}")
    return 1 if diff or missing else 0


def cmd_drift(args: argparse.Namespace) -> int:
    repo = Repo.from_path(args.root)
    build = pathlib.Path(args.build).expanduser().resolve() if args.build else repo.build
    ignored = repo.policies.get("allowed_live_drift_paths", [])
    drift = live_drift(build, pathlib.Path(args.target).expanduser(), ignored)
    if args.output:
        write_json(pathlib.Path(args.output).expanduser(), drift)
    for path in drift.get("changed", []):
        print(f"[DRIFT] {path}")
    for path in drift.get("stale", []):
        print(f"[STALE] {path}")
    for path in drift.get("unmanaged", []):
        print(f"[UNMANAGED] {path}")
    print(
        f"[INFO] status={drift['status']} changed={len(drift.get('changed', []))} "
        f"stale={len(drift.get('stale', []))} unmanaged={len(drift.get('unmanaged', []))}"
    )
    return 1 if drift.get("changed") or drift.get("stale") or drift.get("unmanaged") else 0


def cmd_doctor(args: argparse.Namespace) -> int:
    repo = Repo.from_path(args.root)
    errors: list[str] = []
    warnings: list[str] = []
    if args.scope == "governance":
        print("[INFO ] scope=governance")
        errors.extend(governance_errors(repo))
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
            drift = live_drift(
                pathlib.Path(args.build).expanduser().resolve() if args.build else repo.build,
                target,
                repo.policies.get("allowed_live_drift_paths", []),
            )
            for path in drift.get("unmanaged", []):
                errors.append(f"live 包含未管理资产: {path}")
    for error in errors:
        print(f"[ERROR] {error}")
    for warning in warnings:
        print(f"[WARN ] {warning}")
    print(f"[INFO ] errors={len(errors)} warnings={len(warnings)}")
    return 1 if errors else 0


def cmd_governance_report(args: argparse.Namespace) -> int:
    report = governance_report(args.root)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    print(f"[INFO] default_profile={report['default_profile']}")
    print(
        "[INFO] "
        f"profiles={len(report['profiles'])} "
        f"skills={len(report['skills'])} "
        f"agents={len(report['agents'])} "
        f"workflows={len(report['workflows'])} "
        f"project_templates={len(report['project_templates'])} "
        f"overlays={len(report['overlays'])}"
    )
    for name, links in report["workflow_links"].items():
        print(
            f"[WORKFLOW] {name} "
            f"profiles={','.join(links['profiles']) or '-'} "
            f"skills={','.join(links['skills']) or '-'} "
            f"agents={','.join(links['agents']) or '-'}"
        )
    for name, links in report["template_links"].items():
        print(
            f"[TEMPLATE] {name} "
            f"profile={links['default_profile'] or '-'} "
            f"workflows={','.join(links['workflows']) or '-'} "
            f"archive_topics={','.join(links['archive_topics']) or '-'}"
        )
    return 0


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


def cmd_archive_note(args: argparse.Namespace) -> int:
    meta = archive_note(
        args.root,
        args.source,
        topic_arg=args.topic,
        dest_arg=args.dest,
        title_arg=args.title,
        description=args.description,
        project_arg=args.project,
        source_repo_arg=args.source_repo,
        workstream_arg=args.workstream,
        session_arg=args.session,
        status_arg=args.status,
        scope_arg=args.scope,
        kind_arg=args.kind,
        owner_arg=args.owner,
        next_action_arg=args.next_action,
        memory_action_arg=args.memory_action,
        tags_arg=args.tag,
        no_project_detect=args.no_project_detect,
        move=args.move,
        dry_run=args.dry_run,
    )
    print(f"[DONE] archive-note destination={meta['destination']} dry_run={int(args.dry_run)}")
    return 0


def cmd_archive_check(args: argparse.Namespace) -> int:
    return run_archive_check(args.root, json_output=args.json)


def cmd_curate_memory(args: argparse.Namespace) -> int:
    mapped = argparse.Namespace(
        repo=args.root,
        memories=args.memories,
        output=args.output,
        days=args.days,
        dry_run=args.dry_run,
        write_memory_candidate=args.write_memory_candidate,
    )
    return run_memory_curator(mapped)


def cmd_archive_search(args: argparse.Namespace) -> int:
    mapped = argparse.Namespace(
        repo=args.root,
        query=args.query,
        limit=args.limit,
        json=args.json,
        include=args.include,
        index_db=args.index_db,
        rebuild_index=args.rebuild_index,
        topic=args.topic,
        tag=args.tag,
        kind=args.kind,
        since=args.since,
        until=args.until,
        project=args.project,
        workstream=args.workstream,
        session=args.session,
        scope=args.scope,
        status=args.status,
        governance_status=args.governance_status,
        memory_action=args.memory_action,
        owner=args.owner,
        open_only=args.open_only,
    )
    return run_archive_search(mapped)


def cmd_session_coach(args: argparse.Namespace) -> int:
    return run_session_coach(args)


def cmd_usage_report(args: argparse.Namespace) -> int:
    argv = [
        "report",
        "--codex-home",
        args.codex_home,
        "--view",
        args.view,
        "--state-db",
        args.state_db,
        "--sessions-root",
        args.sessions_root,
        "--limit",
        str(args.limit),
        "--top-models",
        str(args.top_models),
        "--top-repos",
        str(args.top_repos),
        "--thread-sort",
        args.thread_sort,
        "--warn-thread-tokens",
        str(args.warn_thread_tokens),
    ]
    if args.json:
        argv.append("--json")
    return usage_dashboard_main(argv)


def cmd_usage_tail(args: argparse.Namespace) -> int:
    argv = [
        "tail",
        "--codex-home",
        args.codex_home,
        "--view",
        args.view,
        "--state-db",
        args.state_db,
        "--sessions-root",
        args.sessions_root,
        "--limit",
        str(args.limit),
        "--top-models",
        str(args.top_models),
        "--top-repos",
        str(args.top_repos),
        "--thread-sort",
        args.thread_sort,
        "--warn-thread-tokens",
        str(args.warn_thread_tokens),
        "--interval",
        str(args.interval),
        "--iterations",
        str(args.iterations),
    ]
    if args.json:
        argv.append("--json")
    if args.interactive:
        argv.append("--interactive")
    if args.once:
        argv.append("--once")
    return usage_dashboard_main(argv)


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
    p.add_argument("--prune-stale", action="store_true", help="delete previously managed files absent from the current build")
    p.add_argument("--output", default="")
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser("apply", parents=[common])
    p.add_argument("--build", default="")
    p.add_argument("--target", default="~/.codex")
    p.add_argument("--profile", default="")
    p.add_argument("--plan", default="")
    p.add_argument("--no-build", dest="run_build", action="store_false", default=True)
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--prune-stale", action="store_true", help="delete previously managed files absent from the current build")
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
    p.add_argument("--scope", default="all", choices=["repo", "governance", "build", "live", "all"])
    p.add_argument("--build", default="")
    p.add_argument("--target", default="~/.codex")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("governance-report", parents=[common])
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_governance_report)

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

    p = sub.add_parser("archive-note", parents=[common])
    p.add_argument("source")
    p.add_argument("--topic", default="")
    p.add_argument("--dest", default="")
    p.add_argument("--title", default="")
    p.add_argument("--description", default="")
    p.add_argument("--project", default="")
    p.add_argument("--source-repo", default="")
    p.add_argument("--workstream", default="")
    p.add_argument("--session", default="")
    p.add_argument("--status", default="closed", choices=["open", "closed", "blocked"])
    p.add_argument("--scope", default="", choices=["", "codex-governance", "codex-knowledge", "project-specific", "session-summary", "legacy-local-runtime"])
    p.add_argument("--kind", default="")
    p.add_argument("--owner", default="")
    p.add_argument("--next-action", default="")
    p.add_argument("--memory-action", default="archive-only", choices=["archive-only", "candidate", "promote-to-agents", "write-to-memory", "drop-or-review"])
    p.add_argument("--tag", action="append", default=[])
    p.add_argument("--no-project-detect", action="store_true")
    p.add_argument("--move", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_archive_note)

    p = sub.add_parser("archive-check", parents=[common])
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_archive_check)

    p = sub.add_parser("archive-search", parents=[common])
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--json", action="store_true")
    p.add_argument("--include", action="append", default=[])
    p.add_argument("--index-db", default="")
    p.add_argument("--rebuild-index", action="store_true")
    p.add_argument("--topic", action="append", default=[])
    p.add_argument("--tag", action="append", default=[])
    p.add_argument("--type", dest="kind", action="append", default=[])
    p.add_argument("--project", action="append", default=[])
    p.add_argument("--workstream", action="append", default=[])
    p.add_argument("--session", action="append", default=[])
    p.add_argument("--scope", action="append", default=[])
    p.add_argument("--status", action="append", default=[])
    p.add_argument("--governance-status", action="append", default=[])
    p.add_argument("--memory-action", action="append", default=[])
    p.add_argument("--owner", action="append", default=[])
    p.add_argument("--open-only", action="store_true")
    p.add_argument("--since", default="")
    p.add_argument("--until", default="")
    p.set_defaults(func=cmd_archive_search)

    p = sub.add_parser("curate-memory", parents=[common])
    p.add_argument("--memories", default="~/.codex/memories")
    p.add_argument("--output", default="")
    p.add_argument("--days", type=int, default=14)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--write-memory-candidate", action="store_true")
    p.set_defaults(func=cmd_curate_memory)

    p = sub.add_parser("session-coach", parents=[common])
    p.add_argument("--codex-home", default="~/.codex")
    p.add_argument("--target", default="~/.codex")
    p.add_argument("--deep", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument("--warn-thread-tokens", type=int, default=None)
    p.add_argument("--top", type=int, default=None)
    p.add_argument("--all", action="store_true")
    p.add_argument("--event", default="", choices=["", "final", "commit", "push", "apply", "resume", "target-switch", "memory-curation"])
    p.add_argument("--fail-on", default="never", choices=["never", "critical", "high", "medium", "info"])
    p.add_argument("--config", default="")
    p.add_argument("--state-file", default="")
    p.add_argument("--reset-state", action="store_true")
    p.add_argument("--no-cooldown", action="store_true")
    p.add_argument("--ack", default="")
    p.add_argument("--clear-acks", action="store_true")
    p.add_argument("--evidence-file", default="")
    p.add_argument("--record-evidence", default="")
    p.add_argument("--evidence-status", default="pass", choices=["pass", "fail"])
    p.add_argument("--evidence-summary", default="")
    p.set_defaults(func=cmd_session_coach)

    p = sub.add_parser("usage-report", parents=[common])
    p.add_argument("--codex-home", default="~/.codex")
    p.add_argument("--view", default="summary", choices=["summary", "threads", "trends"])
    p.add_argument("--state-db", default="")
    p.add_argument("--sessions-root", default="")
    p.add_argument("--limit", type=int, default=8)
    p.add_argument("--top-models", type=int, default=5)
    p.add_argument("--top-repos", type=int, default=5)
    p.add_argument("--thread-sort", default="updated", choices=["updated", "tokens", "model", "repo"])
    p.add_argument("--json", action="store_true")
    p.add_argument("--warn-thread-tokens", type=int, default=50_000_000)
    p.set_defaults(func=cmd_usage_report)

    p = sub.add_parser("usage-tail", parents=[common])
    p.add_argument("--codex-home", default="~/.codex")
    p.add_argument("--view", default="summary", choices=["summary", "threads", "trends", "auto"])
    p.add_argument("--interactive", action="store_true")
    p.add_argument("--state-db", default="")
    p.add_argument("--sessions-root", default="")
    p.add_argument("--limit", type=int, default=8)
    p.add_argument("--top-models", type=int, default=5)
    p.add_argument("--top-repos", type=int, default=5)
    p.add_argument("--thread-sort", default="updated", choices=["updated", "tokens", "model", "repo"])
    p.add_argument("--json", action="store_true")
    p.add_argument("--warn-thread-tokens", type=int, default=50_000_000)
    p.add_argument("--interval", type=float, default=3.0)
    p.add_argument("--iterations", type=int, default=0)
    p.add_argument("--once", action="store_true")
    p.set_defaults(func=cmd_usage_tail)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        raise SystemExit(args.func(args))
    except (CodexAssetError, ArchiveGovernanceError) as exc:
        print(f"[FATAL] {exc}", file=sys.stderr)
        raise SystemExit(2)
