"""
Native Windows System Tray Application for MyRemotePC.
Provides a background tray presence, single-instance mutex enforcement,
status menu, quick actions (copy ID/code, open viewer), and clean lifecycle shutdown.
"""

import os
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Optional, Any

from PIL import Image

from .config import ConfigManager, generate_access_code
from .clipboard import set_clipboard_text

# Locate icon asset relative to frozen bundle or project root
if getattr(sys, 'frozen', False):
    ICON_PATH = Path(sys._MEIPASS) / "static" / "icon.ico" if hasattr(sys, '_MEIPASS') else Path(sys.executable).parent / "static" / "icon.ico"
else:
    ICON_PATH = Path(__file__).resolve().parent.parent / "static" / "icon.ico"

def check_single_instance(mutex_name: str = "Global\\MyRemotePC_SingleInstance_Mutex") -> Optional[Any]:
    """Ensure only one instance runs across the user session on Windows."""
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.GetLastError.restype = wintypes.DWORD

    ERROR_ALREADY_EXISTS = 183
    handle = kernel32.CreateMutexW(None, True, mutex_name)
    last_error = kernel32.GetLastError()
    if last_error == ERROR_ALREADY_EXISTS:
        return None
    return handle

def is_startup_enabled(app_name: str = "MyRemotePC") -> bool:
    """Check if application is registered in HKCU Run key."""
    if sys.platform != "win32":
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, app_name)
            return True
    except FileNotFoundError:
        return False
    except Exception:
        return False

def set_startup_enabled(enabled: bool, app_name: str = "MyRemotePC") -> bool:
    """Register or unregister application from Windows boot in HKCU Run."""
    if sys.platform != "win32":
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                if getattr(sys, 'frozen', False):
                    cmd = f'"{sys.executable}"'
                else:
                    main_py = Path(__file__).resolve().parent.parent / "main.py"
                    cmd = f'"{sys.executable}" "{main_py}"'
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                except FileNotFoundError:
                    pass
        return True
    except Exception as e:
        print(f"[Tray] Error setting startup registry: {e}")
        return False

class SystemTrayApp:
    def __init__(self, server_instance: Any, on_quit_callback: Optional[Any] = None):
        self.server = server_instance
        self.config: ConfigManager = server_instance.config
        self.on_quit_callback = on_quit_callback
        self.icon = None
        self._load_icon_image()

    def _load_icon_image(self) -> Image.Image:
        if ICON_PATH.exists():
            try:
                self.icon_image = Image.open(ICON_PATH)
                return self.icon_image
            except Exception:
                pass
        # Fallback 64x64 blue tile with 'R' if icon is missing
        img = Image.new("RGBA", (64, 64), color=(37, 99, 235, 255))
        self.icon_image = img
        return self.icon_image

    def _action_open_viewer(self, icon, item):
        protocol = "https" if self.config.enable_tls else "http"
        url = f"{protocol}://localhost:{self.config.port}"
        webbrowser.open(url)

    def _action_copy_machine_id(self, icon, item):
        set_clipboard_text(self.config.machine_id)
        if icon:
            try:
                icon.notify(f"Machine ID: {self.config.machine_id}", "Copied to Clipboard")
            except Exception:
                pass

    def _action_copy_access_code(self, icon, item):
        code = self.config.current_plain_code
        if code:
            set_clipboard_text(code)
            if icon:
                try:
                    icon.notify("Access code copied to clipboard.", "MyRemotePC Security")
                except Exception:
                    pass
        else:
            if icon:
                try:
                    icon.notify("Plaintext code unavailable in memory. Reset code to view.", "MyRemotePC Security")
                except Exception:
                    pass

    def _action_generate_new_code(self, icon, item):
        new_code = generate_access_code()
        self.config.set_new_access_code(new_code, persist=True)
        set_clipboard_text(new_code)
        if hasattr(self.server, "revoke_all_sessions"):
            self.server.revoke_all_sessions()
        if icon:
            try:
                icon.notify(f"New Access Code: {new_code} (Copied to Clipboard)\nAll active sessions revoked.", "MyRemotePC Security")
            except Exception:
                pass

    def _action_disconnect_all_viewers(self, icon, item):
        count = 0
        if hasattr(self.server, "revoke_all_sessions"):
            count = self.server.revoke_all_sessions()
        if icon:
            try:
                icon.notify(f"Disconnected {count} active viewer session(s).", "MyRemotePC Security")
            except Exception:
                pass

    def _action_toggle_startup(self, icon, item):
        current_state = is_startup_enabled()
        set_startup_enabled(not current_state)

    def _action_quit(self, icon, item):
        if self.on_quit_callback:
            self.on_quit_callback()
        if icon:
            icon.stop()

    def build_menu(self):
        import pystray
        protocol = "HTTPS" if self.config.enable_tls else "HTTP"
        status_label = f"Status: Online ({protocol}:{self.config.port})"
        machine_label = f"Machine ID: {self.config.machine_id}"
        code_label = f"Access Code: {self.config.current_plain_code or '[Protected Hash]'}"

        return pystray.Menu(
            pystray.MenuItem(status_label, self._action_open_viewer, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(machine_label, self._action_copy_machine_id),
            pystray.MenuItem("Copy Machine ID", self._action_copy_machine_id),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(code_label, self._action_copy_access_code),
            pystray.MenuItem("Copy Access Code", self._action_copy_access_code),
            pystray.MenuItem("Generate New Access Code", self._action_generate_new_code),
            pystray.MenuItem("Disconnect All Viewers", self._action_disconnect_all_viewers),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Open Web Viewer", self._action_open_viewer),
            pystray.MenuItem(
                "Start with Windows",
                self._action_toggle_startup,
                checked=lambda item: is_startup_enabled()
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit MyRemotePC", self._action_quit)
        )

    def on_ready(self, icon):
        """Called as soon as system tray icon is active."""
        if getattr(self.config, 'is_first_run', False) and self.config.current_plain_code:
            try:
                icon.notify(
                    f"Host Ready!\nMachine ID: {self.config.machine_id}\nAccess Code: {self.config.current_plain_code}\n(Code copied to clipboard)",
                    "MyRemotePC First-Run Setup"
                )
                set_clipboard_text(self.config.current_plain_code)
            except Exception:
                pass

    def run(self):
        """Run system tray message loop."""
        import pystray
        self.icon = pystray.Icon(
            name="MyRemotePC",
            icon=self.icon_image,
            title=f"MyRemotePC ({self.config.machine_id})",
            menu=self.build_menu()
        )
        self.icon.run(setup=self.on_ready)

    def stop(self):
        if self.icon:
            self.icon.stop()
