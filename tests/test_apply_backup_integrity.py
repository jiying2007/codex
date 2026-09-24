"""A directory prune must retain its complete pre-apply backup."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.codex_assets import core
from tests.test_apply_prune import write_json


class ApplyBackupIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.build = self.root / "build"
        self.target = self.root / "live"
        self.backup = self.root / "backup"
        write_json(self.root / "manifests/policies.json", {"schema_version": 2, "protected_paths": []})
        write_json(self.build / "control/state/managed-files.json", {"schema_version": 2, "managed": []})
        self.directory = self.target / "vendor/old/1.0.0"
        (self.directory / "references").mkdir(parents=True)
        (self.directory / "SKILL.md").write_text("old skill\n", encoding="utf-8")
        (self.directory / "references/run.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        (self.directory / "references/run.sh").chmod(0o755)
        (self.directory / "reference-link").symlink_to("references/run.sh")
        managed = []
        for path in [self.directory, *self.directory.rglob("*")]:
            kind = "symlink" if path.is_symlink() else "dir" if path.is_dir() else "file"
            managed.append({"path": path.relative_to(self.target).as_posix(), "type": kind})
        write_json(self.target / "control/state/managed-files.json", {"schema_version": 2, "managed": managed})
        self.before = core.tree_fingerprint(self.target)
        self.plan = core.plan_apply(self.root, self.build, self.target, self.backup, overwrite=False, prune_stale=True)

    def test_nested_prune_backup_and_rollback_preserve_original_tree(self) -> None:
        core.apply_plan(self.plan, dry_run=False)
        self.assertFalse(self.directory.exists())
        saved = self.backup / "vendor/old/1.0.0"
        self.assertEqual((saved / "SKILL.md").read_text(encoding="utf-8"), "old skill\n")
        self.assertTrue((saved / "references/run.sh").stat().st_mode & 0o111)
        self.assertTrue((saved / "reference-link").is_symlink())
        plan_file = self.root / "plan.json"
        plan_file.write_text(json.dumps(self.plan), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            result = core.rollback_plan(plan_file)
        self.assertEqual(result["skipped"], 0)
        self.assertEqual(core.tree_fingerprint(self.target), self.before)

    def test_snapshot_failure_happens_before_target_content_mutation(self) -> None:
        original = core.backup_existing

        def fail_parent(dest: Path, backup: Path, dry_run: bool) -> None:
            if dest == self.directory:
                raise OSError("fixture backup failure")
            original(dest, backup, dry_run)

        with patch.object(core, "backup_existing", side_effect=fail_parent):
            with self.assertRaisesRegex(OSError, "fixture backup failure"):
                core.apply_plan(self.plan, dry_run=False)
        self.assertEqual(core.tree_fingerprint(self.target), self.before)

    def test_dry_run_has_no_backup_or_target_writes(self) -> None:
        core.apply_plan(self.plan, dry_run=True)
        self.assertFalse(self.backup.exists())
        self.assertEqual(core.tree_fingerprint(self.target), self.before)


if __name__ == "__main__":
    unittest.main()
