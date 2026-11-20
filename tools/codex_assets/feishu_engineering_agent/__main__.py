"""No-model local SDD preview. No production Bot configuration or DB is read."""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
from typing import Optional, Sequence

from .models import InboundEvent, IntakeRejected, WorkItemKey
from .routing import route_message


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Feishu Engineering Agent: deterministic offline intake only",
    )
    parser.add_argument("--dry-run", action="store_true", help="mandatory; never calls Codex")
    parser.add_argument("--allow-repo", action="append", default=[], metavar="ALIAS")
    parser.add_argument("--selected-repo", default="", metavar="ALIAS")
    parser.add_argument("--text", default="", help="non-sensitive local fixture only")
    parser.add_argument("--probe-runtime", action="store_true", help="no-model local Codex CLI/App Server help/version probe")
    parser.add_argument("--codex-bin", default="codex", help="PATH command name, never an arbitrary shell expression")
    parser.add_argument("--provider", choices=("tapd", "feishu_project"))
    parser.add_argument("--workspace")
    parser.add_argument("--item-kind", choices=("requirement", "defect"))
    parser.add_argument("--item-id")
    parser.add_argument("--manual", action="store_true",
                        help="no-API, local-only WorkItem registration from stdin")
    parser.add_argument("--db", default="",
                        help="absolute, private SQLite file path for --manual only")
    parser.add_argument("--event-id", default="",
                        help="caller-generated unique local command receipt ID")
    try:
        args = parser.parse_args(argv)
        if args.manual:
            if (args.dry_run or args.probe_runtime or args.text or args.provider
                    or args.workspace or args.item_kind or args.item_id
                    or args.codex_bin != "codex"):
                parser.error("--manual cannot be mixed with preview/probe/source options")
            if not args.db or not args.event_id or not args.allow_repo:
                parser.error("--manual requires --db, --event-id and --allow-repo")
            if not pathlib.Path(args.db).is_absolute():
                parser.error("--db must be an absolute private path")
            command = sys.stdin.read(12001)
            if not command or len(command) > 12000:
                parser.error("--manual expects a bounded /wi command from stdin")
            from .manual_items import ManualWorkItemService
            event = InboundEvent(
                source="offline_fixture", tenant="local", chat="terminal",
                actor="uid_" + str(os.getuid()), event_id=args.event_id,
                text=command,
            )
            result = ManualWorkItemService(args.db).handle(
                event, args.selected_repo, args.allow_repo,
            )
            print(json.dumps({
                "reply": result or "duplicate_event_ignored",
                "source_level": "user_supplied_unverified",
                "model_invoked": False, "external_api_accessed": False,
            }, ensure_ascii=False, sort_keys=True))
            return 0
        if args.db or args.event_id:
            parser.error("--db and --event-id are only for --manual")
        if args.probe_runtime:
            if (args.dry_run or args.text or args.allow_repo or args.selected_repo
                    or args.provider or args.workspace or args.item_kind or args.item_id):
                parser.error("--probe-runtime must be an independent no-model command")
            from .sessions import probe_local_app_server
            result = probe_local_app_server(args.codex_bin)
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            return 0 if result["available"] else 3
        if not args.dry_run:
            parser.error("--dry-run is required; no production execution entrypoint exists")
        if not args.text:
            parser.error("--text is required for --dry-run")
        event = InboundEvent(
            source="offline_fixture",
            tenant="offline", chat="preview", actor="fixture",
            event_id="preview-1", text=args.text,
        )
        decision = route_message(event.text, args.selected_repo, args.allow_repo)
        output = decision.as_dict()
        output["scope"] = "offline_only"
        output["runtime_accessed"] = False
        output["external_workitem_verified"] = False
        workitem_values = (args.provider, args.workspace, args.item_kind, args.item_id)
        if any(value is not None for value in workitem_values):
            if any(value is None for value in workitem_values):
                parser.error("all WorkItem source fields must be supplied together")
            key = WorkItemKey(
                args.provider, "offline", args.workspace, args.item_kind, args.item_id,
            )
            output["workitem_fingerprint"] = key.fingerprint
        print(json.dumps(output, ensure_ascii=False, sort_keys=True))
        return 0
    except IntakeRejected as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
