"""Local read-only boundary around the unmodified official Lark CLI."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import time
from typing import Any, Dict, Mapping, Sequence

from .feishu_codex_bot import ApplicationCredentials, FeishuCodexError, FeishuTransport, load_env_file
from .feishu_documents import checked_range, checked_token, parse_document_url
from .feishu_cli_coverage import coverage_receipt, document_coverage, revision_of, sheet_coverage

ALLOWED = ("wiki/+node-get", "docs/+fetch", "sheets/+workbook-info", "sheets/+csv-get", "sheets/+cells-get")
SECRET_KEYS = {"access_token", "tenant_access_token", "user_access_token", "app_secret", "appsecret", "authorization"}
BLOCK_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}")
MAX_RESPONSE = 2 * 1024 * 1024


class ReadError(ValueError):
    def __init__(self, kind: str, message: str, details: Any = None) -> None:
        super().__init__(message)
        self.kind, self.details = kind, details


def digest(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def redact(value: Any, secrets: Sequence[str]) -> Any:
    if isinstance(value, dict):
        return {key: ("REDACTED" if key.lower() in SECRET_KEYS else redact(item, secrets)) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item, secrets) for item in value]
    if isinstance(value, str):
        for secret in secrets:
            if secret:
                value = value.replace(secret, "REDACTED")
    return value


def continuation(data: Mapping[str, Any], requested: str) -> Dict[str, Any]:
    return sheet_coverage(data, requested)


class Backend:
    def __init__(self, root: pathlib.Path, runtime: pathlib.Path) -> None:
        self.root, self.runtime = root, runtime
        self.meta = json.loads((root / "manifests/feishu_cli.json").read_text())
        if tuple(self.meta.get("allowed_commands", ())) != ALLOWED or self.meta.get("writes_allowed") is not False:
            raise ReadError("policy_invalid", "只读命令契约无效")
        self.binary = root / self.meta["binary_rel"]
        if self.binary.is_symlink() or not self.binary.is_file() or digest(self.binary) != self.meta["binary_sha256"]:
            raise ReadError("backend_unavailable", "官方 CLI 未安装或来源哈希不匹配")
        policy = root / self.meta["policy_rel"]
        if policy.is_symlink() or not policy.is_file():
            raise ReadError("policy_invalid", "缺少只读策略文件")
        shutil.copyfile(policy, runtime / "policy.yml")
        self.env = {key: os.environ[key] for key in ("PATH", "HOME", "LANG", "LC_ALL") if key in os.environ}
        self.env.update({"LARKSUITE_CLI_CONFIG_DIR": str(runtime), "LARKSUITE_CLI_BRAND": "feishu",
                         "LARKSUITE_CLI_STRICT_MODE": "bot", "LARKSUITE_CLI_DEFAULT_AS": "bot"})
        self.secrets = []
        self.deadline = time.monotonic() + 90
        self.verify_policy()

    def invoke(self, argv: Sequence[str]) -> Dict[str, Any]:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise ReadError("timeout", "本次读取超过总时限")
        try:
            result = subprocess.run([str(self.binary), *argv], cwd=str(self.runtime), env=self.env,
                                    capture_output=True, text=True, timeout=min(30, remaining))
        except subprocess.TimeoutExpired:
            raise ReadError("timeout", "官方 CLI 读取超时") from None
        except OSError:
            raise ReadError("backend_unavailable", "官方 CLI 无法执行") from None
        raw = result.stdout if result.returncode == 0 else result.stderr or result.stdout
        if len(raw.encode()) > MAX_RESPONSE:
            raise ReadError("response_too_large", "响应超过 2 MiB；请缩小读取范围")
        try:
            payload = json.loads(raw)
        except ValueError:
            raise ReadError("invalid_response", "官方 CLI 未返回完整 JSON") from None
        if not isinstance(payload, dict):
            raise ReadError("invalid_response", "官方 CLI 返回格式无效")
        if result.returncode:
            error = redact(payload.get("error", {}), self.secrets)
            raise ReadError("backend_error", "官方飞书读取失败", error)
        return payload

    def verify_policy(self) -> None:
        active = self.invoke(["config", "policy", "show"])
        rules = active.get("rules", [])
        if active.get("source") != "yaml" or not isinstance(rules, list) or len(rules) != 1 or not isinstance(rules[0], dict):
            raise ReadError("policy_invalid", "官方 CLI 未加载只读策略")
        rule = rules[0]
        if (rule.get("max_risk") != "read" or rule.get("identities") != ["bot"]
                or tuple(rule.get("allow", ())) != ALLOWED or rule.get("allow_unannotated") is not False):
            raise ReadError("policy_invalid", "官方 CLI 的有效策略与本机契约不一致")

    def authenticate(self) -> None:
        from lark_oapi.api.auth.v3 import InternalTenantAccessTokenRequest, InternalTenantAccessTokenRequestBody
        values = load_env_file(self.root / "mcp/secrets/feishu.env")
        credentials = ApplicationCredentials(values.get("FEISHU_APP_ID", ""), values.get("FEISHU_APP_SECRET", ""))
        if not credentials.app_id or not credentials.app_secret:
            raise ReadError("credentials_missing", "缺少本机应用凭据")
        self.secrets.append(credentials.app_secret)
        client = FeishuTransport(credentials).client
        request = InternalTenantAccessTokenRequest.builder().request_body(
            InternalTenantAccessTokenRequestBody.builder().app_id(credentials.app_id)
            .app_secret(credentials.app_secret).build()).build()
        try:
            response = client.auth.v3.tenant_access_token.internal(request)
            payload = json.loads(response.raw.content) if response.success() else {}
        except Exception:
            raise ReadError("authentication_failed", "本机应用身份认证失败") from None
        token = payload.get("tenant_access_token")
        if not isinstance(token, str) or not token:
            raise ReadError("authentication_failed", "未取得有效的短期应用 token")
        self.secrets.append(token)
        self.env.update({"LARKSUITE_CLI_APP_ID": credentials.app_id, "LARKSUITE_CLI_TENANT_ACCESS_TOKEN": token})

    def read(self, command: str, flags: Sequence[str]) -> Dict[str, Any]:
        if command not in ALLOWED:
            raise ReadError("command_denied", "仅允许已登记的飞书只读命令")
        payload = self.invoke([*command.split("/"), *flags, "--as", "bot"])
        if payload.get("ok") is not True or payload.get("identity") != "bot" or not isinstance(payload.get("data"), dict):
            raise ReadError("invalid_response", "官方 CLI 未确认 bot 读取成功")
        return redact(payload["data"], self.secrets)


def validate_input(args: argparse.Namespace) -> None:
    reference = parse_document_url(args.url)
    if not 1000 <= args.max_chars <= 25000:
        raise ReadError("invalid_input", "max-chars 必须为 1000 至 25000")
    if args.range:
        checked_range(args.range)
    if args.sheet_id:
        checked_token(args.sheet_id)
    if args.expected_revision and not re.fullmatch(r"[0-9]{1,18}", args.expected_revision):
        raise ReadError("invalid_input", "expected-revision 必须为非负数字版本")
    if args.revision_id != -1 and not 1 <= args.revision_id <= 2**63 - 1:
        raise ReadError("invalid_input", "revision-id 必须为正整数或 -1")
    if not -1 <= args.max_depth <= 100:
        raise ReadError("invalid_input", "max-depth 必须为 -1 至 100")
    if args.include and (args.format != "cells" or args.action != "read"):
        raise ReadError("invalid_input", "include 仅用于 read --format cells")
    if args.include and not set(args.include.split(",")) <= {"value", "formula", "style", "comment", "data_validation", "conditional_format", "truncation"}:
        raise ReadError("invalid_input", "include 包含不支持的单元格信息类别")
    if args.format == "cells" and (args.action != "read" or reference.kind == "docx"):
        raise ReadError("invalid_input", "cells 模式仅用于读取电子表格")
    if reference.kind == "sheets" and (args.action == "catalog" or args.revision_id != -1
            or args.start_block or args.end_block or args.max_depth != -1 or args.scope != "outline" or args.keyword):
        raise ReadError("invalid_input", "文档参数不能用于电子表格")
    if reference.kind == "docx" and (reference.sheet or reference.cell_range or args.sheet_id or args.range):
        raise ReadError("invalid_input", "文档读取不能使用表格范围参数")
    if args.action != "read":
        if args.scope != "outline" or args.keyword or args.start_block or args.end_block or args.include:
            raise ReadError("invalid_input", "inspect/catalog 不接受正文选择参数")
        return
    # Wiki target type is resolved later; explicit document parameters are
    # still validated before credentials and during dry-run.
    if args.scope == "keyword" and not args.keyword:
        raise ReadError("invalid_input", "keyword 读取需要 --keyword")
    if args.keyword and args.scope != "keyword":
        raise ReadError("invalid_input", "keyword 参数仅适用于 keyword scope")
    if args.scope == "section" and (not args.start_block or args.end_block):
        raise ReadError("invalid_input", "section 需要 --start-block，不能使用 --end-block")
    if args.scope == "range" and not (args.start_block or args.end_block):
        raise ReadError("invalid_input", "range 需要 --start-block 或 --end-block")
    if (args.start_block or args.end_block) and args.scope not in ("range", "section"):
        raise ReadError("invalid_input", "块端点仅适用于 range/section")
    for value, sentinel in ((args.start_block, "0"), (args.end_block, "-1")):
        if value and value != sentinel and not BLOCK_ID.fullmatch(value):
            raise ReadError("invalid_input", "文档块标识无效")
    if args.scope == "section" and args.start_block == "0":
        raise ReadError("invalid_input", "section 需要真实标题/块 ID，不能使用文档起点 0")


def check_revision(data: Mapping[str, Any], args: argparse.Namespace) -> Optional[str]:
    revision = revision_of(data)
    expected = args.expected_revision
    if expected and revision != expected:
        raise ReadError("revision_mismatch", "资源版本变化或不可核验；本段不得并入原覆盖记录",
                        {"expected_revision": expected, "actual_revision": revision})
    if args.revision_id > 0 and revision != str(args.revision_id):
        raise ReadError("revision_mismatch", "文档未返回指定版本", {"expected_revision": str(args.revision_id), "actual_revision": revision})
    return revision


def finish(source: Mapping[str, Any], data: Dict[str, Any], coverage: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    revision = check_revision(data, args)
    coverage["revision"] = revision
    coverage["revision_check"] = "matched" if args.expected_revision or args.revision_id > 0 else "unbound"
    return {"ok": True, "identity": "bot", "source": dict(source), "data": data, "coverage": coverage,
            "receipt": coverage_receipt(source, coverage, revision)}


def fetch(backend: Backend, args: argparse.Namespace) -> Dict[str, Any]:
    validate_input(args)
    reference = parse_document_url(args.url)
    kind, token = reference.kind, reference.token
    if kind == "wiki":
        node = backend.read("wiki/+node-get", ["--node-token", reference.url])
        kind, token = node.get("obj_type"), checked_token(node.get("obj_token"))
    source = {"url": reference.url, "type": kind, "token": token, "trust": "untrusted_external_content"}
    if kind in ("sheet", "sheets"):
        if args.action == "catalog" or args.revision_id != -1 or args.start_block or args.end_block or args.max_depth != -1 or args.scope != "outline" or args.keyword:
            raise ReadError("invalid_input", "文档参数不能用于电子表格")
        if args.action == "inspect":
            data = backend.read("sheets/+workbook-info", ["--spreadsheet-token", token])
            return finish(source, data, {"status": "structure-only", "whole_resource_complete": False}, args)
        sheet = args.sheet_id or reference.sheet
        if not sheet:
            raise ReadError("selection_required", "请先 inspect 查看工作表，再传 --sheet-id；不按索引猜工作表")
        checked_token(sheet)
        cell_range = checked_range(args.range or reference.cell_range or "A1:T50")
        flags = ["--spreadsheet-token", token, "--sheet-id", sheet,
                 "--range", cell_range, "--max-chars", str(args.max_chars)]
        if args.format == "cells":
            if args.include:
                flags.extend(["--include", args.include])
            command = "sheets/+cells-get"
        else:
            command = "sheets/+csv-get"
        data = backend.read(command, flags)
        if args.format == "csv" and not isinstance(data.get("annotated_csv"), str):
            raise ReadError("invalid_response", "表格响应缺少 CSV 正文")
        if args.format == "cells" and not isinstance(data.get("ranges"), list):
            raise ReadError("invalid_response", "单元格响应缺少 ranges")
        return finish(dict(source, sheet_id=sheet, read_format=args.format), data, continuation(data, cell_range), args)
    if kind != "docx":
        raise ReadError("unsupported_type", "本次只接入新版文档和电子表格；多维表格需另行接入")
    if reference.sheet or reference.cell_range or args.sheet_id or args.range or args.format == "cells":
        raise ReadError("invalid_input", "文档读取不能使用表格参数")
    scope = "outline" if args.action == "inspect" else "range" if args.action == "catalog" else args.scope
    start, end = ("0", "-1") if args.action == "catalog" else (args.start_block, args.end_block)
    depth = 0 if args.action == "catalog" else args.max_depth
    flags = ["--doc", token, "--scope", scope, "--detail", "with-ids", "--doc-format", "xml"]
    if scope == "keyword":
        flags.extend(["--keyword", args.keyword])
    if start:
        flags.extend(["--start-block-id", start])
    if end:
        flags.extend(["--end-block-id", end])
    if depth != -1:
        flags.extend(["--max-depth", str(depth)])
    if args.revision_id > 0:
        flags.extend(["--revision-id", str(args.revision_id)])
    data = backend.read("docs/+fetch", flags)
    if not isinstance(data.get("document"), dict) or not isinstance(data["document"].get("content"), str):
        raise ReadError("invalid_response", "文档响应缺少正文")
    coverage = document_coverage(data, scope, start, end, depth)
    # Validate the version even when the content exceeds the output budget.
    revision = check_revision(data, args)
    if len(json.dumps(data, ensure_ascii=False)) > args.max_chars:
        hints = {"revision": revision, "scope": scope, "block_ids": coverage["block_ids"][:200],
                 "top_level_block_ids": coverage["top_level_block_ids"][:200],
                 "catalog_hint_complete": bool(coverage["top_level_block_ids"]) and coverage["full_document_requested"]
                    and not coverage["excerpts"] and not coverage["truncation_signals"]
                    and len(coverage["top_level_block_ids"]) <= 200,
                 "next_action": "使用 catalog 或有界 range 继续，必须覆盖无标题正文和首标题前内容"}
        raise ReadError("content_budget_exceeded", "正文超预算；返回块定位提示，不截断正文。请按有界块范围缩小读取。", hints)
    result = finish(source, data, coverage, args)
    result["scope"] = scope
    return result


def configure_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("action", choices=["inspect", "catalog", "read"])
    parser.add_argument("--url", required=True)
    parser.add_argument("--sheet-id", default="")
    parser.add_argument("--range", default="")
    parser.add_argument("--scope", choices=["outline", "section", "range", "keyword", "full"], default="outline")
    parser.add_argument("--keyword", default="")
    parser.add_argument("--start-block", default="")
    parser.add_argument("--end-block", default="")
    parser.add_argument("--max-depth", type=int, default=-1)
    parser.add_argument("--revision-id", type=int, default=-1)
    parser.add_argument("--expected-revision", default="")
    parser.add_argument("--format", choices=["csv", "cells"], default="csv")
    parser.add_argument("--include", default="")
    parser.add_argument("--max-chars", type=int, default=8000)
    parser.add_argument("--dry-run", action="store_true")


def run(args: argparse.Namespace) -> int:
    try:
        validate_input(args)
        reference = parse_document_url(args.url)
        if args.dry_run:
            print(json.dumps({"ok": True, "dry_run": True, "network_requested": False,
                              "credentials_loaded": False, "url": reference.url, "action": args.action,
                              "target_type_requires_resolution": reference.kind == "wiki"}, ensure_ascii=False))
            return 0
        root = pathlib.Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory(prefix="codex-feishu-read-") as temp:
            backend = Backend(root, pathlib.Path(temp))
            backend.authenticate()
            result = fetch(backend, args)
            result["backend"] = {"name": "larksuite/cli", "version": "1.0.97", "identity": "bot"}
            result["receipt"]["backend"] = dict(result["backend"])
            print(json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, FeishuCodexError, ImportError):
        print(json.dumps({"ok": False, "error": {"kind": "local_config_unavailable", "message": "本机配置不可用；请检查受管安装及凭据权限"}}, ensure_ascii=False))
        return 2
    except (ReadError, ValueError) as exc:
        error = {"kind": getattr(exc, "kind", "invalid_input"), "message": str(exc)}
        if getattr(exc, "details", None) is not None:
            error["details"] = exc.details
        print(json.dumps({"ok": False, "error": error}, ensure_ascii=False))
        return 2
