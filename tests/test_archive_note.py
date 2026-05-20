from __future__ import annotations

import json
import pathlib
import shutil
import tempfile
import unittest

from tools.codex_assets.core import archive_note
from tools.codex_assets.archive_governance import ArchiveGovernanceError


def write_json(path: pathlib.Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


class ArchiveNoteTest(unittest.TestCase):
    def test_archive_index_keeps_topic_title_across_item_titles(self) -> None:
        root = pathlib.Path(tempfile.mkdtemp(prefix="codex-archive-note-test-"))
        self.addCleanup(shutil.rmtree, root)
        write_json(
            root / "manifests/policies.json",
            {"schema_version": 2, "protected_paths": [], "skip_source_paths": []},
        )
        source_dir = root / "notes"
        source_dir.mkdir(parents=True)
        first = source_dir / "first.md"
        second = source_dir / "second.md"
        first.write_text("# First\n")
        second.write_text("# Second\n")

        archive_note(root, first, topic_arg="session-wrap", title_arg="Project A Session")
        archive_note(root, second, topic_arg="session-wrap", title_arg="Project B Session")

        index = root / "docs/archive/session-wrap/index.md"
        text = index.read_text()
        self.assertIn("# Session Wrap Archive", text)
        self.assertNotIn("# Project A Session", text)
        self.assertNotIn("# Project B Session", text)
        self.assertIn("- Index title is topic-level", text)
        self.assertIn("first.md", text)
        self.assertIn("second.md", text)

    def test_archive_note_preflights_governance_before_writing(self) -> None:
        root = pathlib.Path(tempfile.mkdtemp(prefix="codex-archive-note-test-"))
        self.addCleanup(shutil.rmtree, root)
        write_json(
            root / "manifests/policies.json",
            {"schema_version": 2, "protected_paths": [], "skip_source_paths": []},
        )
        source = root / "notes/open.md"
        source.parent.mkdir(parents=True)
        source.write_text("# Open\n", encoding="utf-8")

        with self.assertRaises(ArchiveGovernanceError):
            archive_note(root, source, topic_arg="session-wrap", status_arg="open")

        self.assertFalse((root / "docs/archive/session-wrap").exists())


if __name__ == "__main__":
    unittest.main()
