"""Host-only, no-model migration inspection/snapshot/rehearsal command.

No service stop/start, consumer cutover or credential disclosure. Backup is
explicit and must follow an operator's real single-consumer freeze procedure.
"""
from __future__ import annotations

import argparse
import json
import pathlib
from typing import Optional, Sequence

from .migration import MigrationPlan, MigrationRejected


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Feishu Agent safe migration prep")
    parser.add_argument("action", choices=("inspect", "backup", "rehearse"))
    parser.add_argument("--db", default="")
    parser.add_argument("--spool", default="")
    parser.add_argument("--private-policy", default="")
    parser.add_argument("--private-env", default="", help="optional private environment file; backup remains sensitive")
    parser.add_argument("--backup-dir", default="")
    parser.add_argument("--consumer-paused", action="store_true",
                        help="operator has verified old consumer is stopped/frozen")
    args = parser.parse_args(argv)
    try:
        if args.action == "rehearse":
            if not args.backup_dir or args.db or args.spool or args.private_policy or args.private_env or args.consumer_paused:
                parser.error("rehearse needs only --backup-dir")
            report = MigrationPlan.rehearse_restore(pathlib.Path(args.backup_dir))
        else:
            if not args.db or not args.spool:
                parser.error("inspect/backup require --db and --spool")
            plan = MigrationPlan(
                pathlib.Path(args.db), pathlib.Path(args.spool),
                pathlib.Path(args.private_policy) if args.private_policy else None,
                pathlib.Path(args.private_env) if args.private_env else None,
            )
            if args.action == "inspect":
                if args.backup_dir or args.consumer_paused:
                    parser.error("inspect may not write a backup")
                report = plan.inspect()
            else:
                if not args.backup_dir or not args.consumer_paused:
                    parser.error("backup requires --backup-dir and --consumer-paused")
                report = plan.backup(pathlib.Path(args.backup_dir))
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0
    except MigrationRejected as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
