"""Absolute shell entrypoint: resolve owned tools before caller packages, keeping cwd."""
from pathlib import Path
import runpy
import sys


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    runpy.run_module("tools.codex_assets", run_name="__main__")
