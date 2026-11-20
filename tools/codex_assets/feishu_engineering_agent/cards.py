"""Feishu Card JSON 2.0 and authenticated, durable callback intents.

This module never calls a model, sends a card or grants an edit. The existing
trusted Lark event ingress must validate transport before passing callbacks.
"""
from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import sqlite3
import time
from typing import Any, Mapping, Optional

from .models import EventConflict, IntakeRejected, _check_id
from .state import RunStore

CARD_LIFETIME_SECONDS = 14 * 24 * 60 * 60
_ACTIONS = {
    "status": "查看进度",
    "request_execution": "申请执行",
    "request_cancel": "申请取消",
}


def _canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


def _sign(secret: bytes, value: Mapping[str, Any]) -> str:
    if not isinstance(secret, bytes) or len(secret) < 32:
        raise IntakeRejected("card signing key must be a private 32-byte secret")
    return hmac.new(secret, _canonical(value), hashlib.sha256).hexdigest()


def _card(store: RunStore, card_id: str) -> dict:
    _check_id(card_id, "card_id")
    with contextlib.closing(store._connect()) as db:
        row = db.execute(
            "SELECT * FROM fea_cards WHERE card_id=?", (card_id,),
        ).fetchone()
    if row is None:
        raise IntakeRejected("card not registered")
    return dict(row)


