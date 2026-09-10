from __future__ import annotations

import json
import pathlib
import shutil
import tempfile
import unittest

from tools.codex_assets.core import CodexAssetError, apply_plan, plan_apply


def write_json(path: pathlib.Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


class ApplyPruneTest(unittest.TestCase):
    def test_prune_stale_deletes_previous_managed_asset_with_backup(self) -> None:
        root = pathlib.Path(tempfile.mkdtemp(prefix="codex-prune-test-"))
        self.addCleanup(shutil.rmtree, root)
        build = root / "build/codex-home"
        target = root / "live"
        backup = root / "backup"
        write_json(root / "manifests/policies.json", {"schema_version": 2, "protected_paths": []})
        current = build / "AGENTS.md"
        current.parent.mkdir(parents=True, exist_ok=True)
        current.write_text("# current\n")
        write_json(
            build / "control/state/managed-files.json",
            {"schema_version": 2, "profile": "test", "managed": [{"path": "AGENTS.md", "type": "file"}]},
        )
        stale = target / "skills/writing-plans"
        stale.parent.mkdir(parents=True, exist_ok=True)
        stale.write_text("old\n")
        write_json(
            target / "control/state/managed-files.json",
            {
                "schema_version": 2,
                "managed": [
                    {"path": "AGENTS.md", "type": "file"},
                    {"path": "skills/writing-plans", "type": "file"},
                ],
            },
        )

        plan = plan_apply(root, build, target, backup, overwrite=False, prune_stale=True)
        self.assertEqual(3, plan["schema_version"])
        self.assertGreater(plan["content_changes"], 0)
        self.assertFalse(plan["content_noop"])
        deletes = [action for action in plan["actions"] if action["action"] == "delete"]
        self.assertEqual(["skills/writing-plans"], [action["path"] for action in deletes])

        apply_plan(plan, dry_run=False)
        self.assertFalse(stale.exists())
        self.assertTrue((backup / "skills/writing-plans").is_file())

    def test_plan_rejects_changed_build_tree(self) -> None:
        root = pathlib.Path(tempfile.mkdtemp(prefix="codex-plan-receipt-test-"))
        self.addCleanup(shutil.rmtree, root)
        build = root / "build/codex-home"
        target = root / "live"
        write_json(root / "manifests/policies.json", {"schema_version": 2, "protected_paths": []})
        (build / "AGENTS.md").parent.mkdir(parents=True, exist_ok=True)
        (build / "AGENTS.md").write_text("before\n")
        state = {"schema_version": 2, "managed": []}
        write_json(build / "control/state/managed-files.json", state)
        write_json(target / "control/state/managed-files.json", state)
        plan = plan_apply(root, build, target, root / "backup", overwrite=False)

        (build / "AGENTS.md").write_text("after\n")
        with self.assertRaisesRegex(CodexAssetError, "build tree 已变化"):
            apply_plan(plan, dry_run=True)

    def test_prune_removes_explicit_retired_live_path_with_backup(self) -> None:
        root = pathlib.Path(tempfile.mkdtemp(prefix="codex-retired-live-test-"))
        self.addCleanup(shutil.rmtree, root)
        build = root / "build/codex-home"
        target = root / "live"
        backup = root / "backup"
        write_json(
            root / "manifests/policies.json",
            {"schema_version": 2, "protected_paths": [], "retired_live_paths": ["vendor/plugins/superpowers"]},
        )
        build.mkdir(parents=True)
        write_json(build / "control/state/managed-files.json", {"schema_version": 2, "managed": []})
        retired = target / "vendor/plugins/superpowers/1.0.0/README.md"
        retired.parent.mkdir(parents=True)
        retired.write_text("retired\n")
        write_json(target / "control/state/managed-files.json", {"schema_version": 2, "managed": []})

        plan = plan_apply(root, build, target, backup, overwrite=False, prune_stale=True)
        deletes = [action for action in plan["actions"] if action["action"] == "delete"]
        self.assertEqual(["vendor/plugins/superpowers"], [action["path"] for action in deletes])
        self.assertEqual("retired-live-path", deletes[0]["reason"])

        apply_plan(plan, dry_run=False)
        self.assertFalse(retired.exists())
        self.assertTrue((backup / "vendor/plugins/superpowers/1.0.0/README.md").is_file())

    def test_noop_is_explicit(self) -> None:
        root = pathlib.Path(tempfile.mkdtemp(prefix="codex-plan-noop-test-"))
        self.addCleanup(shutil.rmtree, root)
        build = root / "build/codex-home"
        target = root / "live"
        write_json(root / "manifests/policies.json", {"schema_version": 2, "protected_paths": []})
        for base in (build, target):
            (base / "AGENTS.md").parent.mkdir(parents=True, exist_ok=True)
            (base / "AGENTS.md").write_text("same\n")
        state = {"schema_version": 2, "managed": []}
        write_json(build / "control/state/managed-files.json", state)
        write_json(target / "control/state/managed-files.json", state)

        plan = plan_apply(root, build, target, root / "backup", overwrite=False)
        self.assertEqual(0, plan["content_changes"])
        self.assertTrue(plan["content_noop"])
        self.assertEqual("already-applied", apply_plan(plan, dry_run=False))

    def test_content_noop_still_creates_missing_directory(self) -> None:
        root = pathlib.Path(tempfile.mkdtemp(prefix="codex-plan-empty-dir-test-"))
        self.addCleanup(shutil.rmtree, root)
        build = root / "build/codex-home"
        target = root / "live"
        write_json(root / "manifests/policies.json", {"schema_version": 2, "protected_paths": []})
        (build / "empty").mkdir(parents=True)
        state = {"schema_version": 2, "managed": []}
        write_json(build / "control/state/managed-files.json", state)
        write_json(target / "control/state/managed-files.json", state)
        plan = plan_apply(root, build, target, root / "backup", overwrite=False)

        self.assertTrue(plan["content_noop"])
        self.assertEqual("applied", apply_plan(plan, dry_run=False))
        self.assertTrue((target / "empty").is_dir())
        self.assertEqual("already-applied", apply_plan(plan, dry_run=False))

    def test_plan_rejects_changed_target_mutation_path(self) -> None:
        root = pathlib.Path(tempfile.mkdtemp(prefix="codex-target-receipt-test-"))
        self.addCleanup(shutil.rmtree, root)
        build = root / "build/codex-home"
        target = root / "live"
        write_json(root / "manifests/policies.json", {"schema_version": 2, "protected_paths": []})
        for base, text in ((build, "new\n"), (target, "old\n")):
            (base / "AGENTS.md").parent.mkdir(parents=True, exist_ok=True)
            (base / "AGENTS.md").write_text(text)
        state = {"schema_version": 2, "managed": []}
        write_json(build / "control/state/managed-files.json", state)
        write_json(target / "control/state/managed-files.json", state)
        plan = plan_apply(root, build, target, root / "backup", overwrite=True)

        (target / "AGENTS.md").write_text("concurrent-change\n")
        with self.assertRaisesRegex(CodexAssetError, "target precondition paths 已变化"):
            apply_plan(plan, dry_run=False)

    def test_applied_plan_is_idempotent(self) -> None:
        root = pathlib.Path(tempfile.mkdtemp(prefix="codex-plan-idempotent-test-"))
        self.addCleanup(shutil.rmtree, root)
        build = root / "build/codex-home"
        target = root / "live"
        write_json(root / "manifests/policies.json", {"schema_version": 2, "protected_paths": []})
        for base, text in ((build, "new\n"), (target, "old\n")):
            (base / "AGENTS.md").parent.mkdir(parents=True, exist_ok=True)
            (base / "AGENTS.md").write_text(text)
        state = {"schema_version": 2, "managed": []}
        write_json(build / "control/state/managed-files.json", state)
        write_json(target / "control/state/managed-files.json", state)
        plan = plan_apply(root, build, target, root / "backup", overwrite=True)

        self.assertEqual("applied", apply_plan(plan, dry_run=False))
        self.assertEqual("already-applied", apply_plan(plan, dry_run=False))

    def test_plan_rejects_changed_keep_path(self) -> None:
        root = pathlib.Path(tempfile.mkdtemp(prefix="codex-keep-receipt-test-"))
        self.addCleanup(shutil.rmtree, root)
        build = root / "build/codex-home"
        target = root / "live"
        write_json(root / "manifests/policies.json", {"schema_version": 2, "protected_paths": []})
        for base in (build, target):
            (base / "kept.txt").parent.mkdir(parents=True, exist_ok=True)
            (base / "kept.txt").write_text("same\n")
        state = {"schema_version": 2, "managed": []}
        write_json(build / "control/state/managed-files.json", state)
        write_json(target / "control/state/managed-files.json", state)
        plan = plan_apply(root, build, target, root / "backup", overwrite=False)

        self.assertTrue(
            any(row["path"] == "kept.txt" for row in plan["target_receipt"]["keep_paths"])
        )
        (target / "kept.txt").write_text("concurrent-change\n")
        with self.assertRaisesRegex(CodexAssetError, "target precondition paths 已变化"):
            apply_plan(plan, dry_run=True)

    def test_v2_plan_requires_regeneration(self) -> None:
        root = pathlib.Path(tempfile.mkdtemp(prefix="codex-v2-plan-test-"))
        self.addCleanup(shutil.rmtree, root)
        build = root / "build/codex-home"
        target = root / "live"
        write_json(root / "manifests/policies.json", {"schema_version": 2, "protected_paths": []})
        build.mkdir(parents=True)
        write_json(build / "control/state/managed-files.json", {"schema_version": 2, "managed": []})
        plan = plan_apply(root, build, target, root / "backup", overwrite=False)
        plan["schema_version"] = 2
        with self.assertRaisesRegex(CodexAssetError, "schema_version 非 3"):
            apply_plan(plan, dry_run=True)


if __name__ == "__main__":
    unittest.main()
