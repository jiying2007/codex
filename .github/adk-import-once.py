"""One-shot exact import; execution only in an isolated source checkout."""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import yaml

ROOT = Path(sys.argv[1]).resolve()
UPSTREAM = Path(sys.argv[2]).resolve()
COMMIT = "7367ef84787de75bb751940b32c9e80009660e47"
sys.path.insert(0, str(ROOT))
from tools.codex_assets.adk_skill_audit import _tree, _digest, _source_tree

def blob(data):
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()

if len(sys.argv) > 3:
    tracked = json.loads(Path(sys.argv[3]).read_text())
else:
    assert subprocess.check_output(["git", "-C", str(UPSTREAM), "rev-parse", "HEAD"], text=True).strip() == COMMIT
    assert not subprocess.check_output(["git", "-C", str(UPSTREAM), "status", "--porcelain"], text=True).strip()
    tracked = {}
    for line in subprocess.check_output(["git", "-C", str(UPSTREAM), "ls-tree", "-r", "--full-tree", "HEAD"], text=True).splitlines():
        meta, path = line.split("\t")
        mode, kind, sha = meta.split()
        tracked[path] = {"blob": sha, "mode": mode, "kind": kind}

assert json.loads((UPSTREAM / "manifest.json").read_text())["version"] == "7.0.31"
license_bytes = (UPSTREAM / "LICENSE").read_bytes()
assert blob(license_bytes) == tracked["LICENSE"]["blob"]
manifest_path = ROOT / "manifests/skills.json"
manifest = json.loads(manifest_path.read_text())
golden = {"provider_repository": "jiying2007/agent-dev-kit", "provider_commit": COMMIT,
          "release": "v7.0.31", "license_blob": blob(license_bytes), "skills": {}}
summary = []
pending = []
for item in manifest["skills"]:
    name = item["name"]
    if not item["enabled"] or not name.startswith("adk-"):
        continue
    source_path = "skills/adk-cross-team-handoff/SKILL.md" if name == "adk-cross-team-handoff" else item["source_path"]
    provider_dir = (UPSTREAM / source_path).parent
    source_tree = _tree(provider_dir)
    prefix = f"{Path(source_path).parent.as_posix()}/"
    expected = {p[len(prefix):]: {k: v[k] for k in ("blob", "mode")}
                for p, v in tracked.items() if p.startswith(prefix) and v["kind"] == "blob"}
    assert source_tree == expected, name
    text = (provider_dir / "SKILL.md").read_text()
    meta = yaml.safe_load(text.split("---", 2)[1])
    assert meta["name"] == name and re.fullmatch(r"\d+\.\d+\.\d+", meta["version"])
    old = ROOT / "src/codex-home" / item["vendor_rel"]
    prior = _tree(old)
    extra = set(prior) - set(source_tree)
    assert not extra - {"LICENSE", "README.md", "agents/openai.yaml"}, (name, extra)
    files = {p: ((provider_dir / p).read_bytes(), v["mode"]) for p, v in source_tree.items()}
    changes = {}
    if "README.md" not in files:
        readme = (f"# {name}\n\nCodex distribution metadata; Skill content and support files remain upstream-owned.\n\n"
                  f"- Skill version: `{meta['version']}`\n- Provider: `jiying2007/agent-dev-kit`\n"
                  f"- Source commit: `{COMMIT}`\n- Source path: `{source_path}`\n"
                  "\nRepository-specific commands in the Skill apply only where those verified entrypoints exist. "
                  "Project acceptance and release rules remain project-owned; Knowledge Hub access uses the Provider Adapter.\n")
        files["README.md"] = (readme.encode(), "100644")
        changes["README.md"] = {"source": None}
    if "LICENSE" not in files:
        installed_license = license_bytes
        if "LICENSE" in prior:
            previous_notice = (old / "LICENSE").read_bytes()
            if previous_notice != license_bytes:
                installed_license += b"\n---\nPrevious distribution notice (retained):\n" + previous_notice
        files["LICENSE"] = (installed_license, "100644")
        changes["LICENSE"] = {"source": None}
    original_openai = None
    if "agents/openai.yaml" not in files:
        if "agents/openai.yaml" in prior:
            data = (old / "agents/openai.yaml").read_bytes()
            assert isinstance(yaml.safe_load(data).get("interface"), dict)
        else:
            data = yaml.safe_dump({"interface": {"display_name": name,
                    "short_description": meta["description"],
                    "default_prompt": f"Use ${name} for its documented workflow."}}, sort_keys=False, allow_unicode=True).encode()
        files["agents/openai.yaml"] = (data, "100644")
        changes["agents/openai.yaml"] = {"source": None}
    else:
        original_openai = yaml.safe_load(files["agents/openai.yaml"][0])
        if "interface" not in original_openai:
            assert set(original_openai) == {"display_name", "short_description"}, name
            assert all(isinstance(v, str) and v for v in original_openai.values()), name
            files["agents/openai.yaml"] = (yaml.safe_dump({"interface": original_openai}, sort_keys=False, allow_unicode=True).encode(), "100644")
            changes["agents/openai.yaml"] = {"source": source_tree["agents/openai.yaml"]}
    new_rel = f"vendor/skills/{name}/{meta['version']}"
    new = ROOT / "src/codex-home" / new_rel
    assert old.parent == new.parent
    if old != new:
        assert not new.exists()
    for p, entry in changes.items():
        entry["installed"] = {"blob": blob(files[p][0]), "mode": files[p][1]}
    old_version = item["version"]
    item.update(version=meta["version"], vendor_rel=new_rel, source_repo="jiying2007/agent-dev-kit",
                source_ref=COMMIT, source_path=source_path, source_blob=source_tree["SKILL.md"]["blob"],
                source_tree_sha256=_digest(source_tree), source_release="v7.0.31", imported_at="2026-09-24")
    if changes:
        item["distribution_metadata"] = changes
    else:
        item.pop("distribution_metadata", None)
    installed_tree = {p: {"blob": blob(data), "mode": mode} for p, (data, mode) in files.items()}
    assert _source_tree(item, installed_tree) == source_tree
    pending.append((old, new, files))
    golden["skills"][name] = {"version": meta["version"], "source_path": source_path,
                             "tree": source_tree, "openai_source": original_openai,
                             "profiles": item["profiles"], "target_rel": item["target_rel"],
                             "installed_license_blob": installed_tree["LICENSE"]["blob"]}
    summary.append({"skill": name, "old_version": old_version, "new_version": meta["version"],
                    "source_files": len(source_tree), "metadata_files": len(changes)})
assert len(summary) == 42
for old, new, files in pending:
    shutil.rmtree(old)
    for p, (data, mode) in files.items():
        out = new / p
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        out.chmod(0o755 if mode == "100755" else 0o644)
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
versions = {i["name"]: i["version"] for i in manifest["skills"]}
registry = ROOT / "src/codex-home/skills/registry.csv"
lines = registry.read_text().splitlines()
for idx in range(1, len(lines)):
    row = lines[idx].split(",")
    row[1] = versions[row[0]]
    lines[idx] = ",".join(row)
registry.write_text("\n".join(lines) + "\n")
fixture = ROOT / "tests/fixtures/adk-skill-sources-7.0.31.json"
fixture.write_text(json.dumps(golden, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
print(json.dumps({"skills": len(summary), "upstream_files": sum(r["source_files"] for r in summary),
                  "metadata_files": sum(r["metadata_files"] for r in summary),
                  "version_changes": sum(r["old_version"] != r["new_version"] for r in summary)}, sort_keys=True))
