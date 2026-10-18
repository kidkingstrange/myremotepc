"""
Cross-Platform Clipboard Manager for MyRemotePC.
Supports Windows (Win32 CF_UNICODETEXT), macOS (pbcopy/pbpaste), and Linux.
Provides bidirectional text clipboard reading and writing with size limits and concurrency guards.
"""

import sys
import subprocess
import time
from typing import Optional

MAX_CLIPBOARD_TEXT_CHARS = 1_000_000  # ~2MB limit to prevent OOM abuse

# ==============================================================================
# Windows Implementation
# ==============================================================================
if sys.platform == 'win32':
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002

    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.argtypes = []
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
    user32.IsClipboardFormatAvailable.restype = wintypes.BOOL

    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL

    def _win_get_clipboard_text(max_chars: int) -> str:
        for _ in range(5):
            if user32.OpenClipboard(None):
                break
            time.sleep(0.02)
        else:
            return ""

        try:
            if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
                return ""
            h_data = user32.GetClipboardData(CF_UNICODETEXT)
            if not h_data:
                return ""
            p_data = kernel32.GlobalLock(h_data)
            if not p_data:
                return ""
            try:
                text = ctypes.c_wchar_p(p_data).value
                if text and len(text) > max_chars:
                    text = text[:max_chars]
                return text or ""
            finally:
                kernel32.GlobalUnlock(h_data)
        except Exception as e:
            print(f"[Clipboard] Win32 read error: {e}")
            return ""
        finally:
            user32.CloseClipboard()

    def _win_set_clipboard_text(text: str, max_chars: int) -> bool:
        if text is None:
            return False
        if not isinstance(text, str):
            text = str(text)
        if len(text) > max_chars:
            text = text[:max_chars]

        for _ in range(5):
            if user32.OpenClipboard(None):
                break
            time.sleep(0.02)
        else:
            return False

        try:
            user32.EmptyClipboard()
            encoded = (text + "\0").encode('utf-16le')
            h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
            if not h_mem:
                return False
            p_mem = kernel32.GlobalLock(h_mem)
            if not p_mem:
                return False
            try:
                ctypes.memmove(p_mem, encoded, len(encoded))
            finally:
                kernel32.GlobalUnlock(h_mem)
            return bool(user32.SetClipboardData(CF_UNICODETEXT, h_mem))
        except Exception as e:
            print(f"[Clipboard] Win32 write error: {e}")
            return False
        finally:
            user32.CloseClipboard()

# ==============================================================================
# macOS Implementation (Native pbcopy / pbpaste)
# ==============================================================================
def _mac_get_clipboard_text(max_chars: int) -> str:
    try:
        proc = subprocess.run(['pbpaste'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=1.0)
        text = proc.stdout.decode('utf-8', errors='replace')
        if len(text) > max_chars:
            text = text[:max_chars]
        return text
    except Exception as e:
        print(f"[Clipboard] macOS pbpaste error: {e}")
        return ""

def _mac_set_clipboard_text(text: str, max_chars: int) -> bool:
    if text is None:
        return False
    if not isinstance(text, str):
        text = str(text)
    if len(text) > max_chars:
        text = text[:max_chars]

    try:
        proc = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
        proc.communicate(input=text.encode('utf-8'), timeout=1.0)
        return proc.returncode == 0
    except Exception as e:
        print(f"[Clipboard] macOS pbcopy error: {e}")
        return False

# ==============================================================================
# Public Unified Interface
# ==============================================================================
def get_clipboard_text(max_chars: int = MAX_CLIPBOARD_TEXT_CHARS) -> str:
    """Read text from system clipboard on active OS."""
    if sys.platform == 'win32':
        return _win_get_clipboard_text(max_chars)
    elif sys.platform == 'darwin':
        return _mac_get_clipboard_text(max_chars)
    else:
        # Linux fallback
        try:
            return subprocess.check_output(['xclip', '-selection', 'clipboard', '-o'], timeout=1.0).decode('utf-8')[:max_chars]
        except Exception:
            return ""

def set_clipboard_text(text: str, max_chars: int = MAX_CLIPBOARD_TEXT_CHARS) -> bool:
    """Write text to system clipboard on active OS."""
    if sys.platform == 'win32':
        return _win_set_clipboard_text(text, max_chars)
    elif sys.platform == 'darwin':
        return _mac_set_clipboard_text(text, max_chars)
    else:
        # Linux fallback
        try:
            p = subprocess.Popen(['xclip', '-selection', 'clipboard'], stdin=subprocess.PIPE)
            p.communicate(input=text.encode('utf-8'), timeout=1.0)
            return p.returncode == 0
        except Exception:
            return False
