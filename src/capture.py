"""
Cross-Platform Screen Capture Engine for MyRemotePC.
Supports Windows (Win32 GDI BitBlt zero-copy) and macOS (Quartz / CoreGraphics via mss/PIL).
Includes multi-monitor enumeration, dynamic resolution change detection, and adaptive compression.
"""

import io
import sys
import time
from typing import List, Dict, Optional, Tuple
from PIL import Image

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

# ==============================================================================
# Windows Capture Implementation (Win32 GDI)
# ==============================================================================
if sys.platform == 'win32':
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32

    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass

    class RECT(ctypes.Structure):
        _fields_ = [('left', wintypes.LONG), ('top', wintypes.LONG), ('right', wintypes.LONG), ('bottom', wintypes.LONG)]

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ('biSize', wintypes.DWORD), ('biWidth', wintypes.LONG), ('biHeight', wintypes.LONG),
            ('biPlanes', wintypes.WORD), ('biBitCount', wintypes.WORD), ('biCompression', wintypes.DWORD),
            ('biSizeImage', wintypes.DWORD), ('biXPelsPerMeter', wintypes.LONG), ('biYPelsPerMeter', wintypes.LONG),
            ('biClrUsed', wintypes.DWORD), ('biClrImportant', wintypes.DWORD)
        ]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [('bmiHeader', BITMAPINFOHEADER), ('bmiColors', wintypes.DWORD * 3)]

    SRCCOPY = 0x00CC0020
    BI_RGB = 0

    def _win_enumerate_monitors() -> List[MonitorInfo]:
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

        MONITORENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(RECT), wintypes.LPARAM)
        proc = MONITORENUMPROC(_monitor_enum_proc)
        user32.EnumDisplayMonitors(None, None, proc, 0)
        if not monitors:
            w = max(640, user32.GetSystemMetrics(0))
            h = max(480, user32.GetSystemMetrics(1))
            monitors.append(MonitorInfo(0, "Display 1 (Primary)", 0, 0, w, h, True))
        return monitors

    class WinScreenCapturer:
        def __init__(self, monitor_index: int = 0):
            self.monitors = _win_enumerate_monitors()
            self.current_monitor_index = monitor_index
            self.hdesktop = None
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
            self._frame_count = 0
            self._init_session(monitor_index)

        def _init_session(self, monitor_index: int):
            self.cleanup()
            self.monitors = _win_enumerate_monitors()
            if monitor_index < 0 or monitor_index >= len(self.monitors):
                monitor_index = 0
            self.current_monitor_index = monitor_index
            target = self.monitors[monitor_index]
            self.left = target.left
            self.top = target.top
            self.width = max(100, target.width)
            self.height = max(100, target.height)

            self.bmi = BITMAPINFO()
            self.bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            self.bmi.bmiHeader.biWidth = self.width
            self.bmi.bmiHeader.biHeight = -self.height
            self.bmi.bmiHeader.biPlanes = 1
            self.bmi.bmiHeader.biBitCount = 32
            self.bmi.bmiHeader.biCompression = BI_RGB

            self.buf = ctypes.create_string_buffer(self.width * self.height * 4)
            self.hdesktop = user32.GetDesktopWindow()
            self.hdc_screen = user32.GetDC(self.hdesktop)
            self.hdc_mem = gdi32.CreateCompatibleDC(self.hdc_screen)
            self.hbmp = gdi32.CreateCompatibleBitmap(self.hdc_screen, self.width, self.height)
            gdi32.SelectObject(self.hdc_mem, self.hbmp)

        def select_monitor(self, index: int):
            if index != self.current_monitor_index and 0 <= index < len(self.monitors):
                self._init_session(index)

        def check_resolution_change(self):
            current_w = user32.GetSystemMetrics(0)
            current_h = user32.GetSystemMetrics(1)
            if self.current_monitor_index == 0 and (current_w != self.width or current_h != self.height):
                self._init_session(0)

        def capture_jpeg(self, quality: int = 75, force: bool = False) -> Optional[Tuple[bytes, int, int]]:
            self._frame_count += 1
            if self._frame_count % 60 == 0:
                self.check_resolution_change()

            if not self.hdc_mem or not self.hdc_screen:
                return None

            success = gdi32.BitBlt(self.hdc_mem, 0, 0, self.width, self.height, self.hdc_screen, self.left, self.top, SRCCOPY)
            if not success:
                self._init_session(self.current_monitor_index)
                return None

            gdi32.GetDIBits(self.hdc_mem, self.hbmp, 0, self.height, self.buf, ctypes.byref(self.bmi), 0)

            raw_mv = memoryview(self.buf)
            buf_len = len(raw_mv)
            if buf_len >= 3072:
                sample = bytes(raw_mv[0:1024]) + bytes(raw_mv[buf_len//2:buf_len//2 + 1024]) + bytes(raw_mv[-1024:])
                current_hash = hash(sample)
            else:
                current_hash = hash(bytes(raw_mv))

            if not force and current_hash == self._last_frame_hash:
                return None

            self._last_frame_hash = current_hash

            try:
                img = Image.frombuffer('RGBA', (self.width, self.height), self.buf, 'raw', 'BGRA', 0, 1)
                rgb_img = img.convert('RGB')
                bio = io.BytesIO()
                rgb_img.save(bio, format='JPEG', quality=max(10, min(95, quality)), optimize=False)
                return bio.getvalue(), self.width, self.height
            except Exception as e:
                print(f"[Capture] JPEG encoding error: {e}")
                return None

        def cleanup(self):
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

# ==============================================================================
# macOS / Generic Capture Implementation (Quartz / CoreGraphics via mss / PIL)
# ==============================================================================
class MacScreenCapturer:
    """macOS screen capturer utilizing native CoreGraphics / mss."""
    def __init__(self, monitor_index: int = 0):
        self._sct = None
        try:
            import mss
            self._sct = mss.mss()
        except Exception:
            pass

        self.monitors = self._enumerate_monitors()
        self.current_monitor_index = monitor_index
        self._last_frame_hash = None
        self._init_session(monitor_index)

    def _enumerate_monitors(self) -> List[MonitorInfo]:
        result = []
        if self._sct:
            for idx, m in enumerate(self._sct.monitors[1:]):  # index 0 is full virtual screen
                result.append(MonitorInfo(
                    index=idx,
                    name=f"Display {idx + 1}" + (" (Primary)" if idx == 0 else ""),
                    left=m["left"],
                    top=m["top"],
                    width=m["width"],
                    height=m["height"],
                    is_primary=(idx == 0)
                ))
        if not result:
            result.append(MonitorInfo(0, "Display 1 (Primary)", 0, 0, 1920, 1080, True))
        return result

    def _init_session(self, monitor_index: int):
        self.monitors = self._enumerate_monitors()
        if monitor_index < 0 or monitor_index >= len(self.monitors):
            monitor_index = 0
        self.current_monitor_index = monitor_index
        m = self.monitors[monitor_index]
        self.left = m.left
        self.top = m.top
        self.width = m.width
        self.height = m.height

    def select_monitor(self, index: int):
        if 0 <= index < len(self.monitors):
            self._init_session(index)

    def capture_jpeg(self, quality: int = 75, force: bool = False) -> Optional[Tuple[bytes, int, int]]:
        try:
            if self._sct:
                # Target monitor index in mss is 1-based (0 is all)
                target_mon = self._sct.monitors[self.current_monitor_index + 1]
                sct_img = self._sct.grab(target_mon)
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            else:
                from PIL import ImageGrab
                img = ImageGrab.grab()

            self.width, self.height = img.size

            # Sample hash for dirty check
            sample = img.tobytes()[::8192]
            current_hash = hash(sample)
            if not force and current_hash == self._last_frame_hash:
                return None
            self._last_frame_hash = current_hash

            bio = io.BytesIO()
            img.save(bio, format='JPEG', quality=max(10, min(95, quality)), optimize=False)
            return bio.getvalue(), self.width, self.height
        except Exception as e:
            print(f"[Capture] macOS capture error: {e}")
            return None

    def cleanup(self):
        if self._sct:
            try:
                self._sct.close()
            except Exception:
                pass
            self._sct = None

# ==============================================================================
# Unified Public Interface & Factory
# ==============================================================================
def enumerate_monitors() -> List[MonitorInfo]:
    """Enumerate monitors on current active platform."""
    if sys.platform == 'win32':
        return _win_enumerate_monitors()
    else:
        capturer = MacScreenCapturer()
        res = capturer.monitors
        capturer.cleanup()
        return res

def ScreenCapturer(monitor_index: int = 0):
    """Factory returning platform-native screen capturer."""
    if sys.platform == 'win32':
        return WinScreenCapturer(monitor_index)
    else:
        return MacScreenCapturer(monitor_index)
