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
    return {"commit": commit, "version": version, "tracked": tracked}


def _candidate(root: Path, source: str, provider: dict[str, Any]) -> dict[str, dict[str, str]]:
    parts = PurePosixPath(source).parts
    if len(parts) != 3 or parts[0] not in ("skills", "optional-skills") or parts[2] != "SKILL.md":
        raise AuditError("provider_skill_source_path_invalid")
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
        source = None
        try:
            source = _ref(item.get("source_path"))
            if source != f"skills/{name}/SKILL.md" and source != f"optional-skills/{name}/SKILL.md":
                raise AuditError("skill_source_name_mismatch")
            vendor = _ref(item.get("vendor_rel"))
            if not vendor.startswith(f"vendor/skills/{name}/") or len(PurePosixPath(vendor).parts) != 4:
                raise AuditError("skill_vendor_path_invalid")
            current = _tree(_path(root, f"src/codex-home/{vendor}"))
            if source_blob is not None and source_blob != current["SKILL.md"]["blob"]:
                gaps.append("local_skill_blob_mismatch")
        except (AuditError, OSError) as exc:
            gaps.append(str(exc) if isinstance(exc, AuditError) else "local_skill_read_failed")
        row: dict[str, Any] = {"name": name, "gaps": gaps, "matches_provider_lock_commit": item.get("source_ref") == lock.get("provider_commit"), "local_tree_sha256": _digest(current) if current else None, "target": None}
        if provider is not None and source is not None:
            try:
                target = _candidate(provider_root.resolve(), source, provider)
                baseline = current or {}
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--provider-root", type=Path)
    parser.add_argument("--expected-provider-commit", default="")
    parser.add_argument("--summary-json", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = audit(args.root, args.provider_root, args.expected_provider_commit)
    except (AuditError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(json.dumps({"schema_version": 1, "status": "blocked", "reason": str(exc) if isinstance(exc, AuditError) else "audit_input_unavailable"}, separators=(",", ":")))
        return 3
    print(json.dumps(summary(report) if args.summary_json else report, ensure_ascii=False, sort_keys=True, separators=(",", ":") if args.summary_json else None, indent=None if args.summary_json else 2))
    return 2 if report["status"] == "needs-fix" else 0


if __name__ == "__main__":
    raise SystemExit(main())
