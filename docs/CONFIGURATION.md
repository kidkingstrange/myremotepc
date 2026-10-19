# MyRemotePC — Configuration Reference

This document describes all configuration options, environment variables, security mechanisms, and credential storage used by MyRemotePC.

---

## 1. Configuration File (`config.json`)

The application automatically creates `config.json` next to the executable on its first run if none exists. A sanitized template is provided in [`config.example.json`](file:///c:/Users/david/OneDrive/Desktop/MyRemotePC/config.example.json).

```json
{
    "machine_id": "849-204-183",
    "machine_name": "HostPC",
    "access_code_hash": "d7cf47637a2d8bac25047b5103954dcbb06969ee0e86bf170ae463bafdc9a53f",
    "salt": "1b718587444ef779abfbdede3ef6db4b",
    "port": 8080,
    "host": "0.0.0.0",
    "target_fps": 30,
    "jpeg_quality": 75,
    "enable_clipboard": true,
    "enable_tls": false,
    "cert_file": "",
    "key_file": ""
}
```

### Parameter Schema

| Key | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `machine_id` | String | Auto-generated 9-digit | Unique identifier assigned to this host machine. |
| `machine_name` | String | System Hostname | Human-readable alias shown in viewer header. |
| `access_code_hash`| String | PBKDF2-SHA256 hex | 100,000 iterations PBKDF2 hash of the unique access code generated on first run. |
| `salt` | String | 16-byte hex | Cryptographic random salt used for password hashing. |
| `port` | Integer | `8080` | TCP port the HTTP and WebSocket servers listen on. |
| `host` | String | `"0.0.0.0"` | Network interface to bind (`0.0.0.0` binds to all LAN interfaces; `127.0.0.1` restricts to localhost). |
| `target_fps` | Integer | `30` | Maximum frame rate cap for screen capture (5 to 60). |
| `jpeg_quality` | Integer | `75` | Default image compression quality (20 to 95). |
| `enable_clipboard`| Boolean| `true` | Allows bidirectional text clipboard synchronization. |

---

## 2. Environment Variable Overrides

For containerized or automated headless environments, any setting can be overridden via environment variables without modifying `config.json`:

| Environment Variable | Overrides Key | Example |
| :--- | :--- | :--- |
| `MYREMOTEPC_HOST` | `host` | `MYREMOTEPC_HOST=127.0.0.1` |
| `MYREMOTEPC_PORT` | `port` | `MYREMOTEPC_PORT=9000` |
| `MYREMOTEPC_ACCESS_CODE` | `access_code` | `MYREMOTEPC_ACCESS_CODE=SuperSecretPass!` |
| `MYREMOTEPC_TARGET_FPS` | `target_fps` | `MYREMOTEPC_TARGET_FPS=60` |
| `MYREMOTEPC_JPEG_QUALITY` | `jpeg_quality` | `MYREMOTEPC_JPEG_QUALITY=85` |

---

## 3. Security Hardening Configurations

### Rate Limiting
- The `/api/auth` endpoint restricts brute-force guessing by enforcing a sliding window of **5 failed attempts per IP address per 60 seconds**.
- Requests exceeding the threshold return HTTP `429 Too Many Requests` with a `Retry-After: 60` header.

### Session Tokens
- On successful authentication, the server generates a cryptographically secure 256-bit URL-safe token using `secrets.token_urlsafe(32)`.
- Tokens are held in memory with an expiration period of 24 hours.
