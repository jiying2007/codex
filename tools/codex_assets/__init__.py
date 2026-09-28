"""Codex asset repository tooling."""

import sys as _sys

if _sys.version_info < (3, 8):
    print(
        "BLOCKED: Codex asset tooling requires Python >=3.8; "
        f"current={_sys.version_info[0]}.{_sys.version_info[1]}.{_sys.version_info[2]} "
        f"executable={_sys.executable}. "
        "Use a Python 3.8 or newer interpreter. See docs/member-rollout.md.",
        file=_sys.stderr,
    )
    raise SystemExit(2)

# The pinned ADK sources import datetime.UTC (added in Python 3.11). Keep their
# exact source identity while giving older supported interpreters the same UTC
# singleton before any Execution Policy module is imported.
import datetime as _datetime

if not hasattr(_datetime, "UTC"):
    _datetime.UTC = _datetime.timezone.utc
