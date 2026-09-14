from __future__ import annotations
import pathlib, subprocess, sys, unittest
ROOT = pathlib.Path(__file__).resolve().parents[1]
class RetiredProfileTest(unittest.TestCase):
    def test_token_lean_selector_fails_closed(self) -> None:
        p = subprocess.run([sys.executable,"-m","tools.codex_assets","skill-search","--root",str(ROOT),"--query","skill asset","--profile","token-lean","--summary-json"],cwd=ROOT,text=True,capture_output=True,check=False)
        self.assertEqual(2,p.returncode)
        self.assertIn("profile 未定义: token-lean",p.stderr)
if __name__ == "__main__": unittest.main()
