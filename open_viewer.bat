@echo off
title MyRemotePC Viewer Launcher
echo Launching MyRemotePC Viewer...
where msedge >nul 2>nul
if %ERRORLEVEL% equ 0 (
    start msedge --app=http://localhost:8080 --window-size=1280,800
) else (
    start http://localhost:8080
)
exit
