# MyRemotePC — Installation & Setup Guide

This guide details how a recipient (who has never touched the development environment) can install, configure, and operate MyRemotePC.

---

## 1. Distribution Methods

MyRemotePC is distributed in two formats:

1. **Pre-built Standalone Release (Recommended — No Python or dependencies required)**:
   - Location: `dist/releases/v1.0.0/MyRemotePC-v1.0.0-windows-x64.zip`
   - Target: Windows 10, Windows 11, or Windows Server 2019/2022 (x64)
2. **Source Distribution**:
   - Location: Repository root
   - Target: Any system with Python 3.10+ installed.

---

## 2. Option A: Standalone Binary Installation (Fastest)

### Step 1: Obtain the Release Archive
Download or copy `MyRemotePC-v1.0.0-windows-x64.zip` from `dist/releases/v1.0.0/` onto your target machine.

### Step 2: Extract the Archive
Extract the zip file to any directory on your computer (e.g. `C:\Tools\MyRemotePC` or `C:\Users\<YourUser>\Desktop\MyRemotePC`).

The extracted directory contains:
- `MyRemotePC.exe` — Self-contained native Windows host engine.
- `start_host.bat` — 1-click launcher for the host.
- `open_viewer.bat` — 1-click launcher for the client viewer.
- `share_over_internet.bat` — 1-click instant internet tunnel.
- `config.example.json` — Reference configuration template.
- `README.md` — Quick-start instructions.

### Step 3: Run the Host
Double-click `start_host.bat` (or run `MyRemotePC.exe` in Command Prompt / PowerShell).

On first run:
- A random 9-digit **Machine ID** and secure **Access Code** are automatically generated and saved to `config.json`.
- The host prints your local and LAN URLs:
  ```text
  ============================================================
    MYREMOTEPC HOST SERVER ACTIVE
    Machine ID   : 186-072-757
    Machine Name : HostPC
    Access Code  : k8m9x2
    Local URL    : http://localhost:8080
    LAN URL      : http://192.168.1.134:8080
  ============================================================
  ```

### Step 4: Open the Viewer
- **On the same machine**: Double-click `open_viewer.bat` or navigate to `http://localhost:8080` in your web browser.
- **On another PC, Mac, iPad, or phone on the same Wi-Fi / LAN**:
  Open your browser and navigate to `http://<YOUR_LAN_IP>:8080` (e.g. `http://192.168.1.134:8080`).
- Enter the Access Code and click **Connect to Remote Desktop**.

---

## 3. Option B: Running from Source

If you prefer running directly from Python source code:

### Prerequisites
- Windows 10/11 x64
- Python 3.10 or newer with `pip`
- Git

### Installation Steps
```powershell
# 1. Clone repository or open project directory
cd c:\Users\david\OneDrive\Desktop\MyRemotePC

# 2. Create isolated virtual environment
python -m venv venv

# 3. Activate environment
.\venv\Scripts\Activate.ps1

# 4. Install dependencies
pip install -r requirements.txt

# 5. Launch host
python main.py
```

---

## 4. Setting up as a Persistent Background Windows Service

To have MyRemotePC start automatically on Windows boot without requiring an open console:

### Using Windows Task Scheduler (Recommended & Free)
1. Open Windows Task Scheduler (`taskschd.msc`).
2. Click **Create Task**.
3. Name: `MyRemotePC Host Service`.
4. Check **Run whether user is logged on or not** and **Run with highest privileges**.
5. Trigger: **At system startup**.
6. Action: **Start a program** -> Browse to `C:\path\to\MyRemotePC.exe`.
7. Start in: `C:\path\to\` (Directory containing `MyRemotePC.exe`).
8. Click **OK** and save.
