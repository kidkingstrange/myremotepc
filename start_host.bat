@echo off
title MyRemotePC Host Engine
echo Starting MyRemotePC Host Engine...
cd /d "%~dp0"
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe main.py
) else (
    python main.py
)
pause
