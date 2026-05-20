from __future__ import annotations

import json
import pathlib
import shutil
import tempfile
import unittest

from tools.codex_assets.archive_governance import build_meta_v2, resolve_project, validate_archive


def write_json(path: pathlib.Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: pathlib.Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


class ArchiveGovernanceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = pathlib.Path(tempfile.mkdtemp(prefix="codex-archive-gov-test-"))
        self.addCleanup(shutil.rmtree, self.root)
        self.parent_repo = self.root / "work/parent"
        self.child_repo = self.parent_repo / "child"
        self.parent_repo.mkdir(parents=True)
        self.child_repo.mkdir(parents=True)
        reg = self.root / "docs/archive/_registry"
        write_json(
            reg / "projects.json",
            {
                "schema_version": 1,
                "projects": [
                    {
                        "project_id": "parent",
                        "repo_paths": [self.parent_repo.as_posix()],
                        "aliases": ["p"],
                        "status": "active",
                    },
                    {
                        "project_id": "child",
                        "repo_paths": [self.child_repo.as_posix()],
                        "aliases": ["c"],
                        "status": "active",
                    },
                ],
            },
        )
        write_json(reg / "topics.json", {"schema_version": 1, "topics": {}})
        write_jsonl(reg / "workstreams.jsonl", [{"workstream_id": "bringup", "project_id": "child", "status": "active"}])
        write_jsonl(
            reg / "sessions.jsonl",
            [
                {
                    "session_id": "20260519-120000-child-bringup",
                    "project_id": "child",
                    "workstream_id": "bringup",
                    "status": "closed",
                    "archive_path": "docs/archive/session-wrap/20260519-120000-child-bringup.md",
                }
            ],
        )
        (reg / "schema.md").write_text("# Schema\n", encoding="utf-8")

    def write_archive(self, *, status: str = "closed", next_action: str = "", governance_status: str = "active") -> pathlib.Path:
        source = self.child_repo / "notes/session.md"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("# Child Bring-up\n\nVerified.\n", encoding="utf-8")
        dest = self.root / "docs/archive/session-wrap/20260519-120000-child-bringup.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        meta_path = pathlib.Path(str(dest) + ".meta.json")
        meta = build_meta_v2(
            self.root,
            source,
            dest,
            meta_path,
            "session-wrap",
            explicit_project="child",
            workstream_id="bringup",
            session_id="20260519-120000-child-bringup",
            status=status,
            owner="leiwenjun",
            next_action=next_action,
        )
        meta["governance_status"] = governance_status
        write_json(meta_path, meta)
        return meta_path

    def test_project_detection_uses_nearest_nested_repo_path(self) -> None:
        match = resolve_project(
            self.root,
            source_repo=(self.child_repo / "drivers/uart").as_posix(),
            cwd=self.parent_repo.as_posix(),
        )

        self.assertIsNotNone(match)
        self.assertEqual("child", match.project_id)
        self.assertEqual(self.child_repo.as_posix(), match.matched_path)

    def test_source_repo_takes_priority_over_cwd(self) -> None:
        match = resolve_project(
            self.root,
            source_repo=self.child_repo.as_posix(),
            source_path=(self.parent_repo / "README.md").as_posix(),
            cwd=self.parent_repo.as_posix(),
        )

        self.assertIsNotNone(match)
        self.assertEqual("child", match.project_id)
        self.assertEqual("source_repo", match.source)

    def test_validate_archive_accepts_meta_v2_with_registry_reference(self) -> None:
        meta_path = self.write_archive()
        meta = json.loads(meta_path.read_text(encoding="utf-8"))

        errors, warnings = validate_archive(self.root)

        self.assertEqual("docs/archive/session-wrap/20260519-120000-child-bringup.md", meta["destination"])
        self.assertEqual("docs/archive/session-wrap/20260519-120000-child-bringup.md.meta.json", meta["metadata"])
        self.assertEqual([], errors)
        self.assertEqual([], warnings)

    def test_validate_archive_requires_next_action_for_open_entry(self) -> None:
        meta_path = self.write_archive(status="open", next_action="resume bring-up")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["next_action"] = ""
        write_json(meta_path, meta)

        errors, _ = validate_archive(self.root)

        self.assertTrue(any("open archive 必须有 owner 和 next_action" in item for item in errors))

    def test_validate_archive_requires_superseded_by(self) -> None:
        self.write_archive(governance_status="superseded")

        errors, _ = validate_archive(self.root)

        self.assertTrue(any("superseded archive 必须有 superseded_by" in item for item in errors))

    def test_validate_archive_rejects_nested_entry_and_noisy_filename(self) -> None:
        source = self.child_repo / "notes/noisy.md"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("# Noisy\n", encoding="utf-8")
        dest = self.root / "docs/archive/session-wrap/nested/20260519-120000-2026-05-19-noisy.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        meta_path = pathlib.Path(str(dest) + ".meta.json")
        meta = build_meta_v2(
            self.root,
            source,
            dest,
            meta_path,
            "session-wrap",
            explicit_project="child",
            workstream_id="bringup",
            session_id="20260519-child-bringup",
            status="closed",
            owner="leiwenjun",
        )
        write_json(meta_path, meta)

        errors, _ = validate_archive(self.root)

        self.assertTrue(any("归档条目必须位于 topic 一层目录" in item for item in errors))
        self.assertTrue(any("slug 中重复 ISO 日期" in item for item in errors))

    def test_validate_archive_rejects_date_only_filename(self) -> None:
        source = self.child_repo / "notes/date-only.md"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("# Date Only\n", encoding="utf-8")
        dest = self.root / "docs/archive/session-wrap/20260519-date-only.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        meta_path = pathlib.Path(str(dest) + ".meta.json")
        meta = build_meta_v2(
            self.root,
            source,
            dest,
            meta_path,
            "session-wrap",
            explicit_project="child",
            workstream_id="bringup",
            session_id="20260519-120000-child-bringup",
            status="closed",
            owner="leiwenjun",
        )
        write_json(meta_path, meta)

        errors, _ = validate_archive(self.root)

        self.assertTrue(any("YYYYMMDD-HHMMSS-slug.md" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
