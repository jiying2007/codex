"""Bounded, metadata-only Linux filesystem accounting. Never deletes files."""
from __future__ import annotations

import argparse
import heapq
import json
import math
import os
import re
import stat
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

PROTECTED_NAMES = {".ssh", ".aws", ".gnupg", ".netrc", ".git-credentials",
                   "auth.json", "credentials.json", "authorized_keys", "cookies.sqlite",
                   "key4.db", ".xauthority", ".iceauthority"}

if __package__:
    from .core import CodexAssetError
else:
    # The sudo worker uses isolated Python, without importing the asset package.
    class CodexAssetError(RuntimeError):
        pass


def mount_points(path="/proc/self/mountinfo"):
    def decode(value):
        return re.sub(r"\\([0-7]{3})", lambda m: chr(int(m[1], 8)), value)
    with open(path, encoding="utf-8") as stream:
        return {decode(line.split()[4]) for line in stream if len(line.split()) > 5}


def contains(root, path):
    return path == root or path.startswith(root.rstrip("/") + "/")


def filesystem_root(path, mounts):
    choices = [m for m in mounts if contains(m, path)]
    if not choices:
        raise CodexAssetError("无法从 mountinfo 确认文件系统根目录")
    return max(choices, key=len)


def mount_identity(mount):
    with open("/proc/self/mountinfo", encoding="utf-8") as stream:
        for line in stream:
            left, right = line.rstrip().split(" - ", 1)
            fields, detail = left.split(), right.split()
            point = re.sub(r"\\([0-7]{3})", lambda m: chr(int(m[1], 8)), fields[4])
            if point == mount:
                return dict(point=mount, device=fields[2], filesystem_type=detail[0],
                            source=detail[1], options=fields[5].split(","))
    return dict(point=mount, state="changed-during-scan")


def disk_stats(path):
    s = os.statvfs(path)
    return dict(total_bytes=s.f_blocks * s.f_frsize,
                used_bytes=(s.f_blocks - s.f_bfree) * s.f_frsize,
                free_bytes=s.f_bfree * s.f_frsize,
                available_bytes=s.f_bavail * s.f_frsize,
                reserved_or_unavailable_bytes=(s.f_bfree - s.f_bavail) * s.f_frsize,
                total_inodes=s.f_files, available_inodes=s.f_favail)


def username(uid):
    import pwd
    try:
        return pwd.getpwuid(uid).pw_name
    except KeyError:
        return str(uid)


