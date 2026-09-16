"""Stdlib-only privacy validation used by vendored runtime execution-policy contracts."""

from __future__ import annotations

import re
from typing import Any, Iterator, Mapping, Optional, Tuple

from .model import ManifestError


_FORBIDDEN_KEYS = frozenset({
    "prompt", "prompts", "raw_prompt", "system_prompt", "message", "messages",
    "raw_message", "input_message", "input_messages", "output_message", "output_messages",
    "password", "passwords", "credential", "credentials", "secret", "secrets", "api_key",
    "access_token", "private_key", "raw_log", "tool_payload", "tool_arguments", "tool_result",
    "tool_results",
})
_SECRET_VALUE_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----", re.IGNORECASE),
    re.compile(r"\bghp_[A-Za-z0-9]{16,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{16,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{10,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{8,}=*\b", re.IGNORECASE),
    re.compile(r"\b(?:password|secret|credential|api[_ -]?key)\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"\b(?:raw[ _.-]?prompt|raw[ _.-]?message|tool[ _.-]?payload)\b", re.IGNORECASE),
)


def _walk(value: Any, path: Tuple[str, ...] = ()) -> Iterator[Tuple[Tuple[str, ...], Optional[str], Any]]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = path + (str(key),)
            yield child_path, str(key), child
            yield from _walk(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            child_path = path + (str(index),)
            yield child_path, None, child
            yield from _walk(child, child_path)


def validate_no_secrets(value: Any, label: str) -> None:
    for path, key, child in _walk(value):
        normalized = str(key).casefold().replace(".", "_").replace("-", "_") if key is not None else ""
        if normalized in _FORBIDDEN_KEYS:
            raise ManifestError("{} contains forbidden sensitive field at {}".format(label, "/".join(path)))
        if isinstance(child, str) and any(pattern.search(child) for pattern in _SECRET_VALUE_PATTERNS):
            raise ManifestError("{} contains secret-like content at {}".format(label, "/".join(path)))
    if isinstance(value, str) and any(pattern.search(value) for pattern in _SECRET_VALUE_PATTERNS):
        raise ManifestError("{} contains secret-like content".format(label))
