"""
MyRemotePC Core Host Server.
Provides asynchronous HTTP endpoints, static asset hosting, security rate limiting,
session lifecycle management, and high-throughput full-duplex WebSocket binary streaming.
"""

import asyncio
from collections import defaultdict
import json
import os
import signal
import struct
import sys
import time
from pathlib import Path
from typing import Set, Dict, Any, Optional, List, Tuple

from aiohttp import web
import aiohttp

from .config import ConfigManager
from .capture import ScreenCapturer, enumerate_monitors
from .input_injector import InputInjector
from .clipboard import get_clipboard_text, set_clipboard_text

# Resolve static directory relative to module or frozen bundle
if getattr(sys, 'frozen', False):
    STATIC_DIR = Path(sys._MEIPASS) / "static" if hasattr(sys, '_MEIPASS') else Path(__file__).resolve().parent.parent / "static"
else:
    STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

class RateLimiter:
    """In-memory IP-based rate limiter with sliding window and progressive penalty."""
    def __init__(self, max_attempts: int = 5, window_seconds: int = 60, max_tracked: int = 5000):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.max_tracked = max_tracked
        self.attempts: Dict[str, List[float]] = defaultdict(list)
        self.banned_until: Dict[str, float] = {}

    def is_allowed(self, ip: str) -> Tuple[bool, int]:
        now = time.time()
        # Check active temporary ban
        if ip in self.banned_until:
            remaining = int(self.banned_until[ip] - now)
            if remaining > 0:
                return False, remaining
            else:
                del self.banned_until[ip]

        # Clean older attempts
        self.attempts[ip] = [t for t in self.attempts[ip] if now - t < self.window_seconds]
        if len(self.attempts[ip]) >= self.max_attempts:
            retry_after = int(self.window_seconds - (now - self.attempts[ip][0]))
            # If persistent offender (e.g. 15+ failures), enforce an extended 15-minute ban
            if len(self.attempts[ip]) >= self.max_attempts * 3:
                self.banned_until[ip] = now + 900
                retry_after = 900
            return False, max(1, retry_after)
        return True, 0

    def record_failure(self, ip: str):
        now = time.time()
        # Bound tracking table memory
        if len(self.attempts) > self.max_tracked:
            # Purge expired entries
            expired = [k for k, v in self.attempts.items() if not v or (now - v[-1] > self.window_seconds * 2)]
            for k in expired:
                self.attempts.pop(k, None)
        self.attempts[ip].append(now)

    def reset(self, ip: str):
        self.attempts.pop(ip, None)
        self.banned_until.pop(ip, None)

