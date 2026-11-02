import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

DATA_DIR = Path.home() / ".local" / "share" / "SignalBoostLK"
DB_PATH = DATA_DIR / "history.db"


def connect():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tested_at TEXT NOT NULL,
            isp TEXT NOT NULL,
            public_ip TEXT,
            downloaded_bytes INTEGER NOT NULL,
            duration_seconds REAL NOT NULL,
            speed_mbps REAL NOT NULL
        )
    """)
    conn.commit()
    return conn


def save_test(result, public_ip=""):
    # closing() actually closes the connection; "with conn" alone only commits.
    with closing(connect()) as conn, conn:
        conn.execute(
            """INSERT INTO tests
            (tested_at, isp, public_ip, downloaded_bytes, duration_seconds, speed_mbps)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (datetime.now().astimezone().isoformat(timespec="seconds"),
             result["isp"], public_ip, result["bytes"],
             result["seconds"], result["mbps"]),
        )


def recent_tests(limit=20):
    """Return newest-first rows: (tested_at, isp, speed_mbps, bytes, seconds, public_ip)."""
    with closing(connect()) as conn:
        return conn.execute(
            """SELECT tested_at, isp, speed_mbps, downloaded_bytes,
                      duration_seconds, public_ip
               FROM tests ORDER BY id DESC LIMIT ?""",
            (limit,),
        ).fetchall()


def clear_history():
    with closing(connect()) as conn, conn:
        conn.execute("DELETE FROM tests")
