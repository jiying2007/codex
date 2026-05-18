from __future__ import annotations

import pathlib
import tempfile
import unittest

from tools.codex_assets.session_coach import (
    Notice,
    apply_cooldown,
    detect_phase,
    group_paths,
    parse_porcelain,
    rank_notices,
)


class SessionCoachTest(unittest.TestCase):
    def test_parse_and_group_paths(self) -> None:
        changes = parse_porcelain(
            " M AGENTS.md\n"
            "?? scripts/session-coach.sh\n"
            "A  manifests/workflows.json\n"
            "?? docs/archive/memory-curation/note.md\n"
        )
        groups = group_paths(changes)
        self.assertEqual(["manifests/workflows.json"], groups["staged"])
        self.assertIn("AGENTS.md", groups["agents"])
        self.assertIn("scripts/session-coach.sh", groups["scripts"])
        self.assertIn("docs/archive/memory-curation/note.md", groups["archive"])
        self.assertIn("manifests/workflows.json", groups["delivery"])

    def test_detect_phase_prefers_apply_then_commit_then_asset(self) -> None:
        empty = group_paths([])
        self.assertEqual("apply", detect_phase(empty, token_pressure=True, live_issue=True))
        staged = group_paths(parse_porcelain("A  manifests/workflows.json\n"))
        self.assertEqual("commit", detect_phase(staged, token_pressure=True, live_issue=False))
        dirty = group_paths(parse_porcelain(" M tools/codex_assets/session_coach.py\n"))
        self.assertEqual("asset-update", detect_phase(dirty, token_pressure=True, live_issue=False))
        self.assertEqual("handoff", detect_phase(empty, token_pressure=True, live_issue=False))

    def test_rank_notices_by_priority(self) -> None:
        notices = [
            Notice("HIGH", "A", "asset", 10, "a", "a").finalize(),
            Notice("MEDIUM", "B", "asset", 90, "b", "b").finalize(),
            Notice("CRITICAL", "C", "handoff", 80, "c", "c").finalize(),
        ]
        ranked = rank_notices(notices, top=2, show_all=False)
        self.assertEqual(["B", "C"], [notice.code for notice in ranked])

    def test_cooldown_suppresses_repeated_medium_not_high(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = pathlib.Path(tmp) / "state.json"
            medium = Notice("MEDIUM", "M", "archive", 10, "m", "m", evidence={"x": 1}).finalize()
            high = Notice("HIGH", "H", "asset", 10, "h", "h", evidence={"x": 1}).finalize()
            kept, suppressed = apply_cooldown([medium, high], state, no_cooldown=False, reset=False)
            self.assertEqual(2, len(kept))
            self.assertEqual(0, suppressed)
            medium2 = Notice("MEDIUM", "M", "archive", 10, "m", "m", evidence={"x": 1}).finalize()
            high2 = Notice("HIGH", "H", "asset", 10, "h", "h", evidence={"x": 1}).finalize()
            kept, suppressed = apply_cooldown([medium2, high2], state, no_cooldown=False, reset=False)
            self.assertEqual(["H"], [notice.code for notice in kept])
            self.assertTrue(kept[0].repeated)
            self.assertEqual(1, suppressed)


if __name__ == "__main__":
    unittest.main()
