# MyRemotePC — Deployment & Remote Access Guide

This guide details how to deploy MyRemotePC across different network environments, ranging from home/office LANs to zero-cost, encrypted WAN access across the Internet.

---

## 1. Local Network (LAN / Wi-Fi) Deployment

When the host and client computers are on the same Wi-Fi or office network:

1. **Find Host IP Address**:
   - The host server automatically prints its LAN IP on startup:
     ```text
     LAN URL: http://192.168.1.134:8080
     ```
   - Or open Command Prompt and run `ipconfig`.
2. **Connect from Client**:
   - On your other PC, Mac, phone, or tablet, open any browser and enter `http://192.168.1.134:8080`.
   - Enter your host access code and connect.
3. **Firewall Requirement**:
   - If the second device cannot connect, ensure port `8080` is allowed in Windows Defender Firewall:
     ```powershell
     # In elevated PowerShell (Run as Administrator)
     netsh advfirewall firewall add rule name="MyRemotePC" dir=in action=allow protocol=TCP localport=8080
     ```

---

## 2. Zero-Cost Internet Access (WAN)

To connect across the Internet without paying for relay servers, static public IPs, or cloud brokers, choose either of the two free options below:

### Option A: Cloudflare Tunnel (Recommended — No Software on Client)
Cloudflare Tunnel allows you to expose `http://localhost:8080` via a secure, encrypted public HTTPS domain for free without opening router ports.

1. **Host Setup**:
   - Run the included launcher script:
     ```bat
     share_over_internet.bat
     ```
   - Or run via npx / cloudflared:
     ```powershell
     npx -y untun@latest tunnel --port 8080
     ```
   - A public HTTPS link is generated (e.g. `https://my-session-xyz.trycloudflare.com`).
2. **Client Connection**:
   - Open that URL in any browser on any device anywhere in the world.
   - Enter your security access code and connect!

### Option B: Tailscale Mesh VPN (Direct Encrypted P2P)
Tailscale creates a secure, private encrypted WireGuard mesh network connecting your devices directly.

1. Install [Tailscale](https://tailscale.com/) on both Host PC and Client PC/Phone.
2. Sign in to the same free account on both devices.
3. On the Client device, open your browser and navigate to:
   ```text
   http://<Host_Tailscale_IP>:8080
   ```
4. All traffic flows directly peer-to-peer with zero intermediate relay latency.

---

## 3. Production Hardening Checklist for Public Access

When exposing MyRemotePC to the public internet:
- [x] Unique high-entropy access code is automatically generated on first run (with PBKDF2-SHA256 hashing).
- [x] Rate limiting is enabled by default to block brute-force attempts.
- [x] Ensure the host is served over HTTPS / WSS when using public tunnels.
- [x] Keep `config.json` restricted to authorized Windows user accounts.
