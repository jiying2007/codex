"""Interpreter preflight, runnable with stdlib only on supported/old Python."""
from __future__ import annotations

import contextlib
import io
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "tools/codex_assets/__init__.py"


class PythonRuntimeTests(unittest.TestCase):
    def test_old_python_has_actionable_exit_before_imports(self) -> None:
        for version in ((3, 9, 20), (3, 10, 19)):
            error = io.StringIO()
            with self.subTest(version=version):
                with mock.patch.object(sys, "version_info", version), contextlib.redirect_stderr(error):
                    with self.assertRaises(SystemExit) as caught:
                        runpy.run_path(str(PACKAGE))
                self.assertEqual(2, caught.exception.code)
                self.assertIn("requires Python >=3.11", error.getvalue())
                self.assertIn("current=" + ".".join(map(str, version)), error.getvalue())
                self.assertIn(sys.executable, error.getvalue())
                self.assertIn("virtual environment", error.getvalue())

    def test_supported_boundary_has_no_output_or_interpreter_switch(self) -> None:
        for version in ((3, 11, 0), (3, 12, 0)):
            output, error = io.StringIO(), io.StringIO()
            with self.subTest(version=version), mock.patch.object(sys, "version_info", version):
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
                    with mock.patch.object(os, "execv", side_effect=AssertionError("must not switch Python")):
                        runpy.run_path(str(PACKAGE))
            self.assertEqual("", output.getvalue())
            self.assertEqual("", error.getvalue())

    def launch(self, code: str, cwd: Path) -> subprocess.CompletedProcess[str]:
        env = {**os.environ, "HOME": str(cwd / "home"), "PYTHONPATH": str(ROOT),
               "PYTHONDONTWRITEBYTECODE": "1"}
        return subprocess.run([sys.executable, "-B", "-S", "-c", code],
                              cwd=cwd, env=env, text=True, capture_output=True,
                              timeout=15, check=False)

    def assert_blocked(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual(2, result.returncode, result.stderr)
        self.assertEqual("", result.stdout)
        self.assertIn("requires Python >=3.11", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertNotIn("ImportError", result.stderr)
        self.assertNotIn("No module named", result.stderr)

    def test_all_module_entrypoints_reject_before_dependencies_or_writes(self) -> None:
        for module in ("tools.codex_assets", "tools.codex_assets.session_bootstrap",
                       "tools.codex_assets.adk_skill_audit"):
            with self.subTest(module=module), tempfile.TemporaryDirectory() as tmp:
                cwd = Path(tmp)
                code = ("import runpy, sys; sys.version_info=(3,10,19); "
                        "sys.argv=['tool','build','--root','.','--target','home/.codex']; "
                        f"runpy.run_module({module!r}, run_name='__main__')")
                self.assert_blocked(self.launch(code, cwd))
                self.assertEqual([], list(cwd.iterdir()))

    def test_importing_submodule_cannot_bypass_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code = "import sys; sys.version_info=(3,10,19); import tools.codex_assets.core"
            self.assert_blocked(self.launch(code, Path(tmp)))

    def test_real_interpreter_without_site_packages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            if sys.version_info < (3, 11):
                code = "import runpy; runpy.run_module('tools.codex_assets', run_name='__main__')"
                self.assert_blocked(self.launch(code, cwd))
            else:
                result = self.launch("import tools.codex_assets; print('preflight-ok')", cwd)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual("preflight-ok\n", result.stdout)
                self.assertEqual("", result.stderr)
            self.assertEqual([], list(cwd.iterdir()))


if __name__ == "__main__":
    unittest.main()
