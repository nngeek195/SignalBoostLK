# Stage 2 — ISP Endpoint Compatibility Report

Measured 2026-11-02 from a Mobitel network (`AS45356 Mobitel Pvt Ltd`) with
`tools/verify_endpoints.py`. Raw output: `endpoint_verification.md` / `.json`,
`sustain_head_10s.json`, `sustain_get_20s.json` (same folder).
Only `GET /` and `HEAD /` were requested. `/download` was never used.

## Verdict: all four endpoints are supported and behave identically

| | Mobitel | Dialog | SLT | Hutch |
|---|---|---|---|---|
| DNS A | 103.2.152.1 | 122.255.0.42 | 222.165.175.10 | 103.21.167.134 |
| DNS AAAA | **none** | 2402:4000:100:28::2 | 2402:d000:0:48::1 | 2405:6b00:0:a00::400d |
| Address used | IPv4 | IPv6 | IPv6 | IPv6 |
| TCP connect | 28–57 ms | 65–1047 ms¹ | 30–48 ms | 114–180 ms |
| TLS | 1.3, AES-256-GCM | same | same | same |
| Certificate | Let's Encrypt, valid, SAN matches | same | same | same |
| HTTP/2 (ALPN) | not offered | not offered | not offered | not offered |
| `GET /` | 200, 109 B body | 200, 109 B | 200, 109 B | 200, 109 B |
| `HEAD /` | 200, 0 B body | same | same | same |
| `Connection` header | `Keep-Alive` | same | same | same |
| Reuse (3 requests, 1 socket) | ✅ | ✅ | ✅ | ✅ |
| Reuse via one httpx.Client | ✅ 1 TCP connect / 3 requests | ✅ | ✅ | ✅ |
| **Idle close** | **~15 s** (close_notify + FIN) | ~15 s | ~15 s | ~15 s |
| **Max connection lifetime** | **~60 s** even while active | ~60 s | ~60 s | ~60 s |

¹ One slow 1047 ms IPv6 connect to Dialog, then 65–83 ms on later runs. Keep an eye on it. If IPv6
paths prove unreliable, a "prefer IPv4" option would help.

The body is the OoklaServer status page:
`<html>…<h1>OoklaServer</h1><p>It worked!<br /></p></body></html>`. The response carries no
`Keep-Alive: timeout=` header, so the limits below were found by measurement only.

## Connection limits (the most important finding)

1. **Idle timeout ≈ 15 s.** The server sends TLS `close_notify` and then a TCP FIN after 14–15 s
   of silence.
2. **Lifetime ≈ 60 s.** With heartbeats every 10 s, every connection on every ISP was closed after
   the 7th request (~70 s). With heartbeats every 5 s it was closed after ~65 s (13 requests).
   So the limit is connection **age**, not a request count.
3. Close is clean (FIN), so it is detected before the next request and no heartbeat fails. In
   1 of ~480 HEAD requests the close raced the request. The engine now retries that once,
   immediately, on a new connection.

**Consequence:** no single connection can be held open indefinitely on these servers. The most the
server allows is one connection per ~60 s, kept active with heartbeats sent more often than every
15 s. The keeper does that and reconnects automatically. Verified live: 150 s on Mobitel at a 10 s
interval gave 15/15 OK with reconnects at exactly 60 s and 120 s.

## Measured data cost (TLS bytes on the socket, TCP/IP headers excluded)

| Item | Bytes (tx / rx) |
|---|---|
| TLS handshake (new connection) | ~597 / ~4,730 |
| `GET /` on a reused connection | ~185 / ~600 |
| `HEAD /` on a reused connection | ~186 / ~490 |

| 20-minute run | Requests OK | Connections | Measured per hour |
|---|---|---|---|
| GET every 10 s (all 4 ISPs) | 484/484 | 18–19 per ISP | **≈ 560 KiB/h** |
| HEAD every 10 s | 484/485² | 18 per ISP | ≈ 520 KiB/h |
| GET every 20 s (10 min) | 124/124 | one per request | ≈ 1.1 MiB/h |

² The one failure was the close race described above. It happened before the retry was added.

For comparison, 0.1.0 used 25 MB every 5 s, which is about 18 GB/h.

**Choosing an interval** (model calibrated on the measurements above):

| Interval | Behaviour | Est. per hour |
|---|---|---|
| 5 s | persistent (replaced every ~60 s) | ~875 KiB |
| **10 s (default)** | persistent (replaced every ~60 s) | **~590 KiB** |
| 14 s | persistent, close to the idle limit | ~510 KiB |
| 30 s | new connection every heartbeat | ~715 KiB |
| 60 s | new connection every heartbeat | ~360 KiB |

A 60 s interval uses the least data, but then there is no persistent connection at all. Each
heartbeat is a separate connect, request and close. The 10 s default fits the product goal of
keeping the connection open as long as the server permits. This is a user setting.

## Possible optimisations (not yet done)

* `HEAD /` instead of `GET /` saves ~110 B per request (~7%). It is verified on all four servers.
  It is configurable per ISP in `isps.json` (`heartbeat.method`).
* TLS session resumption would cut most of the ~4.7 KB handshake download at each 60 s
  reconnect. httpx doesn't expose it, so this would need a custom transport. Worth considering
  for the Android OkHttp client too.

## Caveats

* All tests ran from a single Mobitel connection. Behaviour from Dialog, SLT or Hutch access
  networks, and through mobile CGNAT, may differ and should be re-run with
  `python tools/verify_endpoints.py --idle-probe 120 --sustain 600`.
* Server limits are operator configuration and can change without notice. The engine doesn't
  depend on them, because it reconnects whenever a connection closes.
