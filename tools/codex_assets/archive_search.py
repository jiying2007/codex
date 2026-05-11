from __future__ import annotations

import argparse
import json
import pathlib
import re
from dataclasses import dataclass
from typing import Any, Sequence


TEXT_SUFFIXES = {".md", ".txt", ".json", ".jsonl", ".yaml", ".yml", ".toml", ".csv"}
SKIP_PARTS = {".git", "build", ".backups", "tmp", ".tmp", "cache", "sessions", "log", "logs"}
HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.*)$")


@dataclass
class Hit:
    path: str
    line: int
    heading: str
    text: str
    score: int


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Search archived Codex knowledge and repository rules.")
    p.add_argument("--repo", required=True)
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--json", action="store_true")
    p.add_argument("--include", action="append", default=[])
    return p


def readable(path: pathlib.Path) -> bool:
    return path.is_file() and path.suffix.lower() in TEXT_SUFFIXES


def rel(path: pathlib.Path, root: pathlib.Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def iter_sources(repo: pathlib.Path, extra: Sequence[str]) -> list[pathlib.Path]:
    roots: list[pathlib.Path] = [
        repo / "AGENTS.md",
        repo / "src/codex-home/AGENTS.md",
        repo / "docs/archive",
    ]
    roots.extend(pathlib.Path(item).expanduser() for item in extra)
    out: list[pathlib.Path] = []
    seen: set[str] = set()
    for root in roots:
        resolved = root.expanduser().resolve()
        key = resolved.as_posix()
        if key in seen or not resolved.exists():
            continue
        seen.add(key)
        if resolved.is_file():
            if readable(resolved):
                out.append(resolved)
            continue
        for path in sorted(resolved.rglob("*")):
            if not path.is_file():
                continue
            parts = set(path.relative_to(resolved).parts)
            if parts & SKIP_PARTS:
                continue
            if readable(path):
                out.append(path)
    return out


def normalize_terms(query: str) -> list[str]:
    return [part.lower() for part in re.split(r"\s+", query.strip()) if part.strip()]


def line_score(text: str, heading: str, terms: Sequence[str]) -> int:
    hay = text.lower()
    score = sum(hay.count(term) for term in terms) * 10
    if heading:
        h = heading.lower()
        score += sum(h.count(term) for term in terms) * 5
    if text.strip().startswith("#"):
        score += 3
    return score


def search_file(path: pathlib.Path, repo: pathlib.Path, terms: Sequence[str]) -> list[Hit]:
    hits: list[Hit] = []
    current_heading = ""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for idx, raw in enumerate(fh, start=1):
                line = raw.rstrip("\n")
                match = HEADING.match(line)
                if match:
                    current_heading = match.group(1).strip()
                lowered = line.lower()
                if terms and not all(term in lowered for term in terms):
                    continue
                if not line.strip():
                    continue
                hits.append(
                    Hit(
                        path=rel(path, repo),
                        line=idx,
                        heading=current_heading,
                        text=line.strip(),
                        score=line_score(line, current_heading, terms),
                    )
                )
    except OSError:
        return []
    return hits


def run(args: argparse.Namespace) -> int:
    repo = pathlib.Path(args.repo).expanduser().resolve()
    terms = normalize_terms(args.query)
    hits: list[Hit] = []
    for path in iter_sources(repo, args.include):
        hits.extend(search_file(path, repo, terms))
    hits.sort(key=lambda item: (-item.score, item.path, item.line))
    trimmed = hits[: max(args.limit, 1)]
    if args.json:
        payload = [
            {
                "path": item.path,
                "line": item.line,
                "heading": item.heading,
                "text": item.text,
                "score": item.score,
            }
            for item in trimmed
        ]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    for item in trimmed:
        heading = f" [{item.heading}]" if item.heading else ""
        print(f"{item.path}:{item.line}{heading}")
        print(f"  {item.text}")
    print(f"[INFO] hits={len(hits)} shown={len(trimmed)}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(list(argv) if argv is not None else None)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
