"""Guard against reintroducing retired language-specific ADK Skills."""
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
RETIRED={"adk-chinese-code-review","adk-chinese-commit-conventions"}


class RetiredADKLanguageSkillTest(unittest.TestCase):
    def test_no_obsolete_managed_skill(self):
        value=json.loads((ROOT/"manifests/skills.json").read_text())
        names={x["name"] for x in value["skills"]}
        self.assertTrue(names.isdisjoint(RETIRED))
        self.assertTrue({"adk-code-review-loop","adk-commit-pr-quality-gate"}<=names)
        for name in RETIRED:
            self.assertFalse((ROOT/"src/codex-home/vendor/skills"/name).exists())

    def test_no_active_superpowers_source(self):
        value=json.loads((ROOT/"manifests/skills.json").read_text())
        active=[x for x in value["skills"] if x.get("enabled") and x.get("profiles")]
        for item in active:
            self.assertNotIn("superpowers",json.dumps(item).lower())


if __name__ == "__main__":
    unittest.main()
