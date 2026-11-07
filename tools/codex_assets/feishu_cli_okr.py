"""Bounded OKR v2 reads through the pinned official CLI; no user auth or writes."""
from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timezone

from .feishu_cli_errors import ReadError
from .feishu_cli_coverage import coverage_receipt

COMMANDS = ("okr/cycles/list", "okr/cycle.objectives/list", "okr/objective.key_results/list")
MAX_PAGES = 10
MAX_CALLS = 40
MAX_ITEMS = 1000
MAX_BYTES = 1024 * 1024
ID = re.compile(r"[1-9][0-9]{0,18}")
FIELDS = ("id", "create_time", "update_time", "owner", "cycle_id", "objective_id",
          "position", "score", "weight", "deadline", "category_id")
UNREAD = ["indicators", "progress_records", "comments", "alignments", "attachments",
          "linked_documents", "other_users_and_cycles"]


def checked_id(value):
    if not isinstance(value, str) or not ID.fullmatch(value) or int(value) > 2**63 - 1:
        raise ReadError("invalid_response", "OKR接口返回无效实体标识")
    return value


def validate_options(args, reference):
    options = (args.okr_user_id or args.okr_user_id_type or args.okr_objective_id or args.okr_page_size != 100)
    if reference.kind != "okr":
        if options:
            raise ReadError("invalid_input", "OKR参数只用于OKR链接")
        return
    if (args.session or args.resume or args.target_range or args.action == "status"
            or args.sheet_id or args.range or args.format != "csv" or args.include
            or args.scope != "outline" or args.keyword or args.start_block or args.end_block
            or args.max_depth != -1 or args.revision_id != -1 or args.expected_revision
            or args.file_mode != "auto" or args.file_offset or args.file_length or args.expected_content_sha256):
        raise ReadError("invalid_input", "OKR首版仅支持stateless inspect/catalog/read，不能混用文档、表格、文件或会话参数")
    if not 1 <= args.okr_page_size <= 100:
        raise ReadError("invalid_input", "okr-page-size必须为1至100")
    if args.okr_user_id_type and not args.okr_user_id:
        raise ReadError("invalid_input", "指定API用户标识类型时必须同时提供okr-user-id")
    if args.okr_user_id and not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", args.okr_user_id):
        raise ReadError("invalid_input", "OKR API用户标识格式无效")
    if args.okr_objective_id:
        try:
            checked_id(args.okr_objective_id)
        except ReadError:
            raise ReadError("invalid_input", "okr-objective-id必须为正整数实体ID") from None
        if args.action == "inspect":
            raise ReadError("invalid_input", "inspect不接受目标正文选择参数")


class Reader:
    def __init__(self, backend, page_size):
        self.backend, self.page_size = backend, page_size
        self.calls, self.bytes = 0, 0
        self.redacted = False

    def pages(self, command, flags):
        rows, tokens, seen, token = [], set(), {}, ""
        for _ in range(MAX_PAGES):
            if self.calls >= MAX_CALLS:
                raise ReadError("coverage_limit", "OKR读取达到40次请求上限；不能声明完整")
            self.calls += 1
            request = list(flags) + ["--page-size", str(self.page_size)]
            if token:
                request += ["--page-token", token]
            page = self.backend.read(command, request)
            self.redacted |= "REDACTED" in json.dumps(page, ensure_ascii=False)
            self.bytes += len(json.dumps(page, ensure_ascii=False).encode())
            if self.bytes > MAX_BYTES:
                raise ReadError("response_too_large", "OKR累计响应超过1 MiB；不返回截断正文")
            items, more = page.get("items"), page.get("has_more")
            if not isinstance(items, list) or type(more) is not bool:
                raise ReadError("invalid_response", "OKR分页缺少可靠items/has_more，不能推断完成")
            for row in items:
                if not isinstance(row, dict):
                    raise ReadError("invalid_response", "OKR分页实体结构无效")
                identity = checked_id(row.get("id"))
                if identity in seen:
                    if seen[identity] != row:
                        raise ReadError("snapshot_changed", "OKR分页期间同一实体发生变化；不得混合结果")
                    continue
                seen[identity] = row
                rows.append(row)
                if len(rows) > MAX_ITEMS:
                    raise ReadError("coverage_limit", "OKR实体数量超过单次读取上限")
            if not more:
                return rows
            next_token = page.get("page_token")
            if (not items or not isinstance(next_token, str) or not 1 <= len(next_token) <= 2048
                    or any(ord(c) < 33 or ord(c) > 126 for c in next_token)
                    or next_token in tokens):
                raise ReadError("invalid_response", "OKR分页没有有效进展；已停止，不跳过未知内容")
            tokens.add(next_token)
            token = next_token
        raise ReadError("coverage_limit", "OKR单个集合超过10页；不能声明完整")


