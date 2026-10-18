#!/usr/bin/env bash
# MyRemotePC Host Launcher for macOS and Linux
echo "Starting MyRemotePC Host Engine..."
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

if [ -f "venv/bin/python" ]; then
    venv/bin/python main.py
elif command -v python3 &>/dev/null; then
    python3 main.py
else
    python main.py
fi
