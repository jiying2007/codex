"""Private, crash-safe queued-task payloads for the Feishu Codex service.

Only *queued* jobs are replayable. A process crash after 'running' always
requires operator reconciliation; this module never retries a model call.
Task text is held in 0600 local spool files, never in SQLite, logs, Git or
outbound diagnostics. Treat this directory as sensitive host data.
"""
from __future__ import annotations

import json
import os
import pathlib
import stat
import tempfile
from typing import Any, Mapping


class SpoolError(RuntimeError):
    pass


class TaskSpool:
    MAX_BYTES = 128 * 1024

    def __init__(self, root: pathlib.Path) -> None:
        self.root = root
        if root.is_symlink():
            raise SpoolError("queued-task directory must not be a symlink")
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = root.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise SpoolError("queued-task directory must be owned by the service and private (0700)")

    def _path(self, task_id: int) -> pathlib.Path:
        if not isinstance(task_id, int) or isinstance(task_id, bool) or task_id <= 0:
            raise SpoolError("invalid queued task ID")
        return self.root / f"{task_id}.json"

    def _sync_directory(self) -> None:
        descriptor = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def put(self, task_id: int, payload: Mapping[str, Any]) -> None:
        target = self._path(task_id)
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
        if not body or len(body) > self.MAX_BYTES:
            raise SpoolError("queued task payload exceeds the private spool limit")
        fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=self.root)
        try:
            with os.fdopen(fd, "wb") as stream:
                os.fchmod(stream.fileno(), 0o600)
                stream.write(body)
                stream.flush()
                os.fsync(stream.fileno())
            # Hard-link is exclusive: never overwrite an existing task payload.
            os.link(temporary, target, follow_symlinks=False)
            self._sync_directory()
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass

    def get(self, task_id: int) -> dict[str, Any]:
        path = self._path(task_id)
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            info = os.fstat(descriptor)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or info.st_nlink != 1 or info.st_mode & 0o077
                    or info.st_size > self.MAX_BYTES):
                raise SpoolError("untrusted queued task payload")
            with os.fdopen(descriptor, "rb", closefd=False) as stream:
                body = stream.read(self.MAX_BYTES + 1)
            if len(body) > self.MAX_BYTES:
                raise SpoolError("queued task payload exceeds limit")
            value = json.loads(body)
            if not isinstance(value, dict):
                raise SpoolError("invalid queued task payload")
            return value
        except (ValueError, UnicodeError) as exc:
            raise SpoolError("invalid queued task payload") from exc
        finally:
            os.close(descriptor)

    def discard(self, task_id: int) -> None:
        path = self._path(task_id)
        try:
            path.unlink()
            self._sync_directory()
        except FileNotFoundError:
            return

    def ids(self) -> list[int]:
        result = []
        for file in self.root.iterdir():
            if file.name.endswith(".json") and file.name[:-5].isdigit():
                result.append(int(file.name[:-5]))
        return result
