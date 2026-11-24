"""Frozen synthetic SQLite history; migration tests never revive retired code."""
import contextlib
import os
import pathlib
import sqlite3


def create_legacy_ledger(path: pathlib.Path) -> pathlib.Path:
    descriptor = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    with contextlib.closing(sqlite3.connect(str(path))) as db:
        db.executescript("""
            CREATE TABLE fea_runs (
                run_id TEXT PRIMARY KEY,
                tenant TEXT NOT NULL, chat TEXT NOT NULL, actor TEXT NOT NULL,
                repo TEXT NOT NULL, mode TEXT NOT NULL,
                provider TEXT, workspace TEXT, kind TEXT, item_id TEXT,
                workitem_fp TEXT, status TEXT NOT NULL,
                revision INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
            );
            CREATE TABLE fea_manual_claims (
                event_key TEXT PRIMARY KEY, content_sha256 TEXT NOT NULL,
                run_id TEXT NOT NULL UNIQUE REFERENCES fea_runs(run_id),
                origin_message_id TEXT NOT NULL, summary_sha256 TEXT NOT NULL,
                source_level TEXT NOT NULL CHECK(source_level='user_supplied_unverified'),
                created_at INTEGER NOT NULL
            );
            INSERT INTO fea_runs VALUES (
                'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'tenant', 'oc_chat', 'ou_owner',
                'robot', 'read', 'feishu_project', 'example-space', 'defect',
                '1000000001', 'synthetic-fingerprint', 'proposed', 0, 1, 1
            );
            INSERT INTO fea_manual_claims VALUES (
                'synthetic-event', 'synthetic-content', 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
                'om_legacy', 'synthetic-summary', 'user_supplied_unverified', 1
            );
        """)
        db.commit()
    return path
