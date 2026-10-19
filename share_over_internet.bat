@echo off
title MyRemotePC - Cloudflare Internet Tunnel
echo ============================================================
echo   MyRemotePC Secure Internet Sharing (Cloudflare Tunnel)
echo   Encrypted HTTPS / WSS Zero-Config Cloudflare Tunnel
echo ============================================================
cd /d "%~dp0"

:: Check if cloudflared is installed or in PATH
set "CLOUDFLARED_BIN=cloudflared.exe"
where cloudflared >nul 2>&1
if %errorlevel% equ 0 (
    set "CLOUDFLARED_BIN=cloudflared"
    goto :RUN_TUNNEL
)

if exist "%~dp0cloudflared.exe" (
    set "CLOUDFLARED_BIN=%~dp0cloudflared.exe"
    goto :RUN_TUNNEL
)

echo [Cloudflare] cloudflared not found locally. Downloading official Cloudflare binary...
curl.exe -fL -o "%~dp0cloudflared.exe" "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
if %errorlevel% neq 0 (
    echo [ERROR] Failed to download cloudflared.exe automatically.
    echo Please download cloudflared from:
    echo   https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
    echo and place cloudflared.exe in this folder.
    pause
    exit /b 1
)
set "CLOUDFLARED_BIN=%~dp0cloudflared.exe"

:RUN_TUNNEL
echo.
set "TARGET_URL=http://localhost:8080"
set "EXTRA_FLAGS="
curl.exe -k -s -o nul https://localhost:8080/api/status >nul 2>&1
if %errorlevel% equ 0 (
    echo [Cloudflare] Detected HTTPS enabled on local host. Enabling secure TLS tunnel relay...
    set "TARGET_URL=https://localhost:8080"
    set "EXTRA_FLAGS=--no-tls-verify"
)

echo [Cloudflare] Starting tunnel for %TARGET_URL% ...
echo [Cloudflare] Look for your public URL below (ends in .trycloudflare.com):
echo.
"%CLOUDFLARED_BIN%" tunnel %EXTRA_FLAGS% --url %TARGET_URL%
pause

