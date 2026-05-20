from __future__ import annotations

import argparse
import json
import pathlib
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Sequence


TEXT_SUFFIXES = {".md", ".txt", ".json", ".jsonl", ".yaml", ".yml", ".toml", ".csv"}
SKIP_PARTS = {".git", "build", ".backups", "tmp", ".tmp", "cache", "sessions", "log", "logs", ".cache"}
HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.*)$")
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)


@dataclass
class Hit:
    path: str
    line: int
    heading: str
    text: str
    score: float
    topic: str
    kind: str
    title: str
    archived_at: str
    tags: list[str]
    project_id: str
    workstream_id: str
    session_id: str
    scope: str
    status: str
    governance_status: str
    memory_action: str
    owner: str
    summary: str


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Search archived Codex knowledge and repository rules.")
    p.add_argument("--repo", required=True)
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
    return p


def readable(path: pathlib.Path) -> bool:
    return path.is_file() and path.suffix.lower() in TEXT_SUFFIXES and not path.name.endswith(".meta.json")


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


def safe_read(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def parse_frontmatter(text: str) -> dict[str, Any]:
    match = FRONTMATTER.match(text)
    if not match:
        return {}
    data: dict[str, Any] = {}
    for raw in match.group(1).splitlines():
        line = raw.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    tags = data.get("tags", "")
    if tags.startswith("[") and tags.endswith("]"):
        inner = tags[1:-1].strip()
        data["tags"] = [item.strip().strip('"').strip("'") for item in inner.split(",") if item.strip()]
    elif tags:
        data["tags"] = [tags]
    return data


def parse_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def detect_kind(path_rel: str, topic: str) -> str:
    if path_rel == "AGENTS.md" or path_rel.endswith("/AGENTS.md"):
        return "rule"
    if "/session-wrap/" in f"/{path_rel}/" or topic == "session-wrap":
        return "session-wrap"
    if "/memory-curation/" in f"/{path_rel}/" or topic == "memory-curation":
        return "memory-curation"
    if "/daily-summary/" in f"/{path_rel}/" or topic == "daily-summary":
        return "daily-summary"
    if "/diag-architecture/" in f"/{path_rel}/" or topic == "diag-architecture":
        return "research-note"
    if topic:
        return topic
    return "document"


def strip_frontmatter(text: str) -> str:
    match = FRONTMATTER.match(text)
    if not match:
        return text
    return text[match.end() :]


def index_path_for(repo: pathlib.Path, value: str) -> pathlib.Path:
    if value:
        return pathlib.Path(value).expanduser().resolve()
    return (repo / ".cache/archive-search.sqlite").resolve()


def connect(path: pathlib.Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("pragma journal_mode=wal")
    db.execute("pragma synchronous=normal")
    db.execute(
        """
        create table if not exists docs (
            path text primary key,
            mtime_ns integer not null,
            topic text not null,
            kind text not null,
            title text not null,
            description text not null,
            archived_at text not null,
            tags text not null,
            project_id text not null default '',
            workstream_id text not null default '',
            session_id text not null default '',
            scope text not null default '',
            status text not null default '',
            governance_status text not null default '',
            memory_action text not null default '',
            owner text not null default '',
            summary text not null default '',
            content text not null
        )
        """
    )
    db.execute(
        """
        create virtual table if not exists docs_fts using fts5(
            path unindexed,
            topic,
            kind,
            title,
            description,
            tags,
            project_id,
            workstream_id,
            session_id,
            scope,
            status,
            governance_status,
            memory_action,
            owner,
            summary,
            content,
            tokenize='unicode61'
        )
        """
    )
    ensure_archive_columns(db)
    return db


def ensure_archive_columns(db: sqlite3.Connection) -> None:
    existing = {row["name"] for row in db.execute("pragma table_info(docs)").fetchall()}
    for column in ["project_id", "workstream_id", "session_id", "scope", "status", "governance_status", "memory_action", "owner", "summary"]:
        if column not in existing:
            db.execute(f"alter table docs add column {column} text not null default ''")
    fts_cols = {row["name"] for row in db.execute("pragma table_info(docs_fts)").fetchall()}
    expected = {"project_id", "workstream_id", "session_id", "scope", "status", "governance_status", "memory_action", "owner", "summary"}
    if not expected.issubset(fts_cols):
        db.execute("drop table if exists docs_fts")
        db.execute(
            """
            create virtual table docs_fts using fts5(
                path unindexed,
                topic,
                kind,
                title,
                description,
                tags,
                project_id,
                workstream_id,
                session_id,
                scope,
                status,
                governance_status,
                memory_action,
                owner,
                summary,
                content,
                tokenize='unicode61'
            )
            """
        )
        db.execute("delete from docs")


def metadata_for(path: pathlib.Path, repo: pathlib.Path, text: str) -> dict[str, Any]:
    path_rel = rel(path, repo)
    frontmatter = parse_frontmatter(text)
    meta_path = path.with_name(path.name + ".meta.json")
    meta = parse_json(meta_path) if meta_path.is_file() else {}
    topic = str(meta.get("topic") or infer_topic(path_rel))
    title = str(meta.get("title") or frontmatter.get("title") or path.stem)
    description = str(meta.get("description") or "")
    archived_at = str(meta.get("archived_at") or "")
    tags = frontmatter.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    meta_tags = meta.get("tags") or []
    if isinstance(meta_tags, str):
        meta_tags = [meta_tags]
    tags = list(tags) + [str(item) for item in meta_tags]
    kind = detect_kind(path_rel, topic)
    return {
        "path": path_rel,
        "topic": topic,
        "kind": str(meta.get("kind") or kind),
        "title": title,
        "description": description,
        "archived_at": archived_at,
        "tags": sorted({str(item) for item in tags if str(item).strip()}),
        "project_id": str(meta.get("project_id") or meta.get("project") or ""),
        "workstream_id": str(meta.get("workstream_id") or ""),
        "session_id": str(meta.get("session_id") or ""),
        "scope": str(meta.get("scope") or ""),
        "status": str(meta.get("status") or ""),
        "governance_status": str(meta.get("governance_status") or ""),
        "memory_action": str(meta.get("memory_action") or ""),
        "owner": str(meta.get("owner") or ""),
        "summary": str(meta.get("summary") or description),
        "content": strip_frontmatter(text),
    }


def infer_topic(path_rel: str) -> str:
    parts = pathlib.PurePosixPath(path_rel).parts
    if len(parts) >= 3 and parts[0] == "docs" and parts[1] == "archive":
        return parts[2]
    return "rules" if path_rel.endswith("AGENTS.md") else "document"


def rebuild_index(db: sqlite3.Connection, repo: pathlib.Path, extra: Sequence[str]) -> tuple[int, int]:
    sources = iter_sources(repo, extra)
    live: dict[str, pathlib.Path] = {}
    updated = 0
    removed = 0
    for path in sources:
        path_rel = rel(path, repo)
        live[path_rel] = path
        stat = path.stat()
        meta_path = path.with_name(path.name + ".meta.json")
        meta_mtime_ns = meta_path.stat().st_mtime_ns if meta_path.is_file() else 0
        mtime_ns = max(stat.st_mtime_ns, meta_mtime_ns)
        row = db.execute("select mtime_ns from docs where path = ?", (path_rel,)).fetchone()
        if row and int(row["mtime_ns"]) == mtime_ns:
            continue
        text = safe_read(path)
        meta = metadata_for(path, repo, text)
        tags_json = json.dumps(meta["tags"], ensure_ascii=False)
        db.execute("delete from docs where path = ?", (path_rel,))
        db.execute("delete from docs_fts where path = ?", (path_rel,))
        db.execute(
            """
            insert into docs(
                path, mtime_ns, topic, kind, title, description, archived_at, tags,
                project_id, workstream_id, session_id, scope, status, governance_status,
                memory_action, owner, summary, content
            )
            values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                path_rel,
                mtime_ns,
                meta["topic"],
                meta["kind"],
                meta["title"],
                meta["description"],
                meta["archived_at"],
                tags_json,
                meta["project_id"],
                meta["workstream_id"],
                meta["session_id"],
                meta["scope"],
                meta["status"],
                meta["governance_status"],
                meta["memory_action"],
                meta["owner"],
                meta["summary"],
                meta["content"],
            ),
        )
        db.execute(
            """
            insert into docs_fts(
                path, topic, kind, title, description, tags, project_id, workstream_id,
                session_id, scope, status, governance_status, memory_action, owner, summary, content
            )
            values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                path_rel,
                meta["topic"],
                meta["kind"],
                meta["title"],
                meta["description"],
                " ".join(meta["tags"]),
                meta["project_id"],
                meta["workstream_id"],
                meta["session_id"],
                meta["scope"],
                meta["status"],
                meta["governance_status"],
                meta["memory_action"],
                meta["owner"],
                meta["summary"],
                meta["content"],
            ),
        )
        updated += 1
    known = {row["path"] for row in db.execute("select path from docs")}
    stale = known - set(live)
    for path_rel in stale:
        db.execute("delete from docs where path = ?", (path_rel,))
        db.execute("delete from docs_fts where path = ?", (path_rel,))
        removed += 1
    db.commit()
    return updated, removed


def normalize_terms(query: str) -> list[str]:
    return [part.lower() for part in re.split(r"\s+", query.strip()) if part.strip()]


def parse_date(value: str) -> str:
    if not value:
        return ""
    raw = value.strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return raw[:10]


def line_hits(
    path: pathlib.Path,
    path_rel: str,
    terms: Sequence[str],
    topic: str,
    kind: str,
    title: str,
    archived_at: str,
    tags: list[str],
    project_id: str = "",
    workstream_id: str = "",
    session_id: str = "",
    scope: str = "",
    status: str = "",
    governance_status: str = "",
    memory_action: str = "",
    owner: str = "",
    summary: str = "",
) -> list[Hit]:
    current_heading = ""
    hits: list[Hit] = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for idx, raw in enumerate(fh, start=1):
                line = raw.rstrip("\n")
                match = HEADING.match(line)
                if match:
                    current_heading = match.group(1).strip()
                lowered = line.lower()
                if terms and not any(term in lowered for term in terms):
                    continue
                if not line.strip():
                    continue
                base = sum(lowered.count(term) for term in terms) * 10 if terms else 1
                hits.append(
                    Hit(
                        path=path_rel,
                        line=idx,
                        heading=current_heading,
                        text=line.strip(),
                        score=float(base),
                        topic=topic,
                        kind=kind,
                        title=title,
                        archived_at=archived_at,
                        tags=tags,
                        project_id=project_id,
                        workstream_id=workstream_id,
                        session_id=session_id,
                        scope=scope,
                        status=status,
                        governance_status=governance_status,
                        memory_action=memory_action,
                        owner=owner,
                        summary=summary,
                    )
                )
    except OSError:
        return []
    return hits


def where_filters(args: argparse.Namespace) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    values: list[Any] = []
    for attr, column in [
        ("topic", "topic"),
        ("kind", "kind"),
        ("project", "project_id"),
        ("workstream", "workstream_id"),
        ("session", "session_id"),
        ("scope", "scope"),
        ("status", "status"),
        ("governance_status", "governance_status"),
        ("memory_action", "memory_action"),
        ("owner", "owner"),
    ]:
        items = [item.strip() for item in getattr(args, attr, []) if item.strip()]
        if items:
            clauses.append(f"docs.{column} in ({','.join('?' for _ in items)})")
            values.extend(items)
    tags = [item.strip() for item in args.tag if item.strip()]
    for tag in tags:
        clauses.append("docs.tags like ?")
        values.append(f'%"{tag}"%')
    if getattr(args, "open_only", False):
        clauses.append("docs.status = ?")
        values.append("open")
    since = parse_date(args.since)
    until = parse_date(args.until)
    if since:
        clauses.append("substr(docs.archived_at, 1, 10) >= ?")
        values.append(since)
    if until:
        clauses.append("substr(docs.archived_at, 1, 10) <= ?")
        values.append(until)
    if clauses:
        return " where " + " and ".join(clauses), values
    return "", values


def query_candidates(db: sqlite3.Connection, args: argparse.Namespace) -> list[sqlite3.Row]:
    where_sql, values = where_filters(args)
    terms = normalize_terms(args.query)
    if args.query.strip():
        sql = (
            "select docs.path, docs.topic, docs.kind, docs.title, docs.archived_at, docs.tags, "
            "docs.project_id, docs.workstream_id, docs.session_id, docs.scope, docs.status, "
            "docs.governance_status, docs.memory_action, docs.owner, docs.summary, "
            "bm25(docs_fts) as rank "
            "from docs_fts join docs on docs.path = docs_fts.path "
            f"{where_sql} "
            "and docs_fts match ? "
            "order by rank limit ?"
        ) if where_sql else (
            "select docs.path, docs.topic, docs.kind, docs.title, docs.archived_at, docs.tags, "
            "docs.project_id, docs.workstream_id, docs.session_id, docs.scope, docs.status, "
            "docs.governance_status, docs.memory_action, docs.owner, docs.summary, "
            "bm25(docs_fts) as rank "
            "from docs_fts join docs on docs.path = docs_fts.path "
            "where docs_fts match ? order by rank limit ?"
        )
        match = " AND ".join(f'"{term}"' for term in terms) if terms else args.query.strip()
        rows = db.execute(sql, [*values, match, max(args.limit * 4, 40)] if where_sql else [match, max(args.limit * 4, 40)]).fetchall()
        return rows
    sql = (
        "select path, topic, kind, title, archived_at, tags, project_id, workstream_id, "
        "session_id, scope, status, governance_status, memory_action, owner, summary, 0.0 as rank from docs"
        f"{where_sql} order by archived_at desc, path limit ?"
    )
    return db.execute(sql, [*values, max(args.limit * 4, 40)]).fetchall()


def row_matches_filters(row: sqlite3.Row, args: argparse.Namespace) -> bool:
    topics = {item.strip() for item in args.topic if item.strip()}
    kinds = {item.strip() for item in args.kind if item.strip()}
    tags = {item.strip() for item in args.tag if item.strip()}
    if topics and str(row["topic"]) not in topics:
        return False
    if kinds and str(row["kind"]) not in kinds:
        return False
    for attr, column in [
        ("project", "project_id"),
        ("workstream", "workstream_id"),
        ("session", "session_id"),
        ("scope", "scope"),
        ("status", "status"),
        ("governance_status", "governance_status"),
        ("memory_action", "memory_action"),
        ("owner", "owner"),
    ]:
        values = {item.strip() for item in getattr(args, attr, []) if item.strip()}
        if values and str(row[column]) not in values:
            return False
    if getattr(args, "open_only", False) and str(row["status"]) != "open":
        return False
    row_tags = set(json.loads(row["tags"] or "[]"))
    if tags and not (row_tags & tags):
        return False
    archived_date = str(row["archived_at"] or "")[:10]
    since = parse_date(args.since)
    until = parse_date(args.until)
    if since and archived_date and archived_date < since:
        return False
    if until and archived_date and archived_date > until:
        return False
    return True


def run(args: argparse.Namespace) -> int:
    repo = pathlib.Path(args.repo).expanduser().resolve()
    index_db = index_path_for(repo, args.index_db)
    db = connect(index_db)
    updated, removed = rebuild_index(db, repo, args.include)
    rows = query_candidates(db, args)
    terms = normalize_terms(args.query)
    if not rows:
        fallback = db.execute(
            "select path, topic, kind, title, archived_at, tags, project_id, workstream_id, "
            "session_id, scope, status, governance_status, memory_action, owner, summary, "
            "0.0 as rank from docs order by archived_at desc, path"
        ).fetchall()
        rows = [row for row in fallback if row_matches_filters(row, args)]
    hits: list[Hit] = []
    for row in rows:
        tags = json.loads(row["tags"] or "[]")
        if not terms:
            hits.append(
                Hit(
                    path=str(row["path"]),
                    line=0,
                    heading="",
                    text=str(row["summary"] or row["title"] or row["path"]),
                    score=1.0,
                    topic=str(row["topic"]),
                    kind=str(row["kind"]),
                    title=str(row["title"]),
                    archived_at=str(row["archived_at"]),
                    tags=tags,
                    project_id=str(row["project_id"]),
                    workstream_id=str(row["workstream_id"]),
                    session_id=str(row["session_id"]),
                    scope=str(row["scope"]),
                    status=str(row["status"]),
                    governance_status=str(row["governance_status"]),
                    memory_action=str(row["memory_action"]),
                    owner=str(row["owner"]),
                    summary=str(row["summary"]),
                )
            )
            continue
        path = repo / row["path"]
        line_matches = line_hits(
            path,
            str(row["path"]),
            terms,
            str(row["topic"]),
            str(row["kind"]),
            str(row["title"]),
            str(row["archived_at"]),
            tags,
            project_id=str(row["project_id"]),
            workstream_id=str(row["workstream_id"]),
            session_id=str(row["session_id"]),
            scope=str(row["scope"]),
            status=str(row["status"]),
            governance_status=str(row["governance_status"]),
            memory_action=str(row["memory_action"]),
            owner=str(row["owner"]),
            summary=str(row["summary"]),
        )
        for item in line_matches:
            rank = float(row["rank"] or 0.0)
            item.score += max(0.0, 20.0 - rank)
            hits.append(item)
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
                "topic": item.topic,
                "type": item.kind,
                "title": item.title,
                "archived_at": item.archived_at,
                "tags": item.tags,
                "project_id": item.project_id,
                "workstream_id": item.workstream_id,
                "session_id": item.session_id,
                "scope": item.scope,
                "status": item.status,
                "governance_status": item.governance_status,
                "memory_action": item.memory_action,
                "owner": item.owner,
                "summary": item.summary,
            }
            for item in trimmed
        ]
        print(json.dumps({"hits": payload, "index_db": index_db.as_posix(), "reindexed": {"updated": updated, "removed": removed}}, ensure_ascii=False, indent=2))
        return 0
    for item in trimmed:
        heading = f" [{item.heading}]" if item.heading else ""
        meta = f" topic={item.topic} type={item.kind}"
        if item.project_id:
            meta += f" project={item.project_id}"
        if item.status:
            meta += f" status={item.status}"
        if item.archived_at:
            meta += f" archived_at={item.archived_at[:10]}"
        print(f"{item.path}:{item.line}{heading}{meta}")
        print(f"  {item.text}")
    print(f"[INFO] hits={len(hits)} shown={len(trimmed)} index_db={index_db} reindexed_updated={updated} reindexed_removed={removed}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(list(argv) if argv is not None else None)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
