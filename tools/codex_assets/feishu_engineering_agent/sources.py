"""Pure link normalization: a reference is never an API-read or authority receipt."""
from __future__ import annotations

import dataclasses
import re
from typing import Tuple
from urllib.parse import urlsplit, urlunsplit

from ..feishu_documents import DocumentReadError, parse_document_url
from .models import IntakeRejected

_URL = re.compile(r"https?://[^\s<>\x22，。；、！？）】]+", re.I)
_SPACE = r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}"
_ID = r"[1-9][0-9]{0,18}"
_PROJECT = re.compile(r"/(" + _SPACE + r")/(issue|story)/detail/(" + _ID + r")/?\Z")
_TAPD = re.compile(r"/(" + _ID + r")/(prong/stories|bugtrace/bugs)/view/(" + _ID + r")/?\Z")
_PROJECT_HOSTS = frozenset(("project.feishu.cn", "project.larksuite.com"))
_TAPD_HOSTS = frozenset(("tapd.cn", "www.tapd.cn"))
MAX_SOURCES = 16


@dataclasses.dataclass(frozen=True)
class EngineeringSource:
    provider: str
    space: str
    url_type: str
    kind: str
    item_id: str
    url: str

    @property
    def is_workitem(self):
        return self.provider in ("feishu_project", "tapd")

    @property
    def route_key(self):
        return self.provider + ":" + self.space


def candidate_urls(text: str) -> Tuple[str, ...]:
    """Recognize even malformed lookalikes, so they cannot fall through to a model."""
    out = []
    for match in _URL.finditer(text):
        url = match.group().rstrip(").,;!?]}")
        lowered = url.lower()
        if ("project.feishu.cn" in lowered or "project.larksuite.com" in lowered
                or "tapd.cn" in lowered
                or (".feishu.cn" in lowered and re.search(r"/(?:wiki|docx|sheets)(?:/|\Z)", lowered))):
            out.append(url)
    return tuple(out)


def parse_source(url: str) -> EngineeringSource:
    if len(url) > 1024 or any(ord(c) < 33 for c in url):
        raise IntakeRejected("invalid source link")
    try:
        p = urlsplit(url)
        if p.scheme != "https" or p.username is not None or p.password is not None or p.port is not None:
            raise ValueError()
        host = p.hostname or ""
        # Reject encoded/ambiguous paths and hostname aliases outside this allowlist.
        if "%" in p.path or "\\" in p.path or p.netloc.lower() != host:
            raise ValueError()
    except ValueError:
        raise IntakeRejected("invalid or unsafe source authority") from None
    if host in _PROJECT_HOSTS:
        match = _PROJECT.fullmatch(p.path)
        if match is None:
            raise IntakeRejected("unsupported Feishu Project work item URL")
        space, url_type, item = match.groups()
        if int(item) > 2**63 - 1:
            raise IntakeRejected("work item ID out of range")
        return EngineeringSource("feishu_project", space, url_type,
                                 "defect" if url_type == "issue" else "requirement",
                                 item, urlunsplit(("https", host, p.path.rstrip("/"), "", "")))
    if host in _TAPD_HOSTS:
        match = _TAPD.fullmatch(p.path)
        if match is None:
            raise IntakeRejected("unsupported TAPD work item URL")
        space, url_type, item = match.groups()
        if int(space) > 2**63 - 1 or int(item) > 2**63 - 1:
            raise IntakeRejected("TAPD ID out of range")
        # Common public TAPD URL forms; no live tenant API is asserted.
        return EngineeringSource("tapd", space, url_type,
                                 "defect" if url_type == "bugtrace/bugs" else "requirement",
                                 item, urlunsplit(("https", "www.tapd.cn", p.path.rstrip("/"), "", "")))
    if re.fullmatch(r"[a-z0-9-]+\.feishu\.cn", host):
        try:
            ref = parse_document_url(url)
        except DocumentReadError:
            raise IntakeRejected("invalid Feishu document link") from None
        return EngineeringSource("feishu_document", host, ref.kind, "document", ref.token, ref.url)
    raise IntakeRejected("source host not allowlisted")


def parse_sources(text: str) -> Tuple[EngineeringSource, ...]:
    urls = candidate_urls(text)
    if len(urls) > 32:
        raise IntakeRejected("too many source references")
    result = tuple(dict.fromkeys(parse_source(url) for url in urls))
    if len(result) > MAX_SOURCES:
        raise IntakeRejected("too many distinct source references")
    # The provider/space/type/id remain link-derived (unverified).
    workitems = {(s.provider, s.space, s.url_type, s.item_id, s.url)
                 for s in result if s.is_workitem}
    if len(workitems) > 1:
        raise IntakeRejected("multiple primary work items; use separate topics")
    return result
