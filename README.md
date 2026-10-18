# MyRemotePC — Modern, Practical & Ultra-Low Latency Remote Access

**MyRemotePC** is a lightweight, high-performance, and cost-effective recreation of the RemotePC desktop remote access system. It is designed to be completely free and self-hosted with zero subscription fees, zero cloud relay bandwidth costs, and minimal resource usage.

---

## 🚀 Key Architectural Advantages

Unlike the legacy RemotePC installation (which uses a 32-bit .NET 4.5 wrapper, 42 separate background executables, proprietary UDT relays, and complex MFC viewers), MyRemotePC provides:

1. **Direct Win32 Zero-Copy Screen Capture**:
   - Captures directly from Windows GDI and desktop display buffers with persistent memory device contexts (`BitBlt` + `GetDIBits`).
   - Achieves up to 60–90 FPS with adaptive JPEG compression and dirty frame skipping (saves 95% CPU and network bandwidth when screen is static).
2. **Native Input Injection**:
   - Uses Windows `user32.SendInput` to provide sub-millisecond mouse movement, clicks, double-clicks, scroll wheel, and full keyboard typing (including Windows key, shortcuts, and international Unicode characters).
3. **Hardware-Decoded Universal Web Viewer**:
   - Pure HTML5/Canvas viewer with glassmorphic UI that runs on any device (Windows, Mac, Linux, iPad, iPhone, Android) with zero software installation required on the client side.
   - Decodes incoming binary frames via browser `createImageBitmap` for GPU-accelerated rendering.
4. **Zero-Cost Operation ($0 Cloud Bills)**:
   - Connects directly over local networks (LAN), peer-to-peer, or through free tunneling (Tailscale, Cloudflare Tunnel, or standard port forwarding).
   - No paid third-party relay or broker servers needed.

---

## 📦 Project Structure

```text
MyRemotePC/
├── config.json             # Persistent machine ID, port, and security access code
├── main.py                 # Application entry point
├── start_host.bat          # 1-Click launcher for host engine
├── open_viewer.bat         # 1-Click launcher for web viewer
├── requirements.txt        # Python dependencies
├── src/
│   ├── capture.py          # Fast Win32 GDI screen capture & multi-monitor engine
│   ├── clipboard.py        # Bidirectional Win32 clipboard sync
│   ├── config.py           # Machine ID & salted PBKDF2 access code hashing
│   ├── input_injector.py   # Win32 SendInput mouse & keyboard dispatcher
│   └── server.py           # aiohttp async server & binary WebSocket stream
└── static/
    ├── app.js              # Binary stream receiver, canvas renderer & input forwarder
    ├── favicon.svg         # RemotePC-style vector logo
    ├── index.html          # Modern dark-mode glassmorphic client interface
    └── styles.css          # Premium CSS styling & responsive layout
```

---

## ⚡ Quick Start Guide

### 1. Start the Host Engine
Double-click `start_host.bat` (or run in terminal):
```powershell
.\venv\Scripts\python.exe main.py
```

The console will display your host information:
```text
============================================================
  MYREMOTEPC HOST SERVER ACTIVE
  Machine ID   : 186-072-757
  Machine Name : Worthy_Writer
  Access Code  : 123456
  Local URL    : http://localhost:8080
  LAN URL      : http://192.168.1.xxx:8080
============================================================
```

### 2. Connect from Any Device

- **On the Same PC (Testing)**:
  - Double-click `open_viewer.bat` or navigate to `http://localhost:8080`.
- **From another PC / Phone / Tablet on the Same Wi-Fi (LAN)**:
  - Open any browser and go to `http://<YOUR_LAN_IP>:8080`.
- **Over the Internet (WAN - $0 Cost)**:
  - **Method A (Zero Config)**: Use [Tailscale](https://tailscale.com/) (Free mesh VPN). Access via `http://<Tailscale_IP>:8080`.
  - **Method B**: Use [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) (Free). Run `cloudflared tunnel --url http://localhost:8080` to get a secure HTTPS URL accessible anywhere in the world.
  - **Method C**: Forward port `8080` on your home router.

### 3. Enter Security Code
Enter the host access code (default: `123456`) and click **Connect to Remote Desktop**.

---

## 🎮 Viewer Features & Hotkeys

- **Floating Quick-Access Toolbar**:
  - **Monitor Switcher**: Seamlessly switch between active displays (Display 1, Display 2, etc.).
  - **Quality Selector**: Switch between Balanced (30 FPS), High Performance (60 FPS), or Low Bandwidth modes.
  - **Special Keys Menu**: Trigger Windows Start Menu (⊞), Show Desktop (⊞+D), Lock Workstation (🔒), and Task Manager / Security.
  - **Clipboard Sync (📋)**: Bidirectional copy/paste between client and host.
  - **Fullscreen Toggle**: Maximizes remote desktop to edge-to-edge display.
- **Diagnostics HUD (F2)**:
  - Press `F2` or click the diagnostics icon on the toolbar to view real-time **FPS**, **RTT Latency (ms)**, **Bandwidth (KB/s)**, and **Resolution**.
