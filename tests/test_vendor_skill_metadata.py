from __future__ import annotations

import json
import pathlib
import tempfile
import unittest

from tools.codex_assets.vendor_skill_metadata import run


class VendorSkillMetadataTest(unittest.TestCase):
    def test_adds_only_missing_adk_vendor_metadata_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory(prefix="codex-vendor-metadata-") as temp:
            root = pathlib.Path(temp)
            skill = root / "src/codex-home/vendor/skills/adk-example/1.0.0"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("---\nname: adk-example\ndescription: Example vendor workflow.\nversion: 1.0.0\nlast_updated: 2026-08-22\n---\n", encoding="utf-8")
            manifest = {"skills": [{"name": "adk-example", "source_kind": "vendor", "owner": "agent-dev-kit", "version": "1.0.0", "vendor_rel": "vendor/skills/adk-example/1.0.0", "source_repo": "llm_agent/agent-dev-kit", "source_ref": "abc", "source_path": "skills/adk-example/SKILL.md"}]}
            (root / "manifests").mkdir()
            (root / "manifests/skills.json").write_text(json.dumps(manifest), encoding="utf-8")
            self.assertEqual(0, run(root))
            self.assertTrue((skill / "README.md").is_file())
            self.assertTrue((skill / "LICENSE").is_file())
            self.assertTrue((skill / "agents/openai.yaml").is_file())
            self.assertEqual(0, run(root))


if __name__ == "__main__":
    unittest.main()
