"""Connection keeper: keeps one lightweight HTTPS connection to an ISP's
OoklaServer open and reconnects when it closes.

Routine traffic is ONLY the configured heartbeat (GET or HEAD on "/", which
returns a 109-byte page). This module never requests /download.

Measured facts (docs/reports/stage2_endpoint_compatibility.md, 2026-11-02),
identical on all four ISP servers:
  * An idle keep-alive connection is closed by the server after ~15 s.
  * Any connection is closed after ~60 s of age, even while heartbeats are
    flowing (a lifetime limit, not a request-count limit).
  * A heartbeat on a reused connection costs ~0.8 KB of TLS traffic;
    a new connection adds ~5.3 KB of TLS handshake.
So with an interval below 15 s one socket serves ~60 s of heartbeats and is
then replaced; with a longer interval every heartbeat opens a new connection.
"""
from __future__ import annotations

import enum
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.backoff import Backoff
from app.core.config import IspServer

log = logging.getLogger(__name__)

USER_AGENT = "SignalBoostLK/2.0"
SERVER_IDLE_TIMEOUT_S = 15.0  # measured, see module docstring
SERVER_MAX_CONNECTION_AGE_S = 60.0  # measured, see module docstring
# Measured TLS 1.3 handshake bytes (tx, rx) incl. certificate chain.
HANDSHAKE_BYTES = (600, 4730)
TLS_RECORD_OVERHEAD = 22  # per application-data record (TLS 1.3 AES-GCM)


class State(enum.Enum):
    STOPPED = "Stopped"
    CONNECTING = "Connecting"
    CONNECTED = "Connected"
    RECONNECTING = "Reconnecting"


@dataclass
class Stats:
    started_at: float = 0.0              # wall clock (time.time())
    heartbeats_ok: int = 0
    heartbeats_failed: int = 0
    connections_opened: int = 0
    reused: int = 0
    bytes_tx: int = 0
    bytes_rx: int = 0
    rtt_total_ms: float = 0.0
    last_ok_at: float | None = None
    last_rtt_ms: float | None = None
    connection_since: float | None = None  # wall clock when current socket opened

    @property
    def reconnects(self) -> int:
        return max(0, self.connections_opened - 1)

    @property
    def avg_rtt_ms(self) -> float | None:
        return self.rtt_total_ms / self.heartbeats_ok if self.heartbeats_ok else None

    @property
    def bytes_total(self) -> int:
        return self.bytes_tx + self.bytes_rx

    def bytes_per_hour(self, now: float) -> float | None:
        elapsed = now - self.started_at
        return self.bytes_total * 3600 / elapsed if elapsed >= 60 else None


@dataclass
class Event:
    kind: str           # state | connected | reused | heartbeat | error | info
    message: str
    at: float = field(default_factory=time.time)
    data: dict[str, Any] = field(default_factory=dict)


def _request_bytes(request: httpx.Request) -> int:
    line = f"{request.method} {request.url.raw_path.decode()} HTTP/1.1\r\n"
    hdrs = sum(len(k) + len(v) + 4 for k, v in request.headers.raw)
    return len(line) + hdrs + 2


def _response_bytes(response: httpx.Response, body_len: int) -> int:
    line = 17 + len(response.reason_phrase)  # "HTTP/1.1 200 " + reason + CRLF
    hdrs = sum(len(k) + len(v) + 4 for k, v in response.headers.raw)
    return line + hdrs + 2 + body_len


