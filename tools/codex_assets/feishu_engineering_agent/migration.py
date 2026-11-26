"""Single-consumer Bot migration preparation and disaster-recovery rehearsal.

Never starts/stops services, touches a running production DB for restore,
reads credential values into logs or creates an additional event consumer.
A host operator chooses when to call backup/rehearsal after service inspection.
"""
from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import pathlib
import re
import shutil
import sqlite3
import stat
import tempfile
import time
from typing import Iterable, Optional

from .models import IntakeRejected


class MigrationRejected(IntakeRejected):
    pass


def _validate_path_parents(path: pathlib.Path) -> None:
    """Reject symlinked, missing, non-directory or writable parent components."""
    path = pathlib.Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise MigrationRejected("private path must be absolute and normalized")
    for parent in reversed(path.parents):
        try:
            info = parent.lstat()
        except OSError:
            raise MigrationRejected("private path parent is unavailable") from None
        if not stat.S_ISDIR(info.st_mode):
            raise MigrationRejected("private path parent must be a real directory")
        if info.st_mode & 0o022 and not info.st_mode & stat.S_ISVTX:
            raise MigrationRejected("private path parent must not be group/world writable")


def _private_file(file_path: pathlib.Path) -> None:
    _validate_path_parents(file_path)
    try:
        info = file_path.lstat()
    except FileNotFoundError:
        raise MigrationRejected("required private source file is missing") from None
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
            or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) & 0o077):
        raise MigrationRejected("source file must be owner-private regular file")


def _private_directory(path: pathlib.Path) -> None:
    _validate_path_parents(path)
    try:
        info = path.lstat()
    except OSError:
        raise MigrationRejected("required private directory is unavailable") from None
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) & 0o077):
        raise MigrationRejected("directory must be owner-private")


def _private_database(path: pathlib.Path) -> None:
    _private_file(path)
    for suffix in ("-wal", "-shm"):
        sidecar = path.with_name(path.name + suffix)
        if sidecar.exists() or sidecar.is_symlink():
            _private_file(sidecar)


def _database_present(path: pathlib.Path) -> bool:
    """Orphan WAL/SHM still represents state that must be reconciled."""
    return any(candidate.exists() or candidate.is_symlink() for candidate in (
        path, path.with_name(path.name + "-wal"), path.with_name(path.name + "-shm")))


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
    _private_database(path)
    uri = path.as_uri() + "?mode=ro" + ("&immutable=1" if immutable else "")
    with contextlib.closing(sqlite3.connect(uri, uri=True, timeout=5)) as db:
        check = db.execute("PRAGMA quick_check").fetchone()
    if not check or check[0] != "ok":
        raise MigrationRejected("SQLite integrity check failed")


def _snapshot(source: pathlib.Path, destination: pathlib.Path) -> None:
    _private_database(source)
    with contextlib.closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=5)) as src:
        with contextlib.closing(sqlite3.connect(str(destination), timeout=5)) as dst:
            src.backup(dst)
            dst.commit()
    os.chmod(str(destination), 0o600)
    _sqlite_check(destination, immutable=True)


def _unified(db) -> bool:
    exists=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='engineering_state_migrations'").fetchone()
    return bool(exists and db.execute(
        "SELECT 1 FROM engineering_state_migrations WHERE migration='unified-state-v1'").fetchone())


