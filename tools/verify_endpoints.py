#!/usr/bin/env python3
"""SignalBoostLK — ISP endpoint verification tool (Stage 2).

Verifies, for every ISP in app/config/isps.json:

  * DNS resolution (A / AAAA)
  * TCP connect time
  * TLS handshake, negotiated version / cipher / ALPN, certificate validity
  * GET / and HEAD / responses (status, headers, body size)
  * Connection reuse: several requests sent over ONE TCP/TLS socket
  * The same behaviour through a single httpx.Client (trace-based)
  * Optional: how long the server keeps an idle keep-alive socket open

TLS is driven through ssl.MemoryBIO so every byte that crosses the socket is
counted exactly (TLS records; TCP/IP headers are not included).

Only the lightweight root endpoint is ever requested. This tool never touches
the /download speed-test endpoint.

Usage:
    python tools/verify_endpoints.py                 # quick checks
    python tools/verify_endpoints.py --idle-probe 330  # + idle timeout probe
    python tools/verify_endpoints.py --json out.json --markdown out.md
"""
from __future__ import annotations

import argparse
import json
import select
import socket
import ssl
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "app" / "config" / "isps.json"
USER_AGENT = "SignalBoostLK/2.0 (endpoint-verifier)"
TIMEOUT = 15.0


# ── Exact-byte TLS connection ────────────────────────────────────────────────
class CountingTLSConnection:
    """Blocking TLS client over a plain socket using MemoryBIO.

    Counts raw bytes written to / read from the TCP socket, so the numbers
    include TLS record overhead, handshake and session tickets.
    """

    def __init__(self, host: str, port: int, alpn: list[str] | None = None,
                 family: int = socket.AF_UNSPEC) -> None:
        self.host = host
        self.port = port
        self.alpn = alpn or ["http/1.1"]
        self.family = family
        self.sock: socket.socket | None = None
        self.tls: ssl.SSLObject | None = None
        self._in = ssl.MemoryBIO()
        self._out = ssl.MemoryBIO()
        self.tx = 0
        self.rx = 0
        self.remote_addr: str = ""
        self.local_port: int = 0
        self.tcp_ms = 0.0
        self.tls_ms = 0.0
        self.handshake_tx = 0
        self.handshake_rx = 0

    # socket I/O ------------------------------------------------------------
    def _flush(self) -> None:
        data = self._out.read()
        if data:
            assert self.sock is not None
            self.sock.sendall(data)
            self.tx += len(data)

    def _fill(self) -> bool:
        """Read one chunk from the socket into the TLS engine. False on EOF."""
        assert self.sock is not None
        data = self.sock.recv(65536)
        if not data:
            self._in.write_eof()
            return False
        self.rx += len(data)
        self._in.write(data)
        return True

    # lifecycle -------------------------------------------------------------
    def connect(self) -> None:
        infos = socket.getaddrinfo(self.host, self.port, self.family, socket.SOCK_STREAM)
        fam, stype, proto, _, addr = infos[0]
        self.sock = socket.socket(fam, stype, proto)
        self.sock.settimeout(TIMEOUT)
        t0 = time.perf_counter()
        self.sock.connect(addr)
        self.tcp_ms = (time.perf_counter() - t0) * 1000
        self.remote_addr = addr[0]
        self.local_port = self.sock.getsockname()[1]

        ctx = ssl.create_default_context()
        ctx.set_alpn_protocols(self.alpn)
        self.tls = ctx.wrap_bio(self._in, self._out, server_hostname=self.host)
        t0 = time.perf_counter()
        while True:
            try:
                self.tls.do_handshake()
                break
            except ssl.SSLWantReadError:
                self._flush()
                if not self._fill():
                    raise ConnectionError("EOF during TLS handshake")
        self._flush()
        self.tls_ms = (time.perf_counter() - t0) * 1000
        self.handshake_tx, self.handshake_rx = self.tx, self.rx

    def send(self, data: bytes) -> None:
        assert self.tls is not None
        self.tls.write(data)
        self._flush()

    def recv_some(self) -> bytes:
        """Return decrypted bytes; b'' means the peer closed the connection."""
        assert self.tls is not None
        while True:
            try:
                return self.tls.read(65536)
            except ssl.SSLWantReadError:
                if not self._fill():
                    return b""
            except (ssl.SSLZeroReturnError, ssl.SSLEOFError):
                return b""

    def close(self) -> None:
        if self.sock is not None:
            try:
                self.sock.close()
            finally:
                self.sock = None