class RemoteServer:
    def __init__(self, config: Optional[ConfigManager] = None):
        self.config = config or ConfigManager()
        self.capturer = ScreenCapturer(monitor_index=0)
        self.injector = InputInjector()
        self.app = web.Application()
        self.rate_limiter = RateLimiter(max_attempts=5, window_seconds=60)
        
        self.active_websockets: Set[web.WebSocketResponse] = set()
        self.authenticated_sessions: Dict[str, float] = {}  # token -> expiry
        self.streaming_tasks: Dict[web.WebSocketResponse, asyncio.Task] = {}
        self.ip_connections: Dict[str, int] = defaultdict(int)
        
        self.target_fps = self.config.target_fps
        self.jpeg_quality = self.config.jpeg_quality
        self.is_running = True
        
        self.setup_routes()

    def revoke_all_sessions(self) -> int:
        """Revoke all active session tokens and forcefully disconnect all connected WebSockets."""
        self.authenticated_sessions.clear()
        count = len(self.active_websockets)
        for ws in list(self.active_websockets):
            if not ws.closed:
                try:
                    asyncio.create_task(self._close_revoked_ws(ws))
                except Exception:
                    pass
        return count

    async def _close_revoked_ws(self, ws: web.WebSocketResponse):
        try:
            await ws.send_json({"type": "error", "error": "Session revoked by host"})
            await ws.close(code=4401, message=b"Session revoked")
        except Exception:
            pass

    def setup_routes(self):
        # API Routes
        self.app.router.add_get('/api/status', self.handle_status)
        self.app.router.add_post('/api/auth', self.handle_auth)
        self.app.router.add_get('/api/monitors', self.handle_monitors)
        self.app.router.add_post('/api/settings', self.handle_settings)
        self.app.router.add_get('/ws', self.handle_websocket)

        # Static Assets & Marketing
        self.app.router.add_static('/static', STATIC_DIR, show_index=False)
        self.app.router.add_get('/', self.handle_index)
        self.app.router.add_get('/landing', self.handle_landing)
        self.app.router.add_get('/pricing', self.handle_landing)
        self.app.router.add_get('/download/windows', self.handle_download_windows)
        self.app.router.add_get('/download/zip', self.handle_download_zip)

    def get_client_ip(self, request: web.Request) -> str:
        remote = request.remote or "unknown"
        # Only trust forwarded proxy headers if the request is proxied from localhost/loopback
        if remote in ("127.0.0.1", "::1", "localhost"):
            cf_ip = request.headers.get("CF-Connecting-IP")
            if cf_ip:
                return cf_ip.strip()
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                return forwarded.split(",")[0].strip()
        return remote

    def is_request_authenticated(self, request: web.Request, data: Optional[Dict[str, Any]] = None) -> bool:
        """Check if request carries a valid session token."""
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            if self._validate_token(token):
                return True
        token_query = request.query.get("token")
        if token_query and self._validate_token(token_query):
            return True
        if data and isinstance(data, dict):
            token_body = data.get("token")
            if token_body and self._validate_token(str(token_body)):
                return True
        return False

    def _validate_token(self, token: str) -> bool:
        if not token:
            return False
        expiry = self.authenticated_sessions.get(token)
        if expiry and expiry > time.time():
            return True
        if token in self.authenticated_sessions:
            self.authenticated_sessions.pop(token, None)
        return False

    async def handle_index(self, request: web.Request) -> web.Response:
        index_file = STATIC_DIR / "index.html"
        if index_file.exists():
            return web.FileResponse(index_file)
        return web.Response(text="MyRemotePC Viewer - UI assets missing", status=404)

    async def handle_landing(self, request: web.Request) -> web.Response:
        landing_file = STATIC_DIR / "landing.html"
        if landing_file.exists():
            return web.FileResponse(landing_file)
        # Fallback to index if landing page not found
        return await self.handle_index(request)

    async def handle_download_windows(self, request: web.Request) -> web.Response:
        installer_candidates = [
            Path(__file__).resolve().parent.parent / "dist" / "releases" / "v1.0.0" / "MyRemotePC-Setup-v1.0.0.exe",
            Path(sys.executable).parent / "MyRemotePC-Setup-v1.0.0.exe" if getattr(sys, 'frozen', False) else None,
            Path(sys.executable).parent / "releases" / "v1.0.0" / "MyRemotePC-Setup-v1.0.0.exe" if getattr(sys, 'frozen', False) else None
        ]
        for candidate in installer_candidates:
            if candidate and candidate.exists():
                return web.FileResponse(
                    candidate,
                    headers={
                        "Content-Disposition": 'attachment; filename="MyRemotePC-Setup-v1.0.0.exe"',
                        "Content-Type": "application/octet-stream"
                    }
                )
        # Fallback redirect to official GitHub Release direct download URL
        raise web.HTTPFound("https://github.com/kidkingstrange/myremotepc/releases/download/v1.0.0/MyRemotePC-Setup-v1.0.0.exe")

    async def handle_download_zip(self, request: web.Request) -> web.Response:
        zip_candidates = [
            Path(__file__).resolve().parent.parent / "dist" / "releases" / "v1.0.0" / "MyRemotePC-v1.0.0-windows-x64.zip",
            Path(sys.executable).parent / "MyRemotePC-v1.0.0-windows-x64.zip" if getattr(sys, 'frozen', False) else None
        ]
        for candidate in zip_candidates:
            if candidate and candidate.exists():
                return web.FileResponse(
                    candidate,
                    headers={
                        "Content-Disposition": 'attachment; filename="MyRemotePC-v1.0.0-windows-x64.zip"',
                        "Content-Type": "application/zip"
                    }
                )
        raise web.HTTPFound("https://github.com/kidkingstrange/myremotepc/releases/download/v1.0.0/MyRemotePC-v1.0.0-windows-x64.zip")

    async def handle_status(self, request: web.Request) -> web.Response:
        monitors = [m.to_dict() for m in self.capturer.monitors]
        return web.json_response({
            "status": "online",
            "machine_id": self.config.machine_id,
            "machine_name": self.config.machine_name,
            "port": self.config.port,
            "monitors": monitors,
            "current_monitor": self.capturer.current_monitor_index,
            "target_fps": self.target_fps,
            "jpeg_quality": self.jpeg_quality,
            "active_viewers": len(self.active_websockets)
        })

    async def handle_monitors(self, request: web.Request) -> web.Response:
        if not self.is_request_authenticated(request):
            return web.json_response({"error": "Unauthorized: valid session token required"}, status=401)
        monitors = [m.to_dict() for m in enumerate_monitors()]
        return web.json_response({"monitors": monitors, "current": self.capturer.current_monitor_index})

    async def handle_auth(self, request: web.Request) -> web.Response:
        client_ip = self.get_client_ip(request)
        allowed, retry_after = self.rate_limiter.is_allowed(client_ip)
        if not allowed:
            return web.json_response(
                {"success": False, "error": f"Too many failed attempts. Try again in {retry_after} seconds."},
                status=429,
                headers={"Retry-After": str(retry_after)}
            )

        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON body"}, status=400)

        access_code = data.get("access_code", "")
        if self.config.verify_access_code(access_code):
            self.rate_limiter.reset(client_ip)
            import secrets
            token = secrets.token_urlsafe(32)
            self.authenticated_sessions[token] = time.time() + 86400  # 24h
            return web.json_response({
                "success": True,
                "token": token,
                "machine_id": self.config.machine_id,
                "machine_name": self.config.machine_name
            })

        self.rate_limiter.record_failure(client_ip)
        return web.json_response({"success": False, "error": "Invalid access code"}, status=401)

    async def handle_settings(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON body"}, status=400)

        if not self.is_request_authenticated(request, data):
            return web.json_response({"error": "Unauthorized: valid session token required"}, status=401)

        if "fps" in data:
            self.target_fps = max(5, min(60, int(data["fps"])))
        if "quality" in data:
            self.jpeg_quality = max(20, min(95, int(data["quality"])))
        if "monitor" in data:
            self.capturer.select_monitor(int(data["monitor"]))

        return web.json_response({
            "success": True,
            "fps": self.target_fps,
            "quality": self.jpeg_quality,
            "monitor": self.capturer.current_monitor_index
        })

    async def handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        client_ip = self.get_client_ip(request)

        # Connection-level rate limit check
        allowed, retry_after = self.rate_limiter.is_allowed(client_ip)
        if not allowed:
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            await ws.send_json({"type": "error", "error": f"Too many failed attempts. Try again in {retry_after} seconds."})
            await ws.close(code=4429, message=b"Rate limit exceeded")
            return ws

        # Enforce maximum concurrent active WebSocket connections per IP
        if self.ip_connections[client_ip] >= 10:
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            await ws.send_json({"type": "error", "error": "Too many concurrent connections from this IP."})
            await ws.close(code=4429, message=b"Connection limit exceeded")
            return ws

        self.ip_connections[client_ip] += 1

        # CSWSH check: validate Origin header if present
        origin = request.headers.get("Origin")
        if origin:
            from urllib.parse import urlparse
            parsed_origin = urlparse(origin)
            origin_host = parsed_origin.hostname or ""
            host_header = (request.headers.get("Host") or "").split(":")[0]
            is_valid_origin = (
                origin_host in ("localhost", "127.0.0.1", "::1", self.config.host, host_header, "0.0.0.0") or
                origin_host.endswith(".trycloudflare.com") or
                origin_host.endswith(".cloudflare.com")
            )
            if not is_valid_origin:
                self.ip_connections[client_ip] = max(0, self.ip_connections[client_ip] - 1)
                ws = web.WebSocketResponse()
                await ws.prepare(request)
                await ws.send_json({"type": "error", "error": "Cross-Origin WebSocket connection rejected."})
                await ws.close(code=1008, message=b"Origin rejected")
                return ws

        ws = web.WebSocketResponse(heartbeat=15.0, max_msg_size=5*1024*1024)
        await ws.prepare(request)

        token = request.query.get("token", "")
        is_authenticated = False
        if token:
            if self._validate_token(token):
                is_authenticated = True
            else:
                self.rate_limiter.record_failure(client_ip)

        self.active_websockets.add(ws)

        stream_task: Optional[asyncio.Task] = None
        if is_authenticated:
            stream_task = asyncio.create_task(self.stream_loop(ws))
            self.streaming_tasks[ws] = stream_task

        auth_deadline = time.time() + 10.0 if not is_authenticated else None

        try:
            while not ws.closed:
                if not is_authenticated:
                    remaining_auth_time = (auth_deadline - time.time()) if auth_deadline else 0
                    if remaining_auth_time <= 0:
                        await ws.send_json({"type": "error", "error": "Authentication timeout. Connection closed."})
                        await ws.close(code=4408, message=b"Auth timeout")
                        break
                    try:
                        msg = await asyncio.wait_for(ws.receive(), timeout=max(0.1, remaining_auth_time))
                    except asyncio.TimeoutError:
                        await ws.send_json({"type": "error", "error": "Authentication timeout. Connection closed."})
                        await ws.close(code=4408, message=b"Auth timeout")
                        break
                else:
                    msg = await ws.receive()

                if msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSING, aiohttp.WSMsgType.CLOSED):
                    break

                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        cmd = json.loads(msg.data)
                    except Exception:
                        continue

                    cmd_type = cmd.get("type", "")

                    if not is_authenticated:
                        if cmd_type == "auth":
                            # Enforce rate limiting on WebSocket auth attempts
                            allowed, retry_after = self.rate_limiter.is_allowed(client_ip)
                            if not allowed:
                                await ws.send_json({
                                    "type": "auth_result",
                                    "success": False,
                                    "error": f"Too many failed attempts. Try again in {retry_after} seconds."
                                })
                                await ws.close(code=4429, message=b"Rate limit exceeded")
                                break

                            code = cmd.get("access_code", "")
                            req_token = cmd.get("token", "")
                            if (req_token and self._validate_token(req_token)) or (code and self.config.verify_access_code(code)):
                                is_authenticated = True
                                auth_deadline = None
                                self.rate_limiter.reset(client_ip)
                                await ws.send_json({"type": "auth_result", "success": True})
                                stream_task = asyncio.create_task(self.stream_loop(ws))
                                self.streaming_tasks[ws] = stream_task
                            else:
                                self.rate_limiter.record_failure(client_ip)
                                allowed, retry_after = self.rate_limiter.is_allowed(client_ip)
                                if not allowed:
                                    await ws.send_json({
                                        "type": "auth_result",
                                        "success": False,
                                        "error": f"Too many failed attempts. Try again in {retry_after} seconds."
                                    })
                                    await ws.close(code=4429, message=b"Rate limit exceeded")
                                    break
                                else:
                                    await ws.send_json({"type": "auth_result", "success": False, "error": "Invalid access code"})
                        continue

                    # Authenticated Controls
                    if cmd_type == "mouse_move":
                        nx = float(cmd.get("x", 0.0))
                        ny = float(cmd.get("y", 0.0))
                        self.injector.mouse_move(
                            nx, ny,
                            self.capturer.left, self.capturer.top,
                            self.capturer.width, self.capturer.height
                        )

                    elif cmd_type == "mouse_button":
                        btn = cmd.get("button", "left")
                        act = cmd.get("action", "click")
                        self.injector.mouse_button(btn, act)

                    elif cmd_type == "mouse_wheel":
                        dy = float(cmd.get("delta_y", 0.0))
                        dx = float(cmd.get("delta_x", 0.0))
                        self.injector.mouse_wheel(dy, dx)

                    elif cmd_type == "key":
                        code = cmd.get("code", "")
                        act = cmd.get("action", "down")
                        char = cmd.get("char")
                        self.injector.key_event(code, act, char)

                    elif cmd_type == "switch_monitor":
                        m_idx = int(cmd.get("index", 0))
                        self.capturer.select_monitor(m_idx)
                        await ws.send_json({
                            "type": "monitor_switched",
                            "index": self.capturer.current_monitor_index,
                            "width": self.capturer.width,
                            "height": self.capturer.height
                        })

                    elif cmd_type == "set_quality":
                        if "quality" in cmd:
                            self.jpeg_quality = max(20, min(95, int(cmd["quality"])))
                        if "fps" in cmd:
                            self.target_fps = max(5, min(60, int(cmd["fps"])))

                    elif cmd_type == "clipboard_read":
                        if not self.config.enable_clipboard:
                            await ws.send_json({"type": "clipboard_content", "text": "", "error": "Clipboard disabled by host policy"})
                        else:
                            loop = asyncio.get_running_loop()
                            clip_txt = await loop.run_in_executor(None, get_clipboard_text)
                            await ws.send_json({"type": "clipboard_content", "text": clip_txt})

                    elif cmd_type == "clipboard_write":
                        if self.config.enable_clipboard:
                            text = cmd.get("text", "")
                            loop = asyncio.get_running_loop()
                            await loop.run_in_executor(None, set_clipboard_text, text)

                    elif cmd_type == "lock_screen":
                        self.injector.lock_workstation()

                    elif cmd_type == "show_desktop":
                        self.injector.show_desktop()

                    elif cmd_type == "ping":
                        t_client = cmd.get("t", 0)
                        await ws.send_json({"type": "pong", "t": t_client, "server_t": time.time()})

                elif msg.type == aiohttp.WSMsgType.ERROR:
                    break

        finally:
            self.ip_connections[client_ip] = max(0, self.ip_connections[client_ip] - 1)
            if stream_task and not stream_task.done():
                stream_task.cancel()
            self.streaming_tasks.pop(ws, None)
            self.active_websockets.discard(ws)

        return ws

    async def stream_loop(self, ws: web.WebSocketResponse):
        """Asynchronous screen capture and binary transmission loop."""
        try:
            await ws.send_json({
                "type": "screen_init",
                "width": self.capturer.width,
                "height": self.capturer.height,
                "monitors": [m.to_dict() for m in self.capturer.monitors],
                "current_monitor": self.capturer.current_monitor_index
            })
        except Exception:
            return

        last_force_time = time.time()

        while not ws.closed and self.is_running:
            t_start = time.time()
            interval = 1.0 / max(5, self.target_fps)

            force_keyframe = (t_start - last_force_time) > 2.0
            if force_keyframe:
                last_force_time = t_start

            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                self.capturer.capture_jpeg,
                self.jpeg_quality,
                force_keyframe
            )

            if result is not None and not ws.closed:
                jpeg_bytes, w, h = result
                timestamp_ms = int(time.time() * 1000) & 0xFFFFFFFF
                header = struct.pack('>4sHHI', b'RPC1', w, h, timestamp_ms)
                packet = header + jpeg_bytes
                
                try:
                    await ws.send_bytes(packet)
                except Exception:
                    break

            elapsed = time.time() - t_start
            sleep_time = max(0.001, interval - elapsed)
            await asyncio.sleep(sleep_time)

    def shutdown(self):
        """Clean shutdown handler."""
        self.is_running = False
        self.capturer.cleanup()

