"""Normalized evidence locators; no content or credential persistence."""
from __future__ import annotations

from .feishu_cli_coverage import revision_of


def enrich(result):
    source, data, coverage = result["source"], result["data"], result["coverage"]
    kind = source["type"]
    supported = kind in ("file", "docx", "sheet", "sheets", "okr")
    file_read = kind == "file" and isinstance(data.get("sha256"), str)
    doc_read = kind == "docx" and result.get("scope") not in (None, "outline") and not coverage.get("structure_only")
    sheet_read = kind in ("sheet", "sheets") and "read_format" in source
    okr_read = kind == "okr" and data.get("content_read") is True
    verified = bool(file_read or doc_read or sheet_read or okr_read)
    result["capabilities"] = {
        "type_supported": supported,
        "read_path_available": supported,
        "access_status": "content-verified" if verified else "metadata-or-structure-only",
        "permission_status": "verified-for-returned-representation" if verified else "content-access-not-verified",
        "format_status": "verified-representation" if verified else "not-verified",
        "content_returned": bool(data.get("content_read") or doc_read or sheet_read),
        "coverage_status": coverage.get("status", "unknown"),
        "whole_resource_complete": result["receipt"].get("whole_resource_complete", False),
    }
    if kind == "file":
        locator = {"kind": "characters", **{key: data[key] for key in (
            "start_char", "end_char", "start_line", "end_line", "starts_mid_line", "ends_mid_line") if key in data}}
        representation = data.get("representation")
    elif kind in ("sheet", "sheets"):
        locator = {"kind": "cells", "requested_range": coverage.get("requested_range"),
                   "actual_ranges": [row.get("actual_range") for row in coverage.get("upstream_coverage", [])]}
        representation = source.get("read_format")
    elif kind == "okr":
        locator = {"kind": "okr-entities", "scope": coverage.get("scope"),
                   "cycle_id": source["token"], "period_id": source["period_id"],
                   "objective_ids": coverage.get("objective_ids", []),
                   "key_result_ids": coverage.get("key_result_ids", [])}
        representation = "okr-v2-richtext"
    else:
        locator = {"kind": "blocks", "scope": result.get("scope"),
                   "block_ids": coverage.get("block_ids", [])}
        representation = "docx-xml" if kind == "docx" else None
    result["evidence"] = {
        "schema": "feishu.evidence/v1",
        "resource": {key: source[key] for key in ("url", "type", "token", "sheet_id", "period_id", "web_user_id", "api_user_id", "user_id_type") if key in source},
        "snapshot": {"revision": coverage.get("revision") or revision_of(data),
                     "sha256": data.get("sha256"), "representation": representation},
        "locator": locator,
        "coverage_status": coverage.get("status", "unknown"),
        "content_redacted": bool(coverage.get("content_redacted")),
        "limitations": (["snapshot-consistency-not-guaranteed", *coverage.get("unread", [])] if kind == "okr"
                        else ["converted-preview-original-unread"] if data.get("representation") == "text-preview" else []),
    }
    return result
