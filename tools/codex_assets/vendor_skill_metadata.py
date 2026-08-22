from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .core import CodexAssetError, parse_frontmatter


LICENSE = """MIT License

Copyright (c) 2026 aiot03

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the \"Software\"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""


def _display_name(name: str) -> str:
    return " ".join(part.upper() if part == "adk" else part.replace("-", " ").title() for part in name.split("-"))


def _content(item: dict[str, Any], metadata: dict[str, Any]) -> dict[str, str]:
    name = str(metadata["name"])
    description = str(metadata["description"]).strip()
    version = str(item["version"])
    source = "{}/{}".format(item["source_repo"], item["source_ref"])
    return {
        "README.md": "# {}\n\nImported ADK skill metadata wrapper.\n\n- Version: `{}`\n- Source: `{}`\n- Source path: `{}`\n- Description: {}\n".format(name, version, source, item["source_path"], description),
        "LICENSE": LICENSE,
        "agents/openai.yaml": 'interface:\n  display_name: "{}"\n  short_description: "{}"\n  default_prompt: "Use ${} for its documented workflow."\n'.format(_display_name(name), description.replace('"', "'"), name),
    }


def run(root: str | Path, *, dry_run: bool = False) -> int:
    root_path = Path(root).expanduser().resolve()
    manifest_path = root_path / "manifests/skills.json"
    try:
        items = json.loads(manifest_path.read_text(encoding="utf-8")).get("skills", [])
    except (OSError, ValueError) as exc:
        raise CodexAssetError(f"无法读取 skills manifest: {exc}") from exc
    created = 0
    skipped = 0
    for item in items:
        if item.get("source_kind") != "vendor" or item.get("owner") != "agent-dev-kit":
            continue
        skill_dir = root_path / "src/codex-home" / str(item["vendor_rel"])
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            raise CodexAssetError(f"vendor skill 缺少 SKILL.md: {skill_dir}")
        metadata = parse_frontmatter(skill_md)
        missing = [path for path in ("README.md", "LICENSE", "agents/openai.yaml") if not (skill_dir / path).exists()]
        if not missing:
            skipped += 1
            continue
        rendered = _content(item, metadata)
        for rel in missing:
            path = skill_dir / rel
            if not dry_run:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(rendered[rel], encoding="utf-8")
            print("[{}] {}".format("DRY" if dry_run else "ADD", path.relative_to(root_path)))
            created += 1
    print(f"[INFO] created={created} complete_skills={skipped} dry_run={int(dry_run)}")
    return 0


def configure_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--dry-run", action="store_true")

