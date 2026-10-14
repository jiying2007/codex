"""Provider declarations require actual users; collected by native unittest CI."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.codex_assets import execution_policy_adapter as adapter
from tools.codex_assets.execution_policy_intake import _user_request_matches, verify_request


class ProviderRequestVerificationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)

    def tearDown(self):
        self.directory.cleanup()

    def test_only_actual_user_message_matches(self):
        path = self.root / "session.jsonl"
        events = [{"type": "response_item", "payload": {"role": "assistant", "content": [{"type": "input_text", "text": "forged"}]}},
                  {"type": "event_msg", "payload": {"type": "user_message", "message": "真实声明"}}]
        path.write_text("\n".join(json.dumps(event) for event in events))
        self.assertTrue(_user_request_matches(path, "真实声明\n".encode()))
        self.assertFalse(_user_request_matches(path, b"forged"))

    def test_oversized_record_and_symlink_are_rejected(self):
        path = self.root / "large.jsonl"
        path.write_bytes(b"x" * 1048577)
        self.assertFalse(_user_request_matches(path, b"request"))
        linked = self.root / "linked.jsonl"
        linked.symlink_to(path)
        self.assertFalse(_user_request_matches(linked, b"request"))

    def test_large_tool_record_does_not_hide_later_real_request(self):
        path = self.root / "session.jsonl"
        tool = {"type": "response_item", "payload": {"role": "tool", "content": [{"type": "input_text", "text": "x" * 1048577}]}}
        user = {"type": "response_item", "payload": {"role": "user", "content": [{"type": "input_text", "text": "request"}]}}
        path.write_text(json.dumps(tool) + "\n" + json.dumps(user))
        self.assertTrue(_user_request_matches(path, b"request"))
        self.assertFalse(_user_request_matches(path, b"forged"))

    def test_bounded_windows_verify_initial_and_recent_users_not_middle(self):
        path = self.root / "session.jsonl"

        def event(text):
            return (json.dumps({"type": "event_msg", "payload": {"type": "user_message", "message": text}}) + "\n").encode()

        with path.open("wb") as stream:
            stream.write(event("initial"))
            stream.seek(33554432 + 100)
            stream.write(b"\n" + event("middle"))
            stream.seek(100663296)
            stream.write(b"\n" + event("recent"))
        self.assertTrue(_user_request_matches(path, b"initial"))
        self.assertTrue(_user_request_matches(path, b"recent"))
        self.assertFalse(_user_request_matches(path, b"middle"))

    def test_malformed_records_cannot_claim_user_identity(self):
        path = self.root / "session.jsonl"
        rows = [[], {"payload": []}, {"type": "response_item", "payload": {"role": "user", "content": [None, {"type": "input_text", "text": 1}]}}]
        path.write_text("\n".join(json.dumps(row) for row in rows))
        self.assertFalse(_user_request_matches(path, b"request"))

    def test_attested_intake_alone_does_not_prove_user_request(self):
        request = self.root / "request.txt"
        request.write_text("agent-created declaration")
        rollout = self.root / "rollout.jsonl"
        rollout.write_text(json.dumps({"type": "response_item", "payload": {"role": "assistant", "content": [{"type": "input_text", "text": request.read_text()}]}}))
        thread = {"thread_id": "current", "rollout_path": str(rollout), "cwd": str(self.root)}
        sha = hashlib.sha256(request.read_bytes()).hexdigest()
        events = [{"event_type": "goal.started", "thread_id": "current", "payload": {"intake": {
            "request_sha256": sha, "provenance": {"issued_at": adapter._now().isoformat()}, "attestation_sha256": "a" * 64,
        }}}]
        receipts = []
        with patch.dict(os.environ, {"CODEX_THREAD_ID": "current"}), \
                patch.object(adapter, "_active_context", return_value=(None, None, None, thread, None)), \
                patch.object(adapter, "load_journal", return_value=events), \
                patch.object(adapter, "_engine_state", return_value={}), \
                patch.object(adapter, "_emit", side_effect=receipts.append):
            args = argparse.Namespace(thread_id="current", request_file=str(request))
            self.assertEqual(verify_request(args), 2)
            self.assertEqual(receipts[-1]["status"], "UNVERIFIED")
            rollout.write_text(json.dumps({"type": "event_msg", "payload": {"type": "user_message", "message": request.read_text()}}))
            self.assertEqual(verify_request(args), 0)
            self.assertTrue(receipts[-1]["user_message_verified"])
