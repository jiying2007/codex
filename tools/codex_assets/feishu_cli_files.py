"""Bounded text representations of Drive files; the official CLI owns transport."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from .feishu_cli_errors import ReadError
from .feishu_cli_coverage import coverage_receipt

MAX_FILE_BYTES = 4 * 1024 * 1024


def decode_text(raw: bytes) -> str:
    if raw.startswith((b"%PDF-", b"PK\x03\x04", b"PK\x05\x06", b"\x89PNG", b"\xff\xd8\xff",
                       b"GIF87a", b"GIF89a", b"\x7fELF", b"\x1f\x8b", b"7z\xbc\xaf\x27\x1c")):
        raise ReadError("unsupported_file_encoding", "文件签名表明它不是纯文本；需可用的 text 预览或专用解析器")
    try:
        if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
            text = raw.decode("utf-16")
        else:
            text = raw.decode("utf-8-sig")
    except UnicodeError:
        raise ReadError("unsupported_file_encoding", "原文件不是受支持的 UTF-8/带 BOM UTF-16 文本；可查询文本预览") from None
    if any(ord(char) < 32 and char not in "\n\r\t\f" for char in text):
        raise ReadError("unsupported_file_encoding", "文件包含二进制控制字符；不能当作完整文本读取")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def source_preview_allowed(error: ReadError) -> bool:
    """A typed denial or missing download scope allows the same-bot source preview."""
    def denied(value: Any) -> bool:
        if isinstance(value, dict):
            for key in ("kind", "type", "code", "status", "status_code", "http_status"):
                if str(value.get(key, "")).lower() in ("403", "permission_denied", "access_denied"):
                    return True
            return any(denied(item) for item in value.values())
        if isinstance(value, list):
            return any(denied(item) for item in value)
        return False
    return error.kind in ("application_scope_missing", "access_denied") or (error.kind == "backend_error" and denied(error.details))


def representation(backend, token: str, mode: str):
    if mode != "auto":
        raw = backend.download(token, mode)
        return raw, mode, []
    fallbacks = []
    try:
        raw = backend.download(token, "download")
        selected = "download"
    except ReadError as error:
        if not source_preview_allowed(error):
            raise
        fallbacks.append(error.kind)
        raw = backend.download(token, "source-preview")
        selected = "source-preview"
    try:
        decode_text(raw)
        return raw, selected, fallbacks
    except ReadError as error:
        if error.kind != "unsupported_file_encoding":
            raise
    candidates = backend.read("drive/+preview", ["--file-token", token, "--list-only"])
    rows = candidates.get("candidates")
    if not isinstance(rows, list):
        raise ReadError("invalid_response", "预览列表缺少 candidates，不能猜测预览类型")
    if not any(isinstance(row, dict) and row.get("type") == "text"
               and row.get("downloadable") is True for row in rows):
        if any(isinstance(row, dict) and row.get("type") == "text" and row.get("status") in ("PROCESSING", "PENDING") for row in rows):
            raise ReadError("preview_pending", "文本预览尚在生成；稍后查询候选项，不立即循环下载")
        raise ReadError("unsupported_file_encoding", "原文件不是支持的文本且没有可下载的 text 预览；PDF/Office/OCR 尚未接入")
    return backend.download(token, "text-preview"), "text-preview", fallbacks + ["binary_source"]


def file_metadata(source: Mapping[str, Any], title: str, args):
    if args.expected_revision or args.revision_id > 0 or args.expected_content_sha256:
        raise ReadError("invalid_input", "inspect 不读取文件正文，不能校验文件哈希或原生文档版本；请 read/catalog")
    data = {"resource_type": "file", "title": title[:500], "content_read_supported": True,
            "content_read": False, "supported_representations": ["download", "source-preview", "text-preview"],
            "max_file_bytes": MAX_FILE_BYTES,
            "next_action": "read 默认下载并读取文本；二进制文件仅在有可用 text 预览时读取预览"}
    coverage = {"status": "metadata-only", "whole_resource_complete": False, "content_read": False,
                "revision": None, "revision_check": "unavailable"}
    return {"ok": True, "identity": "bot", "source": dict(source), "data": data, "coverage": coverage,
            "receipt": coverage_receipt(source, coverage, None)}


def read_file(backend, source: Mapping[str, Any], title: str, args):
    if args.expected_revision or args.revision_id > 0:
        raise ReadError("invalid_input", "文件读取不支持 docx revision；请用 --expected-content-sha256 绑定同一内容")
    raw, selected, fallbacks = representation(backend, source["token"], args.file_mode)
    if len(raw) > MAX_FILE_BYTES:
        raise ReadError("file_too_large", "文件超过 4 MiB 上限，不能输出局部下载作为完整内容")
    sha = hashlib.sha256(raw).hexdigest()
    if args.expected_content_sha256 and args.expected_content_sha256 != sha:
        raise ReadError("content_mismatch", "文件表示内容变化；本段不得并入原覆盖记录",
                        {"expected_sha256": args.expected_content_sha256, "actual_sha256": sha,
                         "representation": selected})
    text = decode_text(raw)
    # Login/error HTML is not the requested Markdown/text file. HTML source
    # files remain readable as source; it is never executed or rendered here.
    head = text.lstrip()[:512].lower()
    if selected != "text-preview" and not title.lower().endswith((".html", ".htm")) and (
            head.startswith("<!doctype html") or head.startswith("<html")):
        if not title:
            raise ReadError("unsupported_file_format", "直接文件链接缺少标题，不能区分 HTML 源文件与错误页；请使用标题为 .html/.htm 的 Wiki 入口或提供原文件")
        raise ReadError("invalid_response", "下载返回 HTML 页面，不能当作目标文件正文")
    total = len(text)
    offset = args.file_offset
    if offset > total:
        raise ReadError("invalid_input", "file-offset 超出文本字符总数", {"total_chars": total})
    if total and offset == total:
        raise ReadError("invalid_input", "file-offset 已位于文件末尾，没有可继续读取的内容", {"total_chars": total})
    end = min(total, offset + args.file_length) if args.file_length else total
    data = {"title": title[:500], "representation": selected, "sha256": sha,
            "hash_scope": "downloaded-representation", "size_bytes": len(raw),
            "total_chars": total, "total_lines": text.count("\n") + int(bool(text) and not text.endswith("\n")),
            "content_read_supported": True, "fallbacks": fallbacks,
            "text_normalization": "BOM removed; CRLF/CR normalized to LF"}
    if args.action == "catalog":
        data["content_read"] = False
        coverage = {"status": "structure-only", "whole_resource_complete": False,
                    "content_read": False, "sha256": sha, "representation": selected}
    else:
        # Select a verifiable character window, never silently slice output.
        # JSON escaping counts against the same budget as document responses.
        base_cost = len(json.dumps(dict(data, content="", start_char=offset, end_char=end,
                                        start_line=total + 1, end_line=total + 1), ensure_ascii=False)) + 160
        budget = max(0, args.max_chars - base_cost)
        lo, hi = offset, end
        while lo < hi:
            middle = (lo + hi + 1) // 2
            cost = len(json.dumps(text[offset:middle], ensure_ascii=False)) - 2
            if cost <= budget:
                lo = middle
            else:
                hi = middle - 1
        actual_end = lo
        if actual_end == offset and end > offset:
            raise ReadError("content_budget_exceeded", "当前预算不足以返回一个文本字符；请增加 max-chars")
        content = text[offset:actual_end]
        start_line = text.count("\n", 0, offset) + 1
        end_line = start_line + content.count("\n") - int(content.endswith("\n"))
        data.update(content=content, content_read=True, start_char=offset, end_char=actual_end,
                    start_line=start_line, end_line=max(start_line, end_line),
                    starts_mid_line=offset > 0 and text[offset - 1] != "\n",
                    ends_mid_line=actual_end < total and (not content or not content.endswith("\n")))
        window_complete = actual_end == end
        raw_complete = selected in ("download", "source-preview") and offset == 0 and actual_end == total
        coverage = {"status": "complete" if window_complete else "partial",
                    "requested_start_char": offset, "requested_end_char": end,
                    "actual_start_char": offset, "actual_end_char": actual_end,
                    "window_complete": window_complete, "whole_resource_complete": raw_complete,
                    "sha256": sha, "representation": selected, "content_read": True,
                    "original_file_complete": raw_complete,
                    "warning": "字符范围左闭右开；text-preview 完成仅表示预览文本，不代表原文件已完整读取"}
        if actual_end < total:
            coverage["next_offset"] = actual_end
        if selected == "text-preview":
            coverage["original_file_unread"] = True
    coverage.update(revision=None, revision_check="unavailable",
                    content_check="matched" if args.expected_content_sha256 else "unbound")
    result = {"ok": True, "identity": "bot", "source": dict(source), "data": data, "coverage": coverage,
              "receipt": coverage_receipt(source, coverage, None)}
    result["receipt"]["sha256"] = sha
    result["receipt"]["representation"] = selected
    result["receipt"]["whole_resource_complete"] = coverage["whole_resource_complete"]
    result["receipt"]["resume_requires_revision_check"] = False
    result["receipt"]["resume_requires_content_sha256"] = True
    return result
