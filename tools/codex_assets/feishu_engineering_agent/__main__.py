"""No-model local SDD preview. No production Bot configuration or DB is read."""
from __future__ import annotations

import argparse
import json
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
    parser.add_argument("--text", required=True, help="non-sensitive local fixture only")
    parser.add_argument("--provider", choices=("tapd", "feishu_project"))
    parser.add_argument("--workspace")
    parser.add_argument("--item-kind", choices=("requirement", "defect"))
    parser.add_argument("--item-id")
    try:
        args = parser.parse_args(argv)
        if not args.dry_run:
            parser.error("--dry-run is required; no production execution entrypoint exists")
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
