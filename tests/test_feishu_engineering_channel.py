"""Feishu channel binding tests: mock transport, no network or model."""
from __future__ import annotations

import pathlib
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from tools.codex_assets.feishu_engineering_agent.cards import register_card
from tools.codex_assets.feishu_engineering_agent.channel import (
    CardPublisher, ExternalOutcomeUnknown, send_interactive_via_existing_transport,
)
from tools.codex_assets.feishu_engineering_agent.models import (
    InboundEvent, IntakeRejected,
)
from tools.codex_assets.feishu_engineering_agent.state import RunStore

KEY = b"independent-private-test-card-key-32-bytes-minimum"
NOW = 1800000000


class CardChannelTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="fea-channel-")
        self.addCleanup(tmp.cleanup)
        self.store = RunStore(pathlib.Path(tmp.name) / "state.sqlite3")
        event = InboundEvent(
            "feishu_message", "tenantA", "oc_team", "ou_owner", "om_in",
            "分析日志",
        )
        run = self.store.create_run(event, "robot-app", {"robot-app"})
        register_card(self.store, run, "card_1", now=NOW)

    def test_publish_once_binds_remote_id_and_no_repeat(self):
        sender = mock.Mock(return_value="om_card")
        publisher = CardPublisher(self.store, sender)
        self.assertEqual(
            "om_card", publisher.send_registered_card("card_1", KEY, now=NOW)
        )
        self.assertEqual("sent", publisher.delivery_state("card_1"))
        self.assertEqual("oc_team", sender.call_args.args[0])
        self.assertEqual("2.0", sender.call_args.args[1]["schema"])
        with self.assertRaises(IntakeRejected):
            publisher.send_registered_card("card_1", KEY, now=NOW)
        sender.assert_called_once()

    def test_unknown_send_is_never_blindly_replayed(self):
        sender = mock.Mock(side_effect=ConnectionError("lost receipt"))
        publisher = CardPublisher(self.store, sender)
        with self.assertRaises(ExternalOutcomeUnknown):
            publisher.send_registered_card("card_1", KEY, now=NOW)
        self.assertEqual("unknown", publisher.delivery_state("card_1"))
        with self.assertRaises(IntakeRejected):
            publisher.send_registered_card("card_1", KEY, now=NOW)
        sender.assert_called_once()

    def test_existing_lark_transport_uses_interactive_message_api(self):
        transport = SimpleNamespace()
        builder = mock.Mock()
        builder.receive_id_type.return_value = builder
        builder.request_body.return_value = builder
        builder.receive_id.return_value = builder
        builder.msg_type.return_value = builder
        builder.content.return_value = builder
        builder.build.return_value = object()
        transport.CreateMessageRequest = SimpleNamespace(builder=mock.Mock(return_value=builder))
        transport.CreateMessageRequestBody = SimpleNamespace(builder=mock.Mock(return_value=builder))
        response = SimpleNamespace(
            success=lambda: True,
            data=SimpleNamespace(message_id="om_card"),
        )
        transport.client = SimpleNamespace(
            im=SimpleNamespace(v1=SimpleNamespace(
                message=SimpleNamespace(create=mock.Mock(return_value=response))
            ))
        )
        result = send_interactive_via_existing_transport(
            transport, "oc_team", {"schema": "2.0"},
        )
        self.assertEqual("om_card", result)
        builder.msg_type.assert_called_with("interactive")
        transport.client.im.v1.message.create.assert_called_once()

    def test_optional_card_registration_reuses_single_ws_consumer(self):
        from tools.codex_assets.feishu_codex_bot import FeishuTransport
        transport = object.__new__(FeishuTransport)
        builder = mock.Mock()
        builder.register_p2_im_message_receive_v1.return_value = builder
        builder.register_p2_card_action_trigger.return_value = builder
        transport.lark = mock.Mock()
        transport.lark.EventDispatcherHandler.builder.return_value = builder
        transport.config = SimpleNamespace(app_id="cli_test", app_secret="test-secret")
        handler = mock.Mock()
        card_handler = mock.Mock()
        transport.start(handler)
        builder.register_p2_card_action_trigger.assert_not_called()
        transport.start(handler, card_handler)
        builder.register_p2_card_action_trigger.assert_called_once_with(card_handler)
        self.assertEqual(2, transport.lark.ws.Client.return_value.start.call_count)


if __name__ == "__main__":
    unittest.main()
