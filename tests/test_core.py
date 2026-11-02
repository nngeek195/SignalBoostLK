"""Engine tests against a local keep-alive server that, like the real
OoklaServers, closes idle connections. No live ISP servers are contacted."""
from __future__ import annotations

import socketserver
import threading
import time
from http.server import BaseHTTPRequestHandler

import pytest

from app.core.backoff import Backoff
from app.core.config import IspServer, load_isps
from app.core.isp_detector import UNKNOWN, identify_isp
from app.core.keeper import HANDSHAKE_BYTES, ConnectionKeeper, State, Stats
from app.database import db

BODY = b"<html><head><title>OoklaServer</title></head><body><h1>OoklaServer</h1><p>It worked!<br /></p></body></html>\n"


class MockServer:
    """HTTP/1.1 keep-alive server; closes a connection after `idle_s` of silence."""

    def __init__(self, idle_s: float = 1.0, status: int = 200,
                 max_age_s: float | None = None) -> None:
        outer = self
        self.status = status
        self.connections = 0
        self.requests: list[str] = []
        self.dropped = 0

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"
            timeout = idle_s

            def setup(self):
                super().setup()
                outer.connections += 1
                self.opened = time.monotonic()

            def _reply(self, body: bool):
                if max_age_s is not None and time.monotonic() - self.opened > max_age_s:
                    # Like the real servers' lifetime limit, but hitting the race:
                    # the request arrives and the server drops the socket unanswered.
                    outer.dropped += 1
                    self.close_connection = True
                    return
                outer.requests.append(f"{self.command} {self.path}")
                self.send_response(outer.status)
                self.send_header("Connection", "Keep-Alive")
                self.send_header("Content-Length", str(len(BODY)))
                self.end_headers()
                if body:
                    self.wfile.write(BODY)

            def do_GET(self):
                self._reply(True)

            def do_HEAD(self):
                self._reply(False)

            def log_message(self, *a):
                pass

        class Srv(socketserver.ThreadingMixIn, socketserver.TCPServer):
            daemon_threads = True
            allow_reuse_address = True

        self.httpd = Srv(("127.0.0.1", 0), Handler)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def server(self, method: str = "GET") -> IspServer:
        return IspServer("Test", "Test", "127.0.0.1", self.port, method, "/", (), scheme="http")

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def mock():
    m = MockServer(idle_s=1.0)
    yield m
    m.close()


def run_keeper(server, interval, duration, **kw):
    events = []
    k = ConnectionKeeper(server, interval, on_event=events.append, **kw)
    k.start()
    time.sleep(duration)
    k.stop()
    return k, events


# ── config / ISP detection ───────────────────────────────────────────────────
def test_config_has_four_isps_and_no_download_heartbeat():
    isps = load_isps()
    assert set(isps) == {"Mobitel", "Dialog", "SLT", "Hutch"}
    for s in isps.values():
        assert s.port == 8080 and s.heartbeat_path == "/" and "download" not in s.heartbeat_url


@pytest.mark.parametrize("org,expected", [
    ("AS45356 Mobitel Pvt Ltd", "Mobitel"),
    ("AS9329 Sri Lanka Telecom PLC", "SLT"),
    ("SLT-Mobitel", "Mobitel"),
    ("AS18001 Dialog Axiata PLC.", "Dialog"),
    ("Hutchison Telecommunications Lanka", "Hutch"),
    ("Acme Consulting", UNKNOWN),   # 'slt' inside a word must not match
    ("", UNKNOWN),
])
def test_identify_isp(org, expected):
    assert identify_isp(org) == expected


# ── backoff ──────────────────────────────────────────────────────────────────
def test_backoff_grows_caps_and_resets():
    b = Backoff(base=2, cap=30, rng=lambda: 1.0)  # rng=1 → always the ceiling
    assert [b.next_delay() for _ in range(6)] == [2, 4, 8, 16, 30, 30]
    b.reset()
    assert b.next_delay() == 2


def test_backoff_jitter_bounds():
    b = Backoff(base=2, cap=300, rng=lambda: 0.0)
    assert b.next_delay() == 1.0  # lower bound base/2


# ── keeper ───────────────────────────────────────────────────────────────────
def test_connection_reused_when_interval_below_idle_timeout(mock):
    k, events = run_keeper(mock.server(), interval=0.3, duration=1.6)
    s = k.stats
    assert s.heartbeats_ok >= 4
    assert mock.connections == 1 and s.connections_opened == 1
    assert s.reused == s.heartbeats_ok - 1
    assert all(r == "GET /" for r in mock.requests)  # never /download
    assert k.state is State.STOPPED


