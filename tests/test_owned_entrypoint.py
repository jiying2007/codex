import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class OwnedEntrypointTests(unittest.TestCase):
    def test_caller_tools_package_cannot_shadow_policy_cli(self):
        with tempfile.TemporaryDirectory() as temp:
            cwd = Path(temp)
            (cwd / "tools").mkdir()
            (cwd / "tools/__init__.py").write_text("raise RuntimeError('caller tools imported')")
            for python_path in ("", ".", str(cwd)):
                with self.subTest(python_path=python_path):
                    environment = dict(os.environ, PYTHONPATH=python_path)
                    result = subprocess.run(
                        ["bash", str(ROOT / "scripts/codex-policy.sh"), "gate", "--help"],
                        cwd=cwd, env=environment, capture_output=True, text=True,
                        timeout=20,
                    )
                    self.assertEqual(0, result.returncode, result.stderr)
                    self.assertIn("--event", result.stdout)
                    self.assertNotIn("caller tools imported", result.stderr)


if __name__ == "__main__":
    unittest.main()
