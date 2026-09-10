#!/usr/bin/env python3
"""Bounded, public-only knowledge-base archiver.

The tool is deliberately conservative: explicit source URLs and an allowlist are
required; it never sends credentials/cookies, respects robots.txt, stays on
allowed domains, and writes only to the requested archive directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser


USER_AGENT = "CodexPublicKnowledgeArchive/0.1 (+public-only; no-auth)"


def network_disabled() -> bool:
    return os.environ.get("CODEX_OFFLINE_HERMETIC") == "1"
MAX_PAGES_HARD_LIMIT = 100
RESERVED_OUTPUT_ROOTS = (Path("/home/leiwenjun/.codex"), Path("/home/leiwenjun/codex"))


class VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._title = False
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
        if tag == "title":
            self._title = True
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
        if tag == "title":
            self._title = False

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        clean = " ".join(data.split())
        if not clean:
            return
        self.text_parts.append(clean)
        if self._title:
            self.title_parts.append(clean)


@dataclass
class ArchiveRecord:
    canonical_url: str
    final_url: str
    title: str
    retrieved_at: str
    content_sha256: str
    text_chars: int
    category: str
    depth: int
    status: str
    local_path: str | None
    note: str | None


def canonicalize(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path or "/"
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, "", parsed.query, ""))


def host_allowed(url: str, allow_domains: Iterable[str]) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == domain or host.endswith("." + domain) for domain in allow_domains)


def safe_output_dir(value: str) -> Path:
    target = Path(value).expanduser().resolve()
    for reserved in RESERVED_OUTPUT_ROOTS:
        if target == reserved or reserved in target.parents:
            raise ValueError(f"output directory is reserved: {target}")
    return target


def request_bytes(url: str, timeout: int) -> tuple[int, str, bytes, str]:
    if network_disabled():
        raise URLError("network disabled by CODEX_OFFLINE_HERMETIC")
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
    with urlopen(request, timeout=timeout) as response:  # nosec B310: explicit public allowlist checked by caller
        return response.status, response.geturl(), response.read(), response.headers.get_content_type()


def robots_allowed(url: str, timeout: int, cache: dict[str, bool]) -> bool:
    if network_disabled():
        return False
    parsed = urlparse(url)
    key = f"{parsed.scheme}://{parsed.netloc}"
    if key in cache:
        return cache[key]
    robots_url = f"{key}/robots.txt"
    parser = RobotFileParser()
    parser.set_url(robots_url)
    try:
        request = Request(robots_url, headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=timeout) as response:  # nosec B310: same public origin as checked url
            parser.parse(response.read().decode("utf-8", errors="replace").splitlines())
    except (HTTPError, URLError, TimeoutError, OSError):
        cache[key] = False
        return False
    cache[key] = parser.can_fetch(USER_AGENT, url)
    return cache[key]


def extract_html(data: bytes) -> tuple[str, str, list[str]]:
    parser = VisibleTextParser()
    parser.feed(data.decode("utf-8", errors="replace"))
    text = "\n".join(parser.text_parts)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    title = " ".join(parser.title_parts).strip() or "Untitled public page"
    return title, text, parser.links


def is_access_gate(final_url: str, text: str) -> bool:
    lowered = (final_url + "\n" + text[:800]).lower()
    gate_markers = ("/login", "登录/注册", "请登录", "安全验证", "captcha", "验证后继续")
    return len(text) < 600 and any(marker.lower() in lowered for marker in gate_markers)


def is_dynamic_shell(text: str) -> bool:
    """Fail closed on JS-only shells instead of archiving a title as a document."""
    return len(text) < 500


def load_existing(index_path: Path) -> dict[str, str]:
    if not index_path.exists():
        return {}
    result: dict[str, str] = {}
    for line in index_path.read_text(encoding="utf-8").splitlines():
        try:
            data = json.loads(line)
            if data.get("status") in {"archived", "unchanged"}:
                result[data["canonical_url"]] = data["content_sha256"]
        except (KeyError, json.JSONDecodeError):
            continue
    return result


def filename_for(url: str) -> str:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    return f"public-{digest}.md"


def markdown_page(record: ArchiveRecord, text: str) -> str:
    return "\n".join([
        f"# {record.title}",
        "",
        f"- Source: {record.final_url}",
        f"- Canonical URL: {record.canonical_url}",
        f"- Retrieved at: {record.retrieved_at}",
        f"- Content SHA-256: {record.content_sha256}",
        f"- Public status: public-read", 
        f"- Category: {record.category}",
        "",
        "---",
        "",
        text,
        "",
    ])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Archive user-specified public knowledge pages with a bounded allowlist.")
    parser.add_argument("--source", action="append", required=True, help="Public seed URL. Repeat for multiple seeds.")
    parser.add_argument("--allow-domain", action="append", required=True, help="Allowed public domain. Repeat as needed.")
    parser.add_argument("--output-dir", required=True, help="Archive output directory; must not be a Codex source/runtime directory.")
    parser.add_argument("--category", default="public-knowledge", help="Local archive classification label.")
    parser.add_argument("--max-pages", type=int, default=20, help="Maximum pages for this run (1-100, default: 20).")
    parser.add_argument("--max-depth", type=int, default=1, help="Link depth from seed URLs (0-2, default: 1).")
    parser.add_argument("--refresh", action="store_true", help="Store a fresh archive body even if its content hash is unchanged.")
    parser.add_argument("--dry-run", action="store_true", help="Discover and validate pages without writing archive files.")
    parser.add_argument("--timeout", type=int, default=15, help="Network timeout in seconds.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 1 <= args.max_pages <= MAX_PAGES_HARD_LIMIT:
        raise SystemExit(f"--max-pages must be 1-{MAX_PAGES_HARD_LIMIT}")
    if not 0 <= args.max_depth <= 2:
        raise SystemExit("--max-depth must be 0-2")
    allow_domains = tuple(sorted({value.strip().lower() for value in args.allow_domain if value.strip()}))
    if not allow_domains:
        raise SystemExit("at least one --allow-domain is required")
    seeds = [canonicalize(url) for url in args.source]
    for seed in seeds:
        if urlparse(seed).scheme not in {"http", "https"} or not host_allowed(seed, allow_domains):
            raise SystemExit(f"source is outside the explicit public allowlist: {seed}")

    output_dir = safe_output_dir(args.output_dir)
    pages_dir = output_dir / "pages"
    index_path = output_dir / "index.jsonl"
    existing = load_existing(index_path)
    robots_cache: dict[str, bool] = {}
    queue: list[tuple[str, int]] = [(seed, 0) for seed in seeds]
    seen: set[str] = set()
    records: list[ArchiveRecord] = []

    while queue and len(records) < args.max_pages:
        requested, depth = queue.pop(0)
        canonical = canonicalize(requested)
        if canonical in seen:
            continue
        seen.add(canonical)
        now = datetime.now(timezone.utc).isoformat()
        if not host_allowed(canonical, allow_domains):
            records.append(ArchiveRecord(canonical, canonical, "", now, "", 0, args.category, depth, "blocked-domain", None, "outside allowlist"))
            continue
        if not robots_allowed(canonical, args.timeout, robots_cache):
            records.append(ArchiveRecord(canonical, canonical, "", now, "", 0, args.category, depth, "blocked-robots", None, "robots unavailable or disallowed"))
            continue
        try:
            status, final_url, body, content_type = request_bytes(canonical, args.timeout)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            records.append(ArchiveRecord(canonical, canonical, "", now, "", 0, args.category, depth, "fetch-error", None, str(exc)))
            continue
        final_url = canonicalize(final_url)
        if not host_allowed(final_url, allow_domains):
            records.append(ArchiveRecord(canonical, final_url, "", now, "", 0, args.category, depth, "blocked-redirect", None, "redirected outside allowlist"))
            continue
        if content_type not in {"text/html", "application/xhtml+xml"}:
            records.append(ArchiveRecord(canonical, final_url, "", now, "", 0, args.category, depth, "unsupported-content", None, content_type))
            continue
        title, text, links = extract_html(body)
        if is_access_gate(final_url, text):
            records.append(ArchiveRecord(canonical, final_url, title, now, "", len(text), args.category, depth, "access-gated", None, "login or verification page"))
            continue
        if is_dynamic_shell(text):
            records.append(ArchiveRecord(canonical, final_url, title, now, "", len(text), args.category, depth, "dynamic-shell", None, "insufficient visible text; requires public rendered/export source"))
            continue
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        rel_path = f"pages/{filename_for(final_url)}"
        status_name = "unchanged" if existing.get(canonical) == digest and not args.refresh else "archived"
        record = ArchiveRecord(canonical, final_url, title, now, digest, len(text), args.category, depth, status_name, rel_path, None)
        records.append(record)
        if not args.dry_run and status_name == "archived":
            pages_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / rel_path).write_text(markdown_page(record, text), encoding="utf-8")
        if depth < args.max_depth:
            for href in links:
                child = canonicalize(urljoin(final_url, href))
                if urlparse(child).scheme in {"http", "https"} and host_allowed(child, allow_domains):
                    queue.append((child, depth + 1))

    if not args.dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
        with index_path.open("a", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(asdict(record), ensure_ascii=False, sort_keys=True) + "\n")
        run = {
            "kind": "public-knowledge-archive-run",
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "allow_domains": allow_domains,
            "sources": seeds,
            "max_pages": args.max_pages,
            "max_depth": args.max_depth,
            "records": [asdict(record) for record in records],
            "raw_content_stored": False,
        }
        (output_dir / "latest-run.json").write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "dry-run" if args.dry_run else "ok", "records": [asdict(record) for record in records]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
