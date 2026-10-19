"""
MyRemotePC - Main Commercial Entrypoint.
Starts the host desktop capture & streaming engine with native system tray presence,
single-instance mutex enforcement, and headless/console mode support.
"""

import argparse
import asyncio
import sys
import threading
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.config import ConfigManager
from src.server import RemoteServer, create_ssl_context, run_app
from src.tray import SystemTrayApp, check_single_instance, set_startup_enabled, is_startup_enabled

def run_server_thread(server: RemoteServer, loop: asyncio.AbstractEventLoop, stop_event: threading.Event):
    """Run aiohttp web server on dedicated background thread."""
    from aiohttp import web

    asyncio.set_event_loop(loop)
    host = server.config.host
    port = server.config.port
    ssl_ctx = None
    if server.config.enable_tls:
        ssl_ctx = create_ssl_context(server.config.cert_file, server.config.key_file)

    runner = web.AppRunner(server.app)
    loop.run_until_complete(runner.setup())
    site = web.TCPSite(runner, host=host, port=port, ssl_context=ssl_ctx)
    loop.run_until_complete(site.start())

    protocol = "https" if ssl_ctx else "http"
    print(f"[MyRemotePC] Host active at {protocol}://localhost:{port}")
    if server.config.is_first_run and server.config.current_plain_code:
        print(f"[MyRemotePC] Unique Access Code: {server.config.current_plain_code}")

    # Wait for stop signal
    stop_event.wait()

    # Clean shutdown
    loop.run_until_complete(runner.cleanup())
    server.shutdown()
    loop.stop()

def main():
    parser = argparse.ArgumentParser(description="MyRemotePC Commercial Host Server")
    parser.add_argument("--console", "--headless", dest="headless", action="store_true", help="Run purely in console/headless mode without system tray")
    parser.add_argument("--install-startup", action="store_true", help="Register MyRemotePC to start automatically on Windows boot")
    parser.add_argument("--uninstall-startup", action="store_true", help="Unregister MyRemotePC from Windows boot")
    parser.add_argument("--port", type=int, default=None, help="Override server port")
    parser.add_argument("--host", type=str, default=None, help="Override bind host")
    args = parser.parse_args()

    # Handle startup registration flags
    if args.install_startup:
        success = set_startup_enabled(True)
        print("[MyRemotePC] Windows boot startup enabled." if success else "[MyRemotePC] Failed to enable startup.")
        sys.exit(0 if success else 1)
    if args.uninstall_startup:
        success = set_startup_enabled(False)
        print("[MyRemotePC] Windows boot startup disabled." if success else "[MyRemotePC] Failed to disable startup.")
        sys.exit(0 if success else 1)

    # 1. Enforce single-instance mutex on Windows
    mutex_handle = check_single_instance()
    if sys.platform == "win32" and mutex_handle is None:
        # Another instance is already running; open browser viewer for convenience
        try:
            cfg = ConfigManager()
            protocol = "https" if cfg.enable_tls else "http"
            import webbrowser
            webbrowser.open(f"{protocol}://localhost:{cfg.port}")
        except Exception:
            pass
        print("[MyRemotePC] Another instance of MyRemotePC is already running. Opening viewer.")
        sys.exit(0)

    # 2. Console / Headless mode
    if args.headless or not sys.platform.startswith("win"):
        try:
            run_app()
        except KeyboardInterrupt:
            print("\n[MyRemotePC] Host server stopped.")
        return

    # 3. System Tray GUI mode (Default for Windows end-users)
    try:
        config = ConfigManager()
        if args.port:
            config.data["port"] = args.port
        if args.host:
            config.data["host"] = args.host

        server = RemoteServer(config=config)
        stop_event = threading.Event()
        loop = asyncio.new_event_loop()

        def on_quit():
            stop_event.set()

        tray_app = SystemTrayApp(server, on_quit_callback=on_quit)

        server_thread = threading.Thread(
            target=run_server_thread,
            args=(server, loop, stop_event),
            daemon=True
        )
        server_thread.start()

        # Run system tray message loop on main thread
        tray_app.run()

    except Exception as e:
        print(f"[MyRemotePC] Tray initialization failed ({e}), falling back to console mode.")
        try:
            run_app()
        except KeyboardInterrupt:
            print("\n[MyRemotePC] Host server stopped.")

if __name__ == "__main__":
    main()
