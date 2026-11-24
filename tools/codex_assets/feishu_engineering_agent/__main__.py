"""No-model preview using the same link parser and intents as the Bot."""
from __future__ import annotations

import argparse
import dataclasses
import json
from typing import Optional, Sequence

from .models import IntakeRejected, check_repo_alias
from .service import intent_for
from .sources import parse_sources


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Feishu Engineering Agent: no-model link preview and CLI probe",
    )
    parser.add_argument("--dry-run", action="store_true", help="parse only; no state or model access")
    parser.add_argument("--text", default="", help="non-sensitive local fixture only")
    parser.add_argument("--allow-repo", action="append", default=[], metavar="ALIAS")
    parser.add_argument("--selected-repo", default="", metavar="ALIAS")
    parser.add_argument("--probe-runtime", action="store_true", help="CLI version and exec/resume help only")
    parser.add_argument("--codex-bin", default="codex", help="PATH executable name")
    args = parser.parse_args(argv)
    try:
        if args.probe_runtime:
            if args.dry_run or args.text or args.allow_repo or args.selected_repo:
                parser.error("--probe-runtime must be an independent no-model command")
            from .sessions import probe_local_cli
            result = probe_local_cli(args.codex_bin)
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            return 0 if result["available"] else 3
        if not args.dry_run or not args.text.strip():
            parser.error("--dry-run and bounded --text are required; legacy --manual is retired")
        if args.codex_bin != "codex":
            parser.error("--codex-bin is only for --probe-runtime")
        if len(args.text) > 12000 or "\0" in args.text:
            raise IntakeRejected("preview text must be bounded and contain no NUL")
        allowed = {check_repo_alias(alias) for alias in args.allow_repo}
        if args.selected_repo and check_repo_alias(args.selected_repo) not in allowed:
            raise IntakeRejected("selected repository must be explicitly allowlisted")
        sources = parse_sources(args.text)
        intent, _ = intent_for(args.text)
        print(json.dumps({
            "scope": "offline_preview",
            "sources": [dataclasses.asdict(source) for source in sources],
            "source_level": "link_unverified",
            "intent": intent,
            "repo": args.selected_repo,
            "state_accessed": False,
            "runtime_accessed": False,
            "external_api_accessed": False,
            "model_invoked": False,
            "run_enqueued": False,
        }, ensure_ascii=False, sort_keys=True))
        return 0
    except IntakeRejected as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