@dataclass
class HttpExchange:
    method: str
    status: int | None = None
    reason: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    body_bytes: int = 0
    body_preview: str = ""
    wire_tx: int = 0
    wire_rx: int = 0
    elapsed_ms: float = 0.0
    same_socket: bool = True
    local_port: int = 0
    error: str = ""


def http_exchange(conn: CountingTLSConnection, method: str, path: str = "/") -> HttpExchange:
    """Send one HTTP/1.1 request on an existing connection and read the reply."""
    ex = HttpExchange(method=method, local_port=conn.local_port)
    req = (
        f"{method} {path} HTTP/1.1\r\n"
        f"Host: {conn.host}:{conn.port}\r\n"
        f"User-Agent: {USER_AGENT}\r\n"
        "Accept: */*\r\n"
        "Connection: keep-alive\r\n\r\n"
    ).encode("ascii")
    tx0, rx0 = conn.tx, conn.rx
    t0 = time.perf_counter()
    try:
        conn.send(req)
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = conn.recv_some()
            if not chunk:
                raise ConnectionError("server closed connection before response headers")
            buf += chunk
        head, body = buf.split(b"\r\n\r\n", 1)
        lines = head.decode("iso-8859-1").split("\r\n")
        _, code, *reason = lines[0].split(" ", 2)
        ex.status = int(code)
        ex.reason = reason[0] if reason else ""
        for line in lines[1:]:
            k, _, v = line.partition(":")
            ex.headers[k.strip()] = v.strip()
        hdr_lc = {k.lower(): v for k, v in ex.headers.items()}
        if method != "HEAD" and "content-length" in hdr_lc:
            want = int(hdr_lc["content-length"])
            while len(body) < want:
                chunk = conn.recv_some()
                if not chunk:
                    raise ConnectionError("server closed connection mid-body")
                body += chunk
        elif method != "HEAD" and "transfer-encoding" in hdr_lc:
            raise NotImplementedError("chunked responses not expected from this endpoint")
        ex.body_bytes = len(body)
        ex.body_preview = body[:120].decode("utf-8", "replace")
    except Exception as exc:  # recorded, not raised: this is a report tool
        ex.error = f"{type(exc).__name__}: {exc}"
    ex.elapsed_ms = (time.perf_counter() - t0) * 1000
    ex.wire_tx, ex.wire_rx = conn.tx - tx0, conn.rx - rx0
    return ex


# ── Report structures ────────────────────────────────────────────────────────
@dataclass
class IspReport:
    isp: str
    host: str
    port: int
    dns_ipv4: list[str] = field(default_factory=list)
    dns_ipv6: list[str] = field(default_factory=list)
    dns_error: str = ""
    connected_addr: str = ""
    tcp_ms: float | None = None
    tls_ms: float | None = None
    tls_version: str = ""
    tls_cipher: str = ""
    alpn_offered_h2_selected: str | None = None
    cert_subject: str = ""
    cert_issuer: str = ""
    cert_not_after: str = ""
    cert_san_matches_host: bool = False
    cert_verified: bool = False
    handshake_wire_tx: int = 0
    handshake_wire_rx: int = 0
    get_exchanges: list[HttpExchange] = field(default_factory=list)
    head_exchange: HttpExchange | None = None
    raw_reuse_verified: bool = False
    httpx_requests: int = 0
    httpx_new_connections: int = 0
    httpx_client_ports: list[int] = field(default_factory=list)
    httpx_statuses: list[int] = field(default_factory=list)
    httpx_reuse_verified: bool = False
    idle_close_after_s: float | None = None
    idle_close_kind: str = ""
    idle_probe_limit_s: float | None = None
    sustain_method: str = ""
    sustain_interval_s: float | None = None
    sustain_duration_s: float | None = None
    sustain_requests: int = 0
    sustain_ok: int = 0
    sustain_connections: int = 0
    sustain_server_closes: list[float] = field(default_factory=list)
    sustain_wire_tx: int = 0
    sustain_wire_rx: int = 0
    sustain_longest_connection_s: float = 0.0
    supported: bool = False
    notes: list[str] = field(default_factory=list)
    error: str = ""


def load_isps() -> dict[str, dict[str, Any]]:
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return data["isps"]