class ConnectionKeeper:
    """Runs on its own thread. Call start()/stop(); events go to on_event."""

    def __init__(self, server: IspServer, interval_s: float,
                 on_event: Callable[[Event], None] = lambda e: None,
                 transport: httpx.BaseTransport | None = None,
                 backoff: Backoff | None = None,
                 timeout_s: float = 10.0) -> None:
        if interval_s <= 0:
            raise ValueError("interval must be > 0")
        self.server = server
        self.interval_s = float(interval_s)
        self.on_event = on_event
        self._transport = transport
        self.backoff = backoff or Backoff(base=2.0, cap=300.0)
        self.timeout_s = timeout_s
        self.state = State.STOPPED
        self.stats = Stats()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._client: httpx.Client | None = None
        self._lock = threading.Lock()

    # ── public API ──────────────────────────────────────────────────────────
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self.stats = Stats(started_at=time.time())
        self._thread = threading.Thread(target=self.run, name="ConnectionKeeper", daemon=True)
        self._thread.start()

    def stop(self, wait: float | None = 5.0) -> None:
        self._stop.set()
        if self._thread and wait is not None and threading.current_thread() is not self._thread:
            self._thread.join(wait)

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def snapshot(self) -> Stats:
        with self._lock:
            return Stats(**self.stats.__dict__)

    # ── internals ───────────────────────────────────────────────────────────
    def _emit(self, kind: str, message: str, **data: Any) -> None:
        log.info("[%s] %s: %s", self.server.name, kind, message)
        try:
            self.on_event(Event(kind, message, data=data))
        except Exception:  # never let a UI callback kill the engine
            log.exception("event callback failed")

    def _set_state(self, state: State, why: str = "") -> None:
        if state is not self.state:
            self.state = state
            self._emit("state", state.value + (f" — {why}" if why else ""), state=state)

    def _make_client(self) -> httpx.Client:
        # ONE client for the whole session. keepalive_expiry must exceed the
        # interval, otherwise httpx itself drops the pooled socket (its
        # default is 5 s) and every heartbeat would open a new connection.
        return httpx.Client(
            http1=True, http2=False, trust_env=False, follow_redirects=False,
            timeout=httpx.Timeout(self.timeout_s),
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=1,
                                keepalive_expiry=self.interval_s + 30),
            headers={"User-Agent": USER_AGENT, "Accept": "*/*", "Connection": "keep-alive"},
            transport=self._transport,
        )

    def heartbeat(self) -> bool:
        """Send one heartbeat. Returns True on HTTP 200."""
        assert self._client is not None
        events: list[str] = []

        def trace(name: str, _info: dict) -> None:
            events.append(name)

        t0 = time.perf_counter()
        try:
            try:
                resp = self._client.request(self.server.heartbeat_method,
                                            self.server.heartbeat_url, extensions={"trace": trace})
            except (httpx.RemoteProtocolError, httpx.ReadError, httpx.WriteError) as exc:
                if "connection.connect_tcp.complete" in events:
                    raise  # failed on a fresh connection: a real failure
                # The server closed the reused socket just as we sent on it
                # (it enforces a ~60 s lifetime). Retry once on a new connection.
                self._emit("info", f"Reused connection was closed by the server "
                                   f"({type(exc).__name__}); retrying on a new connection")
                events.clear()
                t0 = time.perf_counter()
                resp = self._client.request(self.server.heartbeat_method,
                                            self.server.heartbeat_url, extensions={"trace": trace})
            body = resp.content
        except httpx.HTTPError as exc:
            with self._lock:
                self.stats.heartbeats_failed += 1
                self.stats.connection_since = None
            self._emit("error", f"Heartbeat failed: {type(exc).__name__}: {exc or 'no detail'}")
            return False
        rtt = (time.perf_counter() - t0) * 1000

        new_conn = "connection.connect_tcp.complete" in events
        tls_done = "connection.start_tls.complete" in events
        tx = _request_bytes(resp.request) + TLS_RECORD_OVERHEAD
        rx = _response_bytes(resp, len(body)) + TLS_RECORD_OVERHEAD
        if new_conn:
            tx += HANDSHAKE_BYTES[0]
            rx += HANDSHAKE_BYTES[1]

        with self._lock:
            s = self.stats
            s.bytes_tx += tx
            s.bytes_rx += rx
            if new_conn:
                s.connections_opened += 1
                s.connection_since = time.time()
            else:
                s.reused += 1
            if resp.status_code == 200:
                s.heartbeats_ok += 1
                s.rtt_total_ms += rtt
                s.last_rtt_ms = rtt
                s.last_ok_at = time.time()
            else:
                s.heartbeats_failed += 1

        if new_conn:
            n = self.stats.connections_opened
            self._emit("connected",
                       f"TCP connected{', TLS handshake complete' if tls_done else ''}"
                       + (" (first connection)" if n == 1 else f" (reconnect #{n - 1})"))
        if resp.status_code != 200:
            self._emit("error", f"Unexpected HTTP {resp.status_code}", status=resp.status_code)
            return False
        self._emit("heartbeat",
                   f"HTTP 200 in {rtt:.0f} ms, {'reused connection' if not new_conn else 'new connection'}",
                   rtt_ms=rtt, reused=not new_conn, bytes=tx + rx)
        return True

    def run(self) -> None:
        self._set_state(State.CONNECTING, self.server.host)
        if self.interval_s >= SERVER_IDLE_TIMEOUT_S:
            self._emit("info", f"Interval {self.interval_s:g}s is longer than the server's "
                               f"~{SERVER_IDLE_TIMEOUT_S:g}s idle timeout: the server will close "
                               "the connection between heartbeats, so each one reconnects.")
        self._client = self._make_client()
        try:
            while not self._stop.is_set():
                if self.heartbeat():
                    self.backoff.reset()
                    self._set_state(State.CONNECTED)
                    wait = self.interval_s
                else:
                    wait = self.backoff.next_delay()
                    self._set_state(State.RECONNECTING, f"retrying in {wait:.0f}s")
                self._stop.wait(wait)
        finally:
            self._client.close()
            self._client = None
            with self._lock:
                self.stats.connection_since = None
            self._set_state(State.STOPPED)
