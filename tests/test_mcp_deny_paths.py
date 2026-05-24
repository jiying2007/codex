from __future__ import annotations

import json
import pathlib
import shutil
import tempfile
import unittest

from tools.codex_assets.mcp_deny_paths import check_mcp_deny_paths


def write_json(path: pathlib.Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


class McpDenyPathTest(unittest.TestCase):
    def make_repo(self) -> pathlib.Path:
        root = pathlib.Path(tempfile.mkdtemp(prefix="codex-mcp-deny-test-"))
        self.addCleanup(shutil.rmtree, root)
        write_json(root / "manifests/assets.json", {"schema_version": 2})
        write_json(
            root / "manifests/mcp_servers.json",
            {
                "schema_version": 2,
                "mcp_servers": [
                    {
                        "name": "docs",
                        "readiness": {
                            "deny_path_tests": [
                                {"name": "reject-auth", "path": "auth.json", "expected_decision": "deny"}
                            ]
                        },
                    }
                ],
            },
        )
        return root

    def test_valid_deny_path_tests_pass(self) -> None:
        self.assertEqual([], check_mcp_deny_paths(self.make_repo()))

    def test_rejects_non_deny_decision(self) -> None:
        root = self.make_repo()
        manifest = json.loads((root / "manifests/mcp_servers.json").read_text())
        manifest["mcp_servers"][0]["readiness"]["deny_path_tests"][0]["expected_decision"] = "allow"
        write_json(root / "manifests/mcp_servers.json", manifest)

        errors = check_mcp_deny_paths(root)
        self.assertIn("mcp_servers:docs deny_path_tests.expected_decision 必须是 deny", errors)


if __name__ == "__main__":
    unittest.main()
