"""
Unit tests for System Tray, Single Instance Mutex, and Windows integration.
"""

import sys
import pytest
from src.tray import check_single_instance, is_startup_enabled, set_startup_enabled, SystemTrayApp
from src.server import RemoteServer
from src.config import ConfigManager

def test_single_instance_mutex():
    if sys.platform == "win32":
        handle1 = check_single_instance("Global\\TestMyRemotePC_Mutex_1")
        assert handle1 is not None
        # Trying to acquire the exact same named mutex a second time should detect existing instance
        handle2 = check_single_instance("Global\\TestMyRemotePC_Mutex_1")
        assert handle2 is None

def test_startup_registry_read():
    if sys.platform == "win32":
        # Should not raise exception
        enabled = is_startup_enabled("NonExistentAppTestKey123")
        assert isinstance(enabled, bool)

def test_tray_menu_structure():
    cfg = ConfigManager()
    server = RemoteServer(config=cfg)
    try:
        tray = SystemTrayApp(server)
        menu = tray.build_menu()
        assert menu is not None
    finally:
        server.shutdown()
