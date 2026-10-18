# MyRemotePC — Troubleshooting & Diagnostics

This document provides diagnostic steps and solutions for common operational issues encountered during installation, execution, or connection.

---

## 1. Connection & Networking Issues

### Issue: "Unable to connect" from a second PC on the same Wi-Fi
- **Probable Cause**: Windows Defender Firewall on the host PC is blocking incoming TCP traffic on port 8080.
- **Solution**:
  1. Open an elevated PowerShell (Right-click -> Run as Administrator).
  2. Run the following command to allow port 8080:
     ```powershell
     netsh advfirewall firewall add rule name="MyRemotePC" dir=in action=allow protocol=TCP localport=8080
     ```
  3. Ensure both PCs are connected to the same Wi-Fi subnet (e.g. `192.168.1.xxx`).

### Issue: Port 8080 is already in use by another application
- **Symptom**: `OSError: [Errno 10048] error while attempting to bind on address ('0.0.0.0', 8080)`.
- **Solution**:
  - Edit `config.json` and change `"port": 8080` to an available port, such as `9000` or `8443`.
  - Alternatively, pass the environment variable before launching:
    ```powershell
    $env:MYREMOTEPC_PORT = "9000"
    .\MyRemotePC.exe
    ```

---

## 2. Authentication & Access Codes

### Issue: "Invalid access code. Please try again."
- **Probable Cause**: The entered access code does not match the stored hash in `config.json`.
- **Solution**:
  - Open `config.json` in a text editor.
  - Check the `"access_code"` field.
  - If you wish to reset your access code, change `"access_code": "mynewpassword"` and delete `"access_code_hash": ""`. The server will automatically re-hash your new password on the next launch!

### Issue: "Too many failed attempts. Try again in 60 seconds."
- **Probable Cause**: The rate limiter triggered after 5 consecutive incorrect password submissions.
- **Solution**: Wait 60 seconds for the sliding window to expire, or restart the host server to clear the in-memory failure tracker.

---

## 3. Screen Capture & Display

### Issue: Screen appears frozen or black
- **Probable Cause**: The host computer has entered sleep mode or the Windows session is locked.
- **Solution**:
  - Ensure Windows power settings do not put the computer to sleep during remote sessions (Settings -> Power & Sleep -> When plugged in, PC goes to sleep: Never).
  - Use the top toolbar's **Special Keys -> Show Desktop** or click to send an input event.

### Issue: Resolution changed or external monitor disconnected
- **Symptom**: Stream aspect ratio distorted or stream stops updating.
- **Solution**:
  - The capture engine automatically detects resolution changes every 60 frames.
  - Refresh the viewer page in your browser to adapt to the new aspect ratio.
  - Use the toolbar **Monitor Switcher** dropdown to reselect the desired display.

---

## 4. Diagnostics & Live Telemetry

- **HUD Display**: Press **`F2`** at any time while connected in the web viewer to toggle the live diagnostics HUD overlay:
  - **FPS**: Current frames rendered per second (target: 30 FPS).
  - **RTT Latency**: Round-trip time in milliseconds between client and host.
  - **Bandwidth**: Current data transfer rate in KB/s.
  - **Resolution**: Native screen width and height.
