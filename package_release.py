"""
MyRemotePC Release Packaging Script.
Copies standalone binary, templates, launchers, and documentation into
dist/releases/v1.0.0/ and builds a distributable ZIP package with SHA-256 checksums.
"""

import hashlib
import os
from pathlib import Path
import shutil
import zipfile

ROOT_DIR = Path(__file__).resolve().parent
DIST_DIR = ROOT_DIR / "dist"
RELEASE_VERSION = "v1.0.0"
RELEASE_DIR = DIST_DIR / "releases" / RELEASE_VERSION
ZIP_NAME = f"MyRemotePC-{RELEASE_VERSION}-windows-x64.zip"

def calculate_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def package():
    print(f"Creating release directory: {RELEASE_DIR}")
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Copy executable
    exe_src = DIST_DIR / "MyRemotePC.exe"
    if not exe_src.exists():
        raise FileNotFoundError(f"Missing build artifact: {exe_src}")
    shutil.copy2(exe_src, RELEASE_DIR / "MyRemotePC.exe")

    # 2. Copy sanitized config template
    shutil.copy2(ROOT_DIR / "config.example.json", RELEASE_DIR / "config.example.json")

    # 3. Create standalone start_host.bat
    start_bat_content = (
        "@echo off\r\n"
        "title MyRemotePC Standalone Host\r\n"
        "echo Starting MyRemotePC Standalone Host Engine...\r\n"
        "cd /d \"%~dp0\"\r\n"
        "MyRemotePC.exe\r\n"
        "pause\r\n"
    )
    with open(RELEASE_DIR / "start_host.bat", "w", encoding="utf-8") as f:
        f.write(start_bat_content)

    # 4. Copy open_viewer.bat
    shutil.copy2(ROOT_DIR / "open_viewer.bat", RELEASE_DIR / "open_viewer.bat")

    # 5. Copy share_over_internet.bat
    shutil.copy2(ROOT_DIR / "share_over_internet.bat", RELEASE_DIR / "share_over_internet.bat")

    # 6. Create Release README
    readme_content = (
        f"# MyRemotePC {RELEASE_VERSION} (Windows x64)\n\n"
        "## Quick Start Guide\n"
        "1. Double-click `start_host.bat` (or `MyRemotePC.exe`).\n"
        "2. The host console displays your unique Machine ID and Access Code.\n"
        "3. Open `open_viewer.bat` (or browse to `http://localhost:8080`) on this computer,\n"
        "   or browse to `http://<YOUR_LAN_IP>:8080` from any other device on your Wi-Fi.\n"
        "4. Enter the Access Code and control your desktop in real-time!\n\n"
        "## Zero-Cost Internet Access (WAN)\n"
        "- Run `share_over_internet.bat` to generate a free public link accessible from anywhere in the world.\n"
        "- Or use Tailscale (Free mesh VPN) and connect via `http://<Tailscale_IP>:8080`.\n"
    )
    with open(RELEASE_DIR / "README.md", "w", encoding="utf-8") as f:
        f.write(readme_content)

    # 7. Create Zip archive
    zip_path = RELEASE_DIR / ZIP_NAME
    print(f"Creating ZIP archive: {zip_path}")
    files_to_zip = [
        "MyRemotePC.exe",
        "config.example.json",
        "start_host.bat",
        "open_viewer.bat",
        "share_over_internet.bat",
        "README.md"
    ]
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in files_to_zip:
            fpath = RELEASE_DIR / fname
            zf.write(fpath, arcname=f"MyRemotePC-{RELEASE_VERSION}/{fname}")

    # 8. Generate SHA256 checksums
    checksum_lines = []
    items_to_check = [
        RELEASE_DIR / "MyRemotePC.exe",
        zip_path,
        RELEASE_DIR / f"MyRemotePC-Setup-{RELEASE_VERSION}.exe"
    ]
    for item in items_to_check:
        if item.exists():
            sha = calculate_sha256(item)
            checksum_lines.append(f"{sha}  {item.name}")
            print(f"SHA-256 [{item.name}]: {sha}")

    with open(RELEASE_DIR / "SHA256SUMS.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(checksum_lines) + "\n")

    print(f"\n[Release Engine] Successfully built release {RELEASE_VERSION} at {RELEASE_DIR}")

if __name__ == "__main__":
    package()
