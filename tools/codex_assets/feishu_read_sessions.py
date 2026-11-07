"""Metadata-only, resource-bound read sessions and conservative coverage unions."""
from __future__ import annotations

import copy
import fcntl
import json
import os
import pathlib
import re
import stat
import tempfile

from .feishu_cli_coverage import rectangle, range_label, revision_of
from .feishu_cli_errors import ReadError, recovery
from .feishu_documents import parse_document_url

SCHEMA = "feishu.read-session/v1"
MAX_STATE = 1024 * 1024
MAX_WINDOWS = 2048
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
SHA = re.compile(r"[a-f0-9]{64}")
BLOCK = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}")
STATE_KEYS = {"schema", "url", "backend_sha256", "resource", "binding", "plan", "segments",
              "pending", "last_error", "failures", "invalidated", "overlap_observed", "sequence", "content_observed"}


def integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def merged_intervals(intervals):
    result = []
    for start, end in sorted(intervals):
        if start == end:
            continue
        if result and start <= result[-1][1]:
            result[-1][1] = max(result[-1][1], end)
        else:
            result.append([start, end])
    return result


def file_gaps(total, segments):
    gaps, cursor = [], 0
    for start, end in merged_intervals(segments):
        if start > cursor:
            gaps.append([cursor, start])
        cursor = max(cursor, end)
    if cursor < total:
        gaps.append([cursor, total])
    return gaps


def sheet_gaps(target, covered):
    """Sweep row bands; never allocate a cell-sized grid."""
    left, top, right, bottom = target
    cuts = {top, bottom + 1}
    for x1, y1, x2, y2 in covered:
        cuts.update((max(top, y1), min(bottom + 1, y2 + 1)))
    cuts = sorted(y for y in cuts if top <= y <= bottom + 1)
    gaps = []
    for y1, stop in zip(cuts, cuts[1:]):
        intervals = merged_intervals([[max(left, x1), min(right + 1, x2 + 1)]
                                     for x1, a, x2, b in covered
                                     if a <= y1 and b >= stop - 1 and x1 <= right and x2 >= left])
        cursor = left
        for x1, x2 in intervals:
            if x1 > cursor:
                gaps.append([cursor, y1, x1 - 1, stop - 1])
            cursor = max(cursor, x2)
        if cursor <= right:
            gaps.append([cursor, y1, right, stop - 1])
    return gaps


