# SignalBoostLK — ISP Endpoint Verification Report

- Generated: 2026-11-02T16:11:03+00:00
- Test network ISP (via ipinfo.io org lookup): AS45356 Mobitel Pvt Ltd
- Requests per connection: 3
- Idle probe limit: 120.0 s
- Only `GET /` and `HEAD /` were requested; `/download` was never used.
- Wire bytes = raw TLS record bytes on the TCP socket (TCP/IP headers excluded).

## Summary

| ISP | Supported | IP used | TCP ms | TLS ms | TLS | GET / | Body | Reuse (raw) | Reuse (httpx) | HEAD / | Idle close |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Mobitel | yes | 103.2.152.1 | 50.4 | 123.9 | TLSv1.3 | 200 | 109 B | yes | yes (1 conn / 3 req) | 200, 0 B body | 14s (TLS close_notify + FIN) |
| Dialog | yes | 2402:4000:100:28::2 | 82.9 | 140.2 | TLSv1.3 | 200 | 109 B | yes | yes (1 conn / 3 req) | 200, 0 B body | 14s (TLS close_notify + FIN) |
| SLT | yes | 2402:d000:0:48::1 | 47.1 | 112.4 | TLSv1.3 | 200 | 109 B | yes | yes (1 conn / 3 req) | 200, 0 B body | 14s (TLS close_notify + FIN) |
| Hutch | yes | 2405:6b00:0:a00::400d | 191.1 | 208.3 | TLSv1.3 | 200 | 109 B | yes | yes (1 conn / 3 req) | 200, 0 B body | 15s (TLS close_notify + FIN) |

## Data cost per heartbeat (measured)

| ISP | TLS handshake tx/rx | GET / tx/rx (reused conn) | HEAD / tx/rx (reused conn) |
|---|---|---|---|
| Mobitel | 597 / 4730 B | 189 / 599 B | 190 / 490 B |
| Dialog | 597 / 4726 B | 184 / 551 B | 185 / 442 B |
| SLT | 597 / 4728 B | 187 / 599 B | 188 / 490 B |
| Hutch | 597 / 4723 B | 182 / 616 B | 183 / 507 B |

## Sustained keep-alive (GET every 10s for 1200s)

| ISP | Requests OK | TCP connections | Server closes (conn age s) | Longest conn | Wire tx/rx | Projected per hour |
|---|---|---|---|---|---|---|
| Mobitel | 121/121 | 18 | [69.8, 69.9, 69.9, 69.9, 69.9, 69.9, 69.8, 69.8, 69.8, 69.8, 69.9, 69.9, 69.9, 69.9, 69.9, 69.9, 69.9] | 70s | 33615 / 157619 B | 560 KiB |
| Dialog | 121/121 | 19 | [69.7, 69.8, 69.8, 69.8, 69.7, 69.7, 69.8, 69.8, 69.8, 69.8, 69.8, 9.8, 69.8, 69.8, 69.8, 69.7, 69.8, 69.8] | 70s | 33607 / 156489 B | 557 KiB |
| SLT | 121/121 | 18 | [69.8, 69.9, 69.9, 69.9, 69.9, 69.8, 69.8, 69.8, 69.8, 69.8, 69.8, 69.9, 69.9, 69.9, 69.9, 69.8, 69.9] | 70s | 33373 / 157583 B | 559 KiB |
| Hutch | 121/121 | 18 | [69.4, 69.6, 69.7, 69.6, 69.6, 69.5, 69.6, 69.5, 69.6, 69.6, 69.6, 69.6, 69.6, 69.6, 69.6, 69.5, 69.6] | 70s | 32768 / 159550 B | 563 KiB |

## Mobitel — `speedtest2.mobitel.lk.prod.hosts.ooklaserver.net:8080`

- DNS A: 103.2.152.1
- DNS AAAA: none
- Connected to: 103.2.152.1
- TLS: TLSv1.3 / TLS_AES_256_GCM_SHA384; ALPN when offering h2: `(none)`
- Certificate: verified=True, SAN matches host=True
  - Subject: commonName=server-21051.prod.hosts.ooklaserver.net
  - Issuer: countryName=US, organizationName=Let's Encrypt, commonName=YR1
  - Not after: Dec 24 10:41:05 2026 GMT
- httpx client ports across requests: [43290, 43290, 43290] (statuses [200, 200, 200])
- GET #1: 200 OK, body 109 B, 101 ms, wire tx/rx 189/599 B, local port 43188
- GET #2: 200 OK, body 109 B, 161 ms, wire tx/rx 189/599 B, local port 43188
- GET #3: 200 OK, body 109 B, 41 ms, wire tx/rx 189/599 B, local port 43188
- HEAD: 200 OK, body 0 B, 29 ms, wire tx/rx 190/490 B
- Relevant response headers: `{'Connection': 'Keep-Alive', 'Cache-Control': 'no-store', 'Content-Type': 'text/html', 'Content-Length': '109'}`
- Body preview: `<html><head><title>OoklaServer</title></head><body><h1>OoklaServer</h1><p>It worked!<br /></p></body></html>
`