def project(row, body=False):
    value = {key: copy.deepcopy(row[key]) for key in FIELDS if key in row}
    if body:
        for key in ("content", "notes"):
            if key in row:
                content = row[key]
                if not isinstance(content, dict) or not isinstance(content.get("blocks"), list):
                    raise ReadError("invalid_response", "OKR富文本结构无效；不把异常结构作为已读正文")
                value[key] = copy.deepcopy(content)
    return value


def fetch_okr(backend, args, reference):
    validate_options(args, reference)
    user = args.okr_user_id or reference.owner_id
    user_type = args.okr_user_id_type or "user_id"
    reader = Reader(backend, args.okr_page_size)
    cycles = reader.pages(COMMANDS[0], ["--user-id", user, "--user-id-type", user_type])
    matches = []
    for cycle in cycles:
        owner = cycle.get("owner")
        if (not isinstance(owner, dict) or owner.get("owner_type") != "user"
                or owner.get("user_id") != user):
            raise ReadError("resource_mismatch", "OKR周期列表的所有者与指定API用户不一致")
        checked_id(cycle.get("tenant_cycle_id"))
        if cycle["id"] == reference.token and cycle["tenant_cycle_id"] == reference.period_id:
            matches.append(cycle)
    if len(matches) != 1:
        raise ReadError("okr_mapping_unverified", "未在该API用户周期列表中找到同时匹配okrId和periodId的记录；不猜测其他用户或周期",
                        {"next_action": "核实网页用户ID与API用户ID映射；必要时显式提供okr-user-id和okr-user-id-type"})
    cycle = matches[0]
    source = {"url": reference.url, "type": "okr", "token": cycle["id"],
              "web_user_id": reference.owner_id, "api_user_id": user, "user_id_type": user_type,
              "period_id": reference.period_id, "trust": "untrusted_external_content"}
    selected_cycle = {key: copy.deepcopy(cycle[key]) for key in (
        "id", "tenant_cycle_id", "owner", "start_time", "end_time", "cycle_status",
        "score", "create_time", "update_time") if key in cycle}
    data = {"cycle": selected_cycle, "mapping_verified": True,
            "mapping_method": "explicit-api-user-and-returned-cycle" if args.okr_user_id else "url-candidate-validated-by-cycle-list",
            "content_read": args.action == "read", "objectives": []}
    objective_ids, kr_ids = [], []
    if args.action != "inspect":
        objectives = reader.pages(COMMANDS[1], ["--cycle-id", cycle["id"], "--user-id-type", user_type])
        for row in objectives:
            if row.get("cycle_id") != cycle["id"]:
                raise ReadError("resource_mismatch", "OKR目标不属于链接对应的用户周期")
        if args.okr_objective_id:
            objectives = [row for row in objectives if row["id"] == args.okr_objective_id]
            if not objectives:
                raise ReadError("selection_required", "指定目标不在已验证周期中")
        for row in objectives:
            objective_ids.append(row["id"])
            obj = project(row, body=args.action == "read")
            if args.action == "read":
                key_results = reader.pages(COMMANDS[2], ["--objective-id", row["id"], "--user-id-type", user_type])
                obj["key_results"] = []
                for kr in key_results:
                    if kr.get("objective_id") != row["id"]:
                        raise ReadError("resource_mismatch", "OKR关键结果不属于当前目标")
                    if kr["id"] in kr_ids:
                        raise ReadError("snapshot_changed", "同一KR在本次读取中归属不同目标；不得重复统计或合并")
                    kr_ids.append(kr["id"])
                    obj["key_results"].append(project(kr, body=True))
            data["objectives"].append(obj)
    data.update(objective_count=len(objective_ids), key_result_count=len(kr_ids))
    if len(json.dumps(data, ensure_ascii=False)) > args.max_chars:
        raise ReadError("content_budget_exceeded", "OKR正文超预算，不截断；可提高max-chars或按目标ID读取",
                        {"objective_ids": objective_ids[:100], "next_action": "catalog查看目标清单，再用okr-objective-id分段读取；不使用文档session"})
    scope = "objective-and-key-results" if args.action == "read" else "objective-catalog" if args.action == "catalog" else "cycle-metadata"
    body_complete = all("content" in row and all("content" in kr for kr in row.get("key_results", []))
                        for row in data["objectives"]) if args.action == "read" else False
    body_complete = body_complete and not reader.redacted
    coverage = {"status": "complete-scope" if body_complete else "structure-only" if args.action != "read" else "partial",
                "scope": scope, "enumeration_complete": True, "content_read": args.action == "read",
                "scope_complete": body_complete, "whole_resource_complete": False,
                "snapshot_consistency": "not-guaranteed", "revision": None, "revision_check": "unavailable",
                "content_redacted": reader.redacted,
                "objective_ids": objective_ids, "key_result_ids": kr_ids,
                "selected_objective_id": args.okr_objective_id or None,
                "unread": list(UNREAD), "requests": reader.calls,
                "retrieved_at": datetime.now(timezone.utc).isoformat()}
    return {"ok": True, "identity": "bot", "source": source, "data": data, "coverage": coverage,
            "receipt": coverage_receipt(source, coverage, None)}
