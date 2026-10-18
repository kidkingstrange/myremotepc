"""
Win32 Clipboard manager for MyRemotePC.
Provides bidirectional text clipboard reading and writing with size limits and concurrency guards.
"""

import ctypes
from ctypes import wintypes
import time

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
MAX_CLIPBOARD_TEXT_CHARS = 1_000_000  # ~2MB UTF-16 limit to prevent OOM abuse

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

def get_clipboard_text(max_chars: int = MAX_CLIPBOARD_TEXT_CHARS) -> str:
    """Read text currently in Windows clipboard safely."""
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
        print(f"[Clipboard] Read error: {e}")
        return ""
    finally:
        user32.CloseClipboard()

def set_clipboard_text(text: str, max_chars: int = MAX_CLIPBOARD_TEXT_CHARS) -> bool:
    """Write text to Windows clipboard with length limits."""
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
        # Encode as null-terminated UTF-16LE
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
        print(f"[Clipboard] Write error: {e}")
        return False
    finally:
        user32.CloseClipboard()
