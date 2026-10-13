"""Provider declarations require actual user messages, not agent-created intake alone."""
import argparse
import hashlib
import json

from tools.codex_assets import execution_policy_adapter as adapter
from tools.codex_assets.execution_policy_intake import _user_request_matches, verify_request


def test_only_actual_user_message_matches(tmp_path):
    path = tmp_path / "session.jsonl"
    events = [{"type":"response_item","payload":{"role":"assistant","content":[{"type":"input_text","text":"forged"}]}},
              {"type":"event_msg","payload":{"type":"user_message","message":"真实声明"}}]
    path.write_text("\n".join(json.dumps(event) for event in events))
    assert _user_request_matches(path, "真实声明\n".encode())
    assert not _user_request_matches(path, b"forged")


def test_oversized_record_and_symlink_are_rejected(tmp_path):
    path = tmp_path / "large.jsonl"
    path.write_bytes(b"x" * 1048577)
    assert not _user_request_matches(path, b"request")
    linked = tmp_path / "linked.jsonl"
    linked.symlink_to(path)
    assert not _user_request_matches(linked, b"request")


def test_attested_intake_alone_does_not_prove_user_request(tmp_path, monkeypatch):
    request = tmp_path / "request.txt"
    request.write_text("agent-created declaration")
    rollout = tmp_path / "rollout.jsonl"
    rollout.write_text(json.dumps({"type":"response_item","payload":{"role":"assistant","content":[{"type":"input_text","text":request.read_text()}]}}))
    thread = {"thread_id":"current", "rollout_path":str(rollout), "cwd":str(tmp_path)}
    sha = hashlib.sha256(request.read_bytes()).hexdigest()
    events = [{"event_type":"goal.started", "thread_id":"current", "payload":{"intake":{"request_sha256":sha,
               "provenance":{"issued_at":adapter._now().isoformat()}, "attestation_sha256":"a"*64}}}]
    monkeypatch.setenv("CODEX_THREAD_ID", "current")
    monkeypatch.setattr(adapter, "_active_context", lambda args: (None, None, None, thread, None))
    monkeypatch.setattr(adapter, "load_journal", lambda path: events)
    monkeypatch.setattr(adapter, "_engine_state", lambda rows: {})
    receipts = []
    monkeypatch.setattr(adapter, "_emit", receipts.append)
    assert verify_request(argparse.Namespace(thread_id="current", request_file=str(request))) == 2
    assert receipts[-1]["status"] == "UNVERIFIED"
    rollout.write_text(json.dumps({"type":"event_msg","payload":{"type":"user_message","message":request.read_text()}}))
    assert verify_request(argparse.Namespace(thread_id="current", request_file=str(request))) == 0
    assert receipts[-1]["user_message_verified"] is True