## Dialog — `ookla1.dialog.lk.prod.hosts.ooklaserver.net:8080`

- DNS A: 122.255.0.42
- DNS AAAA: 2402:4000:100:28::2
- Connected to: 2402:4000:100:28::2
- TLS: TLSv1.3 / TLS_AES_256_GCM_SHA384; ALPN when offering h2: `(none)`
- Certificate: verified=True, SAN matches host=True
  - Subject: commonName=server-11442.prod.hosts.ooklaserver.net
  - Issuer: countryName=US, organizationName=Let's Encrypt, commonName=YR2
  - Not after: Jan 23 21:47:43 2027 GMT
- httpx client ports across requests: [34264, 34264, 34264] (statuses [200, 200, 200])
- GET #1: 200 OK, body 109 B, 312 ms, wire tx/rx 184/551 B, local port 34210
- GET #2: 200 OK, body 109 B, 52 ms, wire tx/rx 184/551 B, local port 34210
- GET #3: 200 OK, body 109 B, 68 ms, wire tx/rx 184/551 B, local port 34210
- HEAD: 200 OK, body 0 B, 107 ms, wire tx/rx 185/442 B
- Relevant response headers: `{'Connection': 'Keep-Alive', 'Cache-Control': 'no-store', 'Content-Type': 'text/html', 'Content-Length': '109'}`
- Body preview: `<html><head><title>OoklaServer</title></head><body><h1>OoklaServer</h1><p>It worked!<br /></p></body></html>
`

## SLT — `hqspeedtest1.slt.lk.prod.hosts.ooklaserver.net:8080`

- DNS A: 222.165.175.10
- DNS AAAA: 2402:d000:0:48::1
- Connected to: 2402:d000:0:48::1
- TLS: TLSv1.3 / TLS_AES_256_GCM_SHA384; ALPN when offering h2: `(none)`
- Certificate: verified=True, SAN matches host=True
  - Subject: commonName=server-60180.prod.hosts.ooklaserver.net
  - Issuer: countryName=US, organizationName=Let's Encrypt, commonName=YR1
  - Not after: Dec  4 17:26:41 2026 GMT
- httpx client ports across requests: [36834, 36834, 36834] (statuses [200, 200, 200])
- GET #1: 200 OK, body 109 B, 101 ms, wire tx/rx 187/599 B, local port 36784
- GET #2: 200 OK, body 109 B, 158 ms, wire tx/rx 187/599 B, local port 36784
- GET #3: 200 OK, body 109 B, 42 ms, wire tx/rx 187/599 B, local port 36784
- HEAD: 200 OK, body 0 B, 38 ms, wire tx/rx 188/490 B
- Relevant response headers: `{'Connection': 'Keep-Alive', 'Cache-Control': 'no-store', 'Content-Type': 'text/html', 'Content-Length': '109'}`
- Body preview: `<html><head><title>OoklaServer</title></head><body><h1>OoklaServer</h1><p>It worked!<br /></p></body></html>
`

## Hutch — `wplsp.hutch.lk.prod.hosts.ooklaserver.net:8080`

- DNS A: 103.21.167.134
- DNS AAAA: 2405:6b00:0:a00::400d
- Connected to: 2405:6b00:0:a00::400d
- TLS: TLSv1.3 / TLS_AES_256_GCM_SHA384; ALPN when offering h2: `(none)`
- Certificate: verified=True, SAN matches host=True
  - Subject: commonName=server-31312.prod.hosts.ooklaserver.net
  - Issuer: countryName=US, organizationName=Let's Encrypt, commonName=YR1
  - Not after: Dec 26 07:25:55 2026 GMT
- httpx client ports across requests: [37802, 37802, 37802] (statuses [200, 200, 200])
- GET #1: 200 OK, body 109 B, 356 ms, wire tx/rx 182/616 B, local port 37724
- GET #2: 200 OK, body 109 B, 171 ms, wire tx/rx 182/616 B, local port 37724
- GET #3: 200 OK, body 109 B, 157 ms, wire tx/rx 182/616 B, local port 37724
- HEAD: 200 OK, body 0 B, 262 ms, wire tx/rx 183/507 B
- Relevant response headers: `{'Connection': 'Keep-Alive', 'Cache-Control': 'no-store', 'Content-Type': 'text/html', 'Content-Length': '109'}`
- Body preview: `<html><head><title>OoklaServer</title></head><body><h1>OoklaServer</h1><p>It worked!<br /></p></body></html>
`