def ensure_engineering_migrated(bot_db: pathlib.Path) -> None:
    """Refuse legacy state before starting a new consumer; never open it writable."""
    path = pathlib.Path(bot_db)
    _validate_path_parents(path)
    legacy = path.with_name("feishu-engineering-agent.sqlite3")
    has_legacy = _database_present(legacy)
    if not path.exists() and not path.is_symlink():
        if _database_present(path):
            raise MigrationRejected("orphan Bot WAL/SHM requires recovery before startup")
        if has_legacy:
            raise MigrationRejected("legacy ledger requires offline backup, rehearsal and unify before startup")
        return
    _private_database(path)
    try:
        with contextlib.closing(sqlite3.connect(path.as_uri()+"?mode=ro", uri=True, timeout=5)) as db:
            if _unified(db):
                # A marker is valid only with its complete archive. A damaged
                # marker-only database must not silently drop old event dedup.
                recorded = db.execute("SELECT archived_runs,archived_records FROM engineering_state_migrations WHERE migration='unified-state-v1'").fetchone()
                actual = (db.execute("SELECT COUNT(*) FROM engineering_legacy_runs").fetchone()[0],
                          db.execute("SELECT COUNT(*) FROM engineering_legacy_records").fetchone()[0])
                db.execute("SELECT message_id FROM engineering_legacy_events LIMIT 1")
                if tuple(recorded) != actual:
                    raise MigrationRejected("Bot migration archive does not match its completion receipt")
                return
            links = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='agent_run_task_links'").fetchone()
            if has_legacy or (links and db.execute("SELECT 1 FROM agent_run_task_links LIMIT 1").fetchone()):
                raise MigrationRejected("legacy ledger requires offline backup, rehearsal and unify before startup")
    except sqlite3.Error:
        raise MigrationRejected("Bot migration state cannot be verified") from None


