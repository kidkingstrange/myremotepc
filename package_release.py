"""
MyRemotePC Release Packaging Script.
Automates standalone binary compilation via PyInstaller, Inno Setup compiler detection,
and creates the distributable ZIP release archive with SHA-256 checksums and commercial EULA.
"""

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

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

def build_executable():
    print("[Release Engine] Compiling standalone executable via PyInstaller...")
    spec_file = ROOT_DIR / "myremotepc.spec"
    pyinstaller_exe = sys.executable.replace("python.exe", "pyinstaller.exe")
    cmd = [pyinstaller_exe if os.path.exists(pyinstaller_exe) else "pyinstaller", "--noconfirm", str(spec_file)]
    res = subprocess.run(cmd, cwd=str(ROOT_DIR))
    if res.returncode != 0:
        raise RuntimeError(f"PyInstaller build failed with exit code {res.returncode}")
    print("[Release Engine] Standalone executable compiled successfully.")

def build_inno_installer():
    iscc_candidates = [
        "iscc",
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe")
    ]
    iscc_path = None
    for cand in iscc_candidates:
        if shutil.which(cand) or os.path.exists(cand):
            iscc_path = cand
            break

    if iscc_path:
        print(f"[Release Engine] Compiling Inno Setup installer using {iscc_path}...")
        iss_file = ROOT_DIR / "installer.iss"
        res = subprocess.run([iscc_path, str(iss_file)], cwd=str(ROOT_DIR))
        if res.returncode == 0:
            print("[Release Engine] Inno Setup installer compiled successfully.")
        else:
            print(f"[Release Engine] Inno Setup compilation returned code {res.returncode}")
    else:
        print("[Release Engine] Inno Setup compiler (ISCC.exe) not found on system. Skipping .exe installer generation.")

def package(build_binary: bool = False):
    if build_binary:
        build_executable()
        build_inno_installer()

    print(f"\n[Release Engine] Preparing release directory: {RELEASE_DIR}")
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)

    # Security Sanity Check: Ensure no personal secrets or configs are packaged
    for forbidden in ["config.json", "*.pem", "*.key", "*.crt"]:
        for match in RELEASE_DIR.glob(forbidden):
            os.remove(match)
            print(f"[Release Engine] Purged sensitive file from release staging: {match.name}")

    # 1. Copy executable
    exe_src = DIST_DIR / "MyRemotePC.exe"
    if not exe_src.exists():
        raise FileNotFoundError(f"Missing build artifact: {exe_src}. Run with --build to compile first.")
    shutil.copy2(exe_src, RELEASE_DIR / "MyRemotePC.exe")

    # 2. Copy sanitized config template, Commercial EULA, and Third-Party Licenses
    shutil.copy2(ROOT_DIR / "config.example.json", RELEASE_DIR / "config.example.json")
    shutil.copy2(ROOT_DIR / "LICENSE", RELEASE_DIR / "LICENSE")
    if (ROOT_DIR / "THIRD_PARTY_LICENSES.md").exists():
        shutil.copy2(ROOT_DIR / "THIRD_PARTY_LICENSES.md", RELEASE_DIR / "THIRD_PARTY_LICENSES.md")

    # 3. Create standalone start_host.bat (convenience runner)
    start_bat_content = (
        "@echo off\r\n"
        "title MyRemotePC Standalone Host\r\n"
        "echo Starting MyRemotePC Standalone Host Engine...\r\n"
        "cd /d \"%~dp0\"\r\n"
        "start \"\" MyRemotePC.exe\r\n"
    )
    with open(RELEASE_DIR / "start_host.bat", "w", encoding="utf-8") as f:
        f.write(start_bat_content)

    # 4. Copy open_viewer.bat and share_over_internet.bat
    shutil.copy2(ROOT_DIR / "open_viewer.bat", RELEASE_DIR / "open_viewer.bat")
    shutil.copy2(ROOT_DIR / "share_over_internet.bat", RELEASE_DIR / "share_over_internet.bat")

    # 5. Create Release README
    readme_content = (
        f"# MyRemotePC {RELEASE_VERSION} (Windows x64)\n\n"
        "## Commercial Remote Desktop Host\n"
        "MyRemotePC provides ultra-low latency, zero-install remote desktop streaming\n"
        "directly into any modern web browser.\n\n"
        "## Quick Start Guide\n"
        "1. Double-click `MyRemotePC.exe`.\n"
        "2. The host starts in your Windows System Tray (blue screen icon in the taskbar).\n"
        "3. Right-click the tray icon to view your unique Machine ID and Access Code.\n"
        "4. Click **Open Web Viewer** (or browse to `http://localhost:8080`) to connect,\n"
        "   or connect from any phone, tablet, or laptop on your Wi-Fi via `http://<YOUR_LAN_IP>:8080`.\n"
        "5. Enter the Access Code and control your desktop in real-time!\n\n"
        "## Internet Access (WAN)\n"
        "- Run `share_over_internet.bat` to generate a secure Cloudflare Tunnel URL.\n"
        "- Or use Tailscale / WireGuard to connect remotely across networks.\n\n"
        "## Licensing\n"
        "This software is distributed under the terms of the Commercial Software License Agreement in `LICENSE`.\n"
    )
    with open(RELEASE_DIR / "README.md", "w", encoding="utf-8") as f:
        f.write(readme_content)

    # 6. Create Zip archive
    zip_path = RELEASE_DIR / ZIP_NAME
    print(f"[Release Engine] Building ZIP archive: {zip_path}")
    files_to_zip = [
        "MyRemotePC.exe",
        "config.example.json",
        "LICENSE",
        "THIRD_PARTY_LICENSES.md",
        "start_host.bat",
        "open_viewer.bat",
        "share_over_internet.bat",
        "README.md"
    ]
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in files_to_zip:
            fpath = RELEASE_DIR / fname
            if fpath.exists():
                zf.write(fpath, arcname=f"MyRemotePC-{RELEASE_VERSION}/{fname}")

    # 7. Generate SHA256 checksums
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", action="store_true", help="Compile executable via PyInstaller before packaging")
    args = parser.parse_args()
    package(build_binary=args.build)
