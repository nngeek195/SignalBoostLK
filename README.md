# SignalBoostLK 🚀

**Your Internet Signal Booster • Network Monitor • Speed Insights**

SignalBoostLK is a desktop application designed to help Sri Lankan internet users monitor, evaluate and improve their understanding of internet connection performance.

It provides a simple and modern interface to monitor network performance, identify your internet service provider and track download speeds.

## ✨ Features

- **ISP Signal Booster** – A dedicated experience for evaluating and improving your internet connection awareness.
- **Automatic ISP Detection** – Automatically identifies your current internet service provider.
- **Manual ISP Selection** – Select your provider manually whenever needed.
- **Multi-ISP Support** – Supports Mobitel, Dialog, SLT and Hutch.
- **Download Speed Testing** – Measure your internet download performance.
- **Continuous Monitoring** – Monitor your connection repeatedly.
- **Custom Testing Interval** – Configure how frequently monitoring runs.
- **Network History** – Review previous speed test results.
- **Modern Interface** – Clean and user-friendly desktop experience.

## 🌐 Supported Internet Providers

- Mobitel
- Dialog
- SLT
- Hutch

## 📥 Download & Installation

### Linux (Ubuntu / Debian)

Download the latest Debian package:

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

Download the Windows application:

[**Download SignalBoostLK for Windows**](https://github.com/nngeek195/SignalBoostLK/actions/runs/41466118253/artifacts/13153166422)

After downloading:

1. Extract the downloaded ZIP file.
2. Open the extracted folder.
3. Run `SignalBoostLK.exe`.

#### Download using GitHub CLI

Install GitHub CLI:

```bash
sudo apt install gh -y
```

Authenticate with GitHub:

```bash
gh auth login
```

Download the Windows application:

```bash
gh run download 41466118253 \
  --repo nngeek195/SignalBoostLK \
  --name SignalBoostLK-Windows \
  --dir SignalBoostLK-Windows
```

The executable will be available at:

```text
SignalBoostLK-Windows/SignalBoostLK.exe
```

## 🚀 How to Use

1. Launch SignalBoostLK.
2. Allow automatic ISP detection or select your provider manually.
3. Configure your monitoring interval.
4. Start monitoring your internet connection.
5. View download speed measurements and network insights.
6. Stop monitoring whenever you need.

**Note:** Frequent monitoring can consume significant internet data. Choose an appropriate interval, especially when using mobile data.

## 🛠️ Technologies

- Python
- PySide6
- SQLite
- HTTPX
- PyInstaller
- GitHub Actions

## ⚙️ Automated Builds

SignalBoostLK uses GitHub Actions to automate Windows application builds.

- Automatic builds when changes are pushed to the main branch.
- Manual workflow execution.
- Windows executable generation.
- Downloadable build artifacts.

[View Build Workflows](https://github.com/nngeek195/SignalBoostLK/actions)

## 📂 Project Repository

[GitHub – SignalBoostLK](https://github.com/nngeek195/SignalBoostLK)

## 📄 License

Refer to the repository for license information.