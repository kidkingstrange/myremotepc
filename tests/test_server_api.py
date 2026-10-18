import asyncio
import tempfile
from pathlib import Path
import pytest
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
    resp = await cli.get('/api/monitors')
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
    resp = await cli.post('/api/settings', json={"fps": 45, "quality": 85})
    assert resp.status == 200
    data = await resp.json()
    assert data["success"] is True
    assert data["fps"] == 45
    assert data["quality"] == 85
    assert server.target_fps == 45
    assert server.jpeg_quality == 85

@pytest.mark.asyncio
async def test_static_index(client):
    cli, server = client
    resp = await cli.get('/')
    assert resp.status == 200
    text = await resp.text()
    assert "MyRemotePC" in text
