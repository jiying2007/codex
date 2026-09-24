"""Incomplete historical managed state must fail before writes, not afterward."""
from __future__ import annotations
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from tools.codex_assets import core


class UnplannedLiveAssetTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.build, self.target, self.backup = [self.root / p for p in ("build", "live", "backup")]
        core.write_json(self.root / "manifests/policies.json", {"protected_paths": ["skills/.system/**"]})
        core.write_json(self.build / "control/state/managed-files.json", {"managed": []})
        core.write_json(self.target / "control/state/managed-files.json", {"managed": []})
        (self.build / "AGENTS.md").write_text("new rules")
        (self.target / "AGENTS.md").write_text("old rules")

    def orphan(self, rel: str) -> Path:
        p = self.target / rel
        p.mkdir(parents=True)
        (p / "SKILL.md").write_text("user-preserved content")
        return p

    def plan(self, prune: bool = True) -> dict:
        return core.plan_apply(self.root, self.build, self.target, self.backup, True, prune)

    def assert_unchanged(self, before: str) -> None:
        self.assertEqual(before, core.tree_fingerprint(self.target))
        self.assertFalse(self.backup.exists())

    def test_missing_ledger_cannot_hide_legacy_entrypoint_or_version(self) -> None:
        for rel in ("skills/user-skill", "vendor/skills/adk-router/0.1.0"):
            self.orphan(rel)
        before = core.tree_fingerprint(self.target)
        for prune in (True, False):
            with self.subTest(prune=prune), self.assertRaisesRegex(core.CodexAssetError, "unplanned live assets=2"):
                self.plan(prune)
        self.assert_unchanged(before)

    def test_no_prior_state_still_checks_physical_inventory(self) -> None:
        (self.target / "control/state/managed-files.json").unlink()
        self.orphan("skills/manual")
        before = core.tree_fingerprint(self.target)
        with self.assertRaisesRegex(core.CodexAssetError, "unplanned live assets=1"):
            self.plan()
        self.assert_unchanged(before)

    def test_orphan_created_after_plan_blocks_dry_run_and_apply(self) -> None:
        plan = self.plan()
        self.orphan("skills/late-arrival")
        before = core.tree_fingerprint(self.target)
        for dry_run in (True, False):
            with self.subTest(dry_run=dry_run), self.assertRaisesRegex(core.CodexAssetError, "unplanned live assets=1"):
                core.apply_plan(plan, dry_run)
        self.assert_unchanged(before)

    def test_dangling_and_external_links_are_not_followed_or_deleted(self) -> None:
        (self.target / "skills").mkdir()
        external = self.root / "external"
        external.mkdir()
        (external / "private.txt").write_text("preserve")
        (self.target / "skills/external").symlink_to(external, target_is_directory=True)
        (self.target / "skills/missing").symlink_to("../missing")
        before = core.tree_fingerprint(self.target)
        with self.assertRaisesRegex(core.CodexAssetError, "unplanned live assets=2"):
            self.plan()
        self.assert_unchanged(before)
        self.assertEqual("preserve", (external / "private.txt").read_text())

    def test_previous_managed_asset_with_reviewed_prune_still_works(self) -> None:
        self.orphan("skills/previous")
        core.write_json(self.target / "control/state/managed-files.json", {
            "managed": [{"path": "skills/previous", "type": "dir"}]})
        plan = self.plan()
        core.apply_plan(plan, False)
        self.assertFalse((self.target / "skills/previous").exists())
        self.assertEqual("user-preserved content", (self.backup / "skills/previous/SKILL.md").read_text())

    def test_explicit_retired_parent_covers_nested_skill_but_not_sibling(self) -> None:
        core.write_json(self.root / "manifests/policies.json", {
            "protected_paths": [], "retired_live_paths": ["vendor/plugins/retired"]})
        self.orphan("vendor/plugins/retired/1/skills/a")
        self.plan()
        self.orphan("vendor/plugins/retired-other/1/skills/b")
        with self.assertRaisesRegex(core.CodexAssetError, "unplanned live assets=1"):
            self.plan()

    def test_system_and_current_build_assets_are_not_orphans(self) -> None:
        self.orphan("skills/.system")
        self.orphan("skills/current")
        (self.build / "skills/current").mkdir(parents=True)
        (self.build / "skills/current/SKILL.md").write_text("new managed text")
        core.apply_plan(self.plan(), False)
        self.assertEqual("user-preserved content", (self.target / "skills/.system/SKILL.md").read_text())

    def test_already_applied_is_not_clean_with_new_orphan(self) -> None:
        plan = self.plan()
        core.apply_plan(plan, False)
        self.orphan("skills/new-manual")
        before = core.tree_fingerprint(self.target)
        with self.assertRaisesRegex(core.CodexAssetError, "unplanned live assets=1"):
            core.apply_plan(plan, False)
        self.assertEqual(before, core.tree_fingerprint(self.target))

    def test_original_rollback_does_not_touch_unrelated_orphan(self) -> None:
        plan = self.plan()
        core.apply_plan(plan, False)
        self.orphan("skills/user-added")
        path = self.root / "plan.json"
        core.write_json(path, plan)
        with contextlib.redirect_stdout(io.StringIO()):
            core.rollback_plan(path)
        self.assertEqual("old rules", (self.target / "AGENTS.md").read_text())
        self.assertEqual("user-preserved content", (self.target / "skills/user-added/SKILL.md").read_text())


if __name__ == "__main__":
    unittest.main()
