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
    assert len(code) == 8
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
        assert cfg.is_first_run is True
        assert cfg.current_plain_code is not None
        assert cfg.verify_access_code(cfg.current_plain_code)
        assert not cfg.verify_access_code("invalid_code_xyz")

        # Verify plaintext access_code is NOT stored in the JSON file on disk
        import json
        with open(cfg_path, "r", encoding="utf-8") as f:
            disk_data = json.load(f)
        assert "access_code" not in disk_data
        assert "access_code_hash" in disk_data
        assert "salt" in disk_data

        # Test changing access code
        cfg.set_new_access_code("newpass999")
        assert cfg.verify_access_code("newpass999")
        assert not cfg.verify_access_code("oldpass")

        # Test rejecting insecure default codes
        with pytest.raises(ValueError):
            cfg.set_new_access_code("123456")
        with pytest.raises(ValueError):
            cfg.set_new_access_code("short")


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

def test_config_purge_insecure_default_hash():
    with tempfile.TemporaryDirectory() as tmpdir:
        import json
        cfg_path = Path(tmpdir) / "legacy_config.json"
        salt = "testsalt12345"
        bad_hash = hash_access_code("123456", salt)
        legacy_data = {
            "machine_id": "111-222-333",
            "access_code_hash": bad_hash,
            "salt": salt
        }
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(legacy_data, f)

        # Loading this config must detect the insecure 123456 hash and auto-regenerate a secure code
        cfg = ConfigManager(config_path=cfg_path)
        assert cfg.is_first_run is True
        assert cfg.current_plain_code is not None
        assert cfg.current_plain_code != "123456"
        assert not cfg.verify_access_code("123456")
        assert cfg.verify_access_code(cfg.current_plain_code)

def test_generate_self_signed_cert():
    with tempfile.TemporaryDirectory() as tmpdir:
        from src.config import generate_self_signed_cert
        cert_p = Path(tmpdir) / "certs" / "cert.pem"
        key_p = Path(tmpdir) / "certs" / "key.pem"
        cp, kp = generate_self_signed_cert(cert_p, key_p)
        assert cp.exists() and cp.stat().st_size > 100
        assert kp.exists() and kp.stat().st_size > 100
        cert_text = cp.read_text()
        key_text = kp.read_text()
        assert "-----BEGIN CERTIFICATE-----" in cert_text
        assert "-----BEGIN RSA PRIVATE KEY-----" in key_text

