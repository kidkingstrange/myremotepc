"""
Configuration manager for MyRemotePC.
Handles Machine ID generation, secure access code hashing, persistent settings,
and environment variable overrides.
"""

import json
import os
import random
import hashlib
import secrets
import sys
from pathlib import Path
from typing import Optional

if getattr(sys, 'frozen', False):
    APP_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parent.parent

def get_default_config_path() -> Path:
    """
    Resolve configuration path safely:
    1. If a config.json already exists in APP_DIR (portable mode), use it.
    2. Otherwise, use %APPDATA%/MyRemotePC/config.json (installed mode) to avoid
       PermissionError when installed into Program Files.
    """
    local_cfg = APP_DIR / "config.json"
    if local_cfg.exists():
        return local_cfg

    appdata = os.getenv("APPDATA")
    if appdata:
        appdata_dir = Path(appdata) / "MyRemotePC"
        return appdata_dir / "config.json"

    return local_cfg

CONFIG_FILE = get_default_config_path()

INSECURE_CODES = {
    "123456", "12345678", "000000", "111111", "password", "password123",
    "changeme", "changeme123", "admin", "admin123", "remote", "remotepc",
    "123123", "qwerty", "letmein", "default"
}

DEFAULT_CONFIG = {
    "machine_id": "",
    "machine_name": "",
    "access_code_hash": "",
    "salt": "",
    "port": 8080,
    "host": "0.0.0.0",
    "target_fps": 30,
    "jpeg_quality": 75,
    "enable_clipboard": True,
    "enable_tls": False,
    "cert_file": "",
    "key_file": ""
}

def get_default_cert_paths() -> tuple[Path, Path]:
    base_dir = CONFIG_FILE.parent
    cert_dir = base_dir / "certs"
    return cert_dir / "cert.pem", cert_dir / "key.pem"

def generate_self_signed_cert(cert_path: Path, key_path: Path) -> tuple[Path, Path]:
    """Generate self-signed X.509 TLS certificate with Subject Alternative Names for LAN/localhost."""
    import datetime
    import ipaddress
    import socket
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization

    cert_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.parent.mkdir(parents=True, exist_ok=True)

    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    hostname = socket.gethostname()
    san_names = [
        x509.DNSName("localhost"),
        x509.DNSName(hostname),
        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
    ]

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        lan_ip = s.getsockname()[0]
        s.close()
        san_names.append(x509.IPAddress(ipaddress.ip_address(lan_ip)))
    except Exception:
        pass

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "MyRemotePC"),
        x509.NameAttribute(NameOID.COMMON_NAME, "MyRemotePC Host"),
    ])

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1))
        .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=3650))
        .add_extension(x509.SubjectAlternativeName(san_names), critical=False)
        .sign(key, hashes.SHA256())
    )

    with open(key_path, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))

    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    return cert_path, key_path

def hash_access_code(code: str, salt: str) -> str:
    """Hash an access code using PBKDF2 with SHA-256."""
    return hashlib.pbkdf2_hmac(
        'sha256',
        code.strip().lower().encode('utf-8'),
        salt.encode('utf-8'),
        100000
    ).hex()

def generate_machine_id() -> str:
    """Generate a clean 9-digit machine identifier (e.g. 849-204-183)."""
    digits = f"{random.randint(100000000, 999999999)}"
    return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"

def generate_access_code(length: int = 8) -> str:
    """Generate a readable, cryptographically secure random access code."""
    alphabet = "23456789abcdefghjkmnpqrstuvwxyz"
    return "".join(secrets.choice(alphabet) for _ in range(length))

