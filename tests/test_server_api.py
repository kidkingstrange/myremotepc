import asyncio
import json
import tempfile
from pathlib import Path
import pytest
import aiohttp
from aiohttp.test_utils import TestClient, TestServer
from aiohttp import web

from src.server import RemoteServer, RateLimiter
from src.config import ConfigManager

@pytest.fixture
def test_config():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = Path(tmpdir) / "config.json"
        cfg = ConfigManager(config_path=cfg_path)
        cfg.set_new_access_code("secret123")
        yield cfg

@pytest.fixture
async def client(test_config):
    server = RemoteServer(config=test_config)
    app = server.app
    test_srv = TestServer(app)
    client = TestClient(test_srv)
    await client.start_server()
    yield client, server
    await client.close()
    server.shutdown()

@pytest.mark.asyncio
async def test_api_status(client):
    cli, server = client
    resp = await cli.get('/api/status')
    assert resp.status == 200
    data = await resp.json()
    assert data["status"] == "online"
    assert data["machine_id"] == server.config.machine_id
    assert "monitors" in data

@pytest.mark.asyncio
async def test_api_monitors(client):
    cli, server = client
    # Unauthenticated request must be rejected
    unauth_resp = await cli.get('/api/monitors')
    assert unauth_resp.status == 401

    # Authenticate and obtain token
    auth_resp = await cli.post('/api/auth', json={"access_code": "secret123"})
    token = (await auth_resp.json())["token"]

    # Authenticated request with Bearer token
    resp = await cli.get('/api/monitors', headers={"Authorization": f"Bearer {token}"})
    assert resp.status == 200
    data = await resp.json()
    assert "monitors" in data

@pytest.mark.asyncio
async def test_api_auth_success(client):
    cli, server = client
    resp = await cli.post('/api/auth', json={"access_code": "secret123"})
    assert resp.status == 200
    data = await resp.json()
    assert data["success"] is True
    assert "token" in data
    assert data["token"] in server.authenticated_sessions

@pytest.mark.asyncio
async def test_api_auth_invalid(client):
    cli, server = client
    resp = await cli.post('/api/auth', json={"access_code": "wrong_code"})
    assert resp.status == 401
    data = await resp.json()
    assert data["success"] is False

@pytest.mark.asyncio
async def test_api_auth_rate_limiting(client):
    cli, server = client
    # Send 5 failed attempts
    for _ in range(5):
        resp = await cli.post('/api/auth', json={"access_code": "wrong"})
        assert resp.status == 401

    # 6th attempt should be blocked with 429 Too Many Requests
    resp = await cli.post('/api/auth', json={"access_code": "wrong"})
    assert resp.status == 429
    data = await resp.json()
    assert "Too many failed attempts" in data["error"]
    assert "Retry-After" in resp.headers

@pytest.mark.asyncio
async def test_api_settings_update(client):
    cli, server = client
    # Unauthenticated request must be rejected
    unauth_resp = await cli.post('/api/settings', json={"fps": 45, "quality": 85})
    assert unauth_resp.status == 401

    # Authenticate
    auth_resp = await cli.post('/api/auth', json={"access_code": "secret123"})
    token = (await auth_resp.json())["token"]

    # Authenticated request
    resp = await cli.post('/api/settings', json={"fps": 45, "quality": 85, "token": token})
    assert resp.status == 200
    data = await resp.json()
    assert data["success"] is True
    assert data["fps"] == 45
    assert data["quality"] == 85
    assert server.target_fps == 45
    assert server.jpeg_quality == 85

@pytest.mark.asyncio
async def test_ws_auth_rate_limiting(client):
    cli, server = client
    ws = await cli.ws_connect('/ws')

    # Send 5 failed auth attempts over WebSocket
    for _ in range(5):
        await ws.send_json({"type": "auth", "access_code": "wrong_code"})
        msg = await ws.receive_json()
        assert msg["type"] == "auth_result"
        assert msg["success"] is False

    # 6th attempt should be rejected with rate limit error and connection closed with 4429
    await ws.send_json({"type": "auth", "access_code": "wrong_code"})
    msg = await ws.receive()
    if msg.type == aiohttp.WSMsgType.TEXT:
        data = json.loads(msg.data)
        assert data["type"] == "auth_result"
        assert "Too many failed attempts" in data["error"]
        close_msg = await ws.receive()
        assert close_msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED)
        assert ws.close_code == 4429 or close_msg.data == 4429
    else:
        assert msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED)
        assert ws.close_code == 4429 or msg.data == 4429



@pytest.mark.asyncio
async def test_static_index(client):
    cli, server = client
    resp = await cli.get('/')
    assert resp.status == 200
    text = await resp.text()
    assert "MyRemotePC" in text

