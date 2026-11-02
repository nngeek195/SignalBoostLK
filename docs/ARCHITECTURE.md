# SignalBoostLK 2.0 — Architecture & Implementation Plan

## Goals (non-negotiable)

* Keep one lightweight HTTPS connection to the selected ISP's OoklaServer for as long as the server
  and OS allow, and reconnect with backoff when it closes.
* Routine traffic consists only of `GET /` (or `HEAD /`) on the server root, which returns a 109-byte
  page. `/download` is **only** used by the optional, user-started speed test.
* No claim that this increases speed. Any performance effect is an experiment that has to be measured.
* No fake data. The UI shows only measured values.

## Proposed final project structure

```
SignalBoostLK/
├── main.py                         # desktop entry point
├── app/                            # desktop app (package name kept so builds keep working)
│   ├── config/isps.json            # ISP servers + detection patterns (schema v2)
│   ├── core/                       # pure Python, no Qt imports → unit-testable
│   │   ├── config.py               # typed loader: IspServer dataclass
│   │   ├── isp_detection.py        # org/ASN → ISP mapping, cached lookup, TTL
│   │   ├── network_watch.py        # psutil: detect interface/address changes
│   │   ├── keeper/
│   │   │   ├── http_client.py      # one persistent httpx.Client + trace → connection events
│   │   │   ├── backoff.py          # exponential backoff with full jitter
│   │   │   ├── states.py           # ConnState enum, events, dataclasses
│   │   │   ├── manager.py          # ConnectionKeeper: start/stop, heartbeat loop, reconnect
│   │   │   └── usage.py            # byte accounting, per-hour rates, averages
│   │   └── speedtest.py            # optional manual speed test (from download_engine.py)
│   ├── database/
│   │   ├── db.py                   # connection, platform data dir, migration runner
│   │   ├── migrations/0001_*.sql … # versioned via PRAGMA user_version
│   │   └── repository.py           # sessions, heartbeats, events, prefs, speed tests
│   ├── notifications.py            # tray / desktop notifications
│   └── ui/
│       ├── theme.py  widgets.py  workers.py (QThread adapter)  main_window.py
│       └── pages/ dashboard.py history.py events.py settings.py speedtest.py
├── tests/                          # pytest; local TLS mock server, no live ISP access
├── tools/verify_endpoints.py       # Stage 2 live verifier (manual, not CI)
├── packaging/linux/build_deb.sh    # + .desktop, icon
├── packaging/windows/              # PyInstaller config
├── mobile/                         # Stage 7: Expo (TypeScript, Expo Router, Zustand, expo-sqlite)
│   ├── app/                        # routes
│   ├── src/store, src/db, src/isp
│   └── modules/signalboost-keeper/ # Expo native module
│       ├── android/ (Kotlin)       # ForegroundService (dataSync type) + OkHttp keeper
│       └── ios/ (Swift, Stage 9)   # foreground-only + BGAppRefresh checks; no always-on promise
├── docs/ARCHITECTURE.md, docs/reports/*
└── .github/workflows/ ci.yml (tests) build-windows.yml build-linux.yml release.yml
```

## Key design decisions

1. **Engine is Qt-free.** `ConnectionKeeper` runs on a plain thread and publishes events through a
   callback. The Qt layer only adapts those events to signals. This lets the whole engine run
   under pytest against a mock server, and it is the same model the Kotlin service will follow.
2. **One httpx.Client for the whole session**, with `max_connections=1` and
   `keepalive_expiry` set above the heartbeat interval. The httpx default of 5 s silently
   discards the pooled socket (see the Stage 1 audit, bug #3).
3. **Connection events come from the httpx trace extension** (`connection.connect_tcp.complete`,
   `connection.start_tls.complete`, `http11.receive_response_headers.complete`) plus the
   client port in `network_stream`. That is how the engine distinguishes *TCP established*,
   *TLS completed*, *HTTP OK*, *connection reused* and *connection replaced* without guessing.
4. **Heartbeat interval is driven by measurement.** Every server closes idle sockets after
   ~15 s and any connection after ~60 s of age (Stage 2). The default is 10 s: one connection
   per minute, about 590 KiB/h. See `reports/stage2_endpoint_compatibility.md`.
5. **Backoff:** exponential with full jitter (base 2 s, cap 5 min). It resets after a successful
   heartbeat and is triggered by network errors or non-200 responses. A request that succeeds on a
   new connection is a *reconnect*, not a failure.
6. **ISP detection:** at most one ipinfo.io lookup per network. It is cached with a TTL
   (default 6 h) and refreshed when `network_watch` sees the default interface or address
   change. If the result doesn't map to a supported ISP, we **ask the user** and never guess.
7. **Data accounting:** byte counts come from measured request/response sizes (headers and body),
   plus a TLS handshake cost per new connection taken from Stage 2 measurements. The UI labels it
   "estimated", because TCP/IP headers and retransmits can't be seen from user space.
8. **Privacy:** no public IP addresses are stored. We store the ISP name and ASN/org only.

## Implementation plan

| Stage | Deliverable | Definition of done |
|---|---|---|
| 1 | Repository audit | `docs/reports/stage1_repository_audit.md` ✅ |
| 2 | Endpoint verification | `tools/verify_endpoints.py` and `docs/reports/stage2_endpoint_compatibility.md`, based on live data ✅ |
| 3 | Keeper engine + tests | `app/core/keeper/*`. pytest against a local TLS server covers: connect, reuse, server-close → reconnect, backoff, usage maths, ISP mapping. A live 30 min soak on Mobitel. |
| 4 | Desktop UI | New dashboard/settings/history pages wired to the engine. Manual run on Linux. |
| 5 | SQLite + usage | Migrations, sessions/heartbeats/events tables, retention pruning, prefs. Tests. |
| 6 | Builds | CI tests + Linux `.deb` + Windows `.exe` as artifacts. Tag → GitHub Release. Remove `Download/*.deb` from the tree and update the README. |
| 7 | Mobile | Expo dev build, Kotlin foreground service (`FOREGROUND_SERVICE_DATA_SYNC`, `POST_NOTIFICATIONS`), OkHttp single client, Zustand UI. |
| 8 | Device test | Your physical Android device: service survives screen-off, Doze behaviour measured and documented. |
| 9 | iOS | Foreground keeper only, plus BGTaskScheduler periodic checks, documented limits. |