def _logical_digest(db) -> str:
    """Compare logical contents of quiesced live DB and the exact backup."""
    h=hashlib.sha256()
    for line in db.iterdump():
        h.update(line.encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def _check_linked_ledgers(bot: pathlib.Path, agent: Optional[pathlib.Path]) -> int:
    """Verify backed-up Bot links against the corresponding AgentRun snapshot.

    This is an integrity check of a quiesced pair, not evidence that all
    uncertain remote effects completed. It never changes a Run status.
    """
    with contextlib.closing(sqlite3.connect(
            bot.as_uri() + "?mode=ro&immutable=1", uri=True, timeout=5)) as db:
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        unified=_unified(db)
        if unified and agent is not None:
            raise MigrationRejected("unified production backup must not contain a live legacy ledger")
        if agent is not None:
            db.execute("ATTACH DATABASE ? AS agent", (agent.as_uri() + "?mode=ro&immutable=1",))
            if db.execute("SELECT 1 FROM agent.sqlite_master WHERE type='table' AND name='fea_runs'").fetchone() is None:
                raise MigrationRejected("AgentRun backup lacks its run ledger")
        if "agent_run_task_links" not in tables:
            return 0
        count = db.execute("SELECT COUNT(*) FROM agent_run_task_links").fetchone()[0]
        if count and agent is None and not unified:
            raise MigrationRejected("linked WorkItems require the matching AgentRun database")
        if count:
            run_table = "engineering_legacy_runs" if unified else "agent.fea_runs"
            missing = db.execute(
                "SELECT 1 FROM agent_run_task_links l "
                "LEFT JOIN tasks t ON t.id=l.task_id "
                "LEFT JOIN " + run_table + " r ON r.run_id=l.agent_run_id "
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
        for path in (self.bot_db, self.bot_spool, self.private_policy, self.private_env):
            if path is not None:
                _validate_path_parents(path)
        if self.bot_db.name == "feishu-engineering-agent.sqlite3":
            raise MigrationRejected("backup source must be the original Bot DB")

    def inspect(self) -> dict:
        _private_file(self.bot_db)
        info = {"database": self.bot_db.name, "spool_count": 0,
                "policy_present": self.private_policy is not None,
                "env_present": self.private_env is not None,
                "agent_ledger_present": _database_present(self.agent_db),
                "no_second_consumer_proven": False}
        _private_directory(self.bot_spool)
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
        with contextlib.closing(sqlite3.connect(self.bot_db.as_uri()+"?mode=ro",uri=True,timeout=5)) as db:
            info["unified_state"]=_unified(db)
        if info["unified_state"]:
            info["retired_ledger_present"]=info["agent_ledger_present"]
            info["agent_ledger_present"]=False
        elif info["agent_ledger_present"]:
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
        _private_directory(target.parent)
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
            if sum(name.startswith("spool/") for name in files) != inspection["spool_count"]:
                raise MigrationRejected("spool entry count changed during backup")
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
        _private_directory(path)
        manifest_file = path / "manifest.json"
        _private_file(manifest_file)
        with manifest_file.open(encoding="utf-8") as stream:
            manifest = json.load(stream)
        if (not isinstance(manifest, dict) or manifest.get("schema") != 1
                or not isinstance(manifest.get("files"), dict)
                or "bot.sqlite3" not in manifest["files"]):
            raise MigrationRejected("invalid backup manifest")
        expected_files = set(manifest["files"])
        # The writer produces only fixed root files and a flat private spool.
        # Do not silently ignore special files, unmanifested directories or
        # missing spool entries during a supposedly complete recovery rehearsal.
        spool = path / "spool"
        _private_directory(spool)
        root_names = {"manifest.json", "bot.sqlite3", "feishu-engineering-agent.sqlite3",
                      "policy.private", "environment.private"}
        observed_files = set()
        for item in path.iterdir():
            if item == spool:
                continue
            if item.name not in root_names:
                raise MigrationRejected("unexpected private backup entry")
            _private_file(item)
            observed_files.add(item.name)
            if item.name != "manifest.json":
                if item.name not in expected_files:
                    raise MigrationRejected("unmanifested private backup file")
                if _digest(item) != manifest["files"][item.name]:
                    raise MigrationRejected("backup checksum mismatch")
        spool_count = 0
        for item in spool.iterdir():
            _private_file(item)
            relative = "spool/" + item.name
            observed_files.add(relative)
            if relative not in expected_files:
                raise MigrationRejected("unmanifested private backup file")
            if _digest(item) != manifest["files"][relative]:
                raise MigrationRejected("backup checksum mismatch")
            spool_count += 1
            if spool_count > 10000:
                raise MigrationRejected("spool over safety bound")
        if observed_files != expected_files | {"manifest.json"}:
            raise MigrationRejected("missing backup entries")
        if type(manifest.get("spool_count")) is not int or manifest["spool_count"] != spool_count:
            raise MigrationRejected("backup spool count mismatch")
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
            # Exclude only the ROOT manifest, never a spool entry of that name.
            # Recreate the spool even if it is empty and prove the count restored.
            (base / "spool").mkdir(mode=0o700)
            originals = [p for p in backup.iterdir()
                         if p not in (backup / "manifest.json", backup / "spool")]
            originals.extend((backup / "spool").iterdir())
            if len(originals) != verified["file_count"]:
                raise MigrationRejected("backup entry count changed before restore")
            restored_spool_count = 0
            for original in originals:
                _private_file(original)
                relative = original.relative_to(backup)
                restored = base / relative
                shutil.copyfile(str(original), str(restored))
                restored.chmod(0o600)
                if _digest(restored) != _digest(original):
                    raise MigrationRejected("restore content mismatch")
                if original.parent == backup / "spool":
                    restored_spool_count += 1
            if restored_spool_count != verified["spool_count"]:
                raise MigrationRejected("restored spool count mismatch")
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

    def unify(self, backup_dir: pathlib.Path, lock_path: pathlib.Path) -> dict:
        """One-time, quiesced archive migration. No automatic legacy resume.

        The old ledger and paired backup are retained untouched. Historical
        run/evidence/session metadata is imported into the Bot DB, never
        interpreted as a new authorized conversation or native thread.
        """
        backup=pathlib.Path(backup_dir)
        lock_path=pathlib.Path(lock_path)
        if not lock_path.is_absolute():
            raise MigrationRejected("exact absolute service lock required")
        _private_file(lock_path)
        _private_database(self.bot_db)
        rehearsed=self.rehearse_restore(backup)
        if self.private_policy is None or not (backup/"policy.private").is_file():
            raise MigrationRejected("unify requires backed-up private policy")
        _private_file(self.private_policy)
        if _digest(self.private_policy)!=_digest(backup/"policy.private"):
            raise MigrationRejected("live policy differs from backup")
        if (self.private_env is not None) != (backup/"environment.private").is_file():
            raise MigrationRejected("unify must include the same backed-up private environment")
        environment = {}
        if self.private_env is not None:
            _private_file(self.private_env)
            if _digest(self.private_env)!=_digest(backup/"environment.private"):
                raise MigrationRejected("live environment differs from backup")
            from ..feishu_codex_bot import FeishuCodexError, load_env_file
            try:
                environment = load_env_file(self.private_env)
            except FeishuCodexError:
                raise MigrationRejected("private environment cannot be verified") from None
        policy=json.loads(self.private_policy.read_text(encoding="utf-8"))
        if (not isinstance(policy,dict) or not (policy.get("manual_workitems_enabled") is True
                                              or policy.get("engineering_enabled") is True)
                or policy.get("engineering_cards_enabled",False) is not False):
            raise MigrationRejected("enable engineering text intake and disable legacy cards before backup")
        # Do not mistake an arbitrary private lock for the service's lock.
        # Freeze explicit effective paths in the paired policy before backup;
        # an environment override must agree instead of silently changing them.
        for field, env_key, actual in (("lock_file", "FEISHU_LOCK_FILE", lock_path),
                                       ("state_db", "FEISHU_STATE_DB", self.bot_db)):
            configured = policy.get(field)
            if (not isinstance(configured, str) or not pathlib.Path(configured).is_absolute()
                    or pathlib.Path(configured).resolve() != actual.resolve()):
                raise MigrationRejected("migration target must match explicit private policy " + field)
            for values in (environment, os.environ):
                override = values.get(env_key)
                if override and (not pathlib.Path(override).is_absolute()
                                 or pathlib.Path(override).resolve() != actual.resolve()):
                    raise MigrationRejected("migration path conflicts with environment " + env_key)
        fd=os.open(str(lock_path),os.O_RDWR|os.O_NOFOLLOW|os.O_CLOEXEC)
        try:
            info=os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid()
                    or info.st_nlink!=1 or info.st_mode&0o077):
                raise MigrationRejected("unsafe singleton lock")
            try:
                fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:
                raise MigrationRejected("service singleton lock is held; freeze all writers first") from None
            with contextlib.ExitStack() as stack:
                db=stack.enter_context(contextlib.closing(sqlite3.connect(str(self.bot_db),timeout=5)))
                db.row_factory=sqlite3.Row
                db.execute("BEGIN IMMEDIATE")
                try:
                    if _unified(db):
                        raise MigrationRejected("legacy ledger already retired; never re-import")
                    source_bot=stack.enter_context(contextlib.closing(sqlite3.connect(
                        (backup/"bot.sqlite3").as_uri()+"?mode=ro&immutable=1",uri=True)))
                    if _logical_digest(db)!=_logical_digest(source_bot):
                        raise MigrationRejected("live Bot DB changed since paired backup")
                    if db.execute("SELECT 1 FROM tasks WHERE status IN ('queued','running','unknown') LIMIT 1").fetchone():
                        raise MigrationRejected("reconcile queued/running/UNKNOWN tasks before migration")
                    live_spool={p.name:_digest(p) for p in self.bot_spool.iterdir() if p.is_file() and not p.is_symlink()}
                    backup_spool={p.name:_digest(p) for p in (backup/"spool").iterdir() if p.is_file()}
                    if live_spool!=backup_spool or len(live_spool)!=len(list(self.bot_spool.iterdir())):
                        raise MigrationRejected("live spool differs from paired backup")
                    source=None
                    if rehearsed["agent_ledger_present"]:
                        _private_database(self.agent_db)
                        legacy_live=stack.enter_context(contextlib.closing(sqlite3.connect(str(self.agent_db),timeout=5)))
                        legacy_live.execute("BEGIN IMMEDIATE")
                        source=stack.enter_context(contextlib.closing(sqlite3.connect(
                            (backup/"feishu-engineering-agent.sqlite3").as_uri()+"?mode=ro&immutable=1",uri=True)))
                        source.row_factory=sqlite3.Row
                        if _logical_digest(legacy_live)!=_logical_digest(source):
                            raise MigrationRejected("live legacy ledger changed since paired backup")
                        if source.execute("SELECT 1 FROM fea_runs WHERE status NOT IN ('proposed','blocked','canceled','completed','failed') OR status IS NULL LIMIT 1").fetchone():
                            raise MigrationRejected("legacy execution/delivery remains unresolved; reconcile before migration")
                        publications = source.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='fea_publications'").fetchone()
                        if publications and source.execute("SELECT 1 FROM fea_publications WHERE effect_state != 'acknowledged' OR effect_state IS NULL LIMIT 1").fetchone():
                            raise MigrationRejected("legacy remote publication remains unresolved; reconcile before migration")
                    elif _database_present(self.agent_db):
                        raise MigrationRejected("legacy ledger appeared after backup")
                    # Do not use executescript: it would commit the current
                    # transaction before the archive and marker are durable.
                    db.execute("CREATE TABLE engineering_legacy_runs (run_id TEXT PRIMARY KEY,tenant TEXT NOT NULL,chat TEXT NOT NULL,actor TEXT NOT NULL,repo TEXT NOT NULL,mode TEXT NOT NULL,provider TEXT,workspace TEXT,kind TEXT,item_id TEXT,status TEXT NOT NULL)")
                    db.execute("CREATE TABLE engineering_legacy_records (table_name TEXT NOT NULL,ordinal INTEGER NOT NULL,payload_json TEXT NOT NULL,payload_sha256 TEXT NOT NULL,PRIMARY KEY(table_name,ordinal))")
                    db.execute("CREATE TABLE engineering_legacy_events (message_id TEXT PRIMARY KEY)")
                    db.execute("CREATE TABLE engineering_state_migrations (migration TEXT PRIMARY KEY,manifest_sha256 TEXT NOT NULL,archived_runs INTEGER NOT NULL,archived_records INTEGER NOT NULL,completed_at INTEGER NOT NULL)")
                    archived_runs=archived_records=0
                    if source is not None:
                        tables=[r[0] for r in source.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name") if not r[0].startswith("sqlite_")]
                        if "fea_runs" not in tables or any(not re.fullmatch(r"fea_[a-z0-9_]+",name) for name in tables):
                            raise MigrationRejected("unexpected legacy table; preserve backup for review")
                        fields="run_id,tenant,chat,actor,repo,mode,provider,workspace,kind,item_id,status"
                        for row in source.execute("SELECT "+fields+" FROM fea_runs"):
                            db.execute("INSERT INTO engineering_legacy_runs("+fields+") VALUES (?,?,?,?,?,?,?,?,?,?,?)",tuple(row))
                            archived_runs+=1
                        for name in tables:
                            for ordinal,row in enumerate(source.execute("SELECT * FROM "+name)):
                                payload=json.dumps(dict(row),sort_keys=True,ensure_ascii=False,separators=(",",":"))
                                db.execute("INSERT INTO engineering_legacy_records VALUES (?,?,?,?)",
                                           (name,ordinal,payload,hashlib.sha256(payload.encode("utf-8")).hexdigest()))
                                archived_records+=1
                                if archived_records>100000:
                                    raise MigrationRejected("legacy archive exceeds safety bound")
                        if "fea_manual_claims" in tables:
                            db.execute("CREATE INDEX engineering_legacy_runs_source ON engineering_legacy_runs(tenant,chat,actor,provider,workspace,kind,item_id)")
                            for row in source.execute("SELECT origin_message_id FROM fea_manual_claims"):
                                db.execute("INSERT OR IGNORE INTO engineering_legacy_events VALUES (?)",(row[0],))
                    if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='agent_run_task_links'").fetchone():
                        linked=db.execute("SELECT 1 FROM agent_run_task_links l LEFT JOIN engineering_legacy_runs r ON r.run_id=l.agent_run_id WHERE r.run_id IS NULL LIMIT 1").fetchone()
                        if linked is not None:
                            raise MigrationRejected("legacy linked task lost its archive record")
                    db.execute("INSERT INTO engineering_state_migrations VALUES ('unified-state-v1',?,?,?,?)",
                               (_digest(backup/"manifest.json"),archived_runs,archived_records,int(time.time())))
                    db.commit()
                except Exception:
                    db.rollback()
                    raise
            return {"unified_state":True,"archived_runs":archived_runs,
                    "archived_records":archived_records,"legacy_runtime_retired":True,
                    "old_ledger_retained":True,"restore_rehearsed":True,
                    "service_changed":False,"operator_freeze_required":True}
        finally:
            os.close(fd)

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
