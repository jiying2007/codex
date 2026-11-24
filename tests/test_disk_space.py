import argparse
import contextlib
import io
import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.codex_assets.disk_space import (
    configure_parser, contains, filesystem_root, mount_points, process_refs,
    reference_identity, run, scan, sudo_scan,
)
from tools.codex_assets.core import CodexAssetError


class DiskSpaceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.future = time.time() + 30 * 86400

    def inventory(self, **kwargs):
        return scan(self.root, mounts=set(), now=self.future, **kwargs)

    def test_readonly_and_hardlinks_are_charged_once(self):
        f = self.root / "a"
        f.write_bytes(b"a" * 8192)
        os.link(str(f), str(self.root / "b"))
        before = f.read_bytes()
        result = self.inventory()
        expected = self.root.stat().st_blocks * 512 + f.stat().st_blocks * 512
        self.assertEqual(result["visible_allocated_bytes"], expected)
        self.assertEqual(before, f.read_bytes())
        self.assertEqual(2, f.stat().st_nlink)
        self.assertTrue(result["read_only"])

    def test_recent_descendant_protects_whole_tree(self):
        folder = self.root / "old-name"
        folder.mkdir()
        f = folder / "recent"
        f.touch()
        os.utime(str(f), (self.future, self.future))
        rows = {r["path"]: r for r in self.inventory()["top_paths"]}
        self.assertIn("recent-change", rows[str(folder)]["reasons"])

    def test_ctime_protects_copied_old_mtime(self):
        f = self.root / "copied"
        f.touch()
        os.utime(str(f), (1, 1))
        result = scan(self.root, mounts=set())
        row = next(x for x in result["top_paths"] if x["path"] == str(f))
        self.assertIn("recent-change", row["reasons"])

    def test_usage_protects_regular_file_access_but_ignores_directory_atime(self):
        folder = self.root / "编译 old tree"
        folder.mkdir()
        child = folder / "output"
        child.touch()
        old_time = child.stat().st_mtime
        os.utime(str(folder), (self.future, old_time))
        with self.subTest("directory enumeration does not make it recent"):
            result = self.inventory(candidate_type="directory", age_basis="usage")
            self.assertEqual("review-required", result["candidate_selection"]["items"][0]["decision"])
        os.utime(str(child), (self.future, old_time))
        changed_only = self.inventory(candidate_type="directory")["candidate_selection"]["items"][0]
        usage = self.inventory(candidate_type="directory", age_basis="usage")["candidate_selection"]["items"][0]
        self.assertEqual("review-required", changed_only["decision"])
        self.assertEqual("retain", usage["decision"])
        self.assertIn("recent-access", usage["reasons"])
        self.assertNotIn("recent-change", usage["reasons"])

    def test_candidate_paths_are_complete_and_preserve_exact_names(self):
        paths = [self.root / "旧 周报.txt", self.root / "old;file", self.root / "x64 host fixed 2it426mw"]
        paths[0].touch()
        paths[1].touch()
        paths[2].mkdir()
        (paths[2] / "nested.bin").touch()
        (self.root / "alias").symlink_to(paths[0])
        for kind, expected in (("file", paths[:2]), ("directory", paths[2:]), ("both", paths)):
            result = self.inventory(candidate_type=kind, top=1)
            self.assertEqual(1, len(result["top_paths"]))
            items = result["candidate_selection"]["items"]
            self.assertEqual({str(p) for p in expected}, {i["path"] for i in items})
        self.assertEqual([], self.inventory(candidate_type="both", candidate_uid=os.getuid() + 1)
                         ["candidate_selection"]["items"])

    def test_candidates_hold_hardlinks_and_private_entries(self):
        f = self.root / "old-log"
        f.touch()
        os.link(str(f), str(self.root / "second-log"))
        profile = self.root / "old-profile"
        profile.mkdir()
        (profile / "cookies.sqlite").touch()
        result = self.inventory(candidate_type="both")
        rows = {Path(i["path"]).name: i for i in result["candidate_selection"]["items"]}
        self.assertIn("hardlink", rows["old-log"]["reasons"])
        self.assertIn("protected-name", rows["old-profile"]["reasons"])

    def test_candidate_list_marks_incomplete_directories_and_files(self):
        for name in ("first", "second", "third"):
            (self.root / name).touch()
        result = self.inventory(candidate_type="file", max_entries=2)
        selection = result["candidate_selection"]
        self.assertEqual("partial", selection["filesystem_coverage"])
        self.assertTrue(selection["items"])
        self.assertTrue(all(x["decision"] == "retain" for x in selection["items"]))

    def test_nested_git_is_protected(self):
        folder = self.root / "copy" / "nested"
        folder.mkdir(parents=True)
        (folder / ".git").write_text("gitdir: /some/repo/.git/worktrees/copy")
        row = next(x for x in self.inventory()["top_paths"] if x["path"].endswith("/copy"))
        self.assertIn("git-or-worktree", row["reasons"])

    def test_symlink_does_not_traverse_target(self):
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "large").write_bytes(b"a" * 40960)
        inside = self.root / "inside"
        inside.mkdir()
        (inside / "link").symlink_to(outside, target_is_directory=True)
        result = scan(inside, mounts=set())
        self.assertEqual([], result["large_files"])
        self.assertEqual(2, result["coverage"]["entries_visited"])

    def test_same_device_bind_mount_is_skipped(self):
        mounted = self.root / "mounted"
        mounted.mkdir()
        (mounted / "invisible").write_bytes(b"a" * 4096)
        result = scan(self.root, mounts={str(mounted)})
        self.assertIn(str(mounted), result["coverage"]["skipped_mounts"])
        self.assertNotIn("invisible", json.dumps(result))

    def test_permission_failure_is_partial_and_not_safe(self):
        blocked = self.root / "blocked"
        blocked.mkdir()
        real_open = os.open

        def denied(path, *args, **kwargs):
            if str(path) == str(blocked):
                raise PermissionError("denied")
            return real_open(path, *args, **kwargs)

        with patch("tools.codex_assets.disk_space.os.open", side_effect=denied):
            result = self.inventory()
        self.assertEqual("partial", result["coverage"]["state"])
        row = next(x for x in result["top_paths"] if x["path"] == str(blocked))
        self.assertIn("incomplete-coverage", row["reasons"])

    def test_entry_limit_does_not_claim_complete_inventory(self):
        for i in range(5):
            (self.root / str(i)).touch()
        result = self.inventory(max_entries=2)
        self.assertEqual("entry-limit", result["coverage"]["stop_reason"])
        self.assertTrue(all(x["decision"] == "retain" for x in result["top_paths"]))

    def test_sparse_file_reports_apparent_and_allocated(self):
        f = self.root / "sparse"
        with f.open("wb") as stream:
            stream.truncate(16 * 1024 * 1024)
        row = self.inventory()["large_files"][0]
        self.assertEqual(16 * 1024 * 1024, row["apparent_bytes"])
        self.assertLess(row["allocated_bytes"], row["apparent_bytes"])

    def test_all_uids_are_retained_in_summary(self):
        f = self.root / "other"
        f.write_bytes(b"a" * 4096)
        real = os.lstat

        def other_uid(path):
            s = real(path)
            if str(path) == str(f):
                class Owned:
                    pass
                v = Owned()
                for field in ("st_uid", "st_dev", "st_ino", "st_mode", "st_nlink", "st_mtime", "st_ctime", "st_blocks", "st_size"):
                    setattr(v, field, getattr(s, field))
                v.st_uid = 987654
                return v
            return s

        with patch("tools.codex_assets.disk_space.os.lstat", side_effect=other_uid):
            result = self.inventory()
        self.assertIn(987654, [x["uid"] for x in result["users"]])
        row = next(x for x in result["top_paths"] if x["path"] == str(f))
        self.assertIn("other-or-mixed-uid", row["reasons"])

    def test_process_paths_and_permission_gaps(self):
        proc = self.root / "proc"
        pid = proc / "123"
        (pid / "fd").mkdir(parents=True)
        (pid / "cwd").symlink_to(self.root)
        (pid / "exe").symlink_to("/usr/bin/test")
        (pid / "maps").write_text("123 123 0 0 0 " + str(self.root / "mapped") + "\n")
        result = process_refs(str(self.root), proc=str(proc))
        self.assertTrue(any(x["kind"] == "cwd" for x in result["references"]))
        self.assertTrue(any(x["kind"] == "map" for x in result["references"]))
        with patch("tools.codex_assets.disk_space.os.listdir", side_effect=[ ["123"], PermissionError() ]):
            partial = process_refs(str(self.root), proc=str(proc))
        self.assertEqual("partial", partial["state"])
        self.assertEqual(1, partial["coverage"]["denied"])
        self.assertTrue(any(x["kind"] == "map" for x in partial["references"]))

    def test_mount_escapes_and_path_boundaries(self):
        info = self.root / "mountinfo"
        info.write_text("1 0 8:1 / / rw - ext4 /dev/sda rw\n2 1 8:2 / /media/a\\040b rw - ext4 /dev/sdb rw\n")
        mounts = mount_points(info)
        self.assertIn("/media/a b", mounts)
        self.assertEqual("/", filesystem_root("/tmp", mounts))
        self.assertFalse(contains("/tmp/a", "/tmp/ab"))

    def test_candidate_reference_check_covers_paths_beyond_display_limit(self):
        pid = self.root / "proc" / "123"
        (pid / "fd").mkdir(parents=True)
        mapped = self.root / "hold with 空格"
        command = self.root / "cmdline evidence"
        command.touch()
        mapped.touch()
        (pid / "cmdline").write_bytes(b"test\0--input=" + os.fsencode(command) + b"\0")
        (pid / "maps").write_text(
            ("123 123 0 0 0 " + str(self.root / "other") + "\n") * 201
            + "123 123 0 0 0 " + str(mapped) + "\n")
        proc = process_refs(str(self.root), proc=str(pid.parent), protect_top_level=True)
        self.assertTrue(proc["references_truncated"])
        self.assertIn(str(command), proc["protected_top_level_paths"])
        self.assertIn(str(mapped), proc["protected_top_level_paths"])
        args = self.sudo_args("--path", str(self.root), "--candidate-type", "file", "--top", "1")
        with patch("tools.codex_assets.disk_space.process_refs", return_value=proc):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(0, run(args))
        selection = json.loads(output.getvalue())["candidate_selection"]
        self.assertEqual("partial", selection["process_coverage"])
        self.assertEqual(2, len(selection["items"]))
        self.assertTrue(all("process-reference" in x["reasons"] for x in selection["items"]))

    def test_deleted_open_file_is_counted_once(self):
        gone = self.root / "gone"
        gone.write_bytes(b"x" * 8192)
        fd = os.open(str(gone), os.O_RDONLY)
        self.addCleanup(os.close, fd)
        expected = os.fstat(fd).st_blocks * 512
        gone.unlink()
        proc = self.root / "proc"
        pid = proc / "123"
        (pid / "fd").mkdir(parents=True)
        (pid / "maps").touch()
        for n in ("1", "2"):
            (pid / "fd" / n).symlink_to("/proc/self/fd/" + str(fd))
        real_link = os.readlink

        def deleted_target(p):
            if str(p).startswith(str(pid / "fd") + "/"):
                return str(gone) + " (deleted)"
            return real_link(p)

        with patch("tools.codex_assets.disk_space.os.readlink", side_effect=deleted_target):
            result = process_refs(str(self.root), proc=str(proc))
        self.assertEqual(expected, result["deleted_open_allocated_bytes"])
        self.assertEqual(1, len(result["deleted_open_files"]))

    def test_nonfinite_limits_are_rejected(self):
        parser = argparse.ArgumentParser()
        configure_parser(parser)
        for option in ("--max-seconds", "--keep-days"):
            for value in ("nan", "inf", "0", "-1"):
                with self.assertRaises(CodexAssetError):
                    run(parser.parse_args([option, value]))

    def test_non_linux_command_is_rejected_without_breaking_cli_import(self):
        parser = argparse.ArgumentParser()
        configure_parser(parser)
        with patch("tools.codex_assets.disk_space.sys.platform", "win32"):
            with self.assertRaises(CodexAssetError):
                run(parser.parse_args([]))

    def sudo_args(self, *options):
        parser = argparse.ArgumentParser()
        configure_parser(parser)
        return parser.parse_args(list(options))

    def test_sudo_uses_fixed_isolated_worker_and_literal_arguments(self):
        args = self.sudo_args("--sudo", "--path", "/tmp/a;$(touch nope)", "--processes")
        report = dict(schema_version="disk-space-triage/v1", read_only=True,
                      privilege=dict(effective_uid=0, reference_uid=os.getuid()))
        completed = subprocess.CompletedProcess([], 2, json.dumps(report), "")
        with patch("tools.codex_assets.disk_space.subprocess.run", return_value=completed) as execute:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(2, sudo_scan(args))
        command = execute.call_args.args[0]
        self.assertEqual(["/usr/bin/sudo", "-n", "--", "/usr/bin/python3", "-I", "-S", "-B"], command[:7])
        self.assertIn(args.path, command)
        self.assertNotIn("--sudo", command)
        self.assertNotIn("shell", execute.call_args.kwargs)

    def test_sudo_failure_does_not_fallback_or_read_password(self):
        completed = subprocess.CompletedProcess([], 1, "", "sudo: a password is required")
        with patch("tools.codex_assets.disk_space.subprocess.run", return_value=completed) as execute:
            with self.assertRaises(CodexAssetError):
                sudo_scan(self.sudo_args("--sudo"))
        self.assertEqual(1, execute.call_count)
        self.assertNotIn("input", execute.call_args.kwargs)

    def test_sudo_rejects_unexpected_worker_identity(self):
        report = dict(schema_version="disk-space-triage/v1", read_only=True,
                      privilege=dict(effective_uid=0, reference_uid=os.getuid() + 1))
        completed = subprocess.CompletedProcess([], 0, json.dumps(report), "")
        with patch("tools.codex_assets.disk_space.subprocess.run", return_value=completed):
            with self.assertRaises(CodexAssetError):
                sudo_scan(self.sudo_args("--sudo"))

    def test_normal_mode_never_invokes_sudo(self):
        args = self.sudo_args("--path", str(self.root))
        with patch("tools.codex_assets.disk_space.subprocess.run") as execute:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(0, run(args))
        execute.assert_not_called()

    def test_candidate_cli_disallows_ambiguous_scope(self):
        for options in (("--candidate-uid", "0"), ("--candidate-type", "file", "--candidate-uid", "-1"),
                        ("--candidate-type", "directory", "--filesystem")):
            with self.subTest(options=options), self.assertRaises(CodexAssetError):
                run(self.sudo_args(*options))

    def test_sudo_identity_preserves_original_uid(self):
        with patch.dict(os.environ, {"SUDO_UID": "12345"}):
            with patch("tools.codex_assets.disk_space.os.geteuid", return_value=0):
                self.assertEqual((12345, "sudo-readonly"), reference_identity())
            with patch("tools.codex_assets.disk_space.os.geteuid", return_value=1002):
                self.assertEqual((os.getuid(), "user-readonly"), reference_identity())

    def test_root_scan_does_not_treat_root_files_as_callers_files(self):
        f = self.root / "owned"
        f.touch()
        own = os.getuid()
        with patch("tools.codex_assets.disk_space.os.getuid", return_value=0):
            report = self.inventory(reference_uid=own)
        row = next(x for x in report["top_paths"] if x["path"] == str(f))
        self.assertNotIn("other-or-mixed-uid", row["reasons"])
        foreign = self.inventory(reference_uid=own + 1)
        other = next(x for x in foreign["top_paths"] if x["path"] == str(f))
        self.assertIn("other-or-mixed-uid", other["reasons"])

    def test_standalone_worker_ignores_pythonpath_and_cwd_modules(self):
        (self.root / "json.py").write_text("raise RuntimeError('cwd import must not run')")
        (self.root / "sitecustomize.py").write_text("raise RuntimeError('startup hook must not run')")
        from tools.codex_assets import disk_space
        environment = dict(os.environ, PYTHONPATH=str(self.root))
        completed = subprocess.run(["/usr/bin/python3", "-I", "-S", "-B", disk_space.__file__, "--help"],
                                   cwd=str(self.root), env=environment, capture_output=True, text=True)
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertIn("--sudo", completed.stdout)


if __name__ == "__main__":
    unittest.main()
