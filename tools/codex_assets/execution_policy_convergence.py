"""Host argument adaptation for a source-verified ADK convergence capability.

No engine code is copied here. Unsupported pinned providers fail explicitly.
"""
from __future__ import annotations

from argparse import Namespace
from typing import Any

from .core import CodexAssetError
from .execution_policy import decision as engine


def require_capability() -> None:
    if getattr(engine, "CONVERGENCE_CONTRACT", None) != "execution_policy.convergence/v1":
        raise CodexAssetError("ADK convergence capability unavailable: import a signed exact provider source set first")


def progress_payload(args: Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {"revision": args.revision}
    fields = {"criterion_id": args.criterion_id, "change_kind": args.change_kind,
              "evidence_ids": args.evidence_id, "plan_before_sha256": args.plan_before_sha256,
              "plan_after_sha256": args.plan_after_sha256, "adjustment": args.adjustment}
    supplied = {key: value for key, value in fields.items() if value is not None}
    if not supplied:
        return payload
    require_capability()
    required = {"criterion_id", "change_kind", "evidence_ids"}
    replan = {"plan_before_sha256", "plan_after_sha256", "adjustment"}
    expected = required | replan if args.change_kind == "replan" else required
    if set(supplied) != expected:
        raise CodexAssetError("progress requires criterion, change kind and evidence; replan also requires before/after plans and adjustment")
    payload.update(supplied)
    return payload


def milestone(state, policy, *, criterion_id: str, verifier=None) -> dict[str, Any]:
    require_capability()
    return engine.evaluate_milestone(state, policy, criterion_id=criterion_id, mode_authority_verifier=verifier)
