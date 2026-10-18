# MyRemotePC — Modern, Practical & Ultra-Low Latency Remote Access

[![Release](https://img.shields.io/badge/Release-v1.0.0-blue.svg)](dist/releases/v1.0.0/)
[![Tests](https://img.shields.io/badge/Tests-18%20Passed-brightgreen.svg)](tests/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20x64-lightgrey.svg)](dist/releases/v1.0.0/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**MyRemotePC** is a production-ready, ultra-low latency, and cost-effective remote desktop access system. Built from the ground up as a modern alternative to legacy remote control tools, it delivers hardware-accelerated screen streaming and interactive control at **$0 cloud cost** with zero subscriptions and zero mandatory third-party accounts.

---

## 🌟 Key Highlights

- **Standalone Native Binary**: Zero Python or runtime installations needed on the host. Simply run `MyRemotePC.exe`.
- **Zero-Install Web Viewer**: Client runs in any modern browser (Chrome, Edge, Firefox, Safari) on any PC, Mac, Linux, iPad, iPhone, or Android device.
- **Direct GPU-Accelerated Frame Capture**: Sub-10ms GDI capture (`BitBlt` + `GetDIBits`) delivering up to 60 FPS with adaptive JPEG compression and dirty frame hashing.
- **Sub-Millisecond Input Synthesis**: Complete mouse, wheel, keyboard, and Windows shortcut control via native `user32.SendInput`.
- **Hardened Security**: PBKDF2-SHA256 password hashing (100,000 iterations), sliding-window IP rate limiting, input boundary clamping, and 2MB clipboard payload protection.
- **Zero-Cost Operation ($0 Cloud Bills)**: Works directly over LAN, peer-to-peer via free mesh VPNs (Tailscale), or instant public tunnels (Cloudflare Tunnel).

---

## ⚡ Quick Start

### For End-Users (Standalone Release)
1. Download or extract the release archive:
   👉 [`dist/releases/v1.0.0/MyRemotePC-v1.0.0-windows-x64.zip`](file:///c:/Users/david/OneDrive/Desktop/MyRemotePC/dist/releases/v1.0.0/MyRemotePC-v1.0.0-windows-x64.zip)
2. Double-click **`start_host.bat`** (or `MyRemotePC.exe`).
3. Note your **Machine ID** and **Access Code** printed in the console.
4. Open **`open_viewer.bat`** (or go to `http://localhost:8080`) from this PC, or `http://<YOUR_LAN_IP>:8080` from any other device on your Wi-Fi network.
5. Enter your Access Code and click **Connect to Remote Desktop**.

### For Developers (Running from Source)
```powershell
# Setup virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Run automated tests
pytest tests/ -v

# Launch host server
python main.py
```

---

## 📁 Repository Structure

```text
MyRemotePC/
├── config.json                     # Persistent machine ID, port, and security access code
├── config.example.json             # Sanitized configuration template
├── main.py                         # Application entrypoint
├── package_release.py              # Release compilation and packaging script
├── myremotepc.spec                 # PyInstaller standalone build specification
├── requirements.txt                # Runtime and development dependencies
├── start_host.bat                  # 1-Click host launcher
├── open_viewer.bat                 # 1-Click viewer launcher
├── share_over_internet.bat         # 1-Click free internet tunnel launcher
├── dist/
│   ├── MyRemotePC.exe              # Standalone 20.1 MB frozen host executable
│   └── releases/v1.0.0/            # Ship-ready release candidate directory
│       ├── MyRemotePC.exe
│       ├── MyRemotePC-v1.0.0-windows-x64.zip
│       ├── SHA256SUMS.txt
│       └── ...
├── docs/                           # Comprehensive Engineering Documentation
│   ├── ARCHITECTURE.md             # Subsystem designs, protocols, and data flow
│   ├── CONFIGURATION.md            # Environment variables and config reference
│   ├── DEPLOYMENT.md               # LAN, WAN, Tailscale, and tunnel setup
│   ├── INSTALLATION.md             # Complete step-by-step setup instructions
│   ├── PRODUCTION_AUDIT.md         # Baseline discovery & architectural audit
│   ├── PRODUCTION_PROGRESS.md      # Engineering milestones & tracking
│   ├── RELEASE_ACCEPTANCE.md       # Objective pass/fail verification contract
│   └── TROUBLESHOOTING.md          # Common failure modes and resolutions
├── src/                            # Core Application Modules
│   ├── capture.py                  # Win32 GDI screen capture & multi-monitor engine
│   ├── clipboard.py                # Bidirectional Win32 clipboard sync
│   ├── config.py                   # Machine ID & salted PBKDF2 hashing
│   ├── input_injector.py           # Win32 SendInput mouse & keyboard dispatcher
│   └── server.py                   # aiohttp async server & binary WebSocket stream
├── static/                         # Web Client Assets
│   ├── app.js                      # Binary stream receiver, canvas renderer & input forwarder
│   ├── favicon.svg                 # SVG application vector logo
│   ├── icon.ico                    # Embedded Windows executable multi-size icon
│   ├── index.html                  # Modern dark-mode glassmorphic client interface
│   └── styles.css                  # Premium CSS styling & responsive layout
└── tests/                          # Automated Verification Suite
    ├── test_clipboard.py           # Clipboard buffer and length tests
    ├── test_config.py              # Configuration & hashing unit tests
    ├── test_input_injector.py      # Input clamping & sanitization tests
    └── test_server_api.py          # API endpoints, rate limiting, and auth tests
```

---

## 📖 Documentation Index

- [Architecture & Protocol Specification](docs/ARCHITECTURE.md)
- [Installation Guide](docs/INSTALLATION.md)
- [Configuration & Environment Variables](docs/CONFIGURATION.md)
- [Deployment & Remote Access (LAN & WAN)](docs/DEPLOYMENT.md)
- [Testing & Verification Guide](docs/TESTING.md)
- [Troubleshooting & Diagnostics](docs/TROUBLESHOOTING.md)
- [Production Audit](docs/PRODUCTION_AUDIT.md)
- [Release Acceptance Criteria](docs/RELEASE_ACCEPTANCE.md)
- [Release Progress Tracking](docs/PRODUCTION_PROGRESS.md)
- [Changelog](CHANGELOG.md)
- [License](LICENSE)

---

## 🔒 Security & Verification

Verify the integrity of release artifacts against `dist/releases/v1.0.0/SHA256SUMS.txt`:
```powershell
Get-FileHash dist\releases\v1.0.0\MyRemotePC-v1.0.0-windows-x64.zip -Algorithm SHA256
```
Expected SHA-256: `e5c80bc2efbec74945d2eccc8287c4d4078dde17b517171743fb5c7578c324fd`
