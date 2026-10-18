"""
Configuration manager for MyRemotePC.
Handles Machine ID generation, secure access code hashing, and persistent settings.
"""

import json
import os
import random
import hashlib
import secrets
from pathlib import Path

CONFIG_FILE = Path(__file__).resolve().parent.parent / "config.json"

DEFAULT_CONFIG = {
    "machine_id": "",
    "machine_name": "",
    "access_code_hash": "",
    "salt": "",
    "port": 8080,
    "host": "0.0.0.0",
    "target_fps": 30,
    "jpeg_quality": 75,
    "enable_clipboard": True
}

def hash_access_code(code: str, salt: str) -> str:
    """Hash an access code using PBKDF2 with SHA-256."""
    return hashlib.pbkdf2_hmac(
        'sha256',
        code.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    ).hex()

def generate_machine_id() -> str:
    """Generate a clean 9-digit machine identifier (e.g. 849-204-183)."""
    digits = f"{random.randint(100000000, 999999999)}"
    return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"

def generate_access_code() -> str:
    """Generate a readable 6-character random access code."""
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"  # omit ambiguous characters (0, O, 1, l, i)
    return "".join(secrets.choice(alphabet) for _ in range(6))

class ConfigManager:
    def __init__(self, config_path: Path = CONFIG_FILE):
        self.config_path = config_path
        self.data = dict(DEFAULT_CONFIG)
        self.current_plain_code = None
        self.load()

    def load(self):
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    self.data.update(saved)
            except Exception as e:
                print(f"[Config] Error loading {self.config_path}: {e}")

        # Initialize missing fields
        modified = False
        if not self.data.get("machine_id"):
            self.data["machine_id"] = generate_machine_id()
            modified = True

        if not self.data.get("machine_name"):
            import socket
            self.data["machine_name"] = socket.gethostname()
            modified = True

        if not self.data.get("access_code_hash"):
            raw_code = self.data.get("access_code", generate_access_code())
            salt = secrets.token_hex(16)
            self.data["salt"] = salt
            self.data["access_code_hash"] = hash_access_code(raw_code, salt)
            self.data["access_code"] = raw_code
            self.current_plain_code = raw_code
            modified = True
        elif not self.current_plain_code and self.data.get("access_code"):
            self.current_plain_code = self.data["access_code"]

        if modified:
            self.save()

    def save(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4)
        except Exception as e:
            print(f"[Config] Error saving config: {e}")

    def verify_access_code(self, code: str) -> bool:
        """Verify an entered access code against stored hash."""
        if not code:
            return False
        # Also check current session plain code if just generated
        if self.current_plain_code and code.strip().lower() == self.current_plain_code.lower():
            return True
        entered_hash = hash_access_code(code.strip().lower(), self.data.get("salt", ""))
        return secrets.compare_digest(entered_hash, self.data.get("access_code_hash", ""))

    def set_new_access_code(self, new_code: str):
        salt = secrets.token_hex(16)
        self.data["salt"] = salt
        self.data["access_code_hash"] = hash_access_code(new_code.strip().lower(), salt)
        self.current_plain_code = new_code.strip().lower()
        self.save()

    @property
    def machine_id(self) -> str:
        return self.data["machine_id"]

    @property
    def machine_name(self) -> str:
        return self.data["machine_name"]

    @property
    def port(self) -> int:
        return self.data.get("port", 8080)

    @property
    def host(self) -> str:
        return self.data.get("host", "0.0.0.0")

    @property
    def target_fps(self) -> int:
        return self.data.get("target_fps", 30)

    @property
    def jpeg_quality(self) -> int:
        return self.data.get("jpeg_quality", 75)
