"""
MyRemotePC Core Host Server.
Provides asynchronous HTTP endpoints, static asset hosting, and high-throughput
full-duplex WebSocket binary desktop streaming and input injection.
"""

import asyncio
import json
import os
import struct
import time
from pathlib import Path
from typing import Set, Dict, Any, Optional

from aiohttp import web
import aiohttp

from .config import ConfigManager
from .capture import ScreenCapturer, enumerate_monitors
from .input_injector import InputInjector
from .clipboard import get_clipboard_text, set_clipboard_text

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

class RemoteServer:
    def __init__(self):
        self.config = ConfigManager()
        self.capturer = ScreenCapturer(monitor_index=0)
        self.injector = InputInjector()
        self.app = web.Application()
        self.active_websockets: Set[web.WebSocketResponse] = set()
        self.authenticated_sessions: Dict[str, float] = {}  # token -> expiry
        self.streaming_tasks: Dict[web.WebSocketResponse, asyncio.Task] = {}
        
        self.target_fps = self.config.target_fps
        self.jpeg_quality = self.config.jpeg_quality
        
        self.setup_routes()

    def setup_routes(self):
        # API Routes
        self.app.router.add_get('/api/status', self.handle_status)
        self.app.router.add_post('/api/auth', self.handle_auth)
        self.app.router.add_get('/api/monitors', self.handle_monitors)
        self.app.router.add_post('/api/settings', self.handle_settings)
        self.app.router.add_get('/ws', self.handle_websocket)

        # Static Assets
        self.app.router.add_static('/static', STATIC_DIR, show_index=False)
        self.app.router.add_get('/', self.handle_index)

    async def handle_index(self, request: web.Request) -> web.Response:
        index_file = STATIC_DIR / "index.html"
        if index_file.exists():
            return web.FileResponse(index_file)
        return web.Response(text="MyRemotePC Viewer - UI not found", status=404)

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
        monitors = [m.to_dict() for m in enumerate_monitors()]
        return web.json_response({"monitors": monitors, "current": self.capturer.current_monitor_index})

    async def handle_auth(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        access_code = data.get("access_code", "")
        if self.config.verify_access_code(access_code):
            import secrets
            token = secrets.token_urlsafe(32)
            self.authenticated_sessions[token] = time.time() + 86400  # 24h
            return web.json_response({
                "success": True,
                "token": token,
                "machine_id": self.config.machine_id,
                "machine_name": self.config.machine_name
            })
        return web.json_response({"success": False, "error": "Invalid access code"}, status=401)

    async def handle_settings(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)

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
        ws = web.WebSocketResponse(heartbeat=15.0, max_msg_size=10*1024*1024)
        await ws.prepare(request)

        # Check authentication query param or wait for auth message
        token = request.query.get("token", "")
        is_authenticated = token in self.authenticated_sessions

        self.active_websockets.add(ws)
        print(f"[WebSocket] Client connected: {request.remote}")

        # Start streaming task once authenticated
        stream_task: Optional[asyncio.Task] = None
        if is_authenticated:
            stream_task = asyncio.create_task(self.stream_loop(ws))
            self.streaming_tasks[ws] = stream_task

        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        cmd = json.loads(msg.data)
                    except Exception:
                        continue

                    cmd_type = cmd.get("type", "")

                    # Handle initial auth if not authenticated via URL
                    if not is_authenticated:
                        if cmd_type == "auth":
                            code = cmd.get("access_code", "")
                            req_token = cmd.get("token", "")
                            if (req_token and req_token in self.authenticated_sessions) or self.config.verify_access_code(code):
                                is_authenticated = True
                                await ws.send_json({"type": "auth_result", "success": True})
                                stream_task = asyncio.create_task(self.stream_loop(ws))
                                self.streaming_tasks[ws] = stream_task
                            else:
                                await ws.send_json({"type": "auth_result", "success": False, "error": "Invalid access code"})
                        continue

                    # Authenticated Command Processing
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
                        clip_txt = get_clipboard_text()
                        await ws.send_json({"type": "clipboard_content", "text": clip_txt})

                    elif cmd_type == "clipboard_write":
                        set_clipboard_text(cmd.get("text", ""))

                    elif cmd_type == "lock_screen":
                        self.injector.lock_workstation()

                    elif cmd_type == "show_desktop":
                        self.injector.show_desktop()

                    elif cmd_type == "ping":
                        t_client = cmd.get("t", 0)
                        await ws.send_json({"type": "pong", "t": t_client, "server_t": time.time()})

                elif msg.type == aiohttp.WSMsgType.ERROR:
                    print(f"[WebSocket] Error: {ws.exception()}")
                    break

        finally:
            if stream_task and not stream_task.done():
                stream_task.cancel()
            self.streaming_tasks.pop(ws, None)
            self.active_websockets.discard(ws)
            print(f"[WebSocket] Client disconnected: {request.remote}")

        return ws

    async def stream_loop(self, ws: web.WebSocketResponse):
        """Asynchronous frame capture and binary transmission loop."""
        print("[Stream] Screen stream started for viewer")
        # Send initial screen info
        await ws.send_json({
            "type": "screen_init",
            "width": self.capturer.width,
            "height": self.capturer.height,
            "monitors": [m.to_dict() for m in self.capturer.monitors],
            "current_monitor": self.capturer.current_monitor_index
        })

        frame_count = 0
        last_force_time = time.time()

        while not ws.closed:
            t_start = time.time()
            interval = 1.0 / max(5, self.target_fps)

            # Send a keyframe every 2 seconds even if screen is static
            force_keyframe = (t_start - last_force_time) > 2.0
            if force_keyframe:
                last_force_time = t_start

            # Capture frame in thread executor to keep event loop free for input
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
                
                # Binary Header:
                # 4 bytes: Magic 'RPC1' (0x52504331)
                # 2 bytes: Width (uint16)
                # 2 bytes: Height (uint16)
                # 4 bytes: Timestamp ms (uint32)
                # Followed by raw JPEG bytes
                header = struct.pack('>4sHHI', b'RPC1', w, h, timestamp_ms)
                packet = header + jpeg_bytes
                
                try:
                    await ws.send_bytes(packet)
                    frame_count += 1
                except Exception as e:
                    print(f"[Stream] Send error: {e}")
                    break

            elapsed = time.time() - t_start
            sleep_time = max(0.001, interval - elapsed)
            await asyncio.sleep(sleep_time)

        print("[Stream] Screen stream ended")

def run_app():
    server = RemoteServer()
    host = server.config.host
    port = server.config.port
    print("=" * 60)
    print(f"  MYREMOTEPC HOST SERVER ACTIVE")
    print(f"  Machine ID   : {server.config.machine_id}")
    print(f"  Machine Name : {server.config.machine_name}")
    print(f"  Access Code  : {server.config.current_plain_code or '[Saved Hash]'}")
    print(f"  Local URL    : http://localhost:{port}")
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        lan_ip = s.getsockname()[0]
        s.close()
        print(f"  LAN URL      : http://{lan_ip}:{port}")
    except Exception:
        pass
    print("=" * 60)
    web.run_app(server.app, host=host, port=port, print=False)

if __name__ == "__main__":
    run_app()