def check_dns(r: IspReport) -> None:
    try:
        for fam, *_, addr in socket.getaddrinfo(r.host, r.port, type=socket.SOCK_STREAM):
            target = r.dns_ipv4 if fam == socket.AF_INET else r.dns_ipv6
            if addr[0] not in target:
                target.append(addr[0])
    except socket.gaierror as exc:
        r.dns_error = str(exc)


def check_alpn_h2(r: IspReport) -> None:
    """Does the server negotiate HTTP/2 when offered? (handshake only)"""
    conn = CountingTLSConnection(r.host, r.port, alpn=["h2", "http/1.1"])
    try:
        conn.connect()
        assert conn.tls is not None
        r.alpn_offered_h2_selected = conn.tls.selected_alpn_protocol() or "(none)"
    except Exception as exc:
        r.notes.append(f"ALPN h2 check failed: {exc}")
    finally:
        conn.close()


def check_raw(r: IspReport, n_get: int) -> None:
    conn = CountingTLSConnection(r.host, r.port)
    try:
        conn.connect()
    except Exception as exc:
        r.error = f"connect/TLS failed: {type(exc).__name__}: {exc}"
        conn.close()
        return
    assert conn.tls is not None
    r.connected_addr = conn.remote_addr
    r.tcp_ms, r.tls_ms = round(conn.tcp_ms, 1), round(conn.tls_ms, 1)
    r.tls_version = conn.tls.version() or ""
    r.tls_cipher = (conn.tls.cipher() or ("",))[0]
    cert = conn.tls.getpeercert() or {}
    r.cert_verified = True  # create_default_context() => CERT_REQUIRED + hostname check
    r.cert_subject = ", ".join(f"{k}={v}" for rdn in cert.get("subject", ()) for k, v in rdn)
    r.cert_issuer = ", ".join(f"{k}={v}" for rdn in cert.get("issuer", ()) for k, v in rdn)
    r.cert_not_after = cert.get("notAfter", "")
    sans = [v for k, v in cert.get("subjectAltName", ()) if k == "DNS"]
    r.cert_san_matches_host = any(
        s == r.host or (s.startswith("*.") and r.host.split(".", 1)[1] == s[2:]) for s in sans
    )
    r.handshake_wire_tx, r.handshake_wire_rx = conn.handshake_tx, conn.handshake_rx

    try:
        port0 = conn.local_port
        for _ in range(n_get):
            ex = http_exchange(conn, "GET")
            ex.same_socket = conn.local_port == port0
            r.get_exchanges.append(ex)
            if ex.error:
                break
        ok = [e for e in r.get_exchanges if e.status == 200 and not e.error]
        r.raw_reuse_verified = len(ok) == n_get and n_get > 1
        if r.raw_reuse_verified:
            r.head_exchange = http_exchange(conn, "HEAD")
    finally:
        conn.close()


def check_httpx(r: IspReport, n: int) -> None:
    new_conns = 0

    def trace(event: str, _info: dict) -> None:
        nonlocal new_conns
        if event == "connection.connect_tcp.complete":
            new_conns += 1

    url = f"https://{r.host}:{r.port}/"
    with httpx.Client(http1=True, http2=False, timeout=TIMEOUT, trust_env=False,
                      headers={"User-Agent": USER_AGENT}) as client:
        for _ in range(n):
            try:
                resp = client.get(url, extensions={"trace": trace})
                r.httpx_statuses.append(resp.status_code)
                stream = resp.extensions.get("network_stream")
                addr = stream.get_extra_info("client_addr") if stream else None
                if addr:
                    r.httpx_client_ports.append(addr[1])
            except httpx.HTTPError as exc:
                r.notes.append(f"httpx request failed: {exc!r}")
                break
    r.httpx_requests = len(r.httpx_statuses)
    r.httpx_new_connections = new_conns
    r.httpx_reuse_verified = (
        r.httpx_requests == n and n > 1 and new_conns == 1 and len(set(r.httpx_client_ports)) == 1
    )


