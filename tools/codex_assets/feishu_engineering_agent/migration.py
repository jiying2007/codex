"""Single-consumer Bot migration preparation and disaster-recovery rehearsal.

Never starts/stops services, touches a running production DB for restore,
reads credential values into logs or creates an additional event consumer.
A host operator chooses when to call backup/rehearsal after service inspection.
"""
from __future__ import annotations

import contextlib
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


def _sqlite_check(path: pathlib.Path, *, immutable: bool = False) -> None:
    uri = path.as_uri() + "?mode=ro" + ("&immutable=1" if immutable else "")
    with contextlib.closing(sqlite3.connect(uri, uri=True, timeout=5)) as db:
        check = db.execute("PRAGMA quick_check").fetchone()
    if not check or check[0] != "ok":
        raise MigrationRejected("SQLite integrity check failed")


def _snapshot(source: pathlib.Path, destination: pathlib.Path) -> None:
    _private_file(source)
    with contextlib.closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=5)) as src:
        with contextlib.closing(sqlite3.connect(str(destination), timeout=5)) as dst:
            src.backup(dst)
            dst.commit()
    os.chmod(str(destination), 0o600)
    _sqlite_check(destination, immutable=True)


def _check_linked_ledgers(bot: pathlib.Path, agent: Optional[pathlib.Path]) -> int:
    """Verify backed-up Bot links against the corresponding AgentRun snapshot.

    This is an integrity check of a quiesced pair, not evidence that all
    uncertain remote effects completed. It never changes a Run status.
    """
    with contextlib.closing(sqlite3.connect(
            bot.as_uri() + "?mode=ro&immutable=1", uri=True, timeout=5)) as db:
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if agent is not None:
            db.execute("ATTACH DATABASE ? AS agent", (agent.as_uri() + "?mode=ro&immutable=1",))
            if db.execute("SELECT 1 FROM agent.sqlite_master WHERE type='table' AND name='fea_runs'").fetchone() is None:
                raise MigrationRejected("AgentRun backup lacks its run ledger")
        if "agent_run_task_links" not in tables:
            return 0
        count = db.execute("SELECT COUNT(*) FROM agent_run_task_links").fetchone()[0]
        if count and agent is None:
            raise MigrationRejected("linked WorkItems require the matching AgentRun database")
        if count:
            missing = db.execute(
                "SELECT 1 FROM agent_run_task_links l "
                "LEFT JOIN tasks t ON t.id=l.task_id "
                "LEFT JOIN agent.fea_runs r ON r.run_id=l.agent_run_id "
                "WHERE t.id IS NULL OR r.run_id IS NULL OR t.repository != r.repo "
                "OR t.sender_open_id != ('agent:' || l.unix_uid) "
                "OR t.mode != CASE r.mode WHEN 'read' THEN 'explain' ELSE r.mode END LIMIT 1"
            ).fetchone()
            if missing is not None:
                raise MigrationRejected("Bot/AgentRun snapshot linkage mismatch")
        return count


