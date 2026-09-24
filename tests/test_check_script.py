from __future__ import annotations

import pathlib
import os
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
CHECK = ROOT / "scripts" / "check.sh"


class CheckScriptCliTest(unittest.TestCase):
    def run_check(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(CHECK), *args],
            cwd="/tmp",
            check=False,
            capture_output=True,
            text=True,
        )

    def test_help_is_side_effect_free(self) -> None:
        result = self.run_check("--help")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("Usage: scripts/check.sh", result.stdout)
        self.assertIn("--pre-apply", result.stdout)
        self.assertIn("--no-build", result.stdout)
        self.assertIn("--plan PATH", result.stdout)
        self.assertNotIn("[DONE] build", result.stdout)

    def test_unknown_argument_fails_closed(self) -> None:
        result = self.run_check("--unknown")
        self.assertEqual(2, result.returncode)
        self.assertIn("[FATAL] 未知参数: --unknown", result.stderr)

    def test_target_requires_a_path(self) -> None:
        result = self.run_check("--target")
        self.assertEqual(2, result.returncode)
        self.assertIn("[FATAL] --target 缺少路径参数", result.stderr)

    def test_plan_requires_a_path(self) -> None:
        result = self.run_check("--plan")
        self.assertEqual(2, result.returncode)
        self.assertIn("[FATAL] --plan 缺少路径参数", result.stderr)

    def test_execution_policy_help_is_side_effect_free_from_non_repo_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            result = subprocess.run(
                [sys.executable, "-m", "tools.codex_assets", "execution-policy", "--help"],
                cwd=home,
                env={**os.environ, "HOME": home, "PYTHONPATH": str(ROOT)},
                check=False, capture_output=True, text=True, timeout=15,
            )
            self.assertEqual([], list(pathlib.Path(home).iterdir()))
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("codex-assets execution-policy", result.stdout)
        self.assertNotIn("[DONE] build", result.stdout)


if __name__ == "__main__":
    unittest.main()