def probe_idle(r: IspReport, limit_s: float) -> None:
    """Open a connection, make one request, then stay silent and wait for the
    server (or a middlebox) to close it. No traffic is sent while waiting."""
    r.idle_probe_limit_s = limit_s
    conn = CountingTLSConnection(r.host, r.port)
    try:
        conn.connect()
        ex = http_exchange(conn, "GET")
        if ex.error or ex.status != 200:
            r.notes.append(f"idle probe: initial request failed ({ex.error or ex.status})")
            return
        assert conn.sock is not None
        conn.sock.setblocking(False)
        t0 = time.monotonic()
        while (elapsed := time.monotonic() - t0) < limit_s:
            readable, _, _ = select.select([conn.sock], [], [], 1.0)
            if not readable:
                continue
            try:
                data = conn.sock.recv(65536)
            except ConnectionResetError:
                r.idle_close_after_s, r.idle_close_kind = round(elapsed, 1), "TCP RST"
                return
            except BlockingIOError:
                continue
            if not data:
                r.idle_close_after_s, r.idle_close_kind = round(elapsed, 1), "TCP FIN"
                return
            conn._in.write(data)
            try:
                extra = conn.tls.read(65536)  # type: ignore[union-attr]
                if not extra:
                    r.idle_close_after_s, r.idle_close_kind = round(elapsed, 1), "TLS close_notify + FIN"
                    return
                r.notes.append(f"idle probe: unexpected {len(extra)} bytes of data")
            except ssl.SSLWantReadError:
                pass  # e.g. TLS 1.3 session ticket
            except (ssl.SSLZeroReturnError, ssl.SSLEOFError):
                r.idle_close_after_s, r.idle_close_kind = round(elapsed, 1), "TLS close_notify"
                return
        r.idle_close_kind = f"still open after {limit_s:.0f}s"
    except Exception as exc:
        r.notes.append(f"idle probe error: {type(exc).__name__}: {exc}")
    finally:
        conn.close()


def _peer_closed(conn: CountingTLSConnection) -> bool:
    """Non-blocking check: has the peer closed this connection while idle?"""
    if conn.sock is None:
        return True
    readable, _, _ = select.select([conn.sock], [], [], 0)
    if not readable:
        return False
    try:
        conn.sock.setblocking(False)
        data = conn.sock.recv(65536)
    except BlockingIOError:
        return False
    except OSError:
        return True
    finally:
        if conn.sock is not None:
            conn.sock.setblocking(True)
            conn.sock.settimeout(TIMEOUT)
    if not data:
        return True
    conn.rx += len(data)
    conn._in.write(data)
    try:
        conn.tls.read(65536)  # type: ignore[union-attr]
        return True  # b"" == close_notify; real data is unexpected here
    except ssl.SSLWantReadError:
        return False  # session ticket or partial record
    except ssl.SSLError:
        return True


def sustain(r: IspReport, duration_s: float, interval_s: float, method: str) -> None:
    """Send a heartbeat every interval_s for duration_s on one connection,
    reconnecting only when the server closes it. Counts every connection."""
    r.sustain_method, r.sustain_interval_s, r.sustain_duration_s = method, interval_s, duration_s
    conn: CountingTLSConnection | None = None
    opened_at = 0.0
    tx = rx = 0
    t_start = time.monotonic()
    next_beat = t_start

    def retire(c: CountingTLSConnection) -> None:
        nonlocal tx, rx
        tx, rx = tx + c.tx, rx + c.rx
        r.sustain_longest_connection_s = max(r.sustain_longest_connection_s,
                                             round(time.monotonic() - opened_at, 1))
        c.close()

    try:
        while time.monotonic() - t_start < duration_s:
            time.sleep(max(0.0, next_beat - time.monotonic()))
            next_beat += interval_s
            if conn is not None and _peer_closed(conn):
                r.sustain_server_closes.append(round(time.monotonic() - opened_at, 1))
                retire(conn)
                conn = None
            for attempt in range(2):
                if conn is None:
                    conn = CountingTLSConnection(r.host, r.port)
                    conn.connect()
                    opened_at = time.monotonic()
                    r.sustain_connections += 1
                r.sustain_requests += 1
                ex = http_exchange(conn, method)
                if not ex.error and ex.status == 200:
                    r.sustain_ok += 1
                    break
                r.notes.append(f"sustain: request failed after {time.monotonic() - opened_at:.1f}s "
                               f"on connection ({ex.error or ex.status}); attempt {attempt + 1}")
                retire(conn)
                conn = None
    except Exception as exc:
        r.notes.append(f"sustain error: {type(exc).__name__}: {exc}")
    finally:
        if conn is not None:
            retire(conn)
    r.sustain_wire_tx, r.sustain_wire_rx = tx, rx
    r.sustain_duration_s = round(time.monotonic() - t_start, 1)  # actual elapsed


