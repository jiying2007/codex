"""Bounded Codex App Server stdio RPC: explicit opt-in, no implicit model calls.

stdio app-server protocol uses initialize -> initialized -> thread/resume and
turn/start, with notifications for turn completion and tool approvals. This
module does not launch Codex unless the host operator creates a transport.
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time
from typing import Any, Callable, Mapping, Optional

from .models import IntakeRejected, _check_id
from .sessions import _absolute_path


class NativeProtocolError(IntakeRejected):
    pass


class ApprovalPending(NativeProtocolError):
    """A host approval request must not be approved by a chat callback."""


class StdioAppServer:
    """A single-outstanding-request client around a qualified Codex process.

    Separates RPC replies from progress notifications. Never returns a
    pseudo-success when a protocol/approval/stdio outcome is unknown.
    """

    MAX_LINE = 1024 * 1024

    def __init__(self, stdin: Any, stdout: Any,
                 timeout_sec: int = 10, on_event: Optional[Callable[[dict], None]] = None):
        if not 1 <= timeout_sec <= 60:
            raise NativeProtocolError("RPC timeout out of bounds")
        self.stdin = stdin
        self.stdout = stdout
        self.timeout_sec = timeout_sec
        self.on_event = on_event
        self._responses = queue.Queue(maxsize=256)
        self._notifications = queue.Queue(maxsize=256)
        self._notification_overflow = False
        self._request_lock = threading.Lock()
        self._next_id = 1
        self._running = False
        self.initialized = False
        self._reader = None

    def start_reader(self) -> None:
        if self._running:
            return
        self._running = True
        self._reader = threading.Thread(
            target=self._read_loop, daemon=True, name="fea-appserver-stdio"
        )
        self._reader.start()

    def _read_loop(self) -> None:
        while self._running:
            try:
                raw = self.stdout.readline(self.MAX_LINE + 1)
                if not raw:
                    self._put({"_fatal": "eof"})
                    return
                if len(raw) > self.MAX_LINE or not raw.endswith("\n"):
                    self._put({"_fatal": "oversized_or_partial_frame"})
                    return
                frame = json.loads(raw)
                if not isinstance(frame, dict):
                    raise ValueError("invalid RPC frame")
                if ("id" in frame and "method" in frame):
                    # These are server->client requests, often dangerous tool
                    # approvals: never auto-authorize from a chat message.
                    self._put({"_approval": frame})
                elif "id" in frame:
                    self._put(frame)
                elif "method" in frame:
                    # A terminal notification may arrive before turn/start
                    # ACK is persisted. Buffer it until the host coordinator
                    # can correlate the exact thread/turn; never drop it or
                    # execute callbacks on the stdout reader thread.
                    try:
                        self._notifications.put_nowait(frame)
                    except queue.Full:
                        self._notification_overflow = True
                        self._put({"_fatal": "notification_overflow"})
                        return
                else:
                    raise ValueError("unknown RPC message")
            except Exception as exc:
                self._put({"_fatal": type(exc).__name__})
                return

    def _put(self, frame: dict) -> None:
        try:
            self._responses.put_nowait(frame)
        except queue.Full:
            # Overflow is not a successful RPC observation.
            self._responses = queue.Queue(maxsize=256)
            self._responses.put_nowait({"_fatal": "response_overflow"})

    def _write(self, frame: dict) -> None:
        payload = json.dumps(frame, ensure_ascii=False, separators=(",", ":")) + "\n"
        if len(payload.encode("utf-8")) > self.MAX_LINE:
            raise NativeProtocolError("request exceeds bounded frame size")
        try:
            self.stdin.write(payload)
            self.stdin.flush()
        except (OSError, ValueError) as exc:
            raise NativeProtocolError("native RPC write outcome unknown") from exc

    def drain_notifications(self, limit: int = 64) -> list:
        """Host calls after durable turn ACK, or on its existing event loop."""
        if not isinstance(limit, int) or not 1 <= limit <= 256:
            raise NativeProtocolError("invalid notification drain limit")
        if self._notification_overflow:
            raise NativeProtocolError("native notification overflow; effect UNKNOWN")
        events = []
        for _ in range(limit):
            try:
                event = self._notifications.get_nowait()
            except queue.Empty:
                break
            events.append(event)
            if self.on_event is not None:
                self.on_event(event)
        return events

    def request(self, request: Mapping[str, Any]) -> dict:
        if self._notification_overflow:
            raise NativeProtocolError("native notification overflow; effect UNKNOWN")
        if not isinstance(request, Mapping) or not request.get("method"):
            raise NativeProtocolError("missing native RPC method")
        with self._request_lock:
            if not self._running:
                self.start_reader()
            rpc_id = self._next_id
            self._next_id += 1
            outgoing = dict(request)
            outgoing["id"] = rpc_id
            self._write(outgoing)
            deadline = time.monotonic() + self.timeout_sec
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise NativeProtocolError("native RPC timeout; effect UNKNOWN")
                try:
                    frame = self._responses.get(timeout=remaining)
                except queue.Empty as exc:
                    raise NativeProtocolError("native RPC timeout; effect UNKNOWN") from exc
                if frame.get("_fatal"):
                    raise NativeProtocolError("native RPC lost: " + frame["_fatal"])
                if frame.get("_approval"):
                    raise ApprovalPending("native tool approval needs independent host authority")
                if frame.get("id") != rpc_id:
                    raise NativeProtocolError("out-of-order/unexpected native RPC response")
                if "error" in frame:
                    raise NativeProtocolError("native RPC method rejected")
                if "result" not in frame:
                    raise NativeProtocolError("native RPC result absent")
                return frame

    def initialize(self, client_name: str = "feishu_engineering_agent") -> dict:
        _check_id(client_name, "client_name")
        if self.initialized:
            raise NativeProtocolError("already initialized")
        response = self.request({
            "method": "initialize",
            "params": {
                "clientInfo": {
                    "name": client_name,
                    "title": "Feishu Engineering Agent",
                    "version": "1.0.0",
                },
                "capabilities": {},
            },
        })
        self._write({"method": "initialized", "params": {}})
        self.initialized = True
        return response

    def resume_exact(self, thread_id: str) -> dict:
        if not self.initialized:
            raise NativeProtocolError("initialize first")
        return self.request({
            "method": "thread/resume",
            "params": {"threadId": _check_id(thread_id, "thread_id"),
                       "excludeTurns": True},
        })

    def turn_start(self, request: Mapping[str, Any], allow_model: bool = False) -> dict:
        if not self.initialized or not allow_model:
            raise NativeProtocolError("model calls disabled; explicit host authorization required")
        if request.get("method") != "turn/start":
            raise NativeProtocolError("turn_start requires turn/start RPC")
        return self.request(request)

    def interrupt_exact(self, request: Mapping[str, Any]) -> dict:
        if not self.initialized or request.get("method") != "turn/interrupt":
            raise NativeProtocolError("interrupt needs qualified exact turn")
        return self.request(request)

    def close(self) -> None:
        self._running = False


class NativeProcess:
    """Qualified host-only process. Does not expose Feishu credentials."""

    def __init__(self, codex_home: str, cwd: str, executable: str = "codex"):
        self.codex_home = _absolute_path(codex_home, "codex_home")
        self.cwd = _absolute_path(cwd, "cwd")
        if executable != "codex":
            raise NativeProtocolError("native executable must be the qualified PATH codex")
        self.executable = executable
        self.process = None

    def open(self, explicitly_qualified: bool = False) -> StdioAppServer:
        if not explicitly_qualified:
            raise NativeProtocolError("real host capability qualification required")
        if self.process is not None:
            raise NativeProtocolError("native process already active")
        safe_env = {k: v for k, v in os.environ.items()
                    if k in ("PATH", "HOME", "LANG", "LC_ALL", "LC_CTYPE", "TERM")}
        safe_env["CODEX_HOME"] = self.codex_home
        process = subprocess.Popen(
            [self.executable, "app-server"], cwd=self.cwd, env=safe_env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1,
        )
        self.process = process
        return StdioAppServer(process.stdin, process.stdout)

    def close(self) -> None:
        if self.process is not None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
            self.process = None
