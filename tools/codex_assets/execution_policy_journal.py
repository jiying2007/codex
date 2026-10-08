"""Serialized host journal validation and narrowly scoped, evidence-preserving recovery."""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path


@contextlib.contextmanager
def journal_lock(path):
    from .execution_policy_adapter import ExecutionPolicyAdapterError

    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path.with_suffix('.intake.lock')),
                 os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ExecutionPolicyAdapterError('journal lock must be a regular file')
        os.fchmod(fd, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def validated_append(path, event, thread):
    from . import execution_policy_adapter as adapter

    with journal_lock(path):
        events = adapter.load_journal(path)
        state = adapter._engine_state(events + [event, adapter.usage_event(thread)])
        adapter.append_journal(path, event)
        return state


def start_goal(path, args, thread):
    from . import execution_policy_adapter as adapter

    with journal_lock(path):
        existing = adapter.load_journal(path)
        now = adapter._now()
        event = adapter.control_event('goal.started', thread['thread_id'], {
            'goal_id':args.goal_id, 'token_budget':args.token_budget,
            'time_budget_seconds':args.time_budget_seconds,
            'usage_baseline_tokens':adapter.usage_event(thread)['payload']['total_tokens'],
            'success_criteria':args.success_criterion, 'required_evidence':args.required_evidence,
            'open_items_count':args.open_items, 'intake':adapter._goal_intake(args, now),
        })
        state = adapter._engine_state(existing + [event, adapter.usage_event(thread)])
        if existing:
            adapter.append_journal(path, event)
        else:
            adapter._write_new_journal(path, event)
        return state


def _atomic_bytes(path, content):
    with tempfile.NamedTemporaryFile(dir=str(path.parent), delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.chmod(temporary, 0o600)
        os.replace(str(temporary), str(path))
        fd = os.open(str(path.parent), os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        temporary.unlink(missing_ok=True)


def recover(path, thread, *, expected_sha256='', apply=False):
    from . import execution_policy_adapter as adapter

    current = os.environ.get('CODEX_THREAD_ID', '')
    if current and current != thread['thread_id']:
        raise adapter.ExecutionPolicyAdapterError('journal recovery requires the current thread')
    with journal_lock(path):
        fd = os.open(str(path), os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_size > 16 * 1024 * 1024:
                raise adapter.ExecutionPolicyAdapterError('journal must be a bounded regular file')
            with os.fdopen(fd, 'rb', closefd=False) as stream:
                original = stream.read(16 * 1024 * 1024 + 1)
        finally:
            os.close(fd)
        before = hashlib.sha256(original).hexdigest()
        if apply and expected_sha256 != before:
            raise adapter.ExecutionPolicyAdapterError('journal recovery requires exact expected SHA256')
        kept, lines, rejected = [], [], []
        for line in original.splitlines(keepends=True):
            if not line.strip():
                lines.append(line)
                continue
            try:
                event = json.loads(line)
                if event.get('thread_id') != thread['thread_id']:
                    raise adapter.ExecutionPolicyAdapterError('journal thread mismatch')
                adapter._engine_state(kept + [event])
            except adapter.ExecutionPolicyAdapterError as exc:
                if (str(exc) != 'progress revision must increase'
                        or event.get('event_type') != 'progress.advanced'):
                    raise adapter.ExecutionPolicyAdapterError('journal cannot be recovered by duplicate-progress policy') from exc
                rejected.append({'event_id':event['event_id'], 'sha256':hashlib.sha256(line).hexdigest(),
                                 'reason_code':'rejected-nonincreasing-progress'})
                continue
            except (ValueError, AttributeError) as exc:
                raise adapter.ExecutionPolicyAdapterError('journal recovery refuses malformed events') from exc
            kept.append(event)
            lines.append(line)
        state = adapter._engine_state(kept + [adapter.usage_event(thread)])
        replacement = b''.join(lines)
        result = {'schema_version':'codex-journal-recovery/v1', 'status':'PLANNED',
                  'read_only':not apply, 'write_performed':False, 'before_sha256':before,
                  'after_sha256':hashlib.sha256(replacement).hexdigest(),
                  'rejected_events':rejected, 'rejected_count':len(rejected),
                  'goal_id':state['goal'].get('goal_id'), 'goal_status':state['goal']['status'],
                  'policy':'duplicate-progress-only', 'original_preserved':False}
        if apply and rejected:
            backup = path.with_name(path.name + '.recovery-' + before + '.original')
            if backup.exists() or backup.is_symlink():
                if backup.is_symlink() or backup.read_bytes() != original:
                    raise adapter.ExecutionPolicyAdapterError('journal recovery backup conflict')
            else:
                _atomic_bytes(backup, original)
            _atomic_bytes(path, replacement)
            adapter._engine_state(adapter.load_journal(path))
            if path.read_bytes() != replacement or backup.read_bytes() != original:
                raise adapter.ExecutionPolicyAdapterError('journal recovery readback failed')
            result.update(status='RECOVERED', write_performed=True, original_preserved=True,
                          backup_name=backup.name)
            receipt = path.with_name(path.name + '.recovery-' + before + '.receipt.json')
            _atomic_bytes(receipt, (json.dumps(result, sort_keys=True) + '\n').encode())
        elif apply:
            result['status'] = 'ALREADY_VALID'
        return result
