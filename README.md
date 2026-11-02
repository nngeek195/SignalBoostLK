# SignalBoostLK — Linux Edition

A desktop ISP monitor and ISP-specific download tester.

## Requirements
- Ubuntu 24.04+ (or another modern Linux desktop)
- Python 3.10+
- Internet connection

## Install
```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
cd SignalBoostLK
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

## Usage
1. Open the application.
2. Click **Detect ISP** to identify the current public IP and provider (optional).
3. Leave the ISP selector on **Auto-detect**, or pick Mobitel, Dialog, SLT or Hutch. A manual choice always takes priority over detection.
4. Set the test size and the interval between tests in Settings (default 25 MB every 60 s). The Settings page shows the worst-case data use per hour.
5. Click **Start monitoring**. The first test starts immediately.
6. Click **Stop** to stop monitoring. A download in progress is cancelled right away.

## ISP endpoints
The endpoints are read from `app/config/isps.json`. Edit that file to change or add servers. They are based on the supplied PowerShell script. ISP server availability, DNS, TLS certificates and endpoint behaviour can change. A successful HTTP request is required before a result is saved.

## Data and privacy
- Test history is stored locally in `~/.local/share/SignalBoostLK/history.db`.
- ISP detection uses `https://ipinfo.io/json` and therefore sends a request to that service.
- The app does not collect credentials or require administrator/root privileges.
- Download tests consume data. Configure a smaller test size if you are on a metered connection.

## Notes
This is an initial Linux MVP. ISP identification depends on provider metadata returned by the IP lookup service; manual selection is provided as a fallback. Download speed is measured as payload bytes received divided by elapsed time, in decimal Mbps.
