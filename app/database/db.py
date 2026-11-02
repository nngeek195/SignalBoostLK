"""SQLite storage with versioned migrations (PRAGMA user_version).

No public IP addresses are stored for keeper sessions.
"""
from __future__ import annotations

import sqlite3
import threading
import time
from contextlib import closing
from pathlib import Path

from app.core.paths import data_dir

DB_PATH: Path = data_dir() / "history.db"
RETENTION_DAYS = 30

MIGRATIONS: list[str] = [
    # 1 — 0.1.0 speed-test table (kept so old history survives the upgrade)
    """
    CREATE TABLE IF NOT EXISTS tests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tested_at TEXT NOT NULL,
        isp TEXT NOT NULL,
        public_ip TEXT,
        downloaded_bytes INTEGER NOT NULL,
        duration_seconds REAL NOT NULL,
        speed_mbps REAL NOT NULL
    );
    """,
    # 2 — connection keeper
    """
    CREATE TABLE sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        isp TEXT NOT NULL,
        host TEXT NOT NULL,
        interval_s REAL NOT NULL,
        started_at REAL NOT NULL,
        ended_at REAL,
        heartbeats_ok INTEGER NOT NULL DEFAULT 0,
        heartbeats_failed INTEGER NOT NULL DEFAULT 0,
        connections_opened INTEGER NOT NULL DEFAULT 0,
        bytes_tx INTEGER NOT NULL DEFAULT 0,
        bytes_rx INTEGER NOT NULL DEFAULT 0,
        avg_rtt_ms REAL
    );
    CREATE TABLE heartbeats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
        at REAL NOT NULL,
        ok INTEGER NOT NULL,
        rtt_ms REAL,
        reused INTEGER,
        bytes INTEGER
    );
    CREATE INDEX idx_heartbeats_session ON heartbeats(session_id, at);
    CREATE TABLE events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER REFERENCES sessions(id) ON DELETE CASCADE,
        at REAL NOT NULL,
        kind TEXT NOT NULL,
        message TEXT NOT NULL
    );
    CREATE INDEX idx_events_at ON events(at);
    CREATE TABLE prefs (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    """,
]

_init_lock = threading.Lock()
_initialised: set[str] = set()


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = path or DB_PATH
    conn = sqlite3.connect(path, timeout=10)
    conn.execute("PRAGMA foreign_keys = ON")
    key = str(path)
    if key not in _initialised:
        with _init_lock:
            migrate(conn)
            _initialised.add(key)
    return conn


def migrate(conn: sqlite3.Connection) -> int:
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    for i, sql in enumerate(MIGRATIONS[version:], start=version + 1):
        with conn:
            conn.executescript(sql)
            conn.execute(f"PRAGMA user_version = {i}")
    return conn.execute("PRAGMA user_version").fetchone()[0]


# ── prefs ────────────────────────────────────────────────────────────────────
def get_pref(key: str, default: str | None = None, path: Path | None = None) -> str | None:
    with closing(connect(path)) as conn:
        row = conn.execute("SELECT value FROM prefs WHERE key = ?", (key,)).fetchone()
    return row[0] if row else default


def set_pref(key: str, value: str, path: Path | None = None) -> None:
    with closing(connect(path)) as conn, conn:
        conn.execute("INSERT INTO prefs(key, value) VALUES(?, ?) "
                     "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))


# ── keeper sessions ──────────────────────────────────────────────────────────
def start_session(isp: str, host: str, interval_s: float, started_at: float,
                  path: Path | None = None) -> int:
    with closing(connect(path)) as conn, conn:
        cur = conn.execute("INSERT INTO sessions(isp, host, interval_s, started_at) VALUES(?,?,?,?)",
                           (isp, host, interval_s, started_at))
        return int(cur.lastrowid)


def update_session(session_id: int, stats, ended_at: float | None = None,
                   path: Path | None = None) -> None:
    with closing(connect(path)) as conn, conn:
        conn.execute(
            """UPDATE sessions SET heartbeats_ok=?, heartbeats_failed=?, connections_opened=?,
                   bytes_tx=?, bytes_rx=?, avg_rtt_ms=?, ended_at=COALESCE(?, ended_at)
               WHERE id=?""",
            (stats.heartbeats_ok, stats.heartbeats_failed, stats.connections_opened,
             stats.bytes_tx, stats.bytes_rx, stats.avg_rtt_ms, ended_at, session_id))


def add_heartbeat(session_id: int, at: float, ok: bool, rtt_ms: float | None,
                  reused: bool | None, nbytes: int | None, path: Path | None = None) -> None:
    with closing(connect(path)) as conn, conn:
        conn.execute("INSERT INTO heartbeats(session_id, at, ok, rtt_ms, reused, bytes) "
                     "VALUES(?,?,?,?,?,?)", (session_id, at, int(ok), rtt_ms,
                                             None if reused is None else int(reused), nbytes))


def add_event(session_id: int | None, at: float, kind: str, message: str,
              path: Path | None = None) -> None:
    with closing(connect(path)) as conn, conn:
        conn.execute("INSERT INTO events(session_id, at, kind, message) VALUES(?,?,?,?)",
                     (session_id, at, kind, message))


def recent_sessions(limit: int = 100, path: Path | None = None) -> list[tuple]:
    """(started_at, ended_at, isp, ok, failed, conns, bytes_total, avg_rtt_ms) newest first."""
    with closing(connect(path)) as conn:
        return conn.execute(
            """SELECT started_at, ended_at, isp, heartbeats_ok, heartbeats_failed,
                      connections_opened, bytes_tx + bytes_rx, avg_rtt_ms
               FROM sessions ORDER BY id DESC LIMIT ?""", (limit,)).fetchall()


def recent_events(limit: int = 300, path: Path | None = None) -> list[tuple]:
    with closing(connect(path)) as conn:
        return conn.execute("SELECT at, kind, message FROM events ORDER BY id DESC LIMIT ?",
                            (limit,)).fetchall()


def usage_totals(since: float, path: Path | None = None) -> int:
    with closing(connect(path)) as conn:
        return int(conn.execute("SELECT COALESCE(SUM(bytes_tx + bytes_rx), 0) FROM sessions "
                                "WHERE started_at >= ?", (since,)).fetchone()[0])


def prune(path: Path | None = None, days: int = RETENTION_DAYS) -> None:
    cutoff = time.time() - days * 86400
    with closing(connect(path)) as conn, conn:
        conn.execute("DELETE FROM heartbeats WHERE at < ?", (cutoff,))
        conn.execute("DELETE FROM events WHERE at < ?", (cutoff,))


def clear_history(path: Path | None = None) -> None:
    with closing(connect(path)) as conn, conn:
        conn.execute("DELETE FROM heartbeats")
        conn.execute("DELETE FROM events")
        conn.execute("DELETE FROM sessions")
