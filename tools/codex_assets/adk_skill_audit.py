"""Read-only ADK Skill provenance audit; never installs or certifies a release."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
from typing import Any

REPOSITORY = "jiying2007/agent-dev-kit"
MAX_JSON = 2 * 1024 * 1024
MAX_FILE = 1024 * 1024
MAX_TREE = 8 * MAX_FILE
MAX_FILES = 256
MAX_SKILLS = 512


class AuditError(ValueError):
    """Invalid or unbounded audit input, not a passing or empty inventory."""


def _bytes(path: Path, limit: int) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise AuditError("regular_file_required")
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise AuditError("input_budget_exceeded")
    return data


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(_bytes(path, MAX_JSON))
    if not isinstance(value, dict):
        raise AuditError("json_object_required")
    return value


def _ref(value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > 300:
        raise AuditError("invalid_relative_path")
    path = PurePosixPath(value)
    if path.is_absolute() or "\\" in value or any(p in ("", ".", "..") for p in value.split("/")):
        raise AuditError("invalid_relative_path")
    if any(ord(char) < 32 for char in value):
        raise AuditError("invalid_relative_path")
    return path.as_posix()


def _path(root: Path, relative: str) -> Path:
    path = root
    for part in PurePosixPath(_ref(relative)).parts:
        path = path / part
        if path.is_symlink():
            raise AuditError("symlink_not_allowed")
    return path


def _blob(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _tree(root: Path) -> dict[str, dict[str, str]]:
    if root.is_symlink() or not root.is_dir():
        raise AuditError("skill_directory_required")
    files: dict[str, dict[str, str]] = {}
    total = 0
    directories = 0
    def unreadable(error: OSError) -> None:
        raise AuditError("skill_directory_unreadable") from error
    for directory, dirs, names in os.walk(root, followlinks=False, onerror=unreadable):
        directories += 1
        if directories > MAX_FILES:
            raise AuditError("tree_budget_exceeded")
        for name in dirs:
            if (Path(directory) / name).is_symlink():
                raise AuditError("symlink_not_allowed")
        for name in sorted(names):
            path = Path(directory) / name
            relative = _ref(path.relative_to(root).as_posix())
            data = _bytes(path, MAX_FILE)
            total += len(data)
            if len(files) >= MAX_FILES or total > MAX_TREE:
                raise AuditError("tree_budget_exceeded")
            files[relative] = {
                "blob": _blob(data),
                "mode": "100755" if path.stat().st_mode & 0o111 else "100644",
            }
    if "SKILL.md" not in files:
        raise AuditError("skill_entrypoint_missing")
    return files


def _source_tree(item: dict[str, Any], installed: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    """Project reviewed distribution metadata back to the exact upstream tree.

    Only non-executable packaging metadata may differ. SKILL.md, references and
    scripts can never be excluded or substituted by this declaration. Original
    metadata identities are verified against the pinned provider by import tests;
    this local check alone is not proof of upstream ownership.
    """
    metadata = item.get("distribution_metadata", {})
    if not isinstance(metadata, dict) or set(metadata) - {"README.md", "LICENSE", "agents/openai.yaml"}:
        raise AuditError("distribution_metadata_invalid")
    source = dict(installed)
    for path, binding in metadata.items():
        if not isinstance(binding, dict) or set(binding) != {"source", "installed"}:
            raise AuditError("distribution_metadata_invalid")
        original, actual = binding["source"], binding["installed"]
        for identity in (actual, original) if original is not None else (actual,):
            if (not isinstance(identity, dict) or set(identity) != {"blob", "mode"}
                    or identity.get("mode") != "100644"
                    or not isinstance(identity.get("blob"), str)
                    or re.fullmatch(r"[0-9a-f]{40}", identity["blob"]) is None):
                raise AuditError("distribution_metadata_invalid")
        if installed.get(path) != actual:
            raise AuditError("distribution_metadata_mismatch")
        if original is None:
            del source[path]
        else:
            # The only reviewed source transformation is flat display metadata
            # to the native Codex interface object. Never replace upstream prose.
            if path != "agents/openai.yaml":
                raise AuditError("distribution_source_override_forbidden")
            source[path] = original
    return source


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, timeout=20,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"}, check=False,
    )
    if result.returncode or len(result.stdout) > MAX_JSON:
        raise AuditError("provider_git_read_failed")
    return result.stdout.decode("utf-8").strip("\n")


def _provider(root: Path, commit: str) -> dict[str, Any]:
    if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise AuditError("exact_provider_commit_required")
    if Path(_git(root, "rev-parse", "--show-toplevel")).resolve() != root:
        raise AuditError("provider_root_must_be_checkout_root")
    if _git(root, "rev-parse", "HEAD") != commit:
        raise AuditError("provider_commit_mismatch")
    if _git(root, "status", "--porcelain", "--untracked-files=all"):
        raise AuditError("provider_checkout_dirty")
    tracked = {}
    for record in _git(root, "ls-tree", "-r", "-z", "--full-tree", "HEAD").split("\0"):
        if record:
            metadata, path = record.split("\t", 1)
            mode, kind, blob = metadata.split()
            tracked[path] = {"mode": mode, "blob": blob, "kind": kind}
    manifest = _json(_path(root, "manifest.json"))
    if tracked.get("manifest.json", {}).get("blob") != _blob(_bytes(root / "manifest.json", MAX_JSON)):
        raise AuditError("provider_manifest_not_exact")
    version = manifest.get("version")
    if not isinstance(version, str) or len(version) > 64 or re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version) is None:
        raise AuditError("provider_version_invalid")
    declared_skills = {
        item["path"]: item["name"]
        for section in ("skills", "optional_skills")
        for item in manifest.get(section, [])
        if isinstance(item, dict) and isinstance(item.get("name"), str)
        and isinstance(item.get("path"), str)
    }
    return {"commit": commit, "version": version, "tracked": tracked,
            "declared_skills": declared_skills}


def _skill_source_name(source: str) -> str:
    parts = PurePosixPath(_ref(source)).parts
    ordinary = len(parts) == 3 and parts[0] in ("skills", "optional-skills")
    nested = len(parts) == 4 and parts[0] == "optional-skills"
    if not (ordinary or nested) or parts[-1] != "SKILL.md" or any(
            re.fullmatch(r"[a-z0-9][a-z0-9-]*", part) is None for part in parts[1:-1]):
        raise AuditError("provider_skill_source_path_invalid")
    return parts[-2]


def _candidate(root: Path, source: str, provider: dict[str, Any]) -> dict[str, dict[str, str]]:
    name = _skill_source_name(source)
    if len(PurePosixPath(source).parts) > 3 and provider["declared_skills"].get(source) != name:
        raise AuditError("provider_nested_skill_not_declared")
    directory = _path(root, str(PurePosixPath(source).parent))
    tree = _tree(directory)
    prefix = f"{PurePosixPath(source).parent}/"
    expected = {path[len(prefix):] for path in provider["tracked"] if path.startswith(prefix)}
    if set(tree) != expected:
        raise AuditError("provider_skill_tree_incomplete")
    for relative, identity in tree.items():
        tracked = provider["tracked"].get(f"{PurePosixPath(source).parent}/{relative}", {})
        if tracked.get("kind") != "blob" or any(tracked.get(k) != v for k, v in identity.items()):
            raise AuditError("provider_skill_tree_not_exact")
    return tree


def audit(root: Path, provider_root: Path | None = None, expected_commit: str = "") -> dict[str, Any]:
    root = root.resolve()
    manifest = _json(_path(root, "manifests/skills.json"))
    lock = _json(_path(root, "manifests/provider-locks/agent-dev-kit.json"))
    if (lock.get("schema") != "codex-provider-lock/v3" or lock.get("repository") != REPOSITORY
            or not isinstance(lock.get("version"), str) or len(lock["version"]) > 64
            or not isinstance(lock.get("provider_commit"), str)
            or re.fullmatch(r"[0-9a-f]{40}", lock["provider_commit"]) is None):
        raise AuditError("provider_lock_identity_invalid")
    inventory = manifest.get("skills")
    if not isinstance(inventory, list) or len(inventory) > MAX_SKILLS:
        raise AuditError("skill_inventory_invalid")
    provider = _provider(provider_root.resolve(), expected_commit) if provider_root is not None else None
    if expected_commit and provider is None:
        raise AuditError("provider_root_required")
    rows = []
    seen = set()
    for item in inventory:
        if not isinstance(item, dict) or type(item.get("enabled")) is not bool:
            raise AuditError("skill_record_invalid")
        name = item.get("name")
        if not isinstance(name, str) or re.fullmatch(r"[a-z0-9][a-z0-9-]{0,119}", name) is None or name in seen:
            raise AuditError("skill_name_invalid_or_duplicate")
        seen.add(name)
        tags = item.get("tags", [])
        if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
            raise AuditError("skill_tags_invalid")
        selected = (name.startswith("adk-") or item.get("owner") == "agent-dev-kit"
                    or item.get("source_repo") in (REPOSITORY, "llm_agent/agent-dev-kit")
                    or bool({"adk", "agent-dev-kit"}.intersection(tags)))
        if not selected or not item["enabled"]:
            continue
        gaps = []
        if item.get("source_repo") != REPOSITORY:
            gaps.append("noncanonical_source_repository")
        if not isinstance(item.get("source_ref"), str) or re.fullmatch(r"[0-9a-f]{40}", item["source_ref"]) is None:
            gaps.append("nonexact_source_commit")
        source_blob = item.get("source_blob")
        if not isinstance(source_blob, str) or re.fullmatch(r"[0-9a-f]{40}", source_blob) is None:
            gaps.append("missing_or_invalid_source_blob")
        current = None
        source_tree = None
        source = None
        try:
            source = _ref(item.get("source_path"))
            if _skill_source_name(source) != name:
                raise AuditError("skill_source_name_mismatch")
            vendor = _ref(item.get("vendor_rel"))
            if not vendor.startswith(f"vendor/skills/{name}/") or len(PurePosixPath(vendor).parts) != 4:
                raise AuditError("skill_vendor_path_invalid")
            current = _tree(_path(root, f"src/codex-home/{vendor}"))
            source_tree = _source_tree(item, current)
            if source_blob is not None and source_blob != current["SKILL.md"]["blob"]:
                gaps.append("local_skill_blob_mismatch")
            # Exact-tree imports also bind references/scripts, not just SKILL.md.
            # Legacy records without this field remain diagnosed by their other gaps.
            if "source_tree_sha256" in item:
                tree_digest = item["source_tree_sha256"]
                if not isinstance(tree_digest, str) or re.fullmatch(r"[0-9a-f]{64}", tree_digest) is None:
                    gaps.append("invalid_source_tree_sha256")
                elif tree_digest != _digest(source_tree):
                    gaps.append("local_skill_tree_mismatch")
            if item.get("distribution_metadata") and "source_tree_sha256" not in item:
                gaps.append("distribution_source_tree_required")
        except (AuditError, OSError) as exc:
            gaps.append(str(exc) if isinstance(exc, AuditError) else "local_skill_read_failed")
        row: dict[str, Any] = {"name": name, "gaps": gaps, "matches_provider_lock_commit": item.get("source_ref") == lock.get("provider_commit"), "local_tree_sha256": _digest(current) if current else None, "target": None}
        if source_tree is not None and item.get("distribution_metadata"):
            row["distribution_metadata_paths"] = sorted(item["distribution_metadata"])
            row["upstream_tree_sha256"] = _digest(source_tree) if source_tree else None
        if provider is not None and source is not None:
            try:
                target = _candidate(provider_root.resolve(), source, provider)
                baseline = source_tree or current or {}
                row["target"] = {
                    "status": "source_available",
                    "entrypoint_blob": target["SKILL.md"]["blob"],
                    "tree_sha256": _digest(target),
                    "file_count": len(target),
                    "added": sorted(set(target) - set(baseline)),
                    "removed": sorted(set(baseline) - set(target)),
                    "changed": sorted(k for k in target.keys() & baseline.keys() if target[k] != baseline[k]),
                    "review_required": True,
                }
            except (AuditError, OSError) as exc:
                row["target"] = {"status": "blocked", "reason": str(exc) if isinstance(exc, AuditError) else "provider_skill_read_failed"}
        rows.append(row)
    if not rows:
        raise AuditError("no_active_adk_skills")
    counts: dict[str, int] = {}
    for row in rows:
        for gap in set(row["gaps"]):
            counts[gap] = counts.get(gap, 0) + 1
    candidate_blocked = sum(row["target"] is None or row["target"]["status"] == "blocked" for row in rows) if provider is not None else 0
    return {
        "schema_version": 1,
        "scope": "adk-skill-provenance-and-upgrade-audit",
        "input_identity": {"skill_manifest_sha256": _digest(manifest), "provider_lock_sha256": _digest(lock)},
        "status": "needs-fix" if counts or candidate_blocked else "consistent",
        "active_adk_skills": len(rows),
        "provider_lock_version": lock.get("version"),
        "skills_matching_provider_lock_commit": sum(row["matches_provider_lock_commit"] for row in rows),
        "gap_counts": dict(sorted(counts.items())),
        "candidate": {"commit": provider["commit"], "version": provider["version"], "blocked_skills": candidate_blocked} if provider else None,
        "claims": {"read_only": True, "release_verified": False, "installation_verified": False, "runtime_qualified": False},
        "skills": rows,
    }


def summary(report: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in report.items() if key != "skills"}


def _visible_entrypoint(stage: Path, profile: str, name: str, entry: dict[str, Any] | None) -> str:
    from .core import unchanged_from_managed

    stage = stage.resolve()
    rel = f"skills/{name}"
    link = _path(stage, "skills") / name
    if entry is None and (link.is_symlink() or link.exists()):
        return "unregistered-entrypoint"
    state = _path(stage, "control/state/managed-files.json")
    if not state.exists():
        return "state-unavailable"
    receipt = _json(state)
    managed = receipt.get("managed")
    if receipt.get("schema_version") != 2 or not isinstance(managed, list):
        raise AuditError("managed_state_invalid")
    if entry is None:
        prefix = f"vendor/skills/{name}/"
        paths = [row["path"] for row in managed
                 if isinstance(row, dict) and isinstance(row.get("path"), str)]
        nested = re.compile(r"vendor/skills/adk-[a-z0-9-]+/[^/]+/" + re.escape(name) + r"/SKILL\.md")
        nested_paths = [path for path in paths if nested.fullmatch(path)]
        if any(_path(stage, path).is_file() for path in nested_paths):
            return "unregistered-entrypoint"
        if nested_paths or any(path == rel or path.startswith(prefix) for path in paths):
            return "unregistered-managed-entry"
    if receipt.get("profile") != profile:
        return "different-profile"
    if entry is None:
        return "absent"
    vendor = _ref(entry.get("vendor_rel"))
    if not vendor.startswith(f"vendor/skills/{name}/") or len(PurePosixPath(vendor).parts) != 4:
        raise AuditError("skill_vendor_path_invalid")
    source = f"{vendor}/SKILL.md"
    required = {rel, source}
    matches = [row for row in managed if isinstance(row, dict) and row.get("path") in required]
    by_path = {row["path"]: row for row in matches}
    if len(matches) != len(by_path):
        raise AuditError("managed_state_duplicate_entries")
    if not by_path:
        return "unmanaged" if link.exists() or link.is_symlink() else "absent"
    if (by_path.get(rel, {}).get("target") != f"../{vendor}"
            or by_path.get(rel, {}).get("type") != "symlink"
            or by_path.get(source, {}).get("type") != "file"):
        return "identity-mismatch"
    installed = _path(stage, source)
    if not unchanged_from_managed(link, by_path[rel]) or not installed.is_file():
        return "drifted"
    data = _bytes(installed, MAX_FILE)
    if (hashlib.sha256(data).hexdigest() != by_path[source].get("sha256")
            or _blob(data) != entry.get("source_blob")):
        return "drifted"
    return "verified-entrypoint"


def visibility(root: Path, name: str, profile: str, build: Path, live: Path,
               provider_root: Path | None = None) -> dict[str, Any]:
    """Inspect each distribution stage; a filesystem entry proves no host discovery."""
    if re.fullmatch(r"adk-[a-z0-9][a-z0-9-]{0,115}", name) is None:
        raise AuditError("invalid_adk_skill_name")
    from .core import active

    root = root.resolve()
    profiles = _json(_path(root, "manifests/profiles.json"))["profiles"]
    if not any(row["name"] == profile for row in profiles):
        raise AuditError("unknown_profile")
    lock = _json(_path(root, "manifests/provider-locks/agent-dev-kit.json"))
    commit = lock.get("provider_commit")
    if (lock.get("repository") != REPOSITORY or not isinstance(commit, str)
            or re.fullmatch(r"[0-9a-f]{40}", commit) is None):
        raise AuditError("provider_lock_identity_invalid")
    rows = [row for row in _json(_path(root, "manifests/skills.json"))["skills"] if row["name"] == name]
    if len(rows) > 1:
        raise AuditError("skill_name_invalid_or_duplicate")
    entry = rows[0] if rows else None
    origin = {"state": "unobserved", "pinned_commit": commit, "declared_skill": None}
    if provider_root is not None:
        pinned = json.loads(_git(provider_root.resolve(), "show", f"{commit}:manifest.json"))
        for section in ("skills", "optional_skills"):
            for record in pinned.get(section, []):
                if record["name"] == name:
                    origin["declared_skill"] = {"class": section, "path": _ref(record["path"])}
        origin["state"] = "declared" if origin["declared_skill"] else "not-declared"
    selection = "not-registered"
    result = {"schema_version": 1, "skill": name, "profile": profile, "upstream": origin,
              "host_discovery": "unobserved"}
    if entry:
        if (type(entry.get("enabled")) is not bool or not isinstance(entry.get("profiles"), list)
                or not all(isinstance(value, str) for value in entry["profiles"])):
            raise AuditError("skill_record_invalid")
        selection = "selected" if active(entry, profile) else "not-selected" if entry["enabled"] else "disabled"
    result["build"] = _visible_entrypoint(build, profile, name, entry)
    result["live"] = _visible_entrypoint(live, profile, name, entry)
    result["distribution"] = {"state": selection, "source_commit": entry.get("source_ref") if entry else None,
                              "matches_provider_lock": entry is not None and entry.get("source_ref") == commit}
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--provider-root", type=Path)
    parser.add_argument("--expected-provider-commit", default="")
    parser.add_argument("--summary-json", action="store_true")
    parser.add_argument("--skill", help="read back one ADK Skill across distribution stages")
    parser.add_argument("--profile", help="Codex Runtime Profile for --skill")
    parser.add_argument("--build", type=Path, help="managed build root for --skill")
    parser.add_argument("--live", type=Path, help="managed live root for --skill")
    args = parser.parse_args(argv)
    if bool(args.skill) != bool(args.profile) or (not args.skill and (args.build or args.live)):
        parser.error("--skill and --profile are required together; --build/--live are for --skill only")
    try:
        if args.skill:
            if args.expected_provider_commit:
                parser.error("--skill uses the exact commit in the provider lock")
            report = visibility(args.root, args.skill, args.profile, args.build or args.root / "build/codex-home",
                                args.live or Path.home() / ".codex", args.provider_root)
            print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=None if args.summary_json else 2))
            return 0
        report = audit(args.root, args.provider_root, args.expected_provider_commit)
    except (AuditError, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(json.dumps({"schema_version": 1, "status": "blocked", "reason": str(exc) if isinstance(exc, AuditError) else "audit_input_unavailable"}, separators=(",", ":")))
        return 3
    print(json.dumps(summary(report) if args.summary_json else report, ensure_ascii=False, sort_keys=True, separators=(",", ":") if args.summary_json else None, indent=None if args.summary_json else 2))
    return 2 if report["status"] == "needs-fix" else 0


if __name__ == "__main__":
    raise SystemExit(main())
