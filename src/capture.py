"""
High-performance Win32 screen capture engine for MyRemotePC.
Uses direct GDI BitBlt with persistent memory device contexts and DIBits.
Supports multi-monitor enumeration, selective display capture, and adaptive compression.
"""

import ctypes
from ctypes import wintypes
import io
import time
from typing import List, Dict, Optional, Tuple
from PIL import Image

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

# Set DPI awareness so coordinate mapping is 1:1 with native pixels
try:
    user32.SetProcessDPIAware()
except Exception:
    pass

class RECT(ctypes.Structure):
    _fields_ = [
        ('left', wintypes.LONG),
        ('top', wintypes.LONG),
        ('right', wintypes.LONG),
        ('bottom', wintypes.LONG)
    ]

class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ('biSize', wintypes.DWORD),
        ('biWidth', wintypes.LONG),
        ('biHeight', wintypes.LONG),
        ('biPlanes', wintypes.WORD),
        ('biBitCount', wintypes.WORD),
        ('biCompression', wintypes.DWORD),
        ('biSizeImage', wintypes.DWORD),
        ('biXPelsPerMeter', wintypes.LONG),
        ('biYPelsPerMeter', wintypes.LONG),
        ('biClrUsed', wintypes.DWORD),
        ('biClrImportant', wintypes.DWORD)
    ]

class BITMAPINFO(ctypes.Structure):
    _fields_ = [('bmiHeader', BITMAPINFOHEADER), ('bmiColors', wintypes.DWORD * 3)]

# Win32 Constants
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79
SM_CMONITORS = 80
SRCCOPY = 0x00CC0020
BI_RGB = 0

class MonitorInfo:
    def __init__(self, index: int, name: str, left: int, top: int, width: int, height: int, is_primary: bool):
        self.index = index
        self.name = name
        self.left = left
        self.top = top
        self.width = width
        self.height = height
        self.is_primary = is_primary

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "name": self.name,
            "left": self.left,
            "top": self.top,
            "width": self.width,
            "height": self.height,
            "is_primary": self.is_primary
        }

def enumerate_monitors() -> List[MonitorInfo]:
    """Enumerate all connected displays using Win32 EnumDisplayMonitors."""
    monitors: List[MonitorInfo] = []

    def _monitor_enum_proc(hMonitor, hdcMonitor, lprcMonitor, dwData):
        rect = lprcMonitor.contents
        w = rect.right - rect.left
        h = rect.bottom - rect.top
        is_primary = (rect.left == 0 and rect.top == 0)
        idx = len(monitors)
        monitors.append(MonitorInfo(
            index=idx,
            name=f"Display {idx + 1}" + (" (Primary)" if is_primary else ""),
            left=rect.left,
            top=rect.top,
            width=w,
            height=h,
            is_primary=is_primary
        ))
        return 1

    MONITORENUMPROC = ctypes.WINFUNCTYPE(
        wintypes.BOOL,
        wintypes.HMONITOR,
        wintypes.HDC,
        ctypes.POINTER(RECT),
        wintypes.LPARAM
    )

    proc = MONITORENUMPROC(_monitor_enum_proc)
    user32.EnumDisplayMonitors(None, None, proc, 0)

    if not monitors:
        # Fallback to primary screen
        w = user32.GetSystemMetrics(0)
        h = user32.GetSystemMetrics(1)
        monitors.append(MonitorInfo(0, "Display 1 (Primary)", 0, 0, w, h, True))

    return monitors

class ScreenCapturer:
    """Persistent GDI capture session with zero-copy memory buffers."""
    def __init__(self, monitor_index: int = 0):
        self.monitors = enumerate_monitors()
        self.current_monitor_index = monitor_index
        self.hdc_screen = None
        self.hdc_mem = None
        self.hbmp = None
        self.buf = None
        self.bmi = None
        self.width = 0
        self.height = 0
        self.left = 0
        self.top = 0
        self._last_frame_hash = None
        self._init_session(monitor_index)

    def _init_session(self, monitor_index: int):
        self.cleanup()
        self.monitors = enumerate_monitors()
        if monitor_index < 0 or monitor_index >= len(self.monitors):
            monitor_index = 0
        self.current_monitor_index = monitor_index
        target = self.monitors[monitor_index]
        self.left = target.left
        self.top = target.top
        self.width = target.width
        self.height = target.height

        # Setup BITMAPINFO for 32-bit BGRA top-down bitmap
        self.bmi = BITMAPINFO()
        self.bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        self.bmi.bmiHeader.biWidth = self.width
        self.bmi.bmiHeader.biHeight = -self.height  # Negative height = top-down
        self.bmi.bmiHeader.biPlanes = 1
        self.bmi.bmiHeader.biBitCount = 32
        self.bmi.bmiHeader.biCompression = BI_RGB

        # Pre-allocate buffer
        self.buf = ctypes.create_string_buffer(self.width * self.height * 4)

        # Create persistent GDI contexts
        self.hdesktop = user32.GetDesktopWindow()
        self.hdc_screen = user32.GetDC(self.hdesktop)
        self.hdc_mem = gdi32.CreateCompatibleDC(self.hdc_screen)
        self.hbmp = gdi32.CreateCompatibleBitmap(self.hdc_screen, self.width, self.height)
        gdi32.SelectObject(self.hdc_mem, self.hbmp)

    def select_monitor(self, index: int):
        """Switch active capture monitor."""
        if index != self.current_monitor_index and 0 <= index < len(self.monitors):
            self._init_session(index)

    def capture_jpeg(self, quality: int = 75, force: bool = False) -> Optional[Tuple[bytes, int, int]]:
        """
        Capture current frame and return (jpeg_bytes, width, height).
        Returns None if frame is identical to previous and force=False.
        """
        if not self.hdc_mem or not self.hdc_screen:
            return None

        # Blit from screen to persistent memory DC
        gdi32.BitBlt(
            self.hdc_mem,
            0, 0,
            self.width, self.height,
            self.hdc_screen,
            self.left, self.top,
            SRCCOPY
        )

        # Read pixels into buffer
        gdi32.GetDIBits(
            self.hdc_mem,
            self.hbmp,
            0,
            self.height,
            self.buf,
            ctypes.byref(self.bmi),
            0
        )

        # Quick sample hash for dirty detection (hash sample points across buffer)
        raw_mv = memoryview(self.buf)
        # Sample 1KB from start, middle, and end
        sample = bytes(raw_mv[0:1024]) + bytes(raw_mv[len(raw_mv)//2:len(raw_mv)//2 + 1024]) + bytes(raw_mv[-1024:])
        current_hash = hash(sample)

        if not force and current_hash == self._last_frame_hash:
            return None  # Screen unchanged

        self._last_frame_hash = current_hash

        # Convert to RGB image and encode
        img = Image.frombuffer('RGBA', (self.width, self.height), self.buf, 'raw', 'BGRA', 0, 1)
        rgb_img = img.convert('RGB')
        
        bio = io.BytesIO()
        rgb_img.save(bio, format='JPEG', quality=quality, optimize=False)
        return bio.getvalue(), self.width, self.height

    def cleanup(self):
        """Free GDI handles."""
        if self.hbmp:
            gdi32.DeleteObject(self.hbmp)
            self.hbmp = None
        if self.hdc_mem:
            gdi32.DeleteDC(self.hdc_mem)
            self.hdc_mem = None
        if self.hdc_screen:
            user32.ReleaseDC(self.hdesktop, self.hdc_screen)
            self.hdc_screen = None

    def __del__(self):
        self.cleanup()
