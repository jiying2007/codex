from __future__ import annotations

import json
import pathlib
import shutil
import tempfile
import unittest

from tools.codex_assets.core import inactive_plugin_skill_patterns, live_drift


def write_state(target: pathlib.Path, managed: list[dict[str, str]]) -> None:
    state = target / "control/state/managed-files.json"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps({"schema_version": 2, "profile": "team-collab", "managed": managed}) + "\n")


class LiveProfileDriftTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = pathlib.Path(tempfile.mkdtemp(prefix="codex-live-profile-"))
        self.addCleanup(shutil.rmtree, self.root)
        self.build = self.root / "build"
        self.live = self.root / "live"
        self.build.mkdir()
        (self.live / "skills/adk-test-strategy").mkdir(parents=True)
        write_state(
            self.live,
            [
                {"path": "skills/adk-test-strategy", "type": "dir"},
            ],
        )

    def test_live_managed_profile_assets_do_not_depend_on_default_build(self) -> None:
        self.assertEqual([], live_drift(self.build, self.live)["unmanaged"])

    def test_unknown_live_skill_still_fails_closed(self) -> None:
        (self.live / "skills/rogue-skill").mkdir(parents=True)
        self.assertEqual(["skills/rogue-skill"], live_drift(self.build, self.live)["unmanaged"])

    def test_plugin_without_active_skill_is_excluded_as_a_whole(self) -> None:
        skill = self.root / "source/vendor/plugins/example/1.0.0/skills/compat/SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("fixture\n")
        patterns = inactive_plugin_skill_patterns(self.root / "source", [], "team-collab")
        self.assertEqual(
            ["vendor/plugins/example/1.0.0", "vendor/plugins/example/1.0.0/**"],
            patterns,
        )


if __name__ == "__main__":
    unittest.main()