@pytest.mark.asyncio
async def test_static_landing(client):
    cli, server = client
    resp = await cli.get('/landing')
    assert resp.status == 200
    text = await resp.text()
    assert "MyRemotePC" in text
    assert "$20" in text

@pytest.mark.asyncio
async def test_download_routes(client):
    cli, server = client
    # /download/windows should either return 200 (if local installer exists) or redirect 302 to GitHub release
    resp = await cli.get('/download/windows', allow_redirects=False)
    assert resp.status in (200, 302)

@pytest.mark.asyncio
async def test_unauthenticated_ws_commands_rejected(client):
    cli, server = client
    ws = await cli.ws_connect('/ws')
    # Attempt to send mouse and clipboard commands without authenticating
    await ws.send_json({"type": "mouse_move", "x": 0.5, "y": 0.5})
    await ws.send_json({"type": "clipboard_read"})
    await ws.send_json({"type": "clipboard_write", "text": "malicious_overwrite"})

    # Send a ping; ping should still receive a pong, but no clipboard or mouse actions should have been processed
    await ws.send_json({"type": "ping", "t": 12345})
    
    # We should NOT receive any screen_init or clipboard_content before authenticating
    # Read messages with a brief timeout
    received_types = []
    try:
        while True:
            msg = await asyncio.wait_for(ws.receive(), timeout=0.3)
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                received_types.append(data.get("type"))
            else:
                break
    except asyncio.TimeoutError:
        pass

    assert "clipboard_content" not in received_types
    assert "screen_init" not in received_types
    await ws.close()

@pytest.mark.asyncio
async def test_client_ip_spoofing_defense(client):
    cli, server = client
    # Remote request with forged headers from non-loopback peer
    # Simulate a request where remote is 192.168.1.50
    class DummyRequest:
        remote = "192.168.1.50"
        headers = {
            "CF-Connecting-IP": "8.8.8.8",
            "X-Forwarded-For": "1.1.1.1"
        }
    
    ip = server.get_client_ip(DummyRequest())
    # Must NOT trust forged headers from non-loopback IP
    assert ip == "192.168.1.50"

    # From trusted loopback proxy, forwarded headers ARE accepted
    class ProxiedRequest:
        remote = "127.0.0.1"
        headers = {
            "CF-Connecting-IP": "8.8.8.8"
        }
    assert server.get_client_ip(ProxiedRequest()) == "8.8.8.8"

def test_tls_ssl_context_creation():
    import ssl
    from src.server import create_ssl_context
    with tempfile.TemporaryDirectory() as tmpdir:
        cert_p = str(Path(tmpdir) / "certs" / "cert.pem")
        key_p = str(Path(tmpdir) / "certs" / "key.pem")
        ctx = create_ssl_context(cert_p, key_p)
        assert ctx is not None
        assert isinstance(ctx, ssl.SSLContext)

@pytest.mark.asyncio
async def test_ws_invalid_query_token_records_failure(client):
    cli, server = client
    # Connect with invalid token 5 times
    for _ in range(5):
        ws = await cli.ws_connect('/ws?token=bogus_token_123')
        await ws.close()

    # 6th connection should be blocked by rate limiter with 4429
    ws = await cli.ws_connect('/ws?token=bogus_token_123')
    msg = await ws.receive()
    if msg.type == aiohttp.WSMsgType.TEXT:
        data = json.loads(msg.data)
        assert "Too many failed attempts" in data.get("error", "")
        close_msg = await ws.receive()
        assert close_msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED)
    else:
        assert msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED)
        assert ws.close_code == 4429 or msg.data == 4429

@pytest.mark.asyncio
async def test_revoke_all_sessions(client):
    cli, server = client
    # Obtain valid auth token
    auth_resp = await cli.post('/api/auth', json={"access_code": "secret123"})
    token = (await auth_resp.json())["token"]
    assert token in server.authenticated_sessions

    # Connect authenticated websocket
    ws = await cli.ws_connect(f'/ws?token={token}')
    assert len(server.active_websockets) == 1

    # Trigger revocation
    revoked_count = server.revoke_all_sessions()
    assert revoked_count == 1
    assert len(server.authenticated_sessions) == 0

    # Wait for close / error message
    revoked_msg_found = False
    while True:
        msg = await asyncio.wait_for(ws.receive(), timeout=1.0)
        if msg.type == aiohttp.WSMsgType.TEXT:
            data = json.loads(msg.data)
            if "Session revoked" in data.get("error", ""):
                revoked_msg_found = True
        elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED):
            break
    assert revoked_msg_found

