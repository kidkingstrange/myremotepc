"""
MyRemotePC - Main Entrypoint.
Starts the host desktop capture & streaming engine.
"""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.server import run_app

if __name__ == "__main__":
    try:
        run_app()
    except KeyboardInterrupt:
        print("\n[MyRemotePC] Host server stopped.")
