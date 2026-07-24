from __future__ import annotations

import pathlib
import subprocess
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
CHECK = ROOT / "scripts" / "check.sh"


class CheckScriptCliTest(unittest.TestCase):
    def run_check(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["rtk", "bash", str(CHECK), *args],
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
        self.assertNotIn("[DONE] build", result.stdout)

    def test_unknown_argument_fails_closed(self) -> None:
        result = self.run_check("--unknown")
        self.assertEqual(2, result.returncode)
        self.assertIn("[FATAL] 未知参数: --unknown", result.stderr)

    def test_target_requires_a_path(self) -> None:
        result = self.run_check("--target")
        self.assertEqual(2, result.returncode)
        self.assertIn("[FATAL] --target 缺少路径参数", result.stderr)


if __name__ == "__main__":
    unittest.main()
