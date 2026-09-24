"""Existing installer must not follow a member's filesystem aliases."""
from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest

from tools.codex_assets import core


class MemberInstallPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.build = self.root / "build"
        self.target = self.root / "member-home/.codex"
        self.backup = self.root / "backup"
        self.target.mkdir(parents=True)
        core.write_json(self.root / "manifests/policies.json", {"protected_paths": []})
        core.write_json(self.build / "control/state/managed-files.json", {"managed": []})
        (self.build / "AGENTS.md").write_text("new rules\n", encoding="utf-8")
        self.outside = self.root / "member-notes.txt"
        self.outside.write_text("member original\n", encoding="utf-8")

    def plan(self, overwrite: bool = True) -> dict:
        return core.plan_apply(self.root, self.build, self.target, self.backup, overwrite)

    def rollback(self, plan: dict) -> dict:
        path = self.root / "plan.json"
        core.write_json(path, plan)
        with contextlib.redirect_stdout(io.StringIO()):
            return core.rollback_plan(path)

    def test_leaf_symlink_is_replaced_not_followed_and_rollback_restores_link(self) -> None:
        dest = self.target / "AGENTS.md"
        dest.symlink_to(self.outside)
        plan = self.plan()
        self.assertEqual("applied", core.apply_plan(plan, False))
        self.assertEqual("member original\n", self.outside.read_text())
        self.assertFalse(dest.is_symlink())
        self.assertEqual("new rules\n", dest.read_text())
        self.assertTrue((self.backup / "AGENTS.md").is_symlink())
        self.assertEqual(0, self.rollback(plan)["skipped"])
        self.assertTrue(dest.is_symlink())
        self.assertEqual(str(self.outside), os.readlink(dest))

    def test_dangling_leaf_symlink_does_not_create_external_file(self) -> None:
        self.outside.unlink()
        (self.target / "AGENTS.md").symlink_to(self.outside)
        core.apply_plan(self.plan(), False)
        self.assertFalse(self.outside.exists())
        self.assertFalse((self.target / "AGENTS.md").is_symlink())

    def test_regular_file_replaces_directory_after_backup(self) -> None:
        dest = self.target / "AGENTS.md"
        dest.mkdir()
        (dest / "keep.txt").write_text("original child")
        plan = self.plan()
        core.apply_plan(plan, False)
        self.assertTrue(dest.is_file())
        self.assertEqual("original child", (self.backup / "AGENTS.md/keep.txt").read_text())
        self.rollback(plan)
        self.assertEqual("original child", (dest / "keep.txt").read_text())

    def test_leaf_hardlink_is_replaced_without_mutating_other_name(self) -> None:
        dest = self.target / "AGENTS.md"
        os.link(self.outside, dest)
        core.apply_plan(self.plan(), False)
        self.assertEqual("member original\n", self.outside.read_text())
        self.assertEqual("new rules\n", dest.read_text())

    def test_file_symlink_is_not_same_file_or_unchanged_managed_file(self) -> None:
        dest = self.target / "AGENTS.md"
        self.outside.write_text("new rules\n")
        dest.symlink_to(self.outside)
        plan = self.plan(overwrite=False)
        action = next(a for a in plan["actions"] if a["path"] == "AGENTS.md")
        self.assertEqual(("keep", "exists"), (action["action"], action["reason"]))
        self.assertFalse(core.unchanged_from_managed(dest, {"type": "file", "sha256": core.sha256(self.outside)}))
        with contextlib.redirect_stdout(io.StringIO()):
            _, different, _ = core.diff_build_live(self.build, self.target)
        self.assertEqual(1, different)

    def test_changed_managed_file_replaced_by_link_is_kept_without_overwrite(self) -> None:
        dest = self.target / "AGENTS.md"
        dest.symlink_to(self.outside)
        core.write_json(self.target / "control/state/managed-files.json", {
            "managed": [{"path": "AGENTS.md", "type": "file", "sha256": core.sha256(self.outside)}]})
        plan = self.plan(overwrite=False)
        action = next(a for a in plan["actions"] if a["path"] == "AGENTS.md")
        self.assertEqual("keep", action["action"])
        core.apply_plan(plan, False)
        self.assertTrue(dest.is_symlink())
        self.assertEqual("member original\n", self.outside.read_text())

    def directory_link(self) -> Path:
        outside = self.root / "shared-folder"
        outside.mkdir()
        (self.build / "vendor").mkdir()
        (self.build / "vendor/tool.txt").write_text("asset")
        (self.target / "vendor").symlink_to(outside, target_is_directory=True)
        return outside

    def test_plan_rejects_directory_symlink_without_creating_backups(self) -> None:
        outside = self.directory_link()
        with self.assertRaisesRegex(core.CodexAssetError, "directory symlink"):
            self.plan()
        self.assertEqual([], list(outside.iterdir()))
        self.assertFalse(self.backup.exists())

    def test_target_root_link_is_rejected_use_the_explicit_real_directory(self) -> None:
        actual = self.target.with_name("actual")
        self.target.rename(actual)
        self.target.symlink_to(actual, target_is_directory=True)
        with self.assertRaisesRegex(core.CodexAssetError, "directory symlink"):
            self.plan()
        self.assertEqual([], list(actual.iterdir()))

    def test_directory_swapped_after_plan_is_rejected_before_any_write(self) -> None:
        outside = self.directory_link()
        (self.target / "vendor").unlink()
        plan = self.plan()
        (self.target / "vendor").symlink_to(outside, target_is_directory=True)
        for dry_run in (True, False):
            with self.subTest(dry_run=dry_run), self.assertRaisesRegex(core.CodexAssetError, "directory symlink"):
                core.apply_plan(plan, dry_run)
        self.assertFalse((self.target / "AGENTS.md").exists())
        self.assertEqual([], list(outside.iterdir()))
        self.assertFalse(self.backup.exists())

    def test_backup_directory_link_is_rejected_before_target_write(self) -> None:
        (self.target / "AGENTS.md").write_text("member original\n")
        outside = self.root / "external-backup"
        outside.mkdir()
        self.backup.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(core.CodexAssetError, "directory symlink"):
            core.apply_plan(self.plan(), False)
        self.assertEqual("member original\n", (self.target / "AGENTS.md").read_text())
        self.assertEqual([], list(outside.iterdir()))

    def test_backup_leaf_link_does_not_redirect_snapshot(self) -> None:
        (self.target / "AGENTS.md").write_text("prior rules\n")
        self.backup.mkdir()
        (self.backup / "AGENTS.md").symlink_to(self.outside)
        with self.assertRaisesRegex(core.CodexAssetError, "backup.*symlink"):
            core.apply_plan(self.plan(), False)
        self.assertEqual("member original\n", self.outside.read_text())
        self.assertEqual("prior rules\n", (self.target / "AGENTS.md").read_text())

    def test_rollback_rejects_redirected_directory_before_removing_any_file(self) -> None:
        outside = self.directory_link()
        (self.target / "vendor").unlink()
        plan = self.plan()
        core.apply_plan(plan, False)
        (self.target / "vendor").rename(self.target / "saved-vendor")
        (outside / "tool.txt").write_text("member shared work")
        (self.target / "vendor").symlink_to(outside, target_is_directory=True)
        before = core.tree_fingerprint(self.target)
        with self.assertRaisesRegex(core.CodexAssetError, "directory symlink"):
            self.rollback(plan)
        self.assertEqual(before, core.tree_fingerprint(self.target))
        self.assertEqual("member shared work", (outside / "tool.txt").read_text())

    def test_traversal_in_serialized_plan_is_rejected_by_apply_and_rollback(self) -> None:
        for relative in ("../member-notes.txt", str(self.outside)):
            plan = self.plan()
            plan["actions"].append({"action": "delete", "path": relative, "backup": str(self.backup / "outside")})
            with self.subTest(relative=relative):
                with self.assertRaisesRegex(core.CodexAssetError, "relative path"):
                    core.apply_plan(plan, False)
                with self.assertRaisesRegex(core.CodexAssetError, "relative path"):
                    self.rollback(plan)
        self.assertEqual("member original\n", self.outside.read_text())

    def test_normal_skill_links_and_noop_continue_to_work(self) -> None:
        (self.build / "skill-link").symlink_to("AGENTS.md")
        plan = self.plan()
        self.assertEqual("applied", core.apply_plan(plan, False))
        self.assertTrue((self.target / "skill-link").is_symlink())
        self.assertEqual("already-applied", core.apply_plan(plan, False))
        self.assertEqual(0, self.plan()["content_changes"])

    def test_parent_replacement_cannot_redirect_later_prune(self) -> None:
        # Replacing an old real directory by a link, then pruning its old
        # children, would otherwise follow the newly installed link.
        (self.target / "old").mkdir()
        (self.target / "old/child").write_text("old content")
        outside = self.root / "shared"
        outside.mkdir()
        (outside / "child").write_text("member data")
        (self.build / "old").symlink_to(outside, target_is_directory=True)
        core.write_json(self.target / "control/state/managed-files.json", {
            "managed": [{"path": "old/child", "type": "file"}]})
        with self.assertRaisesRegex(core.CodexAssetError, "directory ancestor"):
            core.plan_apply(self.root, self.build, self.target, self.backup, True, True)
        self.assertEqual("member data", (outside / "child").read_text())
        self.assertEqual("old content", (self.target / "old/child").read_text())
        self.assertFalse(self.backup.exists())


if __name__ == "__main__":
    unittest.main()
