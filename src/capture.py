"""
Cross-Platform Screen Capture Engine for MyRemotePC.
Supports Windows (Win32 GDI BitBlt zero-copy) and macOS (Quartz / CoreGraphics via mss/PIL).
Includes multi-monitor enumeration, dynamic resolution change detection, and adaptive compression.
"""

import io
import sys
import threading
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

    # Declare explicit 64-bit handle types for Windows API
    user32.OpenInputDesktop.restype = ctypes.c_void_p
    user32.OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    user32.SetThreadDesktop.restype = wintypes.BOOL
    user32.SetThreadDesktop.argtypes = [ctypes.c_void_p]
    user32.CloseDesktop.restype = wintypes.BOOL
    user32.CloseDesktop.argtypes = [ctypes.c_void_p]
    user32.GetUserObjectInformationW.restype = wintypes.BOOL
    user32.GetUserObjectInformationW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]

    user32.GetDesktopWindow.restype = ctypes.c_void_p
    user32.GetDC.restype = ctypes.c_void_p
    user32.GetDC.argtypes = [ctypes.c_void_p]
    user32.ReleaseDC.restype = ctypes.c_int
    user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

    gdi32.CreateCompatibleDC.restype = ctypes.c_void_p
    gdi32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
    gdi32.CreateCompatibleBitmap.restype = ctypes.c_void_p
    gdi32.CreateCompatibleBitmap.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    gdi32.SelectObject.restype = ctypes.c_void_p
    gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    gdi32.DeleteObject.restype = ctypes.c_int
    gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
    gdi32.DeleteDC.restype = ctypes.c_int
    gdi32.DeleteDC.argtypes = [ctypes.c_void_p]
    gdi32.BitBlt.restype = ctypes.c_int
    gdi32.BitBlt.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, wintypes.DWORD]
    gdi32.GetDIBits.restype = ctypes.c_int
    gdi32.GetDIBits.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]

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
            self._lock = threading.Lock()
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
            self._current_hdesk = None
            self._current_desk_name = ""
            self._last_frame_hash = None
            self._frame_count = 0
            self._is_locked = False
            with self._lock:
                self._init_session_locked(monitor_index)

        def _get_desktop_name(self, hdesk) -> str:
            if not hdesk:
                return ""
            try:
                buf = ctypes.create_unicode_buffer(256)
                needed = wintypes.DWORD()
                if user32.GetUserObjectInformationW(hdesk, 2, buf, ctypes.sizeof(buf), ctypes.byref(needed)):
                    return buf.value
            except Exception:
                pass
            return ""

        def _ensure_input_desktop(self) -> bool:
            """
            Attach thread to active input desktop.
            Properly closes duplicate HDESK handles to eliminate Windows handle exhaustion.
            Returns True if the desktop attachment changed, requiring GDI DC recreation.
            """
            try:
                # 0x01FF covers DESKTOP_SWITCHDESKTOP, READOBJECTS, WRITEOBJECTS, etc.
                hdesk = user32.OpenInputDesktop(0, False, 0x01FF)
                if hdesk:
                    desk_name = self._get_desktop_name(hdesk)
                    if not self._current_hdesk or (desk_name and desk_name != self._current_desk_name):
                        user32.SetThreadDesktop(hdesk)
                        if self._current_hdesk:
                            try:
                                user32.CloseDesktop(self._current_hdesk)
                            except Exception:
                                pass
                        self._current_hdesk = hdesk
                        self._current_desk_name = desk_name
                        self._is_locked = False
                        return True
                    else:
                        # Same active desktop: close redundant handle immediately to prevent leak
                        try:
                            user32.CloseDesktop(hdesk)
                        except Exception:
                            pass
                        return False
                else:
                    self._is_locked = True
                    return False
            except Exception:
                self._is_locked = True
                return False

        def _init_session_locked(self, monitor_index: int):
            self._cleanup_locked()
            self._ensure_input_desktop()
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
            self.hdc_screen = user32.GetDC(0)
            if self.hdc_screen:
                self.hdc_mem = gdi32.CreateCompatibleDC(self.hdc_screen)
                if self.hdc_mem:
                    self.hbmp = gdi32.CreateCompatibleBitmap(self.hdc_screen, self.width, self.height)
                    if self.hbmp:
                        gdi32.SelectObject(self.hdc_mem, self.hbmp)

        def _init_session(self, monitor_index: int):
            with self._lock:
                self._init_session_locked(monitor_index)

        def select_monitor(self, index: int):
            with self._lock:
                if 0 <= index < len(self.monitors):
                    if index != self.current_monitor_index:
                        self._init_session_locked(index)
                else:
                    if self.current_monitor_index != 0:
                        self._init_session_locked(0)

        def check_resolution_change(self):
            with self._lock:
                monitors = _win_enumerate_monitors()
                if len(monitors) != len(self.monitors):
                    self._init_session_locked(min(self.current_monitor_index, max(0, len(monitors) - 1)))
                    return
                idx = min(self.current_monitor_index, len(monitors) - 1)
                new_target = monitors[idx]
                if (new_target.width != self.width or new_target.height != self.height or
                    new_target.left != self.left or new_target.top != self.top):
                    self._init_session_locked(idx)

        def _generate_lock_placeholder(self) -> Tuple[bytes, int, int]:
            """Create an informational placeholder frame when desktop is locked / UAC."""
            w = max(640, self.width)
            h = max(480, self.height)
            try:
                from PIL import Image, ImageDraw
                img = Image.new("RGB", (w, h), color=(18, 24, 38))
                draw = ImageDraw.Draw(img)
                msg1 = "DESKTOP LOCKED / SESSION INACTIVE"
                msg2 = "Unlock host machine or accept UAC elevation prompt to resume view."
                draw.text((max(20, w // 2 - 160), max(20, h // 2 - 20)), msg1, fill=(239, 68, 68))
                draw.text((max(20, w // 2 - 240), max(20, h // 2 + 10)), msg2, fill=(156, 163, 175))
                bio = io.BytesIO()
                img.save(bio, format="JPEG", quality=75)
                return bio.getvalue(), w, h
            except Exception:
                img = Image.new("RGB", (w, h), color=(15, 15, 15))
                bio = io.BytesIO()
                img.save(bio, format="JPEG", quality=50)
                return bio.getvalue(), w, h

        def capture_jpeg(self, quality: int = 75, force: bool = False, force_keyframe: bool = False, **kwargs) -> Optional[Tuple[bytes, int, int]]:
            effective_force = force or force_keyframe
            self._frame_count += 1
            if self._frame_count % 60 == 0 or self._is_locked:
                self.check_resolution_change()

            with self._lock:
                # If desktop changed (e.g. unlock or session switch), re-init GDI session immediately
                desktop_changed = self._ensure_input_desktop()
                if desktop_changed:
                    self._init_session_locked(self.current_monitor_index)

                # Try primary GDI zero-copy capture path
                if self.hdc_mem and self.hdc_screen:
                    success = gdi32.BitBlt(self.hdc_mem, 0, 0, self.width, self.height, self.hdc_screen, self.left, self.top, SRCCOPY)
                    if success:
                        gdi32.GetDIBits(self.hdc_mem, self.hbmp, 0, self.height, self.buf, ctypes.byref(self.bmi), 0)
                        raw_mv = memoryview(self.buf)
                        buf_len = len(raw_mv)
                        if buf_len >= 3072:
                            sample = bytes(raw_mv[0:1024]) + bytes(raw_mv[buf_len//2:buf_len//2 + 1024]) + bytes(raw_mv[-1024:])
                            current_hash = hash(sample)
                        else:
                            current_hash = hash(bytes(raw_mv))

                        if not effective_force and current_hash == self._last_frame_hash and not self._is_locked:
                            return None

                        self._last_frame_hash = current_hash
                        self._is_locked = False
                        try:
                            img = Image.frombuffer('RGBA', (self.width, self.height), self.buf, 'raw', 'BGRA', 0, 1)
                            rgb_img = img.convert('RGB')
                            bio = io.BytesIO()
                            rgb_img.save(bio, format='JPEG', quality=max(10, min(95, quality)), optimize=False)
                            return bio.getvalue(), self.width, self.height
                        except Exception as e:
                            print(f"[Capture] GDI buffer conversion error: {e}")

            # Fallback path via ImageGrab
            try:
                from PIL import ImageGrab
                if self.current_monitor_index == 0:
                    img = ImageGrab.grab()
                else:
                    target = self.monitors[min(self.current_monitor_index, len(self.monitors) - 1)]
                    bbox = (target.left, target.top, target.left + target.width, target.top + target.height)
                    img = ImageGrab.grab(bbox=bbox)

                w, h = img.size
                sample = img.tobytes()[::8192]
                current_hash = hash(sample)
                if not effective_force and current_hash == self._last_frame_hash and not self._is_locked:
                    return None
                self._last_frame_hash = current_hash
                self._is_locked = False

                bio = io.BytesIO()
                img.save(bio, format='JPEG', quality=max(10, min(95, quality)), optimize=False)
                return bio.getvalue(), w, h
            except Exception:
                # Both GDI and ImageGrab failed (desktop locked, UAC prompt, or session switched)
                if not self._is_locked or effective_force:
                    self._is_locked = True
                    lock_frame, lw, lh = self._generate_lock_placeholder()
                    self._last_frame_hash = hash(lock_frame)
                    return lock_frame, lw, lh
                return None

        def _cleanup_locked(self):
            if self.hbmp:
                gdi32.DeleteObject(self.hbmp)
                self.hbmp = None
            if self.hdc_mem:
                gdi32.DeleteDC(self.hdc_mem)
                self.hdc_mem = None
            if self.hdc_screen:
                user32.ReleaseDC(0, self.hdc_screen)
                self.hdc_screen = None
            if self._current_hdesk:
                try:
                    user32.CloseDesktop(self._current_hdesk)
                except Exception:
                    pass
                self._current_hdesk = None
                self._current_desk_name = ""

        def cleanup(self):
            with self._lock:
                self._cleanup_locked()

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

    def capture_jpeg(self, quality: int = 75, force: bool = False, force_keyframe: bool = False, **kwargs) -> Optional[Tuple[bytes, int, int]]:
        effective_force = force or force_keyframe
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
            if not effective_force and current_hash == self._last_frame_hash:
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
