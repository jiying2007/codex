"""Single-consumer Bot migration preparation and disaster-recovery rehearsal.

Never starts/stops services, touches a running production DB for restore,
reads credential values into logs or creates an additional event consumer.
A host operator chooses when to call backup/rehearsal after service inspection.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import shutil
import sqlite3
import stat
import tempfile
import time
from typing import Iterable, Optional

from .models import IntakeRejected


class MigrationRejected(IntakeRejected):
    pass


def _private_file(file_path: pathlib.Path) -> None:
    if (file_path.is_symlink() or not file_path.is_file()
            or file_path.stat().st_uid != os.getuid()
            or (stat.S_IMODE(file_path.stat().st_mode) & 0o077)):
        raise MigrationRejected("source file must be owner-private regular file")


def _digest(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


class MigrationPlan:
    """Snapshot legacy state (WAL-aware) and prove restore in a disposable tree."""

    def __init__(
        self, bot_db: pathlib.Path, bot_spool: pathlib.Path,
        private_policy: Optional[pathlib.Path] = None,
    ):
        self.bot_db = pathlib.Path(bot_db)
        self.bot_spool = pathlib.Path(bot_spool)
        self.private_policy = pathlib.Path(private_policy) if private_policy else None
        for path in (self.bot_db, self.bot_spool):
            if not path.is_absolute():
                raise MigrationRejected("migration source must be explicit absolute path")
        if self.private_policy is not None and not self.private_policy.is_absolute():
            raise MigrationRejected("policy must be explicit absolute path")
        if self.bot_db.name == "feishu-engineering-agent.sqlite3":
            raise MigrationRejected("backup source must be the original Bot DB")

    def inspect(self) -> dict:
        _private_file(self.bot_db)
        info = {"database": self.bot_db.name, "spool_count": 0,
                "policy_present": self.private_policy is not None,
                "no_second_consumer_proven": False}
        if not self.bot_spool.is_dir() or self.bot_spool.is_symlink():
            raise MigrationRejected("legacy spool must be an existing directory")
        if (self.bot_spool.stat().st_uid != os.getuid()
                or (stat.S_IMODE(self.bot_spool.stat().st_mode) & 0o077)):
            raise MigrationRejected("spool directory must be owner-private")
        for entry in self.bot_spool.iterdir():
            if not entry.is_file() or entry.is_symlink():
                raise MigrationRejected("unsafe legacy spool entry")
            _private_file(entry)
            info["spool_count"] += 1
            if info["spool_count"] > 10000:
                raise MigrationRejected("spool over safety bound")
        if self.private_policy is not None:
            _private_file(self.private_policy)
        with sqlite3.connect(str(self.bot_db), timeout=3) as db:
            check = db.execute("PRAGMA quick_check").fetchone()
        if not check or check[0] != "ok":
            raise MigrationRejected("legacy SQLite is not healthy")
        return info

    def backup(self, target_dir: pathlib.Path) -> dict:
        """One immutable private backup; operator should freeze the consumer first."""
        inspection = self.inspect()
        target = pathlib.Path(target_dir)
        if not target.is_absolute() or target.exists() or target.is_symlink():
            raise MigrationRejected("backup target must be a new absolute directory")
        old_umask = os.umask(0o077)
        try:
            target.mkdir(mode=0o700, parents=False)
            (target / "spool").mkdir(mode=0o700)
            with sqlite3.connect(str(self.bot_db), timeout=5) as source:
                with sqlite3.connect(str(target / "bot.sqlite3"), timeout=5) as copy:
                    source.backup(copy)
            os.chmod(str(target / "bot.sqlite3"), 0o600)
            files = {"bot.sqlite3": _digest(target / "bot.sqlite3")}
            for entry in self.bot_spool.iterdir():
                _private_file(entry)
                name = entry.name
                if name in (".", "..") or "/" in name:
                    raise MigrationRejected("invalid spool entry name")
                destination = target / "spool" / name
                with entry.open("rb") as src, destination.open("xb") as dst:
                    shutil.copyfileobj(src, dst, length=65536)
                os.chmod(str(destination), 0o600)
                files["spool/" + name] = _digest(destination)
            if self.private_policy is not None:
                with self.private_policy.open("rb") as src, (
                    target / "policy.private"
                ).open("xb") as dst:
                    shutil.copyfileobj(src, dst, length=65536)
                os.chmod(str(target / "policy.private"), 0o600)
                files["policy.private"] = _digest(target / "policy.private")
            manifest = {
                "schema": 1, "created_at": int(time.time()),
                "source_db_name": self.bot_db.name,
                "spool_count": inspection["spool_count"], "files": files,
                "service_stopped_proven": False, "restore_rehearsed": False,
            }
            with (target / "manifest.json").open("x", encoding="utf-8") as output:
                json.dump(manifest, output, sort_keys=True)
            os.chmod(str(target / "manifest.json"), 0o600)
        except Exception:
            # Retain partial private backup for operator investigation. Never
            # delete it automatically or touch original state on failure.
            raise
        finally:
            os.umask(old_umask)
        return {"backup_dir": str(target), "spool_count": inspection["spool_count"],
                "manifest_sha256": _digest(target / "manifest.json"),
                "restored": False}

    @staticmethod
    def verify_backup(backup_dir: pathlib.Path) -> dict:
        path = pathlib.Path(backup_dir)
        if not path.is_absolute() or path.is_symlink() or not path.is_dir():
            raise MigrationRejected("invalid private backup directory")
        if (path.stat().st_uid != os.getuid()
                or stat.S_IMODE(path.stat().st_mode) & 0o077):
            raise MigrationRejected("backup directory not owner-private")
        manifest_file = path / "manifest.json"
        _private_file(manifest_file)
        with manifest_file.open(encoding="utf-8") as stream:
            manifest = json.load(stream)
        if (not isinstance(manifest, dict) or manifest.get("schema") != 1
                or not isinstance(manifest.get("files"), dict)
                or "bot.sqlite3" not in manifest["files"]):
            raise MigrationRejected("invalid backup manifest")
        expected_files = set(manifest["files"])
        observed_files = set()
        for item in path.rglob("*"):
            if item.is_symlink():
                raise MigrationRejected("symlink in immutable backup")
            if item.is_file():
                _private_file(item)
                relative = item.relative_to(path).as_posix()
                observed_files.add(relative)
                if relative == "manifest.json":
                    continue
                if relative not in expected_files:
                    raise MigrationRejected("unmanifested private backup file")
                if _digest(item) != manifest["files"][relative]:
                    raise MigrationRejected("backup checksum mismatch")
        if observed_files != expected_files | {"manifest.json"}:
            raise MigrationRejected("missing backup entries")
        with sqlite3.connect(str(path / "bot.sqlite3")) as db:
            check = db.execute("PRAGMA quick_check").fetchone()
        if not check or check[0] != "ok":
            raise MigrationRejected("snapshot DB integrity failed")
        return {"valid": True, "spool_count": manifest["spool_count"],
                "file_count": len(expected_files)}

    @classmethod
    def rehearse_restore(cls, backup_dir: pathlib.Path) -> dict:
        """Restore to a NEW temp directory, never to a running Bot path."""
        verified = cls.verify_backup(backup_dir)
        with tempfile.TemporaryDirectory(prefix="fea-rehearsal-") as destination:
            base = pathlib.Path(destination)
            backup = pathlib.Path(backup_dir)
            for original in backup.rglob("*"):
                if not original.is_file() or original.name == "manifest.json":
                    continue
                relative = original.relative_to(backup)
                restored = base / relative
                restored.parent.mkdir(exist_ok=True, parents=True)
                shutil.copyfile(str(original), str(restored))
                if _digest(restored) != _digest(original):
                    raise MigrationRejected("restore content mismatch")
            with sqlite3.connect(str(base / "bot.sqlite3")) as db:
                check = db.execute("PRAGMA quick_check").fetchone()
            if not check or check[0] != "ok":
                raise MigrationRejected("rehearsal DB invalid")
        return {"restore_rehearsed": True,
                "source_was_not_modified": True, "verified_files": verified["file_count"]}

    @staticmethod
    def cutover_gate(
        backup_verified: bool, restore_rehearsed: bool,
        old_consumer_stopped: bool, singleton_lock_acquired: bool,
        callbacks_qualified: bool, runtime_qualified: bool,
    ) -> dict:
        """A decision only. Does NOT stop/start services or approve model usage."""
        conditions = {
            "backup_verified": backup_verified,
            "restore_rehearsed": restore_rehearsed,
            "old_consumer_stopped": old_consumer_stopped,
            "singleton_lock_acquired": singleton_lock_acquired,
            "callbacks_qualified": callbacks_qualified,
            "runtime_qualified": runtime_qualified,
        }
        if any(type(x) is not bool for x in conditions.values()):
            raise MigrationRejected("cutover evidence fields must be booleans")
        return {"can_cutover": all(conditions.values()),
                "missing": [k for k, passed in conditions.items() if not passed],
                "service_changed": False, "consumer_started": False}
