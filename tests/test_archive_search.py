from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import pathlib
import shutil
import tempfile
import unittest

from tools.codex_assets.archive_governance import content_digest
from tools.codex_assets.archive_search import run as run_archive_search


def write_json(path: pathlib.Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class ArchiveSearchTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = pathlib.Path(tempfile.mkdtemp(prefix="codex-archive-search-test-"))
        self.addCleanup(shutil.rmtree, self.root)
        self.note = self.root / "docs/archive/session-wrap/20260519-120000-child-bringup.md"
        self.note.parent.mkdir(parents=True, exist_ok=True)
        self.note.write_text("# Child Bring-up\n\n构建恢复入口。\n", encoding="utf-8")
        self.meta_path = pathlib.Path(str(self.note) + ".meta.json")
        self.meta = {
            "schema_version": 2,
            "archive_id": "20260519-120000-child-bringup",
            "topic": "session-wrap",
            "kind": "session-wrap",
            "scope": "project-specific",
            "project_id": "child",
            "workstream_id": "bringup",
            "session_id": "20260519-120000-child-bringup",
            "title": "Child Bring-up",
            "summary": "构建恢复入口",
            "description": "",
            "status": "closed",
            "governance_status": "active",
            "memory_action": "archive-only",
            "owner": "leiwenjun",
            "next_action": "",
            "source_repo": "/tmp/child",
            "archived_at": "2026-05-19T10:00:00+08:00",
            "tags": ["child", "build"],
            "content_sha256": content_digest(self.note),
        }
        write_json(self.meta_path, self.meta)

    def args(self, **overrides: object) -> argparse.Namespace:
        values: dict[str, object] = {
            "repo": self.root.as_posix(),
            "query": "",
            "limit": 20,
            "json": True,
            "include": [],
            "index_db": "",
            "rebuild_index": False,
            "topic": [],
            "tag": [],
            "kind": [],
            "project": ["child"],
            "workstream": [],
            "session": [],
            "scope": [],
            "status": [],
            "governance_status": [],
            "memory_action": [],
            "owner": [],
            "open_only": False,
            "since": "",
            "until": "",
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def run_json(self, args: argparse.Namespace) -> dict:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(0, run_archive_search(args))
        return json.loads(out.getvalue())

    def test_empty_query_returns_doc_level_hit_with_meta_filters(self) -> None:
        payload = self.run_json(self.args())

        self.assertEqual(1, len(payload["hits"]))
        self.assertEqual("child", payload["hits"][0]["project_id"])
        self.assertEqual("closed", payload["hits"][0]["status"])
        self.assertEqual(0, payload["hits"][0]["line"])

    def test_meta_mtime_reindexes_status_without_touching_body(self) -> None:
        self.assertEqual([], self.run_json(self.args(open_only=True))["hits"])
        meta = dict(self.meta)
        meta["status"] = "open"
        meta["next_action"] = "resume bring-up"
        write_json(self.meta_path, meta)
        stat = self.meta_path.stat()
        os.utime(self.meta_path, ns=(stat.st_atime_ns + 1_000_000_000, stat.st_mtime_ns + 1_000_000_000))

        payload = self.run_json(self.args(open_only=True))

        self.assertEqual(1, len(payload["hits"]))
        self.assertEqual("open", payload["hits"][0]["status"])


if __name__ == "__main__":
    unittest.main()
