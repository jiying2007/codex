"""Codex asset repository tooling."""

import sys as _sys

# ADK requires 3.11. Fail before loading CLI/SDK/policy code, also for submodules
# launched with python -m. Do not switch interpreters or alter vendored sources.
if _sys.version_info < (3, 11):
    print(
        "BLOCKED: Codex asset tooling requires Python >=3.11; "
        f"current={_sys.version_info[0]}.{_sys.version_info[1]}.{_sys.version_info[2]} "
        f"executable={_sys.executable}. "
        "Activate a Python 3.11/3.12 virtual environment and retry. "
        "See docs/member-rollout.md. Do not replace system Python or edit vendored ADK files.",
        file=_sys.stderr,
    )
    raise SystemExit(2)
