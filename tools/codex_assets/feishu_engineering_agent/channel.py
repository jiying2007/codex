"""Optional single-consumer Feishu channel binding; all external sends are explicit.

Adapters reuse the existing Bot's lark-oapi client. No second WebSocket
listener, scheduler or model runtime is created here.
"""
from __future__ import annotations

import contextlib
import json
from typing import Any, Callable, Mapping, Optional

from .cards import _card, accept_callback, card_ack, render_card
from .models import IntakeRejected, _check_id
from .state import RunStore


class ExternalOutcomeUnknown(IntakeRejected):
    """Network outcome may have succeeded; automatic retry is prohibited."""


def send_interactive_via_existing_transport(transport: Any, chat_id: str,
                                            card: dict) -> str:
    """Use the existing lark-oapi client; caller must be the sole Bot consumer."""
    _check_id(chat_id, "chat_id")
    request = (
        transport.CreateMessageRequest.builder()
        .receive_id_type("chat_id")
        .request_body(
            transport.CreateMessageRequestBody.builder()
            .receive_id(chat_id)
            .msg_type("interactive")
            .content(json.dumps(card, ensure_ascii=False, separators=(",", ":")))
            .build()
        ).build()
    )
    result = transport.client.im.v1.message.create(request)
    if not result.success():
        raise ExternalOutcomeUnknown("Feishu send rejected or outcome unknown")
    message_id = getattr(getattr(result, "data", None), "message_id", "")
    _check_id(message_id, "message_id")
    return message_id


class CardPublisher:
    """Persist 'sending' before the non-idempotent remote message creation."""

    def __init__(self, store: RunStore,
                 send_interactive: Callable[[str, dict], str]):
        if not callable(send_interactive):
            raise IntakeRejected("explicit sending transport required")
        self.store = store
        self.send_interactive = send_interactive
        with contextlib.closing(store._connect()) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS fea_card_delivery (
                card_id TEXT PRIMARY KEY, state TEXT NOT NULL,
                last_error TEXT NOT NULL DEFAULT ''
            )""")
            db.commit()

    def send_registered_card(
        self, card_id: str, signing_key: bytes, now: Optional[int] = None,
    ) -> str:
        """One network attempt; crash/lost ACK leaves UNKNOWN, never resend."""
        card = _card(self.store, card_id)
        if card["message_id"]:
            raise IntakeRejected("card already bound to a posted message")
        view = render_card(self.store, card_id, signing_key, now=now)
        with contextlib.closing(self.store._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                exists = db.execute(
                    "SELECT state FROM fea_card_delivery WHERE card_id=?",
                    (card_id,),
                ).fetchone()
                if exists is not None:
                    raise IntakeRejected("card send already attempted; reconcile manually")
                db.execute(
                    "INSERT INTO fea_card_delivery(card_id,state) VALUES (?,'sending')",
                    (card_id,),
                )
                db.commit()
            except Exception:
                db.rollback()
                raise
        try:
            message_id = self.send_interactive(card["chat"], view)
            _check_id(message_id, "message_id")
            with contextlib.closing(self.store._connect()) as db:
                db.execute("BEGIN IMMEDIATE")
                try:
                    row = db.execute(
                        "SELECT message_id FROM fea_cards WHERE card_id=?",
                        (card_id,),
                    ).fetchone()
                    if row is None or row["message_id"]:
                        raise IntakeRejected("card message bound or unavailable")
                    db.execute(
                        "UPDATE fea_cards SET message_id=? WHERE card_id=?",
                        (message_id, card_id),
                    )
                    db.execute(
                        "UPDATE fea_card_delivery SET state='sent' WHERE card_id=?",
                        (card_id,),
                    )
                    db.commit()
                except Exception:
                    db.rollback()
                    raise
            return message_id
        except Exception as exc:
            # Remote send and local binding can have different outcomes.
            with contextlib.closing(self.store._connect()) as db:
                db.execute(
                    "UPDATE fea_card_delivery SET state='unknown',last_error=? "
                    "WHERE card_id=?",
                    (type(exc).__name__, card_id),
                )
                db.commit()
            raise ExternalOutcomeUnknown(
                "card remote outcome UNKNOWN; inspect chat before manual recovery"
            ) from exc

    def delivery_state(self, card_id: str) -> str:
        with contextlib.closing(self.store._connect()) as db:
            row = db.execute(
                "SELECT state FROM fea_card_delivery WHERE card_id=?",
                (card_id,),
            ).fetchone()
        return row["state"] if row else "not_attempted"


def make_single_consumer_card_callback(
    store: RunStore, verification_token: str,
    app_id: str, signing_key: bytes,
) -> Callable[[Any], Any]:
    """Register with the SAME lark EventDispatcherHandler as im.receive.

    No automatic websocket start; SDK validation and CARD-frame delivery must
    be qualified on the actual pinned lark-oapi wheel before enabling.
    """
    import lark_oapi as lark
    from lark_oapi.event.callback.model.p2_card_action_trigger import (
        P2CardActionTriggerResponse,
    )

    def callback(data: Any) -> Any:
        try:
            envelope = json.loads(lark.JSON.marshal(data))
            receipt = accept_callback(
                store, envelope, verification_token, app_id, signing_key,
            )
            view = render_card(store, receipt["card_id"], signing_key)
            response = card_ack(receipt, view)
        except (IntakeRejected, ValueError, TypeError, KeyError):
            response = {
                "toast": {"type": "warning", "content": "操作未通过验证或卡片已过期"}
            }
        # Must finish without remote/model I/O in the SDK's 3-second deadline.
        return P2CardActionTriggerResponse(response)

    return callback