def verify(isp: str, cfg: dict[str, Any], n_get: int, idle_limit: float,
           sustain_s: float = 0, sustain_interval: float = 10, sustain_method: str = "GET") -> IspReport:
    r = IspReport(isp=isp, host=cfg["host"], port=int(cfg["port"]))
    check_dns(r)
    if r.dns_error:
        r.error = f"DNS failed: {r.dns_error}"
        return r
    check_raw(r, n_get)
    if r.error:
        return r
    check_alpn_h2(r)
    check_httpx(r, n_get)
    if idle_limit > 0:
        probe_idle(r, idle_limit)
    if sustain_s > 0:
        sustain(r, sustain_s, sustain_interval, sustain_method)
    r.supported = bool(r.get_exchanges) and all(
        e.status == 200 and not e.error for e in r.get_exchanges
    )
    return r


# ── Output ───────────────────────────────────────────────────────────────────
def to_markdown(reports: list[IspReport], meta: dict[str, Any]) -> str:
    out = ["# SignalBoostLK — ISP Endpoint Verification Report", ""]
    out += [f"- Generated: {meta['generated_at']}",
            f"- Test network ISP (via ipinfo.io org lookup): {meta.get('test_network', 'not checked')}",
            f"- Requests per connection: {meta['n_get']}",
            f"- Idle probe limit: {meta['idle_limit'] or 'not run'}"
            + (" s" if meta["idle_limit"] else ""),
            "- Only `GET /` and `HEAD /` were requested; `/download` was never used.",
            "- Wire bytes = raw TLS record bytes on the TCP socket (TCP/IP headers excluded).",
            ""]
    out += ["## Summary", "",
            "| ISP | Supported | IP used | TCP ms | TLS ms | TLS | GET / | Body | Reuse (raw) | Reuse (httpx) | HEAD / | Idle close |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in reports:
        g = r.get_exchanges[0] if r.get_exchanges else None
        h = r.head_exchange
        idle = (f"{r.idle_close_after_s:.0f}s ({r.idle_close_kind})" if r.idle_close_after_s is not None
                else (r.idle_close_kind or "—"))
        out.append(
            f"| {r.isp} | {'yes' if r.supported else 'NO'} | {r.connected_addr or '—'} | "
            f"{r.tcp_ms if r.tcp_ms is not None else '—'} | {r.tls_ms if r.tls_ms is not None else '—'} | "
            f"{r.tls_version or '—'} | {g.status if g else '—'} | {g.body_bytes if g else '—'} B | "
            f"{'yes' if r.raw_reuse_verified else 'no'} | "
            f"{'yes' if r.httpx_reuse_verified else 'no'} ({r.httpx_new_connections} conn / {r.httpx_requests} req) | "
            f"{(str(h.status) + ', ' + str(h.body_bytes) + ' B body') if h else '—'} | {idle} |")
    out += ["", "## Data cost per heartbeat (measured)", "",
            "| ISP | TLS handshake tx/rx | GET / tx/rx (reused conn) | HEAD / tx/rx (reused conn) |",
            "|---|---|---|---|"]
    for r in reports:
        gets = [e for e in r.get_exchanges[1:] if not e.error] or r.get_exchanges
        g = gets[0] if gets else None
        h = r.head_exchange
        out.append(f"| {r.isp} | {r.handshake_wire_tx} / {r.handshake_wire_rx} B | "
                   f"{(str(g.wire_tx) + ' / ' + str(g.wire_rx) + ' B') if g else '—'} | "
                   f"{(str(h.wire_tx) + ' / ' + str(h.wire_rx) + ' B') if h else '—'} |")
    if meta.get("sustain_s"):
        out += ["", f"## Sustained keep-alive ({meta['sustain_method']} every "
                f"{meta['sustain_interval']:g}s for {meta['sustain_s']:g}s)", "",
                "| ISP | Requests OK | TCP connections | Server closes (conn age s) | Longest conn | Wire tx/rx | Projected per hour |",
                "|---|---|---|---|---|---|---|"]
        for r in reports:
            total = r.sustain_wire_tx + r.sustain_wire_rx
            per_h = total * 3600 / r.sustain_duration_s if r.sustain_duration_s else 0
            out.append(f"| {r.isp} | {r.sustain_ok}/{r.sustain_requests} | {r.sustain_connections} | "
                       f"{r.sustain_server_closes or 'none'} | {r.sustain_longest_connection_s:.0f}s | "
                       f"{r.sustain_wire_tx} / {r.sustain_wire_rx} B | {per_h / 1024:.0f} KiB |")
    for r in reports:
        out += ["", f"## {r.isp} — `{r.host}:{r.port}`", ""]
        if r.error:
            out.append(f"**Error:** {r.error}")
        out += [f"- DNS A: {', '.join(r.dns_ipv4) or 'none'}",
                f"- DNS AAAA: {', '.join(r.dns_ipv6) or 'none'}",
                f"- Connected to: {r.connected_addr}",
                f"- TLS: {r.tls_version} / {r.tls_cipher}; ALPN when offering h2: `{r.alpn_offered_h2_selected}`",
                f"- Certificate: verified={r.cert_verified}, SAN matches host={r.cert_san_matches_host}",
                f"  - Subject: {r.cert_subject}",
                f"  - Issuer: {r.cert_issuer}",
                f"  - Not after: {r.cert_not_after}",
                f"- httpx client ports across requests: {r.httpx_client_ports} (statuses {r.httpx_statuses})"]
        for i, e in enumerate(r.get_exchanges, 1):
            out.append(f"- GET #{i}: {e.status} {e.reason}, body {e.body_bytes} B, "
                       f"{e.elapsed_ms:.0f} ms, wire tx/rx {e.wire_tx}/{e.wire_rx} B, "
                       f"local port {e.local_port}{' — ' + e.error if e.error else ''}")
        if r.head_exchange:
            e = r.head_exchange
            out.append(f"- HEAD: {e.status} {e.reason}, body {e.body_bytes} B, {e.elapsed_ms:.0f} ms, "
                       f"wire tx/rx {e.wire_tx}/{e.wire_rx} B{' — ' + e.error if e.error else ''}")
        if r.get_exchanges:
            hdrs = r.get_exchanges[0].headers
            keep = {k: v for k, v in hdrs.items()
                    if k.lower() in ("connection", "keep-alive", "content-length", "content-type",
                                     "cache-control", "server")}
            out.append(f"- Relevant response headers: `{keep}`")
            out.append(f"- Body preview: `{r.get_exchanges[0].body_preview}`")
        for n in r.notes:
            out.append(f"- Note: {n}")
    return "\n".join(out) + "\n"


def detect_test_network() -> str:
    """Org of the network the test runs from (no IP address is stored)."""
    try:
        with httpx.Client(timeout=10, trust_env=False) as c:
            return str(c.get("https://ipinfo.io/json").json().get("org", "unknown"))
    except Exception as exc:
        return f"lookup failed ({exc})"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--isp", action="append", help="only test this ISP (repeatable)")
    ap.add_argument("-n", type=int, default=3, help="requests per connection (default 3)")
    ap.add_argument("--idle-probe", type=float, default=0, metavar="SECONDS",
                    help="wait up to SECONDS for the server to close an idle connection")
    ap.add_argument("--sustain", type=float, default=0, metavar="SECONDS",
                    help="send heartbeats for SECONDS on one kept-alive connection")
    ap.add_argument("--sustain-interval", type=float, default=10, metavar="SECONDS")
    ap.add_argument("--sustain-method", choices=("GET", "HEAD"), default="GET")
    ap.add_argument("--json", type=Path, help="write JSON results here")
    ap.add_argument("--markdown", type=Path, help="write a Markdown report here")
    ap.add_argument("--no-network-info", action="store_true",
                    help="skip the ipinfo.io lookup of the test network's ISP")
    args = ap.parse_args()

    isps = load_isps()
    selected = {k: v for k, v in isps.items() if not args.isp or k in args.isp}
    reports: dict[str, IspReport] = {}

    def run(name: str, cfg: dict[str, Any]) -> None:
        reports[name] = verify(name, cfg, args.n, args.idle_probe, args.sustain,
                                args.sustain_interval, args.sustain_method)

    threads = [threading.Thread(target=run, args=item) for item in selected.items()]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    ordered = [reports[k] for k in selected]

    meta = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "n_get": args.n, "idle_limit": args.idle_probe, "sustain_s": args.sustain,
            "sustain_interval": args.sustain_interval, "sustain_method": args.sustain_method}
    if not args.no_network_info:
        meta["test_network"] = detect_test_network()

    md = to_markdown(ordered, meta)
    print(md)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps({"meta": meta, "results": [asdict(r) for r in ordered]},
                                        indent=2), encoding="utf-8")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(md, encoding="utf-8")
    return 0 if all(r.supported for r in ordered) else 1


if __name__ == "__main__":
    sys.exit(main())
