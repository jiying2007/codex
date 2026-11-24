"""Canonical operator policy snapshot shared by remote and local intake."""
from __future__ import annotations

import hashlib
import json
from typing import Iterable

from .models import check_repo_alias


def local_agent_policy_digest(
    unix_uid: int, repo: str, mode: str, billing_source: str,
    agent_allowed_modes: Iterable[str], edit_strategy: str,
    commit_enabled: bool, *, repo_path: str = "", base_ref: str = "",
    worktree_root: str = "", branch_prefix: str = "",
    allowed_modes: Iterable[str] = (),
    verification_commands: Iterable[Iterable[str]] = (),
    agent_codex_home: str = "", openai_base_url: str = "",
    credential_fingerprint: str = "", codex_bin: str = "",
    isolation_bin: str = "", deny_push_hooks_path: str = "",
    deny_read_paths: Iterable[str] = (),
    isolation_write_paths: Iterable[str] = (),
    codex_timeout_sec: int = 0, max_prompt_chars: int = 0,
    budget_policy: Iterable[str] = (),
) -> str:
    """Canonical digest of the operator-controlled execution policy."""
    payload = {
        "unix_uid": int(unix_uid),
        "repo": check_repo_alias(repo),
        "mode": mode,
        "billing_source": billing_source,
        "repo_path": repo_path,
        "base_ref": base_ref,
        "worktree_root": worktree_root,
        "branch_prefix": branch_prefix,
        "allowed_modes": sorted(set(allowed_modes)),
        "agent_allowed_modes": sorted(set(agent_allowed_modes)),
        "edit_strategy": edit_strategy,
        "commit_enabled": bool(commit_enabled),
        "verification_commands": [list(command) for command in verification_commands],
        "agent_codex_home": str(agent_codex_home),
        "openai_base_url": str(openai_base_url),
        "credential_fingerprint": str(credential_fingerprint),
        "codex_bin": str(codex_bin),
        "isolation_bin": str(isolation_bin),
        "deny_push_hooks_path": str(deny_push_hooks_path),
        "deny_read_paths": sorted(str(path) for path in deny_read_paths),
        "isolation_write_paths": sorted(str(path) for path in isolation_write_paths),
        "codex_timeout_sec": int(codex_timeout_sec),
        "max_prompt_chars": int(max_prompt_chars),
        "budget_policy": list(budget_policy),
    }
    return hashlib.sha256(json.dumps(
        payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
