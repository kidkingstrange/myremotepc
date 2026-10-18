# MyRemotePC — Architecture Specification

This document details the software architecture, data flow, IPC protocols, and subsystem designs of MyRemotePC.

---

## 1. High-Level Architecture Diagram

```mermaid
graph TD
    subgraph Host Machine (Windows x64)
        HostServer[aiohttp Asynchronous Host Server<br/>HTTP REST + WebSocket Router]
        CaptureEngine[Win32 GDI Capture Engine<br/>BitBlt + GetDIBits + DIBitmap]
        InputInjector[Win32 SendInput Dispatcher<br/>user32.SendInput]
        ClipboardMgr[Win32 Clipboard Manager<br/>CF_UNICODETEXT]
        ConfigMgr[Configuration & Auth Manager<br/>PBKDF2-SHA256]
    end

    subgraph Client Device (Browser / Any OS)
        ClientUI[HTML5 / CSS3 Glassmorphic Viewport]
        AppJS[Client Engine app.js<br/>WebSocket Binary Client]
        Canvas[HTML5 2D Canvas<br/>Hardware createImageBitmap]
    end

    subgraph Network Transport
        HTTP[HTTP REST Endpoints: /api/status, /api/auth]
        WSStream[Binary WebSocket Stream: /ws<br/>Custom 'RPC1' Binary Packets]
    end

    HostServer <--> ConfigMgr
    HostServer --> CaptureEngine
    HostServer --> InputInjector
    HostServer <--> ClipboardMgr

    ClientUI --> HTTP
    AppJS <--> WSStream
    WSStream <--> HostServer
    AppJS --> Canvas
```

---

## 2. Subsystem Deep-Dive

### 2.1 Screen Capture Pipeline (`src/capture.py`)
- **Zero-Copy GDI Memory Context**:
  - Allocates a persistent 32-bit top-down bitmap (`BITMAPINFO` with negative height) in memory on initialization.
  - Reuses the memory device context (`CreateCompatibleDC`) and reusable buffer allocation across all frames, producing zero memory allocation overhead per tick.
- **Dynamic Resolution Adaptation**:
  - Periodically verifies active screen metrics. If the host display changes resolution or docks/undocks an external monitor, the GDI contexts and buffer structures automatically reinitialize without dropping the connection.
- **Adaptive Frame Rate & Dirty Detection**:
  - Evaluates dirty hashes across sample regions of the frame buffer. If the desktop is idle, duplicate frames are omitted, reducing CPU and network usage by 95%.
  - Pushes a forced keyframe every 2 seconds to ensure newly connected clients or temporary packet drops recover immediately.

### 2.2 Binary WebSocket Streaming Protocol
Frames are transmitted over WebSocket in a binary packet format:

| Offset (Bytes) | Field | Type | Description |
| :--- | :--- | :--- | :--- |
| `0..3` | **Magic** | `char[4]` | Constant header `RPC1` (0x52504331). |
| `4..5` | **Width** | `uint16` (Big Endian) | Pixel width of the frame (e.g. 1920). |
| `6..7` | **Height** | `uint16` (Big Endian) | Pixel height of the frame (e.g. 1080). |
| `8..11` | **Timestamp** | `uint32` (Big Endian) | Host millisecond timestamp for RTT calculation. |
| `12..N` | **Payload** | `byte[]` | Raw compressed JPEG image bytes. |

### 2.3 Client-Side Rendering (`static/app.js`)
- Receives the binary `ArrayBuffer` from WebSocket.
- Extracts the 12-byte header with a `DataView`.
- Instantiates a `Blob` containing JPEG bytes and passes it to `window.createImageBitmap()`.
- `createImageBitmap` performs hardware-accelerated decoding off the main UI thread.
- Renders the bitmap onto the `<canvas>` element via `ctx.drawImage()`.

### 2.4 Input Synthesis & Sanitization (`src/input_injector.py`)
- Translates normalized pointer coordinates `(0.0 to 1.0)` sent from the client canvas into absolute Windows virtual desktop coordinates `(0 to 65535)`.
- Validates and clamps inputs using `clamp_float()` to protect against `NaN`, `Inf`, or malicious out-of-bounds coordinates.
- Maps browser key codes (`KeyboardEvent.code`) to native Windows Virtual Key codes (`VK_MAP`) and scan codes.
- Direct Unicode typing using `KEYEVENTF_UNICODE` for international characters and emojis.