def create_ssl_context(cert_file: Optional[str] = None, key_file: Optional[str] = None):
    """Load SSL context for TLS transport encryption (HTTPS / WSS), generating self-signed if missing."""
    import ssl
    from .config import get_default_cert_paths, generate_self_signed_cert

    if not cert_file or not key_file:
        cp, kp = get_default_cert_paths()
    else:
        cp, kp = Path(cert_file), Path(key_file)

    if not cp.exists() or not kp.exists():
        try:
            print("[Server] Generating self-signed TLS certificate for secure LAN transport encryption...")
            cp, kp = generate_self_signed_cert(cp, kp)
        except Exception as e:
            print(f"[Server] Failed to auto-generate TLS certificate: {e}")
            return None

    try:
        ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ctx.load_cert_chain(str(cp), str(kp))
        return ctx
    except Exception as e:
        print(f"[Server] Failed to load SSL certificate chain: {e}")
        return None

def run_app():
    server = RemoteServer()
    host = server.config.host
    port = server.config.port
    ssl_ctx = None
    protocol = "http"
    if server.config.enable_tls:
        ssl_ctx = create_ssl_context(server.config.cert_file, server.config.key_file)
        if ssl_ctx:
            protocol = "https"

    print("=" * 60)
    print(f"  MYREMOTEPC HOST SERVER ACTIVE ({protocol.upper()})")
    print(f"  Machine ID   : {server.config.machine_id}")
    print(f"  Machine Name : {server.config.machine_name}")
    print(f"  Access Code  : {server.config.current_plain_code or '[Protected Hash]'}")
    print(f"  Local URL    : {protocol}://localhost:{port}")
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        lan_ip = s.getsockname()[0]
        s.close()
        print(f"  LAN URL      : {protocol}://{lan_ip}:{port}")
    except Exception:
        pass
    if server.config.is_first_run and server.config.current_plain_code:
        print("-" * 60)
        print(f"  [Security] Unique access code generated: {server.config.current_plain_code}")
        print("  Please save this code to connect from remote client viewers.")
    print("=" * 60)
    try:
        web.run_app(server.app, host=host, port=port, ssl_context=ssl_ctx, print=False)
    finally:
        server.shutdown()

if __name__ == "__main__":
    run_app()