def test_reconnects_after_server_closes_idle_connection(mock):
    k, events = run_keeper(mock.server(), interval=1.5, duration=3.4)
    s = k.stats
    assert s.heartbeats_ok == 3 and s.heartbeats_failed == 0
    assert mock.connections == 3 and s.connections_opened == 3 and s.reconnects == 2
    assert sum(e.kind == "connected" for e in events) == 3


def test_head_heartbeat(mock):
    k, _ = run_keeper(mock.server("HEAD"), interval=0.3, duration=0.8)
    assert k.stats.heartbeats_ok >= 2 and set(mock.requests) == {"HEAD /"}


def test_failure_triggers_backoff_then_recovers():
    m = MockServer()
    port = m.port
    m.close()  # nothing listening → connection refused
    k = ConnectionKeeper(IspServer("T", "T", "127.0.0.1", port, "GET", "/", (), scheme="http"),
                         0.2, backoff=Backoff(base=0.2, cap=0.4, rng=lambda: 1.0))
    k.start()
    # Poll: on Windows a refused localhost connect takes ~2 s, on Linux it is instant.
    deadline = time.monotonic() + 20
    while k.stats.heartbeats_failed < 2 and time.monotonic() < deadline:
        time.sleep(0.05)
    k.stop()
    assert k.stats.heartbeats_ok == 0 and k.stats.heartbeats_failed >= 2
    assert k.backoff.attempt >= 2


def test_non_200_is_failure(mock):
    mock.status = 503
    k, events = run_keeper(mock.server(), interval=0.3, duration=0.5, backoff=Backoff(0.5, 1))
    assert k.stats.heartbeats_ok == 0 and k.stats.heartbeats_failed >= 1
    assert any("503" in e.message for e in events)


# ── data usage ───────────────────────────────────────────────────────────────
def test_byte_accounting(mock):
    k, events = run_keeper(mock.server(), interval=0.3, duration=1.0)
    beats = [e for e in events if e.kind == "heartbeat"]
    assert k.stats.bytes_total == sum(e.data["bytes"] for e in beats)
    first, later = beats[0].data["bytes"], beats[1].data["bytes"]
    assert first - later == sum(HANDSHAKE_BYTES)  # only the new connection pays the handshake
    assert 400 < later < 1500  # small heartbeat, not a download


def test_usage_rates():
    s = Stats(started_at=1000.0, bytes_tx=1000, bytes_rx=2600, heartbeats_ok=4, rtt_total_ms=200,
              connections_opened=3)
    assert s.bytes_per_hour(1030) is None  # under a minute → not shown
    assert s.bytes_per_hour(1000 + 3600) == 3600
    assert s.avg_rtt_ms == 50 and s.reconnects == 2


# ── database ─────────────────────────────────────────────────────────────────
def test_db_migrations_and_persistence(tmp_path):
    path = tmp_path / "h.db"
    conn = db.connect(path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == len(db.MIGRATIONS)
    conn.close()
    sid = db.start_session("Mobitel", "h", 10, 100.0, path=path)
    db.add_heartbeat(sid, 101.0, True, 42.0, False, 6000, path=path)
    db.add_event(sid, 101.0, "connected", "TCP connected", path=path)
    db.update_session(sid, Stats(started_at=100, heartbeats_ok=1, connections_opened=1,
                                 bytes_tx=700, bytes_rx=5300, rtt_total_ms=42), ended_at=110.0,
                      path=path)
    db.set_pref("interval_s", "10", path=path)
    assert db.get_pref("interval_s", path=path) == "10"
    (row,) = db.recent_sessions(path=path)
    assert row == (100.0, 110.0, "Mobitel", 1, 0, 1, 6000, 42.0)
    assert db.recent_events(path=path)[0][1:] == ("connected", "TCP connected")
    assert db.usage_totals(0, path=path) == 6000


def test_db_upgrades_legacy_010_database(tmp_path):
    import sqlite3
    path = tmp_path / "old.db"
    c = sqlite3.connect(path)
    c.executescript(db.MIGRATIONS[0])
    c.execute("INSERT INTO tests(tested_at,isp,downloaded_bytes,duration_seconds,speed_mbps) "
              "VALUES('x','SLT',1,1,1)")
    c.commit()
    c.close()
    conn = db.connect(path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM tests").fetchone()[0] == 1


def test_lifetime_limit_race_is_retried_not_failed():
    m = MockServer(idle_s=5.0, max_age_s=0.5)
    try:
        k, events = run_keeper(m.server(), interval=0.2, duration=1.5)
    finally:
        m.close()
    assert m.dropped >= 1
    assert k.stats.heartbeats_failed == 0            # dropped sockets were retried at once
    assert k.stats.connections_opened == m.connections >= 2
    assert any(e.kind == "info" and "retrying" in e.message for e in events)
