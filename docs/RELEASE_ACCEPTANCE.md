# Release Acceptance Criteria — MyRemotePC v1.0.0

**Target Release**: v1.0.0  
**Date**: October 18, 2026  
**Status**: Active Acceptance Contract

---

## 1. Acceptance Gates

Every requirement defined below has an objective verification method and a definitive Pass/Fail condition. A release cannot be declared ready if any mandatory gate fails.

| ID | Domain | Requirement | Verification Method | Pass / Fail Condition |
| :--- | :--- | :--- | :--- | :--- |
| **G-01** | **Standalone Execution** | The Host application must execute on a clean Windows machine without requiring Python, virtual environments, or external interpreters installed. | Run compiled `MyRemotePC.exe` on a system with isolated environment. | **PASS**: Starts, binds to port, serves UI, and begins capture. |
| **G-02** | **Screen Streaming** | The screen capture engine must deliver full 1080p desktop frames over WebSocket with sub-100ms latency. | Automated WebSocket test verifying `RPC1` binary header, dimensions, and frame arrival rate ≥ 20 FPS. | **PASS**: Constant frame delivery without memory leaks or buffer exhaustion. |
| **G-03** | **Input Synthesis** | Mouse movement, left/right clicks, wheel scrolling, and keyboard keystrokes must be injected accurately into Windows. | Automated synthetic input test verifying coordinate translation and `SendInput` execution. | **PASS**: Pointer translates to correct pixel; key events register. |
| **G-04** | **Security & Rate Limiting** | The `/api/auth` endpoint must reject brute-force attacks by rate-limiting failed attempts. | Automated test sending 10 consecutive invalid access codes within 5 seconds. | **PASS**: Requests after threshold return HTTP 429 Too Many Requests. |
| **G-05** | **Input Sanitization** | Out-of-bounds pointer coordinates (e.g. `< 0.0` or `> 1.0` or `NaN`) must be clamped or rejected without crashing the host. | Automated fuzzing test sending extreme/malformed coordinates. | **PASS**: Host remains online, coordinates clamped safely to `[0.0, 1.0]`. |
| **G-06** | **Clipboard Security** | Clipboard text transfers must have strict size limits (≤ 2 MB) and safe memory allocation. | Automated test sending 10MB payload to `clipboard_write`. | **PASS**: Payload truncated or rejected safely without process OOM. |
| **G-07** | **Multi-Monitor Support** | The system must detect all active monitors and allow switching between displays without restarting. | Multi-monitor enumeration verification in `src/capture.py`. | **PASS**: Returns display list; switching alters capture rect immediately. |
| **G-08** | **Configuration & Overrides** | Application must support `config.json` plus environment variable overrides (`MYREMOTEPC_PORT`, `MYREMOTEPC_HOST`, `MYREMOTEPC_ACCESS_CODE`). | Automated test setting environment variables and verifying precedence. | **PASS**: Environment variable overrides file configuration accurately. |
| **G-09** | **Automated Test Coverage** | A comprehensive test suite (`pytest`) must exist and pass 100% of unit, integration, and security checks. | Execution of `pytest tests/ -v`. | **PASS**: 100% tests pass with zero errors or unhandled exceptions. |
| **G-10** | **Release Packaging** | Release bundle in `dist/releases/v1.0.0/` must include standalone binary, documentation, checksums, and launchers. | Verify presence, plausibility of file sizes, and SHA-256 manifest. | **PASS**: Complete standalone distribution ready for extraction and use. |

---

## 2. Platform & Compatibility Contract

- **Supported Host Operating Systems**: Windows 10 (x64), Windows 11 (x64), Windows Server 2019/2022.
- **Client Viewer Compatibility**: Any modern browser supporting WebSockets and HTML5 Canvas (Chrome 80+, Edge 80+, Firefox 75+, Safari 13+, iOS Safari, Android Chrome).
- **Minimum Hardware Requirements**:
  - Host CPU: Dual-Core 2.0 GHz or higher.
  - Host RAM: 512 MB available.
  - Network: 1 Mbps minimum bandwidth for 720p/1080p balanced streaming.
