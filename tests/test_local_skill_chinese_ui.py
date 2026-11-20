"""Current Codex-owned UI overlays are all Chinese and source methods stay independent."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
HAN = re.compile(r"[\u3400-\u9fff]")


class LocalSkillChineseUiTests(unittest.TestCase):
    def test_all_enabled_non_adk_skill_metadata_is_chinese(self) -> None:
        manifest = json.loads((ROOT / "manifests/skills.json").read_text(encoding="utf-8"))
        rows = [
            row for row in manifest["skills"]
            if row.get("enabled") is True and row.get("owner") != "agent-dev-kit"
        ]
        self.assertGreaterEqual(len(rows), 30)
        for row in rows:
            with self.subTest(skill=row["name"], owner=row["owner"]):
                path = ROOT / "src/codex-home" / row["vendor_rel"] / "agents/openai.yaml"
                self.assertTrue(path.is_file(), path)
                data = yaml.safe_load(path.read_text(encoding="utf-8"))
                interface = data.get("interface")
                self.assertIsInstance(interface, dict)
                for field in ("display_name", "short_description"):
                    value = interface.get(field)
                    self.assertIsInstance(value, str)
                    self.assertRegex(value, HAN)
                    self.assertTrue(3 <= len(value) <= 160)
        self.assertFalse(any(row.get("owner") == "agent-dev-kit" for row in rows))

    def test_source_identity_is_not_a_ui_translation_contract(self) -> None:
        manifest = json.loads((ROOT / "manifests/skills.json").read_text(encoding="utf-8"))
        for row in manifest["skills"]:
            if row.get("owner") == "agent-dev-kit":
                continue
            self.assertTrue(row.get("source_repo"))
            self.assertTrue(row.get("source_path"))
            # UI-only local formatting does not authorize vendor SKILL.md edits.
            self.assertTrue((ROOT / "src/codex-home" / row["vendor_rel"] / "SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
