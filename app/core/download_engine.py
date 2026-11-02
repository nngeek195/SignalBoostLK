import json
import time
import uuid
from pathlib import Path

import httpx

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "isps.json"


def load_servers() -> dict:
    """Load ISP -> Ookla server base URL mapping from app/config/isps.json."""
    with open(CONFIG_PATH, encoding="utf-8") as fh:
        return {str(k): str(v).rstrip("/") for k, v in json.load(fh).items()}


SERVERS = load_servers()
SUPPORTED_ISPS = tuple(SERVERS)

HEADERS = {
    "Accept": "*/*",
    "Origin": "https://www.speedtest.net",
    "Referer": "https://www.speedtest.net/",
    "User-Agent": "Mozilla/5.0 SignalBoostLK/0.1",
}


class TestCancelled(Exception):
    """Raised when a running download test is cancelled by the user."""


def run_download_test(isp: str, size_bytes: int, progress_callback=None, should_cancel=None):
    if isp not in SERVERS:
        raise ValueError(f"No configured test server for ISP: {isp}")
    if size_bytes < 1_000_000:
        raise ValueError("Test size must be at least 1 MB.")

    url = (
        f"{SERVERS[isp]}/download"
        f"?nocache={uuid.uuid4()}&size={int(size_bytes)}&guid={uuid.uuid4()}"
    )
    received = 0
    last_emit = 0.0

    # Stream to memory in chunks; no large temporary file is needed.
    with httpx.Client(
        timeout=httpx.Timeout(90.0, connect=15.0),
        follow_redirects=True,
        headers=HEADERS,
        trust_env=False,
    ) as client:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            # Start timing once the response begins, so TLS/connect latency
            # does not drag down the throughput figure.
            started = time.perf_counter()
            for chunk in response.iter_bytes(chunk_size=128 * 1024):
                if should_cancel and should_cancel():
                    raise TestCancelled("Download test cancelled.")
                if not chunk:
                    continue
                received += len(chunk)
                now = time.perf_counter()
                if progress_callback and (now - last_emit >= 0.15):
                    progress_callback(received, size_bytes)
                    last_emit = now

    if received == 0:
        raise RuntimeError("Server returned no data.")

    elapsed = max(time.perf_counter() - started, 0.001)
    mbps = (received * 8) / elapsed / 1_000_000
    if progress_callback:
        progress_callback(received, size_bytes)
    return {
        "isp": isp,
        "bytes": received,
        "seconds": elapsed,
        "mbps": mbps,
        "url": url.split("?")[0],
    }