def bounded_window(rect):
    left, top, right, bottom = rect
    right = min(right, left + 25)
    bottom = min(bottom, top + 99, top + 2000 // (right - left + 1) - 1)
    return range_label((left, top, right, bottom))


def target_rectangle(value):
    rect = rectangle(value)
    if not rect or "!" in value or not all(integer(x) for x in rect):
        raise ReadError("invalid_input", "target-range 必须是有序的 A1:C200 形式")
    if rect[2] > 18278 or rect[3] > 1000000:
        raise ReadError("invalid_input", "target-range 超出支持的列/行上限")
    return list(rect)


def new_state(url, backend_sha256):
    return {"schema": SCHEMA, "url": parse_document_url(url, allow_files=True).url,
            "backend_sha256": backend_sha256, "resource": None, "binding": None, "plan": None,
            "segments": [], "pending": None, "last_error": None, "failures": 0,
            "invalidated": False, "overlap_observed": False, "sequence": 0, "content_observed": False}


def validate_state(state):
    if not isinstance(state, dict) or set(state) != STATE_KEYS or state["schema"] != SCHEMA:
        raise ReadError("invalid_session", "会话记录格式无效；不读取未知字段或其他格式")
    if parse_document_url(state["url"], allow_files=True).url != state["url"]:
        raise ReadError("invalid_session", "会话链接不是规范资源链接")
    if not isinstance(state["backend_sha256"], str) or not SHA.fullmatch(state["backend_sha256"]):
        raise ReadError("invalid_session", "会话缺少有效后端身份")
    for key in ("sequence", "failures"):
        if not integer(state[key]) or not 0 <= state[key] <= 100000:
            raise ReadError("invalid_session", "会话计数无效")
    if any(type(state[key]) is not bool for key in ("invalidated", "overlap_observed", "content_observed")):
        raise ReadError("invalid_session", "会话状态字段无效")
    resource = state["resource"]
    if resource is not None:
        if not isinstance(resource, dict) or not set(resource) <= {"type", "token", "sheet_id"} or not {"type", "token"} <= set(resource):
            raise ReadError("invalid_session", "会话资源身份无效")
        if any(not isinstance(value, str) or not BLOCK.fullmatch(value) for value in resource.values()):
            raise ReadError("invalid_session", "会话资源标识无效")
    binding = state["binding"]
    if binding is not None:
        if not isinstance(binding, dict) or not set(binding) <= {"kind", "value", "representation", "format", "include"}:
            raise ReadError("invalid_session", "会话版本绑定无效")
        if binding.get("kind") not in ("sha256", "revision") or not isinstance(binding.get("value"), str):
            raise ReadError("invalid_session", "会话版本类型无效")
        if binding["kind"] == "sha256":
            if not SHA.fullmatch(binding["value"]) or binding.get("representation") not in ("download", "source-preview", "text-preview"):
                raise ReadError("invalid_session", "会话哈希或表示类型无效")
        elif not re.fullmatch(r"[0-9]{1,18}", binding["value"]):
            raise ReadError("invalid_session", "会话原生版本无效")
        if "format" in binding and binding["format"] not in ("csv", "cells"):
            raise ReadError("invalid_session", "会话表格格式无效")
        include = binding.get("include", "")
        if not isinstance(include, str) or not set(filter(None, include.split(","))) <= {
                "value", "formula", "style", "comment", "data_validation", "conditional_format", "truncation"}:
            raise ReadError("invalid_session", "会话单元格视图无效")
    plan = state["plan"]
    if resource and binding:
        expected_binding = "sha256" if resource["type"] == "file" else "revision"
        if binding["kind"] != expected_binding:
            raise ReadError("invalid_session", "会话资源与版本类型不匹配")
    if plan is not None:
        if not isinstance(plan, dict) or plan.get("kind") not in ("file", "sheet", "docx"):
            raise ReadError("invalid_session", "会话覆盖计划无效")
        expected_plan = "sheet" if resource and resource["type"] in ("sheet", "sheets") else resource["type"] if resource else None
        if plan["kind"] != expected_plan:
            raise ReadError("invalid_session", "会话资源与覆盖计划类型不匹配")
        if plan["kind"] == "file":
            if set(plan) != {"kind", "total"} or not integer(plan["total"]) or not 0 <= plan["total"] <= 4 * 1024 * 1024:
                raise ReadError("invalid_session", "文件覆盖计划无效")
        elif plan["kind"] == "sheet":
            if set(plan) != {"kind", "range"} or not isinstance(plan["range"], str):
                raise ReadError("invalid_session", "表格覆盖计划无效")
            target_rectangle(plan["range"])
        else:
            if set(plan) != {"kind", "blocks"} or not isinstance(plan["blocks"], list) or not 1 <= len(plan["blocks"]) <= MAX_WINDOWS:
                raise ReadError("invalid_session", "文档覆盖计划无效")
            if len(set(plan["blocks"])) != len(plan["blocks"]) or any(
                    not isinstance(x, str) or not BLOCK.fullmatch(x) or x == "0" for x in plan["blocks"]):
                raise ReadError("invalid_session", "文档块计划无效")
    segments = state["segments"]
    if not isinstance(segments, list) or len(segments) > MAX_WINDOWS or (segments and not plan):
        raise ReadError("invalid_session", "会话覆盖窗口无效或过多")
    for segment in segments:
        if plan["kind"] == "docx":
            if not isinstance(segment, str) or segment not in plan["blocks"]:
                raise ReadError("invalid_session", "会话文档块不在计划内")
        elif plan["kind"] == "file":
            if not isinstance(segment, list) or len(segment) != 2 or not all(integer(x) for x in segment) or not 0 <= segment[0] <= segment[1] <= plan["total"]:
                raise ReadError("invalid_session", "会话文件窗口无效")
        else:
            if not isinstance(segment, list) or len(segment) != 4 or not all(integer(x) for x in segment):
                raise ReadError("invalid_session", "会话表格窗口无效")
            left, top, right, bottom = target_rectangle(plan["range"])
            if not left <= segment[0] <= segment[2] <= right or not top <= segment[1] <= segment[3] <= bottom:
                raise ReadError("invalid_session", "会话表格窗口越界")
    pending = state["pending"]
    if pending is not None:
        if not isinstance(pending, dict) or not set(pending) <= {"action", "scope", "start_block", "end_block", "range"}:
            raise ReadError("invalid_session", "会话下一步无效")
        if pending.get("action") not in ("inspect", "catalog", "read"):
            raise ReadError("invalid_session", "会话动作无效")
        if "scope" in pending and pending["scope"] not in ("outline", "range", "full"):
            raise ReadError("invalid_session", "会话scope无效")
        for key in ("start_block", "end_block"):
            if key in pending and (not isinstance(pending[key], str) or not BLOCK.fullmatch(pending[key])):
                raise ReadError("invalid_session", "会话块端点无效")
        if "range" in pending:
            target_rectangle(pending["range"])
    error = state["last_error"]
    if error is not None and (not isinstance(error, dict) or set(error) != {"kind"} or
                              not isinstance(error["kind"], str) or not re.fullmatch(r"[a-z_]{1,64}", error["kind"])):
        raise ReadError("invalid_session", "会话错误摘要无效")
    return state


def summary(state):
    validate_state(state)
    plan, binding = state["plan"], state["binding"]
    complete, original, missing, next_step = False, False, [], state["pending"]
    reason = None
    if state["invalidated"]:
        reason, next_step = "snapshot-invalidated-use-new-session", None
    elif plan and binding:
        if plan["kind"] == "file":
            missing = file_gaps(plan["total"], state["segments"])
            complete = not missing and state["content_observed"]
            original = complete and binding.get("representation") in ("download", "source-preview")
            if missing:
                next_step = {"action": "read", "file_offset": missing[0][0],
                             "file_length": missing[0][1] - missing[0][0]}
            elif not complete:
                next_step = {"action": "read"}
        elif plan["kind"] == "sheet":
            missing = sheet_gaps(target_rectangle(plan["range"]), state["segments"])
            complete = not missing
            if missing and next_step is None:
                next_step = {"action": "read", "range": bounded_window(missing[0])}
        else:
            missing = [x for x in plan["blocks"] if x not in state["segments"]]
            complete = bool(plan["blocks"]) and not missing
            original = complete
            if missing and next_step is None:
                next_step = {"action": "read", "scope": "range", "start_block": missing[0], "end_block": missing[0]}
        if complete:
            next_step = None
    elif state["resource"]:
        kind = state["resource"]["type"]
        if kind == "file":
            next_step = {"action": "read"}
        elif kind == "docx" and binding and state["last_error"] != {"kind": "unverifiable_catalog"}:
            next_step = {"action": "catalog"}
        else:
            reason = "native-revision-or-explicit-range-plan-required"
            next_step = None
    else:
        next_step = next_step or {"action": "inspect"}
    if state["last_error"] and state["last_error"]["kind"] == "redacted_content":
        complete, original, next_step, reason = False, False, None, "redacted-content-not-complete"
    if state["failures"] >= 3:
        next_step, reason = None, "no-progress-after-three-attempts"
    display_plan = copy.deepcopy(plan)
    if display_plan and display_plan["kind"] == "docx":
        display_plan["block_count"] = len(display_plan["blocks"])
        display_plan["blocks"] = display_plan["blocks"][:32]
    return {"schema": SCHEMA, "resource": state["resource"], "binding": binding, "plan": display_plan,
            "covered": state["segments"][:32], "missing": missing[:32], "scope_complete": complete,
            "covered_count": len(state["segments"]), "missing_count": len(missing),
            "display_truncated": bool(len(state["segments"]) > 32 or len(missing) > 32
                                      or (plan and plan["kind"] == "docx" and len(plan["blocks"]) > 32)),
            "whole_resource_complete": original and not state["invalidated"],
            "overlap_observed": state["overlap_observed"], "next": next_step,
            "blocking_reason": reason, "last_error": state["last_error"],
            "sequence": state["sequence"], "content_persisted": False}


def prepare(state, args):
    if args.target_range and state["plan"] and state["plan"]["kind"] == "sheet" and state["plan"]["range"] != args.target_range:
        raise ReadError("session_mismatch", "覆盖计划不能在同一会话中改变；请使用新会话")
    if args.resume:
        if args.file_offset or args.file_length or args.range or args.start_block or args.end_block or args.keyword or args.scope != "outline":
            raise ReadError("invalid_input", "resume 自动选择下一窗口，不能同时传手工窗口参数")
        step = summary(state)["next"]
        if step is None:
            if summary(state)["scope_complete"] and not state["invalidated"]:
                kind = state["resource"]["type"]
                if kind == "file":
                    step = {"action": "catalog"}
                elif kind == "docx":
                    step = {"action": "inspect"}
                else:
                    x, y, _, _ = target_rectangle(state["plan"]["range"])
                    step = {"action": "read", "range": range_label((x, y, x, y))}
                args._session_revalidation = True
            else:
                raise ReadError("session_stalled", "当前会话没有可自动执行的下一步；请查看 status 的 blocking_reason")
        for key, value in step.items():
            setattr(args, key, value)
    binding = state["binding"]
    resource = state["resource"]
    if resource and resource.get("sheet_id"):
        if args.sheet_id and args.sheet_id != resource["sheet_id"]:
            raise ReadError("session_mismatch", "工作表与既有会话不同")
        args.sheet_id = resource["sheet_id"]
    plan_range = args.target_range or (state["plan"]["range"] if state["plan"] and state["plan"]["kind"] == "sheet" else "")
    if args.action == "read" and plan_range:
        target = target_rectangle(plan_range)
        if not args.range:
            args.range = bounded_window(target)
        actual = rectangle(args.range)
        if not actual or not target[0] <= actual[0] <= actual[2] <= target[2] or not target[1] <= actual[1] <= actual[3] <= target[3]:
            raise ReadError("invalid_input", "读取窗口不能超出会话目标范围")
    if binding:
        if binding["kind"] == "sha256":
            if args.expected_content_sha256 and args.expected_content_sha256 != binding["value"]:
                raise ReadError("session_mismatch", "指定哈希与既有会话不同")
            if args.file_mode not in ("auto", binding["representation"]):
                raise ReadError("session_mismatch", "文件表示方式与既有会话不同")
            args.file_mode = binding["representation"]
            args.expected_content_sha256 = binding["value"]
        else:
            if args.expected_revision and args.expected_revision != binding["value"]:
                raise ReadError("session_mismatch", "指定版本与既有会话不同")
            args.expected_revision = binding["value"]
            if resource and resource["type"] == "docx":
                args.revision_id = int(binding["value"])
            if "format" in binding:
                args.format, args.include = binding["format"], binding.get("include", "")
    return True


def record(state, result, args):
    value = copy.deepcopy(state)
    source, coverage, data = result["source"], result["coverage"], result["data"]
    resource = {key: source[key] for key in ("type", "token", "sheet_id") if key in source}
    # Workbook inspect does not select a tab. A later explicitly selected tab
    # may bind that previously unbound identity, but never replace a bound tab.
    old = value["resource"]
    if old and any(old[key] != resource.get(key) for key in old):
        raise ReadError("session_mismatch", "Wiki底层对象或选中工作表发生变化")
    value["resource"] = resource
    value["last_error"] = None
    kind = resource["type"]
    binding = None
    if kind == "file" and data.get("sha256"):
        binding = {"kind": "sha256", "value": data["sha256"], "representation": data["representation"]}
    elif kind in ("docx", "sheet", "sheets"):
        revision = coverage.get("revision") or revision_of(data)
        if revision:
            binding = {"kind": "revision", "value": revision}
            if source.get("read_format"):
                binding.update(format=source["read_format"], include=args.include)
    if binding:
        previous = value["binding"]
        if previous and any(binding.get(key, old_value) != old_value for key, old_value in previous.items()):
            raise ReadError("session_mismatch", "资源版本、表示或数据视图发生变化")
        if previous:
            binding = dict(previous, **binding)
        value["binding"] = binding
    value["pending"] = None
    if coverage.get("content_redacted"):
        value["last_error"] = {"kind": "redacted_content"}
    elif kind == "file" and binding:
        total = data["total_chars"]
        plan = {"kind": "file", "total": total}
        if value["plan"] and value["plan"] != plan:
            raise ReadError("session_mismatch", "同一内容哈希的字符长度发生变化")
        value["plan"] = plan
        if data.get("content_read"):
            value["content_observed"] = True
            segment = [coverage["actual_start_char"], coverage["actual_end_char"]]
            value["overlap_observed"] |= any(segment[0] < b and a < segment[1] for a, b in value["segments"])
            value["segments"] = merged_intervals(value["segments"] + [segment])
    elif kind in ("sheet", "sheets"):
        ref = parse_document_url(args.url, allow_files=True)
        target = args.target_range or ref.cell_range
        if target:
            target_rectangle(target)
            plan = {"kind": "sheet", "range": target}
            if value["plan"] and value["plan"] != plan:
                raise ReadError("session_mismatch", "工作表目标范围发生变化")
            value["plan"] = plan
        countable = (coverage.get("window_complete") is True and coverage.get("status") == "complete"
                     and not coverage.get("truncation_signals"))
        if value["plan"] and binding and countable:
            rows = coverage.get("upstream_coverage", [])
            if len(rows) == 1 and rows[0].get("status") == "complete" and rectangle(rows[0].get("actual_range")):
                segment = list(rectangle(rows[0]["actual_range"]))
                value["overlap_observed"] |= any(
                    max(segment[0], x1) <= min(segment[2], x2) and max(segment[1], y1) <= min(segment[3], y2)
                    for x1, y1, x2, y2 in value["segments"])
                if segment not in value["segments"]:
                    value["segments"].append(segment)
        elif args.action == "read" and value["plan"] and binding:
            rect = rectangle(coverage.get("requested_range"))
            if rect:
                x1, y1, x2, y2 = rect
                if y1 < y2:
                    value["pending"] = {"action": "read", "range": range_label((x1, y1, x2, (y1 + y2) // 2))}
                elif x1 < x2:
                    value["pending"] = {"action": "read", "range": range_label((x1, y1, (x1 + x2) // 2, y2))}
    elif kind == "docx" and binding:
        reliable_catalog = (args.action == "catalog" and coverage.get("full_document_requested")
                            and coverage.get("status") == "structure-only" and not coverage.get("reason")
                            and not coverage.get("excerpts") and not coverage.get("truncation_signals")
                            and coverage.get("top_level_unidentified_count", 0) == 0)
        if reliable_catalog and coverage.get("top_level_block_ids"):
            plan = {"kind": "docx", "blocks": coverage["top_level_block_ids"]}
            if value["plan"] and value["plan"] != plan:
                raise ReadError("session_mismatch", "文档顶层块清单发生变化")
            value["plan"] = plan
        elif args.action == "catalog":
            value["last_error"] = {"kind": "unverifiable_catalog"}
        if (coverage.get("full_document_complete") and coverage.get("top_level_block_ids")
                and coverage.get("top_level_unidentified_count", 0) == 0):
            value["plan"] = {"kind": "docx", "blocks": coverage["top_level_block_ids"]}
            value["segments"] = list(value["plan"]["blocks"])
        elif value["plan"] and coverage.get("status") == "complete-scope" and args.start_block == args.end_block:
            if args.start_block in value["plan"]["blocks"]:
                value["overlap_observed"] |= args.start_block in value["segments"]
                if args.start_block not in value["segments"]:
                    value["segments"].append(args.start_block)
    progressed = any(state[key] != value[key] for key in
                     ("resource", "binding", "plan", "content_observed", "segments"))
    # A completed snapshot is intentionally read again to check its identity.
    progressed |= summary(state)["scope_complete"] and summary(value)["scope_complete"]
    value["failures"] = 0 if progressed else value["failures"] + 1
    value["sequence"] += 1
    validate_state(value)
    return value


def failed(state, error):
    value = copy.deepcopy(state)
    kind = getattr(error, "kind", "invalid_input")
    value["last_error"] = {"kind": kind if re.fullmatch(r"[a-z_]{1,64}", kind) else "backend_error"}
    value["invalidated"] |= kind in ("content_mismatch", "revision_mismatch", "session_mismatch")
    value["failures"] += 1
    value["sequence"] += 1
    return validate_state(value)


class SessionStore:
    """One private JSON file and lock per explicitly selected job; never pickle."""
    def __init__(self, name, url, backend_sha256, root=None, require_existing=False):
        if not isinstance(name, str) or not NAME.fullmatch(name):
            raise ReadError("invalid_input", "session 必须为1至64位字母、数字、下划线或短横线")
        self.name = name
        self.root = pathlib.Path(root) if root is not None else pathlib.Path("/tmp") / ("codex-feishu-sessions-" + str(os.getuid()))
        self.path = self.root / (name + ".json")
        self.url = parse_document_url(url, allow_files=True).url
        self.backend_sha256 = backend_sha256
        self.lock_fd = None
        self.state = None
        self.require_existing = require_existing

    def _directory(self, create):
        if create:
            try:
                self.root.mkdir(mode=0o700)
            except FileExistsError:
                pass
        info = self.root.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise ReadError("session_unavailable", "会话目录必须是当前用户拥有的独立700目录")

    @staticmethod
    def _regular(fd):
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) & 0o077:
            raise ReadError("session_unavailable", "会话文件必须为当前用户拥有的私有普通文件")
        return info

    def load(self, allow_missing=False):
        try:
            fd = os.open(str(self.path), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except FileNotFoundError:
            if allow_missing:
                return new_state(self.url, self.backend_sha256)
            raise ReadError("session_unavailable", "会话不存在；请先用session开始读取") from None
        with os.fdopen(fd, "rb") as stream:
            if self._regular(stream.fileno()).st_size > MAX_STATE:
                raise ReadError("invalid_session", "会话文件超过上限")
            raw = stream.read(MAX_STATE + 1)
        if len(raw) > MAX_STATE:
            raise ReadError("invalid_session", "会话文件超过上限")
        try:
            state = validate_state(json.loads(raw))
        except (ValueError, TypeError, KeyError, AttributeError):
            raise ReadError("invalid_session", "会话记录损坏或包含未知字段；不执行恢复") from None
        if state["url"] != self.url or state["backend_sha256"] != self.backend_sha256:
            raise ReadError("session_mismatch", "会话资源链接或固定后端身份不匹配；请使用新会话")
        return state

    def status(self):
        try:
            self._directory(False)
        except FileNotFoundError:
            raise ReadError("session_unavailable", "会话目录尚不存在") from None
        return summary(self.load())

    def __enter__(self):
        self._directory(True)
        self.lock_fd = os.open(str(self.root / (self.name + ".lock")),
                               os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        try:
            self._regular(self.lock_fd)
            fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.state = self.load(allow_missing=not self.require_existing)
        except BlockingIOError:
            os.close(self.lock_fd)
            self.lock_fd = None
            raise ReadError("session_busy", "同一session正在读取；请等待该次调用完成") from None
        except BaseException:
            os.close(self.lock_fd)
            self.lock_fd = None
            raise
        return self

    def save(self, state):
        validate_state(state)
        raw = (json.dumps(state, ensure_ascii=False, sort_keys=True) + "\n").encode()
        if len(raw) > MAX_STATE:
            raise ReadError("invalid_session", "会话覆盖记录超过大小上限；请按授权对象拆分任务")
        fd, temp = tempfile.mkstemp(prefix="." + self.name + "-", dir=str(self.root))
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, str(self.path))
            directory_fd = os.open(str(self.root), os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
        self.state = state

    def __exit__(self, *_):
        if self.lock_fd is not None:
            os.close(self.lock_fd)
            self.lock_fd = None
