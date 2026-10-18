# Changelog — MyRemotePC

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2026-10-18

### Initial Production Release

#### Added
- **High-Speed GDI Capture Engine**:
  - Direct Win32 GDI capture (`BitBlt` + `GetDIBits`) with persistent zero-copy memory device contexts.
  - Multi-monitor enumeration and real-time display switching.
  - Dynamic resolution adaptation detecting display changes without dropping connections.
  - Adaptive JPEG compression and dirty frame hashing to save CPU and bandwidth when idle.
- **Input Synthesis & Injection**:
  - Sub-millisecond pointer translation via `user32.SendInput`.
  - Strict coordinate clamping `[0.0, 1.0]` with `NaN`/`Inf` sanitization.
  - Mouse clicks, double-clicks, and horizontal/vertical scroll wheel support.
  - Full keyboard mapping including Windows key, modifier keys, and Unicode characters.
- **Security & Hardening**:
  - IP-based sliding window rate limiter on `/api/auth` (max 5 attempts / 60s, returns HTTP 429).
  - PBKDF2-SHA256 password hashing with 100,000 iterations and cryptographic salts.
  - Memory-safe clipboard text synchronization with 2MB payload cap.
- **Universal Web Viewer**:
  - Hardware-accelerated frame decoding via `createImageBitmap` rendering to HTML5 Canvas.
  - Glassmorphic dark-mode interface with floating quick-actions toolbar.
  - Multi-monitor selector, quality presets, special keys menu (Show Desktop, Lock Workstation, Start Menu).
  - Live diagnostics HUD (`F2`) displaying real-time FPS, RTT latency, and bandwidth.
- **Release Engineering & Packaging**:
  - Standalone frozen Windows executable (`MyRemotePC.exe`, 20.1 MB) built with PyInstaller with bundled assets and zero runtime dependencies.
  - Distributable release zip (`MyRemotePC-v1.0.0-windows-x64.zip`) with SHA-256 manifest.
  - One-click launchers (`start_host.bat`, `open_viewer.bat`, `share_over_internet.bat`).
  - Comprehensive automated test suite (`pytest`) with 18 passing unit and integration tests.
