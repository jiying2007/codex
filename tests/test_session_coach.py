from __future__ import annotations

import pathlib
import subprocess
import tempfile
import unittest

from tools.codex_assets.session_coach import (
    Notice,
    ack_notice,
    apply_cooldown,
    detect_phase,
    group_paths,
    parse_porcelain,
    rank_notices,
)
from tools.codex_assets.session_coach_checks import archive_quality_notices, event_policy_notices, evidence_notices
from tools.codex_assets.session_coach_config import load_config, validate_config
from tools.codex_assets.session_coach_core import fail_on_triggered, make_notice, overall_status
from tools.codex_assets.session_coach_evidence import record_evidence


class SessionCoachTest(unittest.TestCase):
    def test_shell_entry_anchors_module_resolution_to_repo_root(self) -> None:
        repo_root = pathlib.Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            collision = pathlib.Path(tmp) / "tools/codex_assets"
            collision.mkdir(parents=True)
            (collision.parent / "__init__.py").write_text("", encoding="utf-8")
            (collision / "__init__.py").write_text("", encoding="utf-8")
            completed = subprocess.run(
                ["rtk", "bash", str(repo_root / "scripts/session-coach.sh"), "--help"],
                cwd=tmp,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertIn("usage: codex-assets session-coach", completed.stdout)

    def test_parse_and_group_paths(self) -> None:
        changes = parse_porcelain(
            " M AGENTS.md\n"
            "?? scripts/session-coach.sh\n"
            "A  manifests/workflows.json\n"
            " M manifests/mcp_servers.json\n"
            "?? knowledge-hub/domains/codex/archive/codex-archive/memory-curation/note.md\n"
        )
        groups = group_paths(changes)
        self.assertEqual(["manifests/workflows.json"], groups["staged"])
        self.assertIn("AGENTS.md", groups["agents"])
        self.assertIn("scripts/session-coach.sh", groups["scripts"])
        self.assertIn("manifests/mcp_servers.json", groups["mcp"])
        self.assertIn("knowledge-hub/domains/codex/archive/codex-archive/memory-curation/note.md", groups["archive"])
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

    def test_ack_suppresses_medium_notice(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = pathlib.Path(tmp) / "state.json"
            ack_notice(state, "ARCHIVE_REVIEW")
            medium = Notice("MEDIUM", "ARCHIVE_REVIEW", "archive", 10, "m", "m").finalize()
            high = Notice("HIGH", "SCRIPT_CHANGED", "asset", 10, "h", "h").finalize()
            kept, suppressed = apply_cooldown([medium, high], state, no_cooldown=False, reset=False)
            self.assertEqual(["SCRIPT_CHANGED"], [notice.code for notice in kept])
            self.assertEqual(1, suppressed)

    def test_stable_key_ignores_dynamic_evidence(self) -> None:
        first = make_notice("CRITICAL", "THREAD_LONG", "handoff", 100, "a", "a", stable_key="thread:1", tokens=1)
        second = make_notice("CRITICAL", "THREAD_LONG", "handoff", 100, "a", "a", stable_key="thread:1", tokens=2)
        self.assertEqual(first.fingerprint, second.fingerprint)

    def test_status_uses_full_notice_set_not_top_slice(self) -> None:
        notices = [Notice("CRITICAL", "C", "handoff", 100, "c", "c").finalize()]
        self.assertEqual([], rank_notices(notices, top=0, show_all=False))
        self.assertEqual("CRITICAL", overall_status(notices))

    def test_fail_on_threshold(self) -> None:
        notices = [Notice("HIGH", "H", "commit", 10, "h", "h").finalize()]
        self.assertTrue(fail_on_triggered(notices, "high"))
        self.assertFalse(fail_on_triggered(notices, "critical"))
        self.assertFalse(fail_on_triggered(notices, "never"))

    def test_config_loads_manifest_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "manifests").mkdir()
            (root / "manifests/session_coach.json").write_text('{"defaults":{"top":7},"events":{"final":{"phase":"handoff"}}}')
            config = load_config(root)
            self.assertEqual(7, config["defaults"]["top"])
            self.assertEqual(50_000_000, config["defaults"]["warn_thread_tokens"])
            self.assertEqual("handoff", config["events"]["final"]["phase"])

    def test_config_validation_rejects_bad_values(self) -> None:
        errors = validate_config({
            "defaults": {"context_pressure_ratio": 2},
            "events": {"bad-event": {"phase": "unknown"}},
            "protected_archive_patterns": ["("],
        })
        self.assertTrue(any("context_pressure_ratio" in error for error in errors))
        self.assertTrue(any("未知事件" in error for error in errors))
        self.assertTrue(any("正则非法" in error for error in errors))

    def test_event_policy_commit_requires_staged_files(self) -> None:
        groups = group_paths(parse_porcelain(" M tools/codex_assets/session_coach.py\n"))
        codes = [notice.code for notice in event_policy_notices(pathlib.Path("/tmp"), groups, "commit")]
        self.assertIn("COMMIT_NOT_STAGED", codes)

    def test_archive_quality_flags_meta_and_secret(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            path = root / "knowledge-hub/domains/codex/archive/codex-archive/topic/note.md"
            path.parent.mkdir(parents=True)
            path.write_text("api" + "_key = should-not-be-here\n")
            groups = {"archive": ["knowledge-hub/domains/codex/archive/codex-archive/topic/note.md"]}
            config = {"defaults": {"archive_max_bytes": 1000}, "protected_archive_patterns": ["api_key"]}
            codes = {notice.code for notice in archive_quality_notices(root, groups, config)}
            self.assertIn("ARCHIVE_META_MISSING", codes)
            self.assertIn("ARCHIVE_SECRET_PATTERN", codes)

    def test_password_pattern_requires_assignment_value(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            path = root / "knowledge-hub/domains/codex/archive/codex-archive/topic/note.md"
            path.parent.mkdir(parents=True)
            groups = {"archive": ["knowledge-hub/domains/codex/archive/codex-archive/topic/note.md"]}
            config = {
                "defaults": {"archive_max_bytes": 1000},
                "protected_archive_patterns": [r"(?i)\bpassword\b\s*[:=]\s*['\"]?[^\s'\"]{8,}"],
            }

            path.write_text("Do not store NAS passwords in repositories.\n")
            codes = {notice.code for notice in archive_quality_notices(root, groups, config)}
            self.assertNotIn("ARCHIVE_SECRET_PATTERN", codes)

            path.write_text("pass" + "word: very-secret-value\n")
            codes = {notice.code for notice in archive_quality_notices(root, groups, config)}
            self.assertIn("ARCHIVE_SECRET_PATTERN", codes)

    def test_evidence_notice_clears_after_recent_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "evidence.json"
            config = {
                "defaults": {"evidence_fresh_minutes": 240},
                "events": {"final": {"phase": "handoff", "required_evidence": "final-ready"}},
            }
            self.assertEqual(["EVIDENCE_MISSING"], [notice.code for notice in evidence_notices("final", config, path)])
            record_evidence(path, "final-ready", "pass", "ok")
            self.assertEqual([], evidence_notices("final", config, path))


if __name__ == "__main__":
    unittest.main()
