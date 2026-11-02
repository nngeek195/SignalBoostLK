# SignalBoostLK

**ISP Monitor • Speed Test • Network Insights**

SignalBoostLK is a desktop network monitoring and ISP-specific download speed boosting application designed for Sri Lankan internet users.

It helps users monitor their internet connection, identify their ISP and measure download performance using ISP-specific Ookla speed test servers.

## Features

- Automatic ISP detection.
- Manual ISP selection.
- Support for Mobitel, Dialog, SLT and Hutch.
- ISP-specific download speed testing.
- Continuous network monitoring.
- Configurable testing intervals.
- Download speed measurements in Mbps.
- Test history and network insights.
- Modern desktop interface.

## Supported ISPs

| ISP | Speed Test Server |
|---|---|
| Mobitel | Mobitel Ookla |
| Dialog | Dialog Ookla |
| SLT | SLT Ookla |
| Hutch | Hutch Ookla |

## Download

### Linux (Ubuntu / Debian)

Download the `.deb` package:

```bash
wget -O signalboostlk.deb \
"https://raw.githubusercontent.com/nngeek195/SignalBoostLK/main/Download/signalboostlk_0.1.0_amd64.deb"
```

Install SignalBoostLK:

```bash
sudo apt install ./signalboostlk.deb
```

Launch the application:

```bash
signalboostlk
```

### Windows

Download the latest Windows build from GitHub Actions:

[Download SignalBoostLK for Windows](https://github.com/nngeek195/SignalBoostLK/actions/runs/41466118253/artifacts/13153166422)

The downloaded artifact is a ZIP file. Extract it and run:

```text
SignalBoostLK.exe
```

Alternatively, download it using GitHub CLI.

Install GitHub CLI and authenticate:

```bash
sudo apt install gh -y
gh auth login
```

Download the Windows executable:

```bash
gh run download 41466118253 \
  --repo nngeek195/SignalBoostLK \
  --name SignalBoostLK-Windows \
  --dir SignalBoostLK-Windows
```

The executable will be available inside:

```text
SignalBoostLK-Windows/SignalBoostLK.exe
```

## How to Use

1. Open SignalBoostLK.
2. Allow the application to detect your ISP automatically.
3. Select an ISP manually if automatic detection is unavailable.
4. Configure the monitoring interval.
5. Start monitoring.
6. View download speed results and network history.
7. Stop monitoring whenever you want.

**Note:** Frequent speed tests consume internet data. Choose an appropriate testing interval, especially when using a mobile data connection.

## Technology Stack

- Python
- PySide6
- Qt
- HTTPX
- SQLite
- PyInstaller
- GitHub Actions

## Build Automation

Windows builds are automatically generated using GitHub Actions.

Workflow:

- Triggered when code is pushed to `main`.
- Can also be started manually.
- Builds the Windows executable.
- Uploads the executable as a downloadable workflow artifact.

[View GitHub Actions](https://github.com/nngeek195/SignalBoostLK/actions)

## Project Repository

[GitHub – SignalBoostLK](https://github.com/nngeek195/SignalBoostLK)

## License

See the repository for license information.
