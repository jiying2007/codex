"""Import one signed, exact ADK source set into Codex's declared assets.

This is a source-repository operation. It never builds or writes the live Codex home.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any

from .adk_skill_audit import (
    REPOSITORY,
    _blob,
    _candidate,
    _digest,
    _provider,
    _source_tree,
    _tree,
    audit,
)


class ImportError(ValueError):
    """Candidate does not satisfy the exact-source import boundary."""


POLICY_FILES = ("__init__.py", "contracts.py", "decision.py", "reducer.py")
TRUSTED_ROOT_SHA256 = "6494e21ea73fa7ee769f85f57d5a3e6a08725eae1e38c755fc3517c9e6bc0b66"
PROTECTED_PREFIXES = (
    "manifests/skills.json",
    "manifests/agents.json",
    "manifests/provider-locks/agent-dev-kit.json",
    "manifests/execution_policy.json",
    "src/codex-home/vendor/skills/",
    "src/codex-home/vendor/agents/agent-dev-kit/",
    "src/codex-home/skills/registry.csv",
    "tools/codex_assets/execution_policy/",
)


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ImportError(f"JSON root must be an object: {path}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True,
        timeout=20, check=False,
    )
    if completed.returncode:
        raise ImportError(completed.stderr.strip() or "git inspection failed")
    return completed.stdout.strip()


def _check_target_clean(root: Path) -> None:
    if _git(root, "branch", "--show-current") in ("", "main", "master"):
        raise ImportError("source import requires an isolated candidate branch")
    for line in _git(root, "status", "--porcelain=v1", "--untracked-files=all").splitlines():
        path = line[3:].split(" -> ")[-1]
        if any(path == prefix or path.startswith(prefix) for prefix in PROTECTED_PREFIXES):
            raise ImportError(f"import target has pre-existing changes: {path}")


def _skill_version(path: Path) -> str:
    match = re.search(r"(?m)^version:\s*([0-9]+\.[0-9]+\.[0-9]+)\s*$", path.read_text(encoding="utf-8"))
    if match is None:
        raise ImportError(f"upstream Skill version is missing: {path}")
    return match.group(1)


def _promotion(evidence_path: Path, provider: dict[str, Any], artifact_sha256: str) -> None:
    evidence = _json(evidence_path)
    source = evidence.get("source", {})
    release = evidence.get("release", {})
    tracked = provider["tracked"]
    expected = {
        "repository": REPOSITORY,
        "ref": "refs/heads/main",
        "event": "push",
        "version": provider["version"],
        "commit": provider["commit"],
        "tree": _git(provider["root"], "rev-parse", "HEAD^{tree}"),
        "manifest_blob": tracked["manifest.json"]["blob"],
    }
    if (evidence.get("schema") != "adk-promotion-evidence/v1"
            or not isinstance(source, dict) or not isinstance(release, dict)
            or any(source.get(key) != value for key, value in expected.items())
            or release.get("release_eligible") is not True
            or release.get("artifact_sha256") != artifact_sha256):
        raise ImportError("signed promotion does not bind the exact ADK source and artifact")


def plan(root: Path, provider_root: Path, commit: str, evidence_path: Path,
         attestation_path: Path, trusted_root: Path, artifact_sha256: str) -> dict[str, Any]:
    root = root.resolve()
    provider_root = provider_root.resolve()
    provider = _provider(provider_root, commit)
    provider["root"] = provider_root
    if not re.fullmatch(r"[0-9a-f]{64}", artifact_sha256):
        raise ImportError("exact release artifact SHA256 is required")
    if (trusted_root.is_symlink() or not trusted_root.is_file()
            or trusted_root.stat().st_size > 1024 * 1024
            or hashlib.sha256(trusted_root.read_bytes()).hexdigest() != TRUSTED_ROOT_SHA256):
        raise ImportError("Sigstore trusted root is not the reviewed exact file")
    _promotion(evidence_path, provider, artifact_sha256)
    verifier = subprocess.run(
        ["cosign", "verify-blob", "--bundle", str(attestation_path),
         "--trusted-root", str(trusted_root),
         "--certificate-identity",
         "https://github.com/jiying2007/agent-dev-kit/.github/workflows/ci.yml@refs/heads/main",
         "--certificate-oidc-issuer", "https://token.actions.githubusercontent.com",
         str(evidence_path)],
        capture_output=True, text=True, timeout=45, check=False,
    )
    if verifier.returncode or "Verified OK" not in verifier.stdout + verifier.stderr:
        raise ImportError("Sigstore promotion verification failed")
    _check_target_clean(root)
    report = audit(root, provider_root, commit)
    if report["status"] != "consistent" or report["candidate"]["blocked_skills"]:
        raise ImportError("ADK source audit is not consistent")
    skills = _json(root / "manifests/skills.json")
    by_name = {item["name"]: item for item in skills["skills"]}
    changes = []
    for row in report["skills"]:
        item = by_name[row["name"]]
        source = PurePosixPath(item["source_path"]).parent
        upstream = provider_root / source
        new_version = _skill_version(upstream / "SKILL.md")
        old_version = item["version"]
        target = row["target"]
        if target["removed"]:
            raise ImportError(f"upstream removed Skill support files: {row['name']}")
        if target["changed"] and new_version == old_version:
            raise ImportError(f"changed Skill did not advance its version: {row['name']}")
        upstream_tree = _candidate(provider_root, item["source_path"], provider)
        for relative, binding in item.get("distribution_metadata", {}).items():
            declared = binding["source"]
            if declared != upstream_tree.get(relative):
                raise ImportError(f"distribution metadata needs review: {row['name']}/{relative}")
        new_rel = "vendor/skills/{}/{}".format(row["name"], new_version)
        new_dir = root / "src/codex-home" / new_rel
        if new_version != old_version and new_dir.exists():
            raise ImportError(f"new Skill version directory already exists: {new_rel}")
        changes.append({
            "name": row["name"], "old_version": old_version, "new_version": new_version,
            "source": source.as_posix(), "old_rel": item["vendor_rel"],
            "new_rel": new_rel, "tree": target["tree_sha256"],
            "blob": target["entrypoint_blob"],
            "changed": target["changed"], "added": target["added"],
        })
    agents = _json(root / "manifests/agents.json")
    agent_names = [item["name"] for item in agents["agents"]
                   if item.get("source_kind") == "vendor" and item.get("source_repo") == REPOSITORY]
    for item in agents["agents"]:
        if item["name"] not in agent_names:
            continue
        source = item["source_path"]
        tracked = provider["tracked"].get(source, {})
        if tracked.get("kind") != "blob" or tracked.get("blob") != _blob((provider_root / source).read_bytes()):
            raise ImportError(f"Agent source is not exact: {source}")
        old = root / "src/codex-home" / item["vendor_rel"]
        if old.is_symlink() or old.read_bytes() != (provider_root / source).read_bytes():
            raise ImportError(f"Agent source needs review: {source}")
        destination = root / "src/codex-home/vendor/agents/agent-dev-kit" / provider["version"] / item["name"] / "AGENTS.md"
        if destination.exists() or destination.is_symlink():
            raise ImportError(f"new Agent version already exists: {item['name']}")
    return {
        "schema": "codex-adk-source-import/v1", "status": "planned",
        "provider_commit": commit, "provider_tree": _git(provider_root, "rev-parse", "HEAD^{tree}"),
        "manifest_blob": provider["tracked"]["manifest.json"]["blob"],
        "version": provider["version"], "artifact_sha256": artifact_sha256,
        "trusted_root_sha256": TRUSTED_ROOT_SHA256,
        "skill_count": len(changes), "changed_skills": [x["name"] for x in changes if x["changed"] or x["added"]],
        "agent_count": len(agent_names), "skills": changes,
    }


def apply(root: Path, provider_root: Path, result: dict[str, Any]) -> None:
    root = root.resolve()
    provider_root = provider_root.resolve()
    version = result["version"]
    commit = result["provider_commit"]
    imported_at = date.today().isoformat()
    skills_path = root / "manifests/skills.json"
    skills = _json(skills_path)
    by_name = {item["name"]: item for item in skills["skills"]}
    for change in result["skills"]:
        item = by_name[change["name"]]
        old_dir = root / "src/codex-home" / change["old_rel"]
        new_dir = root / "src/codex-home" / change["new_rel"]
        if new_dir != old_dir:
            shutil.copytree(old_dir, new_dir, symlinks=False)
        source_dir = provider_root / change["source"]
        upstream = _candidate(provider_root, item["source_path"], _provider(provider_root, commit))
        metadata = item.get("distribution_metadata", {})
        for relative, identity in upstream.items():
            if relative in metadata:
                declared = metadata[relative]["source"]
                if declared != identity:
                    raise ImportError("distribution source metadata changed: {}".format(change["name"]))
                continue
            destination = new_dir / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_dir / relative, destination)
        installed = _tree(new_dir)
        projected = _source_tree(item, installed)
        if projected != upstream:
            raise ImportError("imported Skill differs from exact upstream: {}".format(change["name"]))
        item["version"] = change["new_version"]
        item["vendor_rel"] = change["new_rel"]
        item["source_ref"] = commit
        item["source_release"] = "v" + version
        item["source_blob"] = change["blob"]
        item["source_tree_sha256"] = _digest(upstream)
        if "local_tree_sha256" in item:
            item["local_tree_sha256"] = _digest(installed)
        item["imported_at"] = imported_at
    _write_json(skills_path, skills)

    registry_path = root / "src/codex-home/skills/registry.csv"
    with registry_path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames
        rows = list(reader)
    if fields != ["name", "version", "status", "owner"]:
        raise ImportError("Skill registry columns changed")
    version_by_name = {item["name"]: item["version"] for item in skills["skills"]}
    for row in rows:
        if row["name"] in version_by_name and row["owner"] == "agent-dev-kit":
            row["version"] = version_by_name[row["name"]]
    with registry_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    agents_path = root / "manifests/agents.json"
    agents = _json(agents_path)
    for item in agents["agents"]:
        if item.get("source_kind") != "vendor" or item.get("source_repo") != REPOSITORY:
            continue
        source = item["source_path"]
        old = root / "src/codex-home" / item["vendor_rel"]
        destination_rel = "vendor/agents/agent-dev-kit/{}/{}/AGENTS.md".format(version, item["name"])
        destination = root / "src/codex-home" / destination_rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        if old.read_bytes() != (provider_root / source).read_bytes():
            raise ImportError("Agent source changed and requires separate review: {}".format(item["name"]))
        shutil.copy2(provider_root / source, destination)
        item["version"] = version
        item["vendor_rel"] = destination_rel
        item["source_ref"] = commit
        item["source_blob"] = _blob(destination.read_bytes())
        item["imported_at"] = imported_at
    _write_json(agents_path, agents)

    source_blobs = {}
    for filename in POLICY_FILES:
        source = provider_root / "src/agent_dev_kit/execution_policy" / filename
        destination = root / "tools/codex_assets/execution_policy" / filename
        shutil.copy2(source, destination)
        source_blobs[filename] = _blob(destination.read_bytes())
    policy_path = root / "manifests/execution_policy.json"
    policy = _json(policy_path)
    baseline = policy["engine"]["behavior_baseline"]
    baseline["version"] = version
    baseline["commit"] = commit
    baseline["source_blobs"] = source_blobs
    _write_json(policy_path, policy)

    lock_path = root / "manifests/provider-locks/agent-dev-kit.json"
    lock = _json(lock_path)
    lock["version"] = version
    lock["release_tag"] = "v" + version
    lock["provider_commit"] = commit
    lock["provider_tree"] = result["provider_tree"]
    lock["manifest_blob"] = result["manifest_blob"]
    lock["release_artifact"] = {
        "name": f"agent-dev-kit-{version}.tar.gz",
        "sha256": result["artifact_sha256"],
    }
    _write_json(lock_path, lock)
    refresh_local_readmes(root, provider_root, commit)


def refresh_local_readmes(root: Path, provider_root: Path, commit: str) -> int:
    """Refresh consumer-only provenance text while preserving upstream files."""
    root = root.resolve()
    provider_root = provider_root.resolve()
    provider = _provider(provider_root, commit)
    historical = _json(root / "tests/fixtures/adk-skill-sources-7.0.31.json")
    old_commit = historical["provider_commit"]
    manifest_path = root / "manifests/skills.json"
    manifest = _json(manifest_path)
    changed = 0
    for item in manifest["skills"]:
        if item.get("enabled") is not True or item.get("owner") != "agent-dev-kit":
            continue
        binding = item.get("distribution_metadata", {}).get("README.md")
        if not isinstance(binding, dict) or binding.get("source", "upstream") is not None:
            continue
        directory = root / "src/codex-home" / item["vendor_rel"]
        readme = directory / "README.md"
        text = readme.read_text(encoding="utf-8")
        old_version = historical["skills"][item["name"]]["version"]
        old_version_line = f"- Skill version: `{old_version}`"
        old_commit_line = f"- Source commit: `{old_commit}`"
        if text.count(old_version_line) != 1 or text.count(old_commit_line) != 1:
            raise ImportError(f"local README provenance needs manual review: {item['name']}")
        updated = text.replace(old_version_line, f"- Skill version: `{item['version']}`")
        updated = updated.replace(old_commit_line, f"- Source commit: `{commit}`")
        readme.write_text(updated, encoding="utf-8")
        installed = _tree(directory)
        binding["installed"] = installed["README.md"]
        if "local_tree_sha256" in item:
            item["local_tree_sha256"] = _digest(installed)
        upstream = _candidate(provider_root, item["source_path"], provider)
        if _source_tree(item, installed) != upstream:
            raise ImportError(f"README refresh changed upstream projection: {item['name']}")
        changed += 1
    _write_json(manifest_path, manifest)
    return changed


def write_source_fixture(root: Path, provider_root: Path, commit: str) -> Path:
    """Freeze independently read upstream Git trees for consumer regressions."""
    root = root.resolve()
    provider_root = provider_root.resolve()
    provider = _provider(provider_root, commit)
    old_path = root / "tests/fixtures/adk-skill-sources-7.0.31.json"
    old = _json(old_path)
    current = _json(root / "manifests/skills.json")
    selected = {item["name"]: item for item in current["skills"]
                if item.get("enabled") is True and item.get("name", "").startswith("adk-")}
    if set(selected) != set(old["skills"]):
        raise ImportError("Skill population differs from reviewed packaging fixture")
    fixture = {
        "license_blob": old["license_blob"],
        "provider_commit": commit,
        "provider_repository": REPOSITORY,
        "release": "v" + provider["version"],
        "skills": {},
    }
    for name, item in sorted(selected.items()):
        old_item = old["skills"][name]
        upstream = _candidate(provider_root, item["source_path"], provider)
        if item["source_path"] != old_item["source_path"] or item["profiles"] != old_item["profiles"]:
            raise ImportError(f"Skill mapping needs review: {name}")
        vendor = root / "src/codex-home" / item["vendor_rel"]
        installed = _tree(vendor)
        fixture["skills"][name] = {
            "installed_license_blob": installed["LICENSE"]["blob"],
            "openai_source": old_item["openai_source"],
            "profiles": old_item["profiles"],
            "source_path": item["source_path"],
            "target_rel": old_item["target_rel"],
            "tree": upstream,
            "version": _skill_version(provider_root / PurePosixPath(item["source_path"]).parent / "SKILL.md"),
        }
    destination = root / "tests/fixtures" / f"adk-skill-sources-{provider['version']}.json"
    if destination.exists():
        raise ImportError("reviewed fixture destination already exists")
    _write_json(destination, fixture)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--provider-root", type=Path, required=True)
    parser.add_argument("--expected-provider-commit", required=True)
    parser.add_argument("--promotion-evidence", type=Path, required=True)
    parser.add_argument("--promotion-attestation", type=Path, required=True)
    parser.add_argument("--trusted-root", type=Path, required=True)
    parser.add_argument("--release-artifact-sha256", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--write-source-fixture", action="store_true")
    parser.add_argument("--refresh-distribution-metadata", action="store_true")
    parser.add_argument("--summary-json", action="store_true")
    args = parser.parse_args()
    try:
        if args.refresh_distribution_metadata:
            if args.apply or args.write_source_fixture:
                raise ImportError("README refresh must be a separate operation")
            changed = refresh_local_readmes(args.root, args.provider_root, args.expected_provider_commit)
            print(json.dumps({"status": "refreshed", "local_readmes": changed}))
            return 0
        if args.write_source_fixture:
            if args.apply:
                raise ImportError("fixture generation and source import must be separate operations")
            destination = write_source_fixture(args.root, args.provider_root, args.expected_provider_commit)
            print(json.dumps({"status": "fixture-written", "path": str(destination)}))
            return 0
        result = plan(args.root, args.provider_root, args.expected_provider_commit,
                      args.promotion_evidence, args.promotion_attestation, args.trusted_root,
                      args.release_artifact_sha256)
        if args.apply:
            apply(args.root, args.provider_root, result)
            result["status"] = "applied-not-verified"
    except (ImportError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "fail", "error": str(exc)}, ensure_ascii=False))
        return 1
    if args.summary_json:
        result = {key: value for key, value in result.items() if key != "skills"}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":") if args.summary_json else None,
                     indent=None if args.summary_json else 2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