def register_card(store: RunStore, run_id: str, card_id: str, now: Optional[int] = None) -> None:
    """Register before sending; bind the actual message ID after send succeeds."""
    run = store.get_run(run_id)
    _check_id(card_id, "card_id")
    when = int(time.time()) if now is None else int(now)
    if when <= 0:
        raise IntakeRejected("invalid card creation time")
    with contextlib.closing(store._connect()) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS fea_cards (
            card_id TEXT PRIMARY KEY, run_id TEXT NOT NULL,
            tenant TEXT NOT NULL, chat TEXT NOT NULL, actor TEXT NOT NULL,
            message_id TEXT NOT NULL DEFAULT '',
            revision INTEGER NOT NULL DEFAULT 0, expires_at INTEGER NOT NULL
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS fea_card_actions (
            click_key TEXT PRIMARY KEY, content_hash TEXT NOT NULL,
            card_id TEXT NOT NULL, revision INTEGER NOT NULL,
            action TEXT NOT NULL, recorded_at INTEGER NOT NULL,
            handled_at INTEGER
        )""")
        db.execute(
            "INSERT INTO fea_cards "
            "(card_id,run_id,tenant,chat,actor,message_id,revision,expires_at) "
            "VALUES (?,?,?,?,?,'',0,?)",
            (card_id, run_id, run["tenant"], run["chat"], run["actor"],
             when + CARD_LIFETIME_SECONDS),
        )
        db.commit()


def bind_sent_message(store: RunStore, card_id: str, message_id: str) -> None:
    """Never allow reassignment to a different posted message."""
    _check_id(message_id, "message_id")
    with contextlib.closing(store._connect()) as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            row = db.execute(
                "SELECT message_id FROM fea_cards WHERE card_id=?", (card_id,),
            ).fetchone()
            if row is None or (row["message_id"] and row["message_id"] != message_id):
                raise IntakeRejected("card message binding cannot change")
            db.execute(
                "UPDATE fea_cards SET message_id=? WHERE card_id=?",
                (message_id, card_id),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise


def render_card(store: RunStore, card_id: str, signing_key: bytes,
                now: Optional[int] = None) -> dict:
    """Build an official Card JSON 2.0 object; no send or callback side effects."""
    card = _card(store, card_id)
    run = store.get_run(card["run_id"])
    when = int(time.time()) if now is None else int(now)
    if when >= card["expires_at"]:
        raise IntakeRejected("card expired, create and bind a new card")
    with contextlib.closing(store._connect()) as db:
        pending = db.execute(
            "SELECT 1 FROM fea_card_actions WHERE card_id=? "
            "AND action IN ('request_execution','request_cancel') "
            "AND handled_at IS NULL LIMIT 1",
            (card_id,),
        ).fetchone() is not None
    actions = ("status",)
    if (not pending and run["status"] not in
            ("completed", "failed", "blocked", "canceled", "unknown")):
        actions = ("status", "request_execution", "request_cancel")
    elements = [{
        "tag": "markdown",
        "content": "**仓库**：" + run["repo"] + "\n**执行状态**：" + run["status"]
                   + "\n**任务 ID**：" + run["run_id"]
                   + ("\n**操作申请**：已记录，待执行端校验" if pending else ""),
    }]
    for action in actions:
        value = {
            "card_id": card_id, "run_id": card["run_id"],
            "revision": card["revision"], "expires_at": card["expires_at"],
            "action": action,
        }
        scope = {**value, "tenant": card["tenant"],
                 "chat": card["chat"], "actor": card["actor"]}
        value["sig"] = _sign(signing_key, scope)
        elements.append({
            "tag": "button", "text": {"tag": "plain_text", "content": _ACTIONS[action]},
            "type": "default",
            "behaviors": [{"type": "callback", "value": value}],
        })
    return {
        "schema": "2.0", "config": {"update_multi": True},
        "header": {"title": {"tag": "plain_text", "content": "研发任务"}},
        "body": {"elements": elements},
    }


def accept_callback(
    store: RunStore, payload: Mapping[str, Any],
    verification_token: str, app_id: str, signing_key: bytes,
    now: Optional[int] = None,
) -> dict:
    """Validate and persist an intent BEFORE returning the 3-second card ACK.

    No network, approval, Codex invocation, Git write or run-state change.
    A future consumer must resolve the pending action under independent policy.
    """
    if not isinstance(payload, dict) or not verification_token or not app_id:
        raise IntakeRejected("invalid callback envelope")
    header = payload.get("header")
    event = payload.get("event")
    context = event.get("context") if isinstance(event, dict) else None
    if not all(isinstance(x, dict) for x in (header, event, context)):
        raise IntakeRejected("missing card callback identity")
    if (payload.get("schema") != "2.0"
            or header.get("event_type") != "card.action.trigger"
            or header.get("app_id") != app_id
            or not isinstance(header.get("token"), str)
            or not hmac.compare_digest(header["token"], verification_token)):
        raise IntakeRejected("unverified card callback origin")
    operator = event.get("operator")
    action_event = event.get("action")
    if not isinstance(operator, dict) or not isinstance(action_event, dict):
        raise IntakeRejected("missing card operator/action")
    value = action_event.get("value")
    if not isinstance(value, dict):
        raise IntakeRejected("missing signed callback value")
    required = ("card_id", "run_id", "revision", "expires_at", "action", "sig")
    if any(k not in value for k in required):
        raise IntakeRejected("incomplete callback value")
    if (value["action"] not in _ACTIONS or type(value["revision"]) is not int
            or type(value["expires_at"]) is not int or
            not isinstance(value["sig"], str)):
        raise IntakeRejected("invalid callback value")
    for name in ("card_id", "run_id"):
        _check_id(value[name], name)
    for name in ("event_id", "tenant_key"):
        _check_id(header.get(name), name)
    _check_id(operator.get("open_id"), "open_id")
    _check_id(operator.get("tenant_key"), "tenant_key")
    _check_id(context.get("open_chat_id"), "open_chat_id")
    _check_id(context.get("open_message_id"), "open_message_id")
    if (operator["tenant_key"] != header["tenant_key"]
            or event.get("host") != "im_message"):
        raise IntakeRejected("callback tenant or host mismatch")
    scope = {
        k: value[k] for k in required if k != "sig"
    }
    scope.update({
        "tenant": header["tenant_key"],
        "chat": context["open_chat_id"],
        "actor": operator["open_id"],
    })
    expected = _sign(signing_key, scope)
    if not hmac.compare_digest(value["sig"], expected):
        raise IntakeRejected("card signature mismatch")

    when = int(time.time()) if now is None else int(now)
    click_key = hashlib.sha256(_canonical({
        "event_id": header["event_id"], "tenant": header["tenant_key"],
        "chat": context["open_chat_id"], "actor": operator["open_id"],
    })).hexdigest()
    content_hash = hashlib.sha256(_canonical(scope)).hexdigest()
    with contextlib.closing(store._connect()) as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            previous = db.execute(
                "SELECT content_hash,action,card_id FROM fea_card_actions "
                "WHERE click_key=?", (click_key,),
            ).fetchone()
            if previous is not None:
                if previous["content_hash"] != content_hash:
                    raise EventConflict("card event ID reused for different action")
                db.rollback()
                return {"accepted": False, "duplicate": True,
                        "action": previous["action"], "run_id": value["run_id"],
                        "card_id": value["card_id"]}
            row = db.execute(
                "SELECT * FROM fea_cards WHERE card_id=?", (value["card_id"],),
            ).fetchone()
            if (row is None or row["run_id"] != value["run_id"]
                    or row["tenant"] != header["tenant_key"]
                    or row["actor"] != operator["open_id"]
                    or row["chat"] != context["open_chat_id"]
                    or row["message_id"] != context["open_message_id"]
                    or not row["message_id"]):
                raise IntakeRejected("card-to-message/operator binding mismatch")
            if when >= row["expires_at"] or value["expires_at"] != row["expires_at"]:
                raise IntakeRejected("card interaction expired")
            if row["revision"] != value["revision"]:
                raise IntakeRejected("stale card interaction")
            run = db.execute(
                "SELECT status FROM fea_runs WHERE run_id=?", (row["run_id"],),
            ).fetchone()
            if run is None or (
                value["action"] != "status" and
                run["status"] in ("completed", "failed", "blocked", "canceled", "unknown")
            ):
                raise IntakeRejected("action unavailable in current run state")
            if value["action"] != "status":
                prior_mutation = db.execute(
                    "SELECT 1 FROM fea_card_actions WHERE card_id=? "
                    "AND revision=? AND action IN "
                    "('request_execution','request_cancel') LIMIT 1",
                    (value["card_id"], value["revision"]),
                ).fetchone()
                if prior_mutation is not None:
                    raise IntakeRejected("card revision action already accepted")
            db.execute(
                "INSERT INTO fea_card_actions "
                "(click_key,content_hash,card_id,revision,action,recorded_at) "
                "VALUES (?,?,?,?,?,?)",
                (click_key, content_hash, value["card_id"], value["revision"],
                 value["action"], when),
            )
            if value["action"] != "status":
                db.execute(
                    "UPDATE fea_cards SET revision=revision+1 WHERE card_id=?",
                    (value["card_id"],),
                )
            db.commit()
        except sqlite3.IntegrityError as exc:
            db.rollback()
            raise IntakeRejected("card action already consumed") from exc
        except Exception:
            db.rollback()
            raise
    return {"accepted": True, "duplicate": False,
            "action": value["action"], "run_id": value["run_id"],
            "card_id": value["card_id"], "run_status": run["status"]}


def card_ack(receipt: Mapping[str, Any], card: Optional[dict] = None) -> dict:
    """A bounded synchronous toast; no claim that the action ran."""
    if not receipt["accepted"]:
        message = "重复操作已忽略"
    elif receipt["action"] == "status":
        message = "当前执行状态：" + receipt.get("run_status", "unknown")
    else:
        message = "请求已记录，等待执行端核验"
    answer = {"toast": {"type": "info", "content": message}}
    if card is not None:
        answer["card"] = {"type": "raw", "data": card}
    return answer


def pending_actions(store: RunStore, limit: int = 20) -> list:
    """Inspect durable action intents; no implicit executor is started."""
    if not 1 <= limit <= 100:
        raise IntakeRejected("invalid pending-action limit")
    with contextlib.closing(store._connect()) as db:
        rows = db.execute(
            "SELECT click_key,card_id,revision,action FROM fea_card_actions "
            "WHERE handled_at IS NULL ORDER BY recorded_at,click_key LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]