def scan(path, *, keep_days=5, max_entries=1000000, max_seconds=120,
         top=20, mounts=None, now=None, reference_uid=None, age_basis="change",
         candidate_type=None, candidate_uid=None):
    root = str(Path(path).resolve(strict=True))
    if not os.path.isdir(root):
        raise CodexAssetError("扫描路径必须是目录")
    mounts = mount_points() if mounts is None else mounts
    start = time.monotonic()
    now = time.time() if now is None else now
    cutoff = now - keep_days * 86400
    dev = os.lstat(root).st_dev
    reference_uid = os.getuid() if reference_uid is None else reference_uid
    candidate_uid = reference_uid if candidate_uid is None else candidate_uid
    owners, rows, seen, large = {}, {}, set(), []
    errors, skipped, error_samples = Counter(), [], []
    visited = 0
    stopped = None

    def row_for(key):
        if key not in rows:
            rows[key] = dict(path=key, allocated_bytes=0, apparent_bytes=0,
                             entries=0, latest_change=0, uids=set(),
                             errors=0, git=False, special=False, skipped_mount=False)
        return rows[key]

    def visit(p, key):
        nonlocal visited, stopped
        row = row_for(key)
        name = os.path.basename(p)
        if visited >= max_entries or time.monotonic() - start >= max_seconds:
            stopped = "entry-limit" if visited >= max_entries else "time-limit"
            return
        visited += 1
        if candidate_type:
            lower = name.lower()
            if (lower in PROTECTED_NAMES or lower.endswith((".lock", ".pid", ".sock", ".key", ".pem"))
                    or lower.startswith((".env", "systemd-private-", "codex-daemon-", "ssh-"))):
                row["protected"] = True
        try:
            s = os.lstat(p)
            if candidate_type and p == key and p != root:
                row["owner_uid"] = s.st_uid
                row["type"] = ("directory" if stat.S_ISDIR(s.st_mode) else
                               "file" if stat.S_ISREG(s.st_mode) else "other")
            if p != root and (p in mounts or s.st_dev != dev):
                row["skipped_mount"] = True
                if len(skipped) < 100:
                    skipped.append(p)
                return
            row["entries"] += 1
            row["latest_change"] = max(row["latest_change"], s.st_mtime, s.st_ctime)
            if age_basis == "usage" and stat.S_ISREG(s.st_mode):
                row["latest_file_access"] = max(row.get("latest_file_access", s.st_atime), s.st_atime)
            row["uids"].add(s.st_uid)
            row["git"] |= name == ".git"
            row["special"] |= not (stat.S_ISDIR(s.st_mode) or
                                      stat.S_ISREG(s.st_mode) or stat.S_ISLNK(s.st_mode))
            duplicate = False
            if not stat.S_ISDIR(s.st_mode) and s.st_nlink > 1:
                if candidate_type:
                    row["hardlink"] = True
                identity = (s.st_dev, s.st_ino)
                duplicate = identity in seen
                seen.add(identity)
            if not duplicate:
                allocated = s.st_blocks * 512
                row["allocated_bytes"] += allocated
                row["apparent_bytes"] += s.st_size
                owner = owners.setdefault(s.st_uid, Counter())
                owner["allocated_bytes"] += allocated
                owner["apparent_bytes"] += s.st_size
                owner["entries"] += 1
                if stat.S_ISREG(s.st_mode):
                    heapq.heappush(large, (allocated, p, s.st_uid, s.st_nlink, s.st_size))
                    if len(large) > top:
                        heapq.heappop(large)
            if stat.S_ISDIR(s.st_mode):
                # O_NOFOLLOW rejects a directory replaced by a symlink before open.
                fd = os.open(p, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                try:
                    opened = os.fstat(fd)
                    if (opened.st_dev, opened.st_ino) != (s.st_dev, s.st_ino):
                        raise OSError("directory changed during scan")
                    with os.scandir(fd) as entries:
                        git_markers = set()
                        for entry in entries:
                            if candidate_type and entry.name in ("HEAD", "objects", "refs"):
                                git_markers.add(entry.name)
                            child = os.path.join(p, entry.name)
                            visit(child, child if p == root else key)
                            if stopped:
                                break
                        row["git"] |= len(git_markers) == 3
                finally:
                    os.close(fd)
        except (OSError, RecursionError) as exc:
            errors[type(exc).__name__] += 1
            row["errors"] += 1
            if len(error_samples) < 20:
                error_samples.append(dict(path=p, kind=type(exc).__name__))

    before = disk_stats(root)
    visit(root, root)
    for row in rows.values():
        reasons = []
        if row["latest_change"] >= cutoff:
            reasons.append("recent-change")
        if age_basis == "usage" and row.get("latest_file_access", float("-inf")) >= cutoff:
            reasons.append("recent-access")
        if stopped or row["errors"] or row["skipped_mount"]:
            reasons.append("incomplete-coverage")
        if row["git"]:
            reasons.append("git-or-worktree")
        if row["special"]:
            reasons.append("runtime-or-special-file")
        if row["uids"] != {reference_uid}:
            reasons.append("other-or-mixed-uid")
        row["uids"] = sorted(row["uids"])
        row["age_days"] = round((now - row["latest_change"]) / 86400, 3)
        row["decision"] = "retain" if reasons else "old-review-required"
        row["reasons"] = reasons or ["age-alone-does-not-authorize-deletion"]
    ranked = sorted(rows.values(), key=lambda r: r["allocated_bytes"], reverse=True)
    result = dict(schema_version="disk-space-triage/v1", read_only=True,
                root=root, started_at=now, cutoff_epoch=cutoff, keep_days=keep_days,
                filesystem_before=before, filesystem_after=disk_stats(root),
                accounting="st_blocks*512; hardlinks charged to first encountered path; not physical/reclaimable bytes",
                coverage=dict(state="partial" if errors or stopped else "visible-tree-complete",
                              stop_reason=stopped, entries_visited=visited,
                              errors=dict(errors), error_samples=error_samples, skipped_mounts=skipped,
                              elapsed_seconds=round(time.monotonic() - start, 3)),
                visible_allocated_bytes=sum(x["allocated_bytes"] for x in owners.values()),
                users=[dict(uid=uid, user=username(uid), **values) for uid, values in
                       sorted(owners.items(), key=lambda x: x[1]["allocated_bytes"], reverse=True)],
                top_paths=ranked[:top], top_paths_total=len(ranked),
                large_files=[dict(allocated_bytes=b, path=p, uid=u, links=n, apparent_bytes=a)
                             for b, p, u, n, a in sorted(large, reverse=True)],
                process_check=dict(state="not-run"))
    if age_basis == "usage":
        result["age_basis"] = age_basis
    if candidate_type:
        items = []
        types = {"file", "directory"} if candidate_type == "both" else {candidate_type}
        for row in sorted(rows.values(), key=lambda item: item["path"]):
            if row.get("type") not in types or row.get("owner_uid") != candidate_uid:
                continue
            reasons = [r for r in row["reasons"]
                       if r not in ("other-or-mixed-uid", "age-alone-does-not-authorize-deletion")]
            if set(row["uids"]) != {candidate_uid}:
                reasons.append("other-or-mixed-uid")
            if row.get("protected"):
                reasons.append("protected-name")
            if row.get("hardlink"):
                reasons.append("hardlink")
            item = dict(row)
            item["reasons"] = reasons or ["requires-review"]
            item["decision"] = "retain" if reasons else "review-required"
            items.append(item)
        result["candidate_selection"] = dict(
            uid=candidate_uid, type=candidate_type, age_basis=age_basis,
            filesystem_coverage=result["coverage"]["state"],
            process_coverage="not-run", items=items)
    return result


def process_refs(root, *, proc="/proc", max_seconds=15, protect_top_level=False):
    start = time.monotonic()
    coverage = Counter()
    refs, deleted, identities = [], [], set()
    protected = set()
    root_dev = os.stat(root).st_dev
    truncated = False

    def protect(target):
        if target != root and contains(root, target):
            rel = os.path.relpath(target, root).split(os.sep, 1)[0]
            protected.add(os.path.join(root, rel))

    for name in os.listdir(proc):
        if not name.isdigit():
            continue
        if time.monotonic() - start >= max_seconds:
            coverage["time_limit"] += 1
            break
        base = os.path.join(proc, name)
        coverage["seen"] += 1
        candidates = []
        try:
            uid = os.stat(base).st_uid
        except (FileNotFoundError, ProcessLookupError):
            coverage["vanished"] += 1
            continue
        except PermissionError:
            coverage["denied"] += 1
            continue
        except OSError:
            coverage["errors"] += 1
            continue
        if protect_top_level:
            try:
                with open(base + "/cmdline", encoding="utf-8", errors="surrogateescape") as stream:
                    for arg in stream.read().split("\x00"):
                        target = arg if arg.startswith("/") else arg.partition("=")[2]
                        if target.startswith("/"):
                            target = os.path.normpath(target)
                            if contains(root, target) and os.path.lexists(target):
                                protect(target)
            except (FileNotFoundError, ProcessLookupError):
                pass
            except PermissionError:
                coverage["cmdline_denied"] += 1
            except OSError:
                coverage["cmdline_errors"] += 1
        outcomes = set()
        for kind in ("cwd", "exe", "fd", "maps"):
            path = base + "/" + kind
            try:
                if kind == "fd":
                    for fd in os.listdir(path):
                        descriptor = path + "/" + fd
                        try:
                            candidates.append(("fd", os.readlink(descriptor), descriptor))
                        except (FileNotFoundError, ProcessLookupError):
                            pass
                elif kind == "maps":
                    with open(path, encoding="utf-8", errors="surrogateescape") as stream:
                        for line in stream:
                            parts = line.split(None, 5)
                            if len(parts) == 6:
                                candidates.append(("map", parts[5].rstrip("\n"), None))
                else:
                    candidates.append((kind, os.readlink(path), None))
            except (FileNotFoundError, ProcessLookupError):
                if kind in ("fd", "maps"):
                    outcomes.add("vanished")
            except PermissionError:
                outcomes.add("denied")
            except OSError:
                outcomes.add("errors")
        if outcomes:
            coverage.update(outcomes)
        else:
            coverage["readable"] += 1
        for kind, target, fd_path in candidates:
            was_deleted = target.endswith(" (deleted)")
            target = target[:-10] if was_deleted else target
            if not contains(root, target):
                continue
            if protect_top_level:
                protect(target)
            if len(refs) < 200:
                refs.append(dict(pid=int(name), uid=uid, kind=kind,
                                 path=target, deleted=was_deleted))
            else:
                truncated = True
            if was_deleted and fd_path:
                try:
                    s = os.stat(fd_path)
                    identity = (s.st_dev, s.st_ino)
                    if s.st_nlink == 0 and s.st_dev == root_dev and identity not in identities:
                        identities.add(identity)
                        deleted.append(dict(pid=int(name), uid=uid,
                                            allocated_bytes=s.st_blocks * 512))
                except OSError:
                    coverage["fd_stat_failed"] += 1
    result = dict(state="partial" if truncated or any(coverage[k] for k in
                ("denied", "errors", "fd_stat_failed", "time_limit", "cmdline_denied",
                 "cmdline_errors")) else "readable-snapshot",
                coverage=dict(coverage), references=refs, references_truncated=truncated,
                deleted_open_files=deleted,
                deleted_open_allocated_bytes=sum(x["allocated_bytes"] for x in deleted),
                limitation="snapshot only; no match never proves unused; deleted mmap-only files may be absent")
    if protect_top_level:
        result["protected_top_level_paths"] = sorted(protected)
    return result


def configure_parser(parser):
    parser.add_argument("--path", default="/tmp")
    parser.add_argument("--filesystem", action="store_true", help="扫描 path 所在挂载点，跳过其子挂载")
    parser.add_argument("--keep-days", type=float, default=5)
    parser.add_argument("--age-basis", choices=("change", "usage"), default="change",
                        help="change 检查 mtime/ctime，usage 另检查普通文件 atime")
    parser.add_argument("--candidate-type", choices=("directory", "file", "both"),
                        help="输出完整顶层候选清单。候选模式自动检查可见进程引用")
    parser.add_argument("--candidate-uid", type=int, help="候选属主 UID，默认使用真实调用者的 UID")
    parser.add_argument("--max-entries", type=int, default=1000000)
    parser.add_argument("--max-seconds", type=float, default=120)
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--processes", action="store_true")
    parser.add_argument("--sudo", action="store_true",
                        help="显式使用 sudo -n 隔离运行只读扫描，不读取密码或自动降级")


def reference_identity():
    """Keep cleanup advice relative to the caller, rather than root."""
    uid = os.getuid()
    sudo_uid = os.environ.get("SUDO_UID", "")
    if os.geteuid() == 0 and sudo_uid.isdecimal():
        return int(sudo_uid), "sudo-readonly"
    return uid, "root-readonly" if os.geteuid() == 0 else "user-readonly"


def sudo_scan(args):
    # Fixed interpreter + isolated mode exclude PYTHONPATH, user site packages,
    # startup hooks and cwd imports. Only this metadata scanner runs as root.
    command = ["/usr/bin/sudo", "-n", "--", "/usr/bin/python3", "-I", "-S", "-B",
               str(Path(__file__).resolve()), "--path", args.path,
               "--keep-days", str(args.keep_days), "--max-entries", str(args.max_entries),
               "--max-seconds", str(args.max_seconds), "--top", str(args.top)]
    if args.filesystem:
        command.append("--filesystem")
    if args.processes:
        command.append("--processes")
    if args.age_basis != "change":
        command.extend(("--age-basis", args.age_basis))
    if args.candidate_type:
        command.extend(("--candidate-type", args.candidate_type))
    if args.candidate_uid is not None:
        command.extend(("--candidate-uid", str(args.candidate_uid)))
    try:
        completed = subprocess.run(command, capture_output=True, text=True)
    except OSError as exc:
        raise CodexAssetError(f"无法启动 sudo 只读扫描: {exc}") from exc
    try:
        report = json.loads(completed.stdout)
        valid = (completed.returncode in (0, 2) and report["schema_version"] == "disk-space-triage/v1"
                 and report["read_only"] is True and report["privilege"]["effective_uid"] == 0
                 and report["privilege"]["reference_uid"] == os.getuid())
    except (ValueError, KeyError, TypeError):
        valid = False
    if not valid:
        raise CodexAssetError("sudo 只读扫描未成功；未降级或请求密码。"
                              "若需要认证，请在自己的终端运行 sudo -v 后重试。 "
                              + completed.stderr.strip()[-500:])
    print(completed.stdout, end="")
    return completed.returncode


def run(args):
    if not sys.platform.startswith("linux"):
        raise CodexAssetError("disk-usage 仅支持 Linux；其他资产命令不受影响")
    if any(not math.isfinite(x) or x <= 0 for x in
           (args.keep_days, args.max_entries, args.max_seconds, args.top)):
        raise CodexAssetError("保留天数、扫描上限和 top 必须大于零")
    if args.candidate_uid is not None and (args.candidate_type is None or args.candidate_uid < 0):
        raise CodexAssetError("--candidate-uid 需要配合 --candidate-type 并指定非负 UID")
    if args.candidate_type and args.filesystem:
        raise CodexAssetError("候选清单需要显式目录作用域，不能与 --filesystem 同用")
    if args.sudo and os.geteuid() != 0:
        return sudo_scan(args)
    try:
        reference_uid, mode = reference_identity()
        requested = str(Path(args.path).resolve(strict=True))
        mounts = mount_points()
        mount = filesystem_root(requested, mounts)
        result = scan(mount if args.filesystem else requested, keep_days=args.keep_days,
                      max_entries=args.max_entries, max_seconds=args.max_seconds,
                      top=args.top, mounts=mounts, reference_uid=reference_uid,
                      age_basis=args.age_basis, candidate_type=args.candidate_type,
                      candidate_uid=args.candidate_uid)
        result["privilege"] = dict(mode=mode, effective_uid=os.geteuid(), reference_uid=reference_uid)
        result["requested_path"] = requested
        result["mount_point"] = mount
        result["mount"] = mount_identity(mount)
        if args.processes or args.candidate_type or args.age_basis == "usage":
            process = process_refs(result["root"], protect_top_level=bool(args.candidate_type))
            result["process_check"] = process
            for row in result["top_paths"]:
                if any(contains(row["path"], r["path"]) for r in process["references"]):
                    row["decision"] = "retain"
                    row["reasons"].append("process-reference")
            if args.candidate_type:
                selection = result["candidate_selection"]
                selection["process_coverage"] = process["state"]
                protected = set(process["protected_top_level_paths"])
                for item in selection["items"]:
                    if item["path"] in protected:
                        item["decision"] = "retain"
                        item["reasons"] = [r for r in item["reasons"] if r != "requires-review"]
                        item["reasons"].append("process-reference")
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0 if result["coverage"]["state"] == "visible-tree-complete" else 2
    except OSError as exc:
        raise CodexAssetError(f"磁盘分析失败: {exc}") from exc


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="disk-usage worker")
    configure_parser(parser)
    try:
        raise SystemExit(run(parser.parse_args()))
    except CodexAssetError as exc:
        print(f"[FATAL] {exc}", file=sys.stderr)
        raise SystemExit(2)
