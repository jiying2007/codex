"""Side-effect-free identity and decision types for Feishu Engineering Agent V2."""
from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from typing import Optional, Tuple


class IntakeRejected(ValueError):
    """Invalid or ambiguous input; callers must never fall back to model execution."""


class EventConflict(IntakeRejected):
    """The same provider event identity was reused for different input."""


_IDENTIFIER = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
_REPO_ALIAS = re.compile(r"\A[a-z][a-z0-9_-]{0,31}\Z")


def _check_id(value: str, name: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise IntakeRejected(name + " must be a bounded identifier")
    return value


def check_repo_alias(value: str) -> str:
    if not isinstance(value, str) or not _REPO_ALIAS.fullmatch(value):
        raise IntakeRejected("invalid repository alias")
    return value


@dataclasses.dataclass(frozen=True)
class WorkItemKey:
    """External provider is authoritative; ID alone cannot identify an item."""

    provider: str
    tenant: str
    workspace: str
    kind: str
    item_id: str

    def __post_init__(self) -> None:
        if self.provider not in ("feishu_project", "tapd"):
            raise IntakeRejected("unsupported workitem provider")
        if self.kind not in ("requirement", "defect"):
            raise IntakeRejected("unsupported workitem kind")
        for name in ("tenant", "workspace", "item_id"):
            _check_id(getattr(self, name), name)

    @property
    def identity(self) -> Tuple[str, str, str, str, str]:
        return (self.provider, self.tenant, self.workspace, self.kind, self.item_id)

    @property
    def fingerprint(self) -> str:
        payload = json.dumps(self.identity, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclasses.dataclass(frozen=True)
class InboundEvent:
    """Already authenticated by a future channel adapter, not this pure core."""

    source: str
    tenant: str
    chat: str
    actor: str
    event_id: str
    text: str

    def __post_init__(self) -> None:
        if self.source not in ("feishu_message", "offline_fixture"):
            raise IntakeRejected("unsupported intake source")
        for name in ("tenant", "chat", "actor", "event_id"):
            _check_id(getattr(self, name), name)
        if (not isinstance(self.text, str) or not self.text.strip()
                or len(self.text) > 12000 or "\x00" in self.text):
            raise IntakeRejected("message text must be nonempty and bounded")

    @property
    def scope(self) -> Tuple[str, str, str, str]:
        return (self.source, self.tenant, self.chat, self.actor)

    @property
    def event_key(self) -> str:
        wire_identity = json.dumps(
            self.scope + (self.event_id,), separators=(",", ":"), ensure_ascii=True,
        )
        return hashlib.sha256(wire_identity.encode("utf-8")).hexdigest()

    @property
    def content_digest(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()


@dataclasses.dataclass(frozen=True)
class Decision:
    """A proposal, never a Codex launch, external ticket update or write approval."""

    kind: str
    repo: str = ""
    task_id: Optional[int] = None
    requires_approval: bool = False
    reason: str = ""
    replayed: bool = False
    run_enqueued: bool = False

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "repo": self.repo,
            "task_id": self.task_id,
            "requires_approval": self.requires_approval,
            "reason": self.reason,
            "replayed": self.replayed,
            "run_enqueued": False,
        }