class ConfigManager:
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or CONFIG_FILE
        self.data = dict(DEFAULT_CONFIG)
        self.current_plain_code: Optional[str] = None
        self.is_first_run: bool = False
        self.load()
        self.apply_env_overrides()

    def load(self):
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    self.data.update(saved)
            except Exception as e:
                print(f"[Config] Error loading {self.config_path}: {e}")

        modified = False
        if not self.data.get("machine_id"):
            self.data["machine_id"] = generate_machine_id()
            modified = True

        if not self.data.get("machine_name"):
            import socket
            self.data["machine_name"] = socket.gethostname()
            modified = True

        # Check for legacy/insecure access code in plaintext
        raw_code = self.data.get("access_code")
        if raw_code and raw_code.strip().lower() in INSECURE_CODES:
            print("[Config] Insecure default access code detected. Purging and generating a unique code.")
            self.data.pop("access_code", None)
            self.data["access_code_hash"] = ""
            self.data["salt"] = ""
            modified = True

        # Check if stored hash matches known insecure defaults
        stored_hash = self.data.get("access_code_hash", "")
        salt = self.data.get("salt", "")
        if stored_hash and salt:
            for bad_code in INSECURE_CODES:
                if secrets.compare_digest(stored_hash, hash_access_code(bad_code, salt)):
                    print("[Config] Stored hash matches insecure default code. Purging and regenerating.")
                    self.data["access_code_hash"] = ""
                    self.data["salt"] = ""
                    modified = True
                    break

        if not self.data.get("access_code_hash"):
            unique_code = generate_access_code()
            new_salt = secrets.token_hex(16)
            self.data["salt"] = new_salt
            self.data["access_code_hash"] = hash_access_code(unique_code, new_salt)
            self.current_plain_code = unique_code
            self.is_first_run = True
            modified = True
        elif raw_code and not self.current_plain_code:
            # Cleanly strip plaintext code out of config file
            self.current_plain_code = raw_code.strip()
            self.data.pop("access_code", None)
            modified = True

        # Guarantee plaintext access_code is never retained in self.data dictionary
        if "access_code" in self.data:
            self.data.pop("access_code", None)
            modified = True

        if modified:
            self.save()

    def apply_env_overrides(self):
        """Allow production environment variables to override file config."""
        if os.getenv("MYREMOTEPC_HOST"):
            self.data["host"] = os.getenv("MYREMOTEPC_HOST")
        if os.getenv("MYREMOTEPC_PORT"):
            try:
                self.data["port"] = int(os.getenv("MYREMOTEPC_PORT"))
            except ValueError:
                pass
        if os.getenv("MYREMOTEPC_TARGET_FPS"):
            try:
                self.data["target_fps"] = max(5, min(60, int(os.getenv("MYREMOTEPC_TARGET_FPS"))))
            except ValueError:
                pass
        if os.getenv("MYREMOTEPC_JPEG_QUALITY"):
            try:
                self.data["jpeg_quality"] = max(20, min(95, int(os.getenv("MYREMOTEPC_JPEG_QUALITY"))))
            except ValueError:
                pass
        if os.getenv("MYREMOTEPC_ACCESS_CODE"):
            override_code = os.getenv("MYREMOTEPC_ACCESS_CODE").strip()
            self.set_new_access_code(override_code, persist=False)

    def save(self):
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            # Ensure plaintext credentials are never written to disk
            to_save = dict(self.data)
            to_save.pop("access_code", None)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(to_save, f, indent=4)
        except Exception as e:
            print(f"[Config] Error saving config: {e}")

    def verify_access_code(self, code: str) -> bool:
        """Verify an entered access code against stored hash."""
        if not code or not isinstance(code, str):
            return False
        cleaned = code.strip().lower()
        if self.current_plain_code and cleaned == self.current_plain_code.lower():
            return True
        entered_hash = hash_access_code(cleaned, self.data.get("salt", ""))
        return secrets.compare_digest(entered_hash, self.data.get("access_code_hash", ""))

    def set_new_access_code(self, new_code: str, persist: bool = True):
        cleaned = new_code.strip()
        if cleaned.lower() in INSECURE_CODES or len(cleaned) < 6:
            raise ValueError("Access code must be at least 6 characters and cannot be a common default.")
        salt = secrets.token_hex(16)
        self.data["salt"] = salt
        self.data["access_code_hash"] = hash_access_code(cleaned, salt)
        self.current_plain_code = cleaned
        self.data.pop("access_code", None)
        if persist:
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

    @property
    def salt(self) -> str:
        return self.data.get("salt", "")

    @property
    def enable_clipboard(self) -> bool:
        return bool(self.data.get("enable_clipboard", True))

    @property
    def enable_tls(self) -> bool:
        return bool(self.data.get("enable_tls", False))

    @property
    def cert_file(self) -> str:
        return self.data.get("cert_file", "")

    @property
    def key_file(self) -> str:
        return self.data.get("key_file", "")

