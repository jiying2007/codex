from __future__ import annotations

import argparse
import pathlib
import sys
from typing import Any

from .core import Repo
from .governance import optional_manifest_items, unsafe_path


def check_mcp_deny_paths(root: str | pathlib.Path) -> list[str]:
    repo = Repo.from_path(root)
    errors: list[str] = []
    servers = optional_manifest_items(repo, "mcp_servers.json", "mcp_servers")
    for server in servers:
        name = str(server.get("name", ""))
        readiness = server.get("readiness", {})
        if not isinstance(readiness, dict):
            errors.append(f"mcp_servers:{name} readiness 必须是 object")
            continue
        tests = readiness.get("deny_path_tests", [])
        if not isinstance(tests, list) or not tests:
            errors.append(f"mcp_servers:{name} deny_path_tests 不能为空")
            continue
        for item in tests:
            if not isinstance(item, dict):
                errors.append(f"mcp_servers:{name} deny_path_tests 条目必须是 object")
                continue
            errors.extend(validate_test(name, item))
    return errors


def validate_test(server_name: str, item: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    name = str(item.get("name", ""))
    path = str(item.get("path", ""))
    expected = str(item.get("expected_decision", ""))
    if not name:
        errors.append(f"mcp_servers:{server_name} deny_path_tests.name 不能为空")
    if not path:
        errors.append(f"mcp_servers:{server_name} deny_path_tests.path 不能为空")
    elif unsafe_path(path):
        errors.append(f"mcp_servers:{server_name} deny_path_tests.path 包含不安全路径: {path}")
    if expected != "deny":
        errors.append(f"mcp_servers:{server_name} deny_path_tests.expected_decision 必须是 deny")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate executable MCP deny-path guard declarations.")
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument("--json", action="store_true", help="reserved for future machine-readable output")
    args = parser.parse_args(argv)
    errors = check_mcp_deny_paths(args.root)
    if errors:
        for error in errors:
            print(f"[ERROR] {error}", file=sys.stderr)
        return 1
    print("[INFO ] mcp_deny_path_tests=pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
