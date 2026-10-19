# MyRemotePC — Testing & Verification Guide

This document describes the automated and manual testing procedures used to verify the functional correctness, performance, and security of MyRemotePC.

---

## 1. Automated Test Suite

The automated test suite is implemented using `pytest` and `pytest-asyncio`.

### Running All Automated Tests
To run the automated test suite from the repository root:

```powershell
# Using the project's virtual environment
.\venv\Scripts\pytest.exe tests/ -v
```

### Test Suite Structure

| Test Module | Coverage Scope | Status |
| :--- | :--- | :--- |
| [`tests/test_config.py`](file:///c:/Users/david/OneDrive/Desktop/MyRemotePC/tests/test_config.py) | Machine ID generation, access code hashing, salt uniqueness, config persistence, environment variable overrides. | **100% Pass** (5 tests) |
| [`tests/test_input_injector.py`](file:///c:/Users/david/OneDrive/Desktop/MyRemotePC/tests/test_input_injector.py) | Float coordinate clamping, NaN/Inf rejection, virtual key code mapping, button and scroll wheel sanitization. | **100% Pass** (3 tests) |
| [`tests/test_clipboard.py`](file:///c:/Users/david/OneDrive/Desktop/MyRemotePC/tests/test_clipboard.py) | Set/get round-trip, Unicode handling, buffer length truncation (max 1M chars / 2MB limit), invalid inputs. | **100% Pass** (3 tests) |
| [`tests/test_server_api.py`](file:///c:/Users/david/OneDrive/Desktop/MyRemotePC/tests/test_server_api.py) | `/api/status`, `/api/monitors`, `/api/auth` (success/failure), IP rate limiting (HTTP 429), `/api/settings`, static asset routes. | **100% Pass** (7 tests) |

**Total Automated Coverage**: 18 tests passing.

---

## 2. Production Artifact Verification (Standalone Binary)

To verify that the standalone release binary `dist/MyRemotePC.exe` operates properly on a machine without Python installed:

### Automated Standalone Test
Run the packaging validation script:
```powershell
python package_release.py
```
This script:
1. Validates the existence and size of `dist/MyRemotePC.exe`.
2. Assembles the release files in `dist/releases/v1.0.0/`.
3. Creates `MyRemotePC-v1.0.0-windows-x64.zip`.
4. Calculates and verifies SHA-256 checksums in `SHA256SUMS.txt`.

### Clean-Environment Isolation Test
To test the release artifact in an isolated temporary directory:
```powershell
python -c "
import tempfile, zipfile, subprocess, time, urllib.request, json, os
from pathlib import Path

td = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
with zipfile.ZipFile('dist/releases/v1.0.0/MyRemotePC-v1.0.0-windows-x64.zip', 'r') as zf:
    zf.extractall(td.name)

test_env = os.environ.copy()
test_env['MYREMOTEPC_PORT'] = '8995'
test_env['MYREMOTEPC_ACCESS_CODE'] = 'clean995'

exe = Path(td.name) / 'MyRemotePC-v1.0.0' / 'MyRemotePC.exe'
proc = subprocess.Popen([str(exe)], cwd=str(exe.parent), env=test_env)
try:
    time.sleep(3)
    with urllib.request.urlopen('http://localhost:8995/api/status') as r:
        data = json.loads(r.read().decode())
        assert data['status'] == 'online'
        assert data['port'] == 8995
    print('Isolated installation test: PASSED')
finally:
    proc.kill()
    proc.wait()
    td.cleanup()
"
```

---

## 3. Manual Functional Verification Checklist

1. **Authentication**:
   - Access `http://localhost:8080`.
   - Submit empty access code -> Blocked by HTML5 validation.
   - Submit incorrect code -> Shows "Invalid access code" message.
   - Submit 5 incorrect codes in 60s -> Returns HTTP 429 Too Many Requests.
   - Submit correct code (displayed on host startup) -> Smooth transition to remote desktop canvas.
2. **Interactive Control**:
   - Click, drag, right-click, and scroll on canvas -> Verified accurate cursor positioning on host.
   - Type in text editors -> Verified alphanumeric and special characters register accurately.
   - Click top toolbar special keys (Windows Start, Show Desktop, Lock Workstation) -> Verified action execution on host.
3. **Diagnostics & Multi-Monitor**:
   - Press `F2` -> HUD displays live FPS (~30 FPS), RTT latency, and bandwidth.
   - Open monitor dropdown -> Switch to secondary display -> Canvas smoothly resizes to target monitor dimensions.
