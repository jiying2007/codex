from __future__ import annotations

import contextlib
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools.codex_assets.adk_skill_audit import AuditError, audit, main, summary


def blob(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


class AdkSkillAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "consumer"
        self.provider = Path(self.temp.name) / "provider"
        self.manifest = self.root / "manifests/skills.json"
        self.lock = self.root / "manifests/provider-locks/agent-dev-kit.json"
        self.skill = self.root / "src/codex-home/vendor/skills/adk-example/1.0.0/SKILL.md"
        self.write(self.skill, "---\nname: adk-example\n---\n# Example\n")
        self.record = {
            "name": "adk-example", "enabled": True, "owner": "agent-dev-kit", "tags": ["adk"],
            "source_repo": "jiying2007/agent-dev-kit", "source_ref": "a" * 40,
            "source_path": "skills/adk-example/SKILL.md", "source_blob": blob(self.skill.read_bytes()),
            "vendor_rel": "vendor/skills/adk-example/1.0.0",
        }
        self.save()
        self.write(self.lock, json.dumps({"schema": "codex-provider-lock/v3", "repository": "jiying2007/agent-dev-kit", "version": "7.0.4", "provider_commit": "a" * 40}))

    def write(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def save(self, records=None) -> None:
        self.write(self.manifest, json.dumps({"skills": [self.record] if records is None else records}))

    def git(self, *args: str) -> str:
        # The fixture is deleted immediately after each test. Wait for Git's
        # automatic maintenance instead of racing a detached writer in .git.
        # Command-local settings do not change developer/global Git config.
        result = subprocess.run(
            ["git", "-c", "maintenance.autoDetach=false", "-c", "gc.autoDetach=false",
             "-C", str(self.provider), *args],
            text=True, capture_output=True, check=True, timeout=10,
        )
        return result.stdout.strip()

    def candidate(self) -> str:
        self.write(self.provider / "manifest.json", '{"version":"7.0.31"}')
        self.write(self.provider / "skills/adk-example/SKILL.md", self.skill.read_text())
        self.write(self.provider / "skills/adk-example/references/example.md", "New supporting material\n")
        self.git("init", "-q")
        self.git("add", ".")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture")
        return self.git("rev-parse", "HEAD")

    def test_fixture_maintenance_is_foreground_and_not_persisted(self) -> None:
        self.provider.mkdir(parents=True)
        self.git("init", "-q")
        for key in ("maintenance.autoDetach", "gc.autoDetach"):
            with self.subTest(key=key):
                self.assertEqual("false", self.git("config", "--get", key))
                with self.assertRaises(subprocess.CalledProcessError):
                    self.git("config", "--local", "--get", key)

    def test_exact_local_metadata_is_not_release_or_runtime_certification(self) -> None:
        report = audit(self.root)
        self.assertEqual(report["status"], "consistent")
        self.assertEqual(report["skills_matching_provider_lock_commit"], 1)
        self.assertEqual(report["claims"], {"read_only": True, "release_verified": False, "installation_verified": False, "runtime_qualified": False})

    def test_legacy_short_refs_and_missing_blobs_are_reported_together(self) -> None:
        self.record.update(source_repo="llm_agent/agent-dev-kit", source_ref="083dc95")
        self.record.pop("source_blob")
        self.save()
        report = audit(self.root)
        self.assertEqual(report["status"], "needs-fix")
        self.assertEqual(report["skills_matching_provider_lock_commit"], 0)
        self.assertEqual(set(report["gap_counts"]), {"noncanonical_source_repository", "nonexact_source_commit", "missing_or_invalid_source_blob"})

    def test_mutated_entrypoint_is_rejected(self) -> None:
        self.skill.write_text("mutated")
        self.assertIn("local_skill_blob_mismatch", audit(self.root)["gap_counts"])

    def test_absent_skill_cannot_be_consistent(self) -> None:
        self.skill.unlink()
        self.assertEqual(audit(self.root)["status"], "needs-fix")

    def test_renaming_owner_does_not_hide_adk_skill(self) -> None:
        self.record.update(owner="local", source_repo="local/codex", tags=[])
        self.save()
        self.assertEqual(audit(self.root)["active_adk_skills"], 1)

    def test_disabled_adk_and_non_adk_are_not_silently_certified(self) -> None:
        disabled = {**self.record, "name": "adk-disabled", "enabled": False}
        local = {**self.record, "name": "local-example", "owner": "local", "source_repo": "local/codex", "tags": []}
        self.save([self.record, disabled, local])
        self.assertEqual(audit(self.root)["active_adk_skills"], 1)

    def test_empty_inventory_and_all_disabled_fail_closed(self) -> None:
        for records in ([], [{**self.record, "enabled": False}]):
            self.save(records)
            with self.assertRaisesRegex(AuditError, "no_active"):
                audit(self.root)

    def test_duplicate_name_and_nonboolean_enable_are_invalid(self) -> None:
        for records in ([self.record, self.record], [{**self.record, "enabled": "false"}]):
            self.save(records)
            with self.assertRaises(AuditError):
                audit(self.root)

    def test_path_traversal_absolute_and_control_paths_are_rejected(self) -> None:
        for value in ("../outside", "/tmp/outside", "vendor/skills/adk-example/../outside", "vendor\\skills\\adk-example", "vendor/skills/adk-example/a\n"):
            self.record["vendor_rel"] = value
            self.save()
            with self.subTest(path=value):
                self.assertEqual(audit(self.root)["status"], "needs-fix")

    def test_vendor_symlink_and_support_symlink_are_not_followed(self) -> None:
        outside = Path(self.temp.name) / "secret"
        outside.write_text("not for audit")
        link = self.skill.parent / "reference.md"
        link.symlink_to(outside)
        report = audit(self.root)
        self.assertEqual(report["status"], "needs-fix")
        self.assertNotIn("not for audit", json.dumps(report))
        link.unlink()
        self.skill.unlink()
        self.skill.symlink_to(outside)
        self.assertEqual(audit(self.root)["status"], "needs-fix")

    def test_manifest_parent_symlink_is_blocked(self) -> None:
        actual = self.root / "real-manifests"
        (self.root / "manifests").rename(actual)
        (self.root / "manifests").symlink_to(actual, target_is_directory=True)
        with self.assertRaisesRegex(AuditError, "symlink"):
            audit(self.root)

    def test_source_name_mismatch_is_not_a_valid_binding(self) -> None:
        self.record["source_path"] = "skills/adk-other/SKILL.md"
        self.save()
        self.assertIn("skill_source_name_mismatch", audit(self.root)["gap_counts"])

    def test_bounded_file_tree_and_inventory_limits(self) -> None:
        for constant, limit in (("MAX_FILE", 1), ("MAX_FILES", 0), ("MAX_TREE", 1)):
            with patch(f"tools.codex_assets.adk_skill_audit.{constant}", limit):
                self.assertEqual(audit(self.root)["status"], "needs-fix")
        with patch("tools.codex_assets.adk_skill_audit.MAX_SKILLS", 0), self.assertRaises(AuditError):
            audit(self.root)

    def test_summary_does_not_include_large_detail_or_body(self) -> None:
        report = summary(audit(self.root))
        self.assertNotIn("skills", report)
        self.assertNotIn("# Example", json.dumps(report))
        self.assertLess(len(json.dumps(report)), 2048)

    def test_target_support_files_and_stale_local_files_are_compared(self) -> None:
        commit = self.candidate()
        self.write(self.skill.parent / "old.md", "stale\n")
        target = audit(self.root, self.provider, commit)["skills"][0]["target"]
        self.assertEqual(target["status"], "source_available")
        self.assertEqual(target["added"], ["references/example.md"])
        self.assertEqual(target["removed"], ["old.md"])
        self.assertTrue(target["review_required"])
        self.assertEqual(len(target["tree_sha256"]), 64)

    def test_changing_support_content_changes_input_tree_identity(self) -> None:
        self.write(self.skill.parent / "reference.md", "first")
        first = audit(self.root)
        self.write(self.skill.parent / "reference.md", "second")
        second = audit(self.root)
        self.assertNotEqual(first["skills"][0]["local_tree_sha256"], second["skills"][0]["local_tree_sha256"])
        self.assertEqual(first["input_identity"], second["input_identity"])

    def test_target_commit_must_be_exact_and_match_checkout(self) -> None:
        self.candidate()
        for commit in ("main", "a" * 40, ""):
            with self.subTest(commit=commit), self.assertRaises(AuditError):
                audit(self.root, self.provider, commit)

    def test_target_untracked_and_dirty_files_block_even_with_same_head(self) -> None:
        commit = self.candidate()
        for path in (self.provider / "untracked", self.provider / "skills/adk-example/SKILL.md"):
            self.write(path, "dirty")
            with self.assertRaisesRegex(AuditError, "dirty"):
                audit(self.root, self.provider, commit)
            if path.name == "untracked":
                path.unlink()

    def test_provider_missing_skill_blocks_mapping_not_inventory(self) -> None:
        commit = self.candidate()
        self.record.update(name="adk-missing", source_path="skills/adk-missing/SKILL.md", vendor_rel="vendor/skills/adk-missing/1.0.0")
        self.save()
        report = audit(self.root, self.provider, commit)
        self.assertEqual(report["candidate"]["blocked_skills"], 1)
        self.assertEqual(report["status"], "needs-fix")

    def test_read_only_audit_preserves_all_fixture_bytes(self) -> None:
        commit = self.candidate()
        def snapshot():
            return {p.relative_to(Path(self.temp.name)).as_posix(): p.read_bytes() for p in Path(self.temp.name).rglob("*") if p.is_file() and ".git" not in p.parts}
        before = snapshot()
        audit(self.root, self.provider, commit)
        self.assertEqual(before, snapshot())

    def test_cli_exit_codes_distinguish_gaps_and_invalid_input(self) -> None:
        for expected, change in ((0, None), (2, "legacy"), (3, "malformed")):
            if change == "legacy":
                self.record["source_ref"] = "old"
                self.save()
            elif change == "malformed":
                self.manifest.write_text("[]")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["--root", str(self.root), "--summary-json"]), expected)
            self.assertIn(json.loads(output.getvalue())["status"], ("consistent", "needs-fix", "blocked"))

    def test_lock_without_identity_is_invalid_not_zero_matches(self) -> None:
        self.lock.write_text("{}")
        with self.assertRaisesRegex(AuditError, "lock_identity"):
            audit(self.root)

    def test_no_provider_checkout_does_not_verify_upstream_membership(self) -> None:
        self.assertIsNone(audit(self.root)["candidate"])
        with self.assertRaisesRegex(AuditError, "provider_root"):
            audit(self.root, expected_commit="a" * 40)

    def test_skip_worktree_cannot_hide_missing_target_support_file(self) -> None:
        commit = self.candidate()
        relative = "skills/adk-example/references/example.md"
        self.git("update-index", "--skip-worktree", relative)
        (self.provider / relative).unlink()
        self.assertEqual(self.git("status", "--porcelain"), "")
        target = audit(self.root, self.provider, commit)["skills"][0]["target"]
        self.assertEqual(target, {"status": "blocked", "reason": "provider_skill_tree_incomplete"})

    def test_ignored_filemode_change_is_still_rejected_against_git_tree(self) -> None:
        commit = self.candidate()
        self.git("config", "core.fileMode", "false")
        (self.provider / "skills/adk-example/references/example.md").chmod(0o755)
        self.assertEqual(self.git("status", "--porcelain"), "")
        target = audit(self.root, self.provider, commit)["skills"][0]["target"]
        self.assertEqual(target["status"], "blocked")

    def test_unreadable_support_directory_is_not_silently_skipped(self) -> None:
        def unreadable_walk(*args, **kwargs):
            kwargs["onerror"](PermissionError("fixture"))
        with patch("tools.codex_assets.adk_skill_audit.os.walk", side_effect=unreadable_walk):
            self.assertIn("skill_directory_unreadable", audit(self.root)["gap_counts"])

    def test_unbounded_lock_version_cannot_expand_summary(self) -> None:
        value = json.loads(self.lock.read_text())
        value["version"] = "x" * 1000
        self.lock.write_text(json.dumps(value))
        with self.assertRaisesRegex(AuditError, "lock_identity"):
            audit(self.root)


if __name__ == "__main__":
    unittest.main()
