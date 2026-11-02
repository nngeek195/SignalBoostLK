# Stage 1 — Repository Audit (SignalBoostLK 0.1.0)

Audited commit: `727c82b` (main), 2026-11-02. 21 tracked files, ~1,000 lines of Python.

## 1. Existing architecture

```
main.py                      QApplication bootstrap → MainWindow
app/
  config/isps.json           ISP → Ookla base URL (flat dict)
  core/
    download_engine.py       run_download_test(): new httpx.Client per test,
                             streams /download?size=N (default 25 MB) and computes Mbps
    isp_detector.py          ipinfo.io lookup + regex org → ISP mapping
    monitor_worker.py        QThread loop: detect ISP → download test → save → sleep
  database/db.py             SQLite `tests` table, created on every connect()
  ui/main_window.py          771 lines: theme/QSS, widgets (Pill, InfoTile, SpeedChart),
                             DetectWorker, MainWindow (Overview / History / Settings pages)
  ui/assets/*.svg            chevrons, GitHub/LinkedIn icons
build_linux_deb.sh           local PyInstaller one-file build → .deb (dpkg-deb)
.github/workflows/build-windows.yml   CI: PyInstaller one-file .exe → artifact (30 days)
Download/signalboostlk_0.1.0_amd64.deb  70 MB binary committed to git
keep.py (untracked)          keep-alive experiment script
```

Data flow per monitoring cycle (old app):
`MonitorWorker.run` → `detect_current_isp()` (ipinfo.io) → `run_download_test()` (25 MB) →
`save_test()` → wait `interval` (default **5 s**) → repeat.

## 2. Critical problem: data consumption

Default settings: 25 MB test every 5 s. The Settings page itself warns "up to ~18 GB per hour".
On top of that, every cycle makes an ipinfo.io request (720 per hour), which will quickly run into
ipinfo's free-tier rate limits. This is the behaviour that 2.0 must eliminate.

## 3. Bugs and technical debt

| # | Severity | Location | Issue |
|---|---|---|---|
| 1 | Critical | `monitor_worker.py`, `main_window.py:517-526` | 25 MB download every 5 s by default (≈18 GB/h). |
| 2 | High | `monitor_worker.py:36` | ISP is re-detected through ipinfo.io on **every** cycle, with no caching. |
| 3 | High | `keep.py` | Uses httpx's default `keepalive_expiry` (5 s) with a 30 s sleep, so the pool discards the connection and **every request opens a new TCP+TLS connection**. Verified: two requests 8 s apart → 2 TCP connects; with `keepalive_expiry=120` → 1. |
| 4 | High | repo | 70 MB `.deb` committed to git (`.git` is 68 MB). README installs it via `raw.githubusercontent.com`. |
| 5 | Medium | README | The Windows download link points to one Actions run whose artifact expires after 30 days (`retention-days: 30`), so the link will break. |
| 6 | Medium | `db.py` | No migrations. The schema is created inline on every `connect()`, and a new connection is opened for every write. |
| 7 | Medium | `db.py:6` | The data directory is hard-coded to `~/.local/share` on Windows too (should use the platform data dir / `QStandardPaths`). |
| 8 | Medium | `db.py` | Stores the user's public IP in every row, which is unnecessary personal data. |
| 9 | Medium | whole repo | No tests, no logging, no type hints on public functions. |
| 10 | Medium | CI | There is no Linux CI build. The `.deb` is built only locally (`build_linux_deb.sh` requires a local `.venv`). |
| 11 | Low | `build_linux_deb.sh:1`, workflow line 1 | A blank line before the shebang makes `#!/usr/bin/env bash` ineffective when the script is executed directly. |
| 12 | Low | workflow | `pyinstaller` is installed twice (requirements.txt plus an explicit step). The build tool sits in runtime `requirements.txt`. |
| 13 | Low | `main_window.py` | 771-line module mixing theme, widgets, workers and pages. |
| 14 | Low | `download_engine.py` | `SERVERS` is loaded at import time, which makes tests harder. The name "download_engine" conflates speed testing with monitoring. |
| 15 | Info | `isp_detector.py` | Matching uses org-name regex only. ASN matching would be more robust. The test network reported `AS45356 Mobitel Pvt Ltd`, which is the only ASN verified so far. |

## 4. Files that can be reused (as-is or nearly)

| File | Why |
|---|---|
| `app/ui/assets/*.svg` | Branding and icons. |
| `main.py` | Bootstrap is fine; only small changes (logging setup). |
| `app/core/isp_detector.py` → `identify_isp()` | The word-boundary regex mapping and the "Mobitel before SLT" ordering are correct. Patterns now live in `isps.json`. |
| `app/ui/main_window.py`: palette, QSS, `Pill`, `InfoTile`, `SpeedChart`, `card()`, `page_header()`, sidebar and social links | Good dark theme and branding. These will be split out into `theme.py` and `widgets.py`. `SpeedChart` can be reused for response-time and data-usage charts. |
| `app/core/download_engine.py` | Kept as the **optional, manual-only** speed test (renamed `speedtest.py`). Its streaming/cancel logic is sound. |

## 5. Files that need modification

| File | Change |
|---|---|
| `app/config/isps.json` | **Done in Stage 2.** Schema v2: host, port, heartbeat method/path, speed-test path, org patterns. |
| `app/core/download_engine.py` | **Done in Stage 2:** loader reads schema v2. Later: rename to `speedtest.py`, never invoked by the monitor. |
| `app/database/db.py` | Platform data dir, migrations, new tables, and dropping the public-IP column from new tables. The old `tests` table is preserved for speed-test history. |
| `build_linux_deb.sh` | Fix shebang, version from one source, icon, call from CI. |
| `.github/workflows/build-windows.yml` | Add a test job and a Linux job, and publish to Releases on tags. |
| `README.md` | Accurate description: no "signal booster" or speed claims, data-usage numbers, Releases-based downloads. |
| `requirements.txt` | Split into runtime and `requirements-dev.txt` (pytest, pyinstaller). |

## 6. Files that should be replaced

| File | Replacement | Reason |
|---|---|---|
| `app/core/monitor_worker.py` | `app/core/keeper/*` (Qt-free engine) plus a thin `app/ui/workers.py` QThread adapter | The old loop is "download 25 MB repeatedly". The new engine is a connection state machine and must be testable without Qt. |
| `app/ui/main_window.py` pages | New dashboard, history, events and settings pages | The current Overview is built around Mbps/progress bars. 2.0 must not show speeds when no speed test runs. |
| `keep.py` | `app/core/keeper/` + `tools/verify_endpoints.py` | Experiment superseded. It is left untracked; you can delete it. |
| `Download/*.deb` | GitHub Releases asset | Binaries do not belong in git. **Not removed yet**, because the README install command depends on it. To be done together with the Release workflow in Stage 6. |

## 7. Features preserved / removed

* Preserved: auto plus manual ISP selection, four ISPs, history, dark UI, branding and social links,
  Windows/Linux builds, and the download speed test (now manual and optional).
* Removed: "continuous monitoring" by repeated speed tests. It is replaced by the lightweight keeper,
  because it consumed GBs per hour (§2).
* Removed from README: "Signal Booster" and "improve your connection" wording. Keeping a connection
  open has not been shown to improve speed. Any such effect must be measured.
