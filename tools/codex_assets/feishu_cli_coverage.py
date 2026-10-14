"""Coverage receipts only; content rendering stays with the official CLI."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, Mapping, Optional, Tuple

Rect = Tuple[int, int, int, int]
TRUNCATION_KEYS = ("has_more", "truncated", "is_truncated")


def column_number(label: str) -> int:
    result = 0
    for char in label:
        result = result * 26 + ord(char) - ord("A") + 1
    return result


def column_label(value: int) -> str:
    result = ""
    while value:
        value, digit = divmod(value - 1, 26)
        result = chr(65 + digit) + result
    return result


def rectangle(value: Any) -> Optional[Rect]:
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"([A-Z]{1,3})([1-9][0-9]*)(?::([A-Z]{1,3})([1-9][0-9]*))?", value.split("!")[-1])
    if not match:
        return None
    left, top = column_number(match[1]), int(match[2])
    right, bottom = column_number(match[3] or match[1]), int(match[4] or match[2])
    return (left, top, right, bottom) if left <= right and top <= bottom else None


def range_label(rect: Rect) -> str:
    left, top, right, bottom = rect
    return f"{column_label(left)}{top}:{column_label(right)}{bottom}"


def truncation_signals(data: Any, path: str = "data") -> list:
    signals = []
    if not isinstance(data, dict):
        return signals
    signals.extend(f"{path}.{key}" for key in TRUNCATION_KEYS if data.get(key) is True)
    signals.extend(f"{path}.{key}:invalid" for key in TRUNCATION_KEYS
                   if key in data and not isinstance(data[key], bool))
    for key in ("ranges", "sheets"):
        for index, item in enumerate(data.get(key, []) if isinstance(data.get(key), list) else []):
            signals.extend(truncation_signals(item, f"{path}.{key}[{index}]"))
    return signals


def contiguous_indices(item: Mapping[str, Any], actual: Rect) -> bool:
    left, top, right, bottom = actual
    if "row_indices" in item and item["row_indices"] != list(range(top, bottom + 1)):
        return False
    if "col_indices" in item:
        values = item["col_indices"]
        letters = [column_label(x) for x in range(left, right + 1)]
        if values != letters and values != list(range(left, right + 1)):
            return False
    return True


def sheet_coverage(data: Mapping[str, Any], requested: str) -> Dict[str, Any]:
    target = rectangle(requested)
    signals = truncation_signals(data)
    entries = data.get("ranges") if isinstance(data.get("ranges"), list) else [data]
    rows = []
    for item in entries:
        if not isinstance(item, dict):
            rows.append({"status": "unknown", "reason": "invalid_range_entry"})
            continue
        row = {key: item[key] for key in ("actual_range", *TRUNCATION_KEYS, "row_indices", "col_indices") if key in item}
        actual = rectangle(item.get("actual_range"))
        clipped = bool(signals)
        valid = bool(target and actual and target[0] <= actual[0] <= actual[2] <= target[2]
                     and target[1] <= actual[1] <= actual[3] <= target[3])
        if any(x.endswith(":invalid") for x in signals):
            row.update(status="unknown", reason="invalid_truncation_flag", continuation_requires_smaller_window=True)
        elif not valid or not contiguous_indices(item, actual):
            row.update(status="unknown", reason="missing_or_inconsistent_coordinates", continuation_requires_smaller_window=True)
        elif actual == target and not clipped:
            row["status"] = "complete"
        else:
            row["status"] = "partial"
            # Advance rows only when the complete requested width was returned.
            if (actual[0] == target[0] and actual[2] == target[2]
                    and actual[1] == target[1] and target[1] < actual[3] < target[3]):
                row["next_range"] = range_label((target[0], actual[3], target[2], target[3]))
                row["overlap_last_row"] = True
            else:
                # Do not guess which cells of a shortened row were returned.
                row.update(continuation_requires_smaller_window=True,
                           reason="two_dimensional_gap_or_truncated_final_row")
        rows.append(row)
    # Multiple ranges must be reconciled explicitly; never infer their union.
    complete = len(rows) == 1 and rows[0].get("status") == "complete" and not signals
    status = "complete" if complete else "unknown" if not rows or any(x.get("status") == "unknown" for x in rows) else "partial"
    return {"requested_range": requested, "status": status, "window_complete": complete,
            "truncation_signals": signals, "upstream_coverage": rows,
            "warning": "complete 仅表示当前窗口；整表需核对全部计划窗口。partial/unknown 不得计为已覆盖；续读可能重叠末行。"}


def document_coverage(data: Mapping[str, Any], scope: str, start: str = "", end: str = "", depth: int = -1) -> Dict[str, Any]:
    document = data.get("document", {})
    content = document.get("content") if isinstance(document, dict) else None
    result = {"status": "unknown", "full_document_requested": scope == "full" or (scope == "range" and start == "0" and end == "-1"),
              "content_truncated_by_adapter": False, "requested_start": start, "requested_end": end,
              "max_depth": depth, "block_ids": [], "top_level_block_ids": [], "excerpts": [],
              "embedded_resources": [], "truncation_signals": truncation_signals(data), "structure_only": depth != -1 or scope == "outline"}
    if not isinstance(content, str) or "<!DOCTYPE" in content.upper() or "<!ENTITY" in content.upper():
        result["reason"] = "missing_or_unsafe_xml"
        return result
    content = re.sub(r"^\s*<\?xml[^?]*\?>", "", content)
    try:
        root = ET.fromstring("<receipt-root>" + content + "</receipt-root>")
    except ET.ParseError:
        result["reason"] = "xml_not_verifiable"
        return result
    container = root[0] if len(root) == 1 and root[0].tag in ("fragment", "document", "doc") else root
    fragment_mode = container.get("mode") if container.tag == "fragment" else None
    mode_mismatch = bool(container.tag == "fragment" and ((fragment_mode and fragment_mode != scope)
                         or (scope == "full" and fragment_mode != "full")))
    for element in container:
        block = element.get("block-id") or element.get("id") or element.get("block_id")
        if block:
            result["top_level_block_ids"].append(block)
    for element in root.iter():
        tag = element.tag.split("}")[-1]
        block = element.get("block-id") or element.get("id") or element.get("block_id")
        if block and block not in result["block_ids"]:
            result["block_ids"].append(block)
        if tag == "excerpt":
            result["excerpts"].append({k: element.attrib[k] for k in ("top-block-id", "parent-block-path") if k in element.attrib})
        if tag in ("img", "source", "sheet", "bitable", "whiteboard", "synced_reference", "vc-transcribe-tab") or (tag == "cite" and element.get("file-type") in ("sheets", "bitable")):
            result["embedded_resources"].append({"type": tag, "block_id": block or "", "content_read": False})
    # Sidecar/degradation tips require inspection rather than an automatic full claim.
    references = document.get("reference_map", {})
    comments = references.get("comments", {}) if isinstance(references, dict) else {}
    has_tips = bool(document.get("tips") or (comments.get("tips") if isinstance(comments, dict) else False))
    has_gaps = bool(result["excerpts"] or result["embedded_resources"] or result["truncation_signals"] or has_tips)
    result["status"] = "partial" if has_gaps else "structure-only" if result["structure_only"] else "complete-scope"
    expected_endpoints = [value for value in (start, end) if value and value not in ("0", "-1")]
    if mode_mismatch or any(value not in result["block_ids"] for value in expected_endpoints):
        result["status"] = "unknown"
        result["reason"] = "upstream_scope_mismatch" if mode_mismatch else "requested_endpoint_missing"
    result["full_document_complete"] = bool(result["full_document_requested"] and result["status"] == "complete-scope" and depth == -1)
    if has_tips and "reason" not in result:
        result["reason"] = "upstream_tips_require_review"
    return result


def revision_of(data: Mapping[str, Any]) -> Optional[str]:
    value = data.get("revision")
    if value is None and isinstance(data.get("document"), dict):
        value = data["document"].get("revision_id")
    return str(value) if isinstance(value, (str, int)) and not isinstance(value, bool) and str(value).isdigit() else None


def coverage_receipt(source: Mapping[str, Any], coverage: Mapping[str, Any], revision: Optional[str]) -> Dict[str, Any]:
    return {"schema": "feishu.read-receipt/v1", "resource": dict(source), "revision": revision,
            "status": coverage.get("status", "unknown"), "coverage": dict(coverage),
            "resume_requires_revision_check": True, "whole_resource_complete": coverage.get("full_document_complete", False)}