class MigrationPlan:
    """Snapshot Bot and sibling AgentRun state; prove restore in a disposable tree."""

    def __init__(
        self, bot_db: pathlib.Path, bot_spool: pathlib.Path,
        private_policy: Optional[pathlib.Path] = None,
        private_env: Optional[pathlib.Path] = None,
    ):
        self.bot_db = pathlib.Path(bot_db)
        self.bot_spool = pathlib.Path(bot_spool)
        self.private_policy = pathlib.Path(private_policy) if private_policy else None
        self.private_env = pathlib.Path(private_env) if private_env else None
        self.agent_db = self.bot_db.with_name("feishu-engineering-agent.sqlite3")
        for path in (self.bot_db, self.bot_spool):
            if not path.is_absolute():
                raise MigrationRejected("migration source must be explicit absolute path")
        if any(path is not None and not path.is_absolute()
               for path in (self.private_policy, self.private_env)):
            raise MigrationRejected("private policy/env must be explicit absolute paths")
        if self.bot_db.name == "feishu-engineering-agent.sqlite3":
            raise MigrationRejected("backup source must be the original Bot DB")

    def inspect(self) -> dict:
        _private_file(self.bot_db)
        info = {"database": self.bot_db.name, "spool_count": 0,
                "policy_present": self.private_policy is not None,
                "env_present": self.private_env is not None,
                "agent_ledger_present": self.agent_db.exists() or self.agent_db.is_symlink(),
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
        for private in (self.private_policy, self.private_env):
            if private is not None:
                _private_file(private)
        _sqlite_check(self.bot_db)
        if info["agent_ledger_present"]:
            _private_file(self.agent_db)
            _sqlite_check(self.agent_db)
        return info

    def backup(self, target_dir: pathlib.Path) -> dict:
        """One immutable private backup; operator should freeze the consumer first."""
        inspection = self.inspect()
        target = pathlib.Path(target_dir)
        if (not target.is_absolute() or target.exists() or target.is_symlink()
                or self.bot_spool.resolve() in target.resolve().parents):
            raise MigrationRejected("backup target must be a new absolute directory outside the spool")
        old_umask = os.umask(0o077)
        try:
            target.mkdir(mode=0o700, parents=False)
            (target / "spool").mkdir(mode=0o700)
            _snapshot(self.bot_db, target / "bot.sqlite3")
            files = {"bot.sqlite3": _digest(target / "bot.sqlite3")}
            agent_snapshot = None
            if inspection["agent_ledger_present"]:
                agent_snapshot = target / "feishu-engineering-agent.sqlite3"
                _snapshot(self.agent_db, agent_snapshot)
                files[agent_snapshot.name] = _digest(agent_snapshot)
            link_count = _check_linked_ledgers(target / "bot.sqlite3", agent_snapshot)
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
            for source, name in ((self.private_policy, "policy.private"),
                                 (self.private_env, "environment.private")):
                if source is None:
                    continue
                _private_file(source)
                destination = target / name
                with source.open("rb") as src, destination.open("xb") as dst:
                    shutil.copyfileobj(src, dst, length=65536)
                os.chmod(str(destination), 0o600)
                files[name] = _digest(destination)
            manifest = {
                "schema": 1, "created_at": int(time.time()),
                "source_db_name": self.bot_db.name,
                "spool_count": inspection["spool_count"], "files": files,
                "agent_ledger_present": agent_snapshot is not None,
                "linked_run_count": link_count,
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
                "agent_ledger_present": agent_snapshot is not None, "linked_run_count": link_count,
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
        agent_name = "feishu-engineering-agent.sqlite3"
        agent = path / agent_name if agent_name in expected_files else None
        _sqlite_check(path / "bot.sqlite3", immutable=True)
        if agent is not None:
            _sqlite_check(agent, immutable=True)
        link_count = _check_linked_ledgers(path / "bot.sqlite3", agent)
        if (manifest.get("agent_ledger_present", agent is not None) != (agent is not None)
                or manifest.get("linked_run_count", link_count) != link_count):
            raise MigrationRejected("backup ledger manifest mismatch")
        return {"valid": True, "spool_count": manifest["spool_count"],
                "file_count": len(expected_files),
                "agent_ledger_present": agent is not None, "linked_run_count": link_count}

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
            agent = base / "feishu-engineering-agent.sqlite3" if verified["agent_ledger_present"] else None
            _sqlite_check(base / "bot.sqlite3", immutable=True)
            if agent is not None:
                _sqlite_check(agent, immutable=True)
            if _check_linked_ledgers(base / "bot.sqlite3", agent) != verified["linked_run_count"]:
                raise MigrationRejected("restored ledger linkage differs")
        return {"restore_rehearsed": True,
                "source_was_not_modified": True, "verified_files": verified["file_count"],
                "agent_ledger_present": verified["agent_ledger_present"],
                "linked_run_count": verified["linked_run_count"]}

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
