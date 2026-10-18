import os
import tempfile
from pathlib import Path
import pytest

from src.config import ConfigManager, hash_access_code, generate_machine_id, generate_access_code

def test_generate_machine_id():
    mid = generate_machine_id()
    assert len(mid) == 11
    parts = mid.split("-")
    assert len(parts) == 3
    assert all(p.isdigit() and len(p) == 3 for p in parts)

def test_generate_access_code():
    code = generate_access_code()
    assert len(code) == 6
    assert code.isalnum()

def test_hash_access_code():
    salt = "testsalt12345"
    h1 = hash_access_code("secret123", salt)
    h2 = hash_access_code("secret123", salt)
    h3 = hash_access_code("wrongpassword", salt)
    assert h1 == h2
    assert h1 != h3

def test_config_manager_creation_and_auth():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = Path(tmpdir) / "test_config.json"
        cfg = ConfigManager(config_path=cfg_path)
        
        assert cfg.machine_id != ""
        assert cfg.port == 8080
        assert cfg.verify_access_code(cfg.current_plain_code)
        assert not cfg.verify_access_code("invalid_code_xyz")

        # Test changing access code
        cfg.set_new_access_code("newpass999")
        assert cfg.verify_access_code("newpass999")
        assert not cfg.verify_access_code("oldpass")

def test_config_manager_env_overrides(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = Path(tmpdir) / "test_config.json"
        
        monkeypatch.setenv("MYREMOTEPC_PORT", "9999")
        monkeypatch.setenv("MYREMOTEPC_HOST", "127.0.0.1")
        monkeypatch.setenv("MYREMOTEPC_TARGET_FPS", "45")
        monkeypatch.setenv("MYREMOTEPC_JPEG_QUALITY", "85")
        monkeypatch.setenv("MYREMOTEPC_ACCESS_CODE", "envsecret")

        cfg = ConfigManager(config_path=cfg_path)
        assert cfg.port == 9999
        assert cfg.host == "127.0.0.1"
        assert cfg.target_fps == 45
        assert cfg.jpeg_quality == 85
        assert cfg.verify_access_code("envsecret")
