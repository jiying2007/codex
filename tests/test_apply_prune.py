from __future__ import annotations

import json
import pathlib
import shutil
import tempfile
import unittest

from tools.codex_assets.core import apply_plan, plan_apply


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
        deletes = [action for action in plan["actions"] if action["action"] == "delete"]
        self.assertEqual(["skills/writing-plans"], [action["path"] for action in deletes])

        apply_plan(plan, dry_run=False)
        self.assertFalse(stale.exists())
        self.assertTrue((backup / "skills/writing-plans").is_file())


if __name__ == "__main__":
    unittest.main()
