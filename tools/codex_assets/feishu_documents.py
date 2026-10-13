"""Bounded Feishu document reads through the application's official API client."""
from __future__ import annotations

import dataclasses
import json
import re
from typing import Any, Callable, Dict, List, Mapping, Tuple
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit


class DocumentReadError(ValueError):
    pass


@dataclasses.dataclass(frozen=True)
class ApplicationCredentials:
    app_id: str
    app_secret: str = dataclasses.field(repr=False)


TOKEN = re.compile(r"[A-Za-z0-9]{1,128}")
LINK = re.compile(r"https://[A-Za-z0-9.-]+\.feishu\.cn/(?:wiki|docx|sheets)/[^\s<>\"，。；）]+")
MAX_DOCUMENTS = 3
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_CONTEXT_CHARS = 12000
TRUNCATED = "\n[内容已截断，不能据此声称完成全文分析]"


def checked_token(value: Any) -> str:
    if not isinstance(value, str) or not TOKEN.fullmatch(value):
        raise DocumentReadError("飞书返回的对象标识无效")
    return value


def checked_range(value: str) -> str:
    match = re.fullmatch(r"([A-Z]{1,3})([1-9][0-9]{0,6}):([A-Z]{1,3})([1-9][0-9]{0,6})", value)
    if not match:
        raise DocumentReadError("range 必须为 A1:C3 形式")
    def column(label: str) -> int:
        result = 0
        for char in label:
            result = result * 26 + ord(char) - ord("A") + 1
        return result
    left, top, right, bottom = match.groups()
    rows = int(bottom) - int(top) + 1
    cols = column(right) - column(left) + 1
    if not 1 <= rows <= 100 or not 1 <= cols <= 26 or rows * cols > 2000:
        raise DocumentReadError("range 最多 100 行、26 列、2000 个单元格，且起止顺序必须正确")
    return value


@dataclasses.dataclass(frozen=True)
class DocumentReference:
    kind: str
    token: str
    sheet: str = ""
    cell_range: str = ""
    url: str = ""


def parse_document_url(value: str) -> DocumentReference:
    if len(value) > 1024 or any(ord(char) < 33 for char in value):
        raise DocumentReadError("飞书文档链接格式无效")
    try:
        parts = urlsplit(value)
        valid_authority = (
            parts.scheme == "https" and parts.username is None and parts.password is None
            and parts.port is None and re.fullmatch(r"[A-Za-z0-9-]+\.feishu\.cn", parts.hostname or "")
        )
    except ValueError:
        raise DocumentReadError("飞书文档链接格式无效") from None
    path = re.fullmatch(r"/(wiki|docx|sheets)/([A-Za-z0-9]{1,128})/?", parts.path)
    if not valid_authority or not path:
        raise DocumentReadError("仅支持 https://<租户>.feishu.cn/ 下的 wiki、docx、sheets 链接")
    try:
        queries = parse_qs(parts.query, keep_blank_values=True, max_num_fields=20)
    except ValueError:
        raise DocumentReadError("飞书链接参数过多") from None
    selected = {}
    for key in ("sheet", "range"):
        if key in queries:
            if len(queries[key]) != 1 or not queries[key][0]:
                raise DocumentReadError(f"{key} 参数必须唯一且非空")
            selected[key] = queries[key][0]
    sheet = checked_token(selected["sheet"]) if "sheet" in selected else ""
    cell_range = checked_range(selected["range"]) if "range" in selected else ""
    canonical = urlunsplit(("https", parts.hostname or "", parts.path.rstrip("/"), urlencode(selected, safe=":"), ""))
    return DocumentReference(path[1], path[2], sheet, cell_range, canonical)


def links_in_text(text: str) -> Tuple[DocumentReference, ...]:
    references: List[DocumentReference] = []
    for match in LINK.finditer(text):
        reference = parse_document_url(match.group().rstrip(").,;!?]}`"))
        if reference not in references:
            references.append(reference)
    if len(references) > MAX_DOCUMENTS:
        raise DocumentReadError(f"每条任务最多读取 {MAX_DOCUMENTS} 个飞书文档链接")
    return tuple(references)


class DocumentReader:
    def __init__(self, get: Callable[[str, Mapping[str, str]], Dict[str, Any]]) -> None:
        self.get = get

    def read(self, reference: DocumentReference) -> str:
        kind, token = reference.kind, reference.token
        title = ""
        if kind == "wiki":
            node = self.get("/open-apis/wiki/v2/spaces/get_node", {"token": token})["node"]
            kind = node.get("obj_type")
            token = checked_token(node.get("obj_token"))
            title = str(node.get("title", ""))[:200]
        if kind == "docx":
            if reference.sheet or reference.cell_range:
                raise DocumentReadError("文档对象不支持 sheet 或 range 参数")
            data = self.get(f"/open-apis/docx/v1/documents/{token}/raw_content", {})
            content = data.get("content")
            if not isinstance(content, str):
                raise DocumentReadError("文档正文响应格式无效")
            text = f"文档标题：{title or '未提供'}\n{content}"
        elif kind in {"sheet", "sheets"}:
            data = self.get(f"/open-apis/sheets/v3/spreadsheets/{token}/sheets/query", {})
            sheets = data.get("sheets", [])
            if not isinstance(sheets, list) or not sheets:
                raise DocumentReadError("电子表格没有可读取的工作表")
            sheet = next((item for item in sheets if item.get("sheet_id") == reference.sheet), None) if reference.sheet else sheets[0]
            if sheet is None:
                raise DocumentReadError("指定工作表不存在或不可见")
            sheet_id = checked_token(sheet.get("sheet_id"))
            grid = sheet.get("grid_properties", {})
            if reference.cell_range:
                cell_range = reference.cell_range
            else:
                cols = min(20, int(grid.get("column_count", 20)))
                rows = min(50, int(grid.get("row_count", 50)))
                if cols < 1 or rows < 1:
                    raise DocumentReadError("工作表网格为空")
                cell_range = f"A1:{chr(ord('A') + cols - 1)}{rows}"
            data = self.get(f"/open-apis/sheets/v2/spreadsheets/{token}/values/{sheet_id}!{cell_range}", {})
            values = data.get("valueRange", {}).get("values")
            if not isinstance(values, list):
                raise DocumentReadError("单元格响应格式无效")
            text = (
                f"工作表：{str(sheet.get('title', ''))[:200]}；sheet={sheet_id}；读取范围={cell_range}。\n"
                "以下仅是指定范围，未读取整个工作表。\n"
                + json.dumps(values, ensure_ascii=False)
            )
        else:
            raise DocumentReadError("当前仅支持新版文档和电子表格，不支持该知识库对象类型")
        if len(text) > 8000:
            text = text[:8000 - len(TRUNCATED)] + TRUNCATED
        return f"[飞书只读参考数据开始]\n来源：{reference.url}\n{text}\n[飞书只读参考数据结束]"
