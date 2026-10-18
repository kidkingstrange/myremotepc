"""
Cross-Platform Input Injection Engine for MyRemotePC.
Supports Windows (user32.SendInput) and macOS (CoreGraphics / ApplicationServices).
Translates normalized viewer pointer coordinates and browser keyboard events
into native operating system mouse and keyboard events.
Includes strict boundary validation, coordinate clamping, and sanitization.
"""

import math
import sys
import time
from typing import Optional, Union, Any

def clamp_float(val: Any, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Safely clamp a numeric input to [min_val, max_val] with NaN/Inf protection."""
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return min_val
        return max(min_val, min(max_val, f))
    except (TypeError, ValueError):
        return min_val

# Virtual key map from browser KeyboardEvent.code
VK_MAP = {
    # Control keys
    "Backspace": 0x08, "Tab": 0x09, "Enter": 0x0D, "ShiftLeft": 0x10, "ShiftRight": 0x10,
    "ControlLeft": 0x11, "ControlRight": 0x11, "AltLeft": 0x12, "AltRight": 0x12,
    "Pause": 0x13, "CapsLock": 0x14, "Escape": 0x1B, "Space": 0x20,
    "PageUp": 0x21, "PageDown": 0x22, "End": 0x23, "Home": 0x24,
    "ArrowLeft": 0x25, "ArrowUp": 0x26, "ArrowRight": 0x27, "ArrowDown": 0x28,
    "PrintScreen": 0x2C, "Insert": 0x2D, "Delete": 0x2E,
    # Meta / Command / Windows Key
    "MetaLeft": 0x5B, "MetaRight": 0x5C, "ContextMenu": 0x5D,
    # Numbers
    "Digit0": 0x30, "Digit1": 0x31, "Digit2": 0x32, "Digit3": 0x33, "Digit4": 0x34,
    "Digit5": 0x35, "Digit6": 0x36, "Digit7": 0x37, "Digit8": 0x38, "Digit9": 0x39,
    # Letters
    "KeyA": 0x41, "KeyB": 0x42, "KeyC": 0x43, "KeyD": 0x44, "KeyE": 0x45,
    "KeyF": 0x46, "KeyG": 0x47, "KeyH": 0x48, "KeyI": 0x49, "KeyJ": 0x4A,
    "KeyK": 0x4B, "KeyL": 0x4C, "KeyM": 0x4D, "KeyN": 0x4E, "KeyO": 0x4F,
    "KeyP": 0x50, "KeyQ": 0x51, "KeyR": 0x52, "KeyS": 0x53, "KeyT": 0x54,
    "KeyU": 0x55, "KeyV": 0x56, "KeyW": 0x57, "KeyX": 0x58, "KeyY": 0x59, "KeyZ": 0x5A,
    # Numpad
    "Numpad0": 0x60, "Numpad1": 0x61, "Numpad2": 0x62, "Numpad3": 0x63, "Numpad4": 0x64,
    "Numpad5": 0x65, "Numpad6": 0x66, "Numpad7": 0x67, "Numpad8": 0x68, "Numpad9": 0x69,
    "NumpadMultiply": 0x6A, "NumpadAdd": 0x6B, "NumpadSubtract": 0x6D, "NumpadDecimal": 0x6E, "NumpadDivide": 0x6F,
    # Function keys
    "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73, "F5": 0x74, "F6": 0x75,
    "F7": 0x76, "F8": 0x77, "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B,
    # Punctuation
    "Semicolon": 0xBA, "Equal": 0xBB, "Comma": 0xBC, "Minus": 0xBD, "Period": 0xBE, "Slash": 0xBF,
    "Backquote": 0xC0, "BracketLeft": 0xDB, "Backslash": 0xDC, "BracketRight": 0xDD, "Quote": 0xDE
}

# ==============================================================================
# Windows Implementation (Win32 SendInput)
# ==============================================================================
if sys.platform == 'win32':
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ('dx', wintypes.LONG), ('dy', wintypes.LONG), ('mouseData', wintypes.DWORD),
            ('dwFlags', wintypes.DWORD), ('time', wintypes.DWORD), ('dwExtraInfo', ctypes.c_ulonglong)
        ]

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ('wVk', wintypes.WORD), ('wScan', wintypes.WORD), ('dwFlags', wintypes.DWORD),
            ('time', wintypes.DWORD), ('dwExtraInfo', ctypes.c_ulonglong)
        ]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [('uMsg', wintypes.DWORD), ('wParamL', wintypes.WORD), ('wParamH', wintypes.WORD)]

    class _INPUT_UNION(ctypes.Union):
        _fields_ = [('mi', MOUSEINPUT), ('ki', KEYBDINPUT), ('hi', HARDWAREINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [('type', wintypes.DWORD), ('u', _INPUT_UNION)]

    INPUT_MOUSE = 0
    INPUT_KEYBOARD = 1
    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    MOUSEEVENTF_RIGHTDOWN = 0x0008
    MOUSEEVENTF_RIGHTUP = 0x0010
    MOUSEEVENTF_MIDDLEDOWN = 0x0020
    MOUSEEVENTF_MIDDLEUP = 0x0040
    MOUSEEVENTF_WHEEL = 0x0800
    MOUSEEVENTF_HWHEEL = 0x1000
    MOUSEEVENTF_ABSOLUTE = 0x8000
    MOUSEEVENTF_VIRTUALDESK = 0x4000
    KEYEVENTF_EXTENDEDKEY = 0x0001
    KEYEVENTF_KEYUP = 0x0002
    KEYEVENTF_UNICODE = 0x0004

    class WinInputInjector:
        def __init__(self):
            self.v_left = 0
            self.v_top = 0
            self.v_width = 1920
            self.v_height = 1080
            self.refresh_screen_metrics()

        def refresh_screen_metrics(self):
            self.v_left = user32.GetSystemMetrics(76)
            self.v_top = user32.GetSystemMetrics(77)
            self.v_width = user32.GetSystemMetrics(78)
            self.v_height = user32.GetSystemMetrics(79)
            if self.v_width <= 0:
                self.v_width = max(1, user32.GetSystemMetrics(0))
                self.v_height = max(1, user32.GetSystemMetrics(1))
                self.v_left = 0
                self.v_top = 0

        def mouse_move(self, norm_x: float, norm_y: float, monitor_left: int = 0, monitor_top: int = 0, monitor_width: int = 1920, monitor_height: int = 1080):
            cx = clamp_float(norm_x, 0.0, 1.0)
            cy = clamp_float(norm_y, 0.0, 1.0)
            abs_x = monitor_left + int(cx * monitor_width)
            abs_y = monitor_top + int(cy * monitor_height)

            self.refresh_screen_metrics()
            norm_vx = int(((abs_x - self.v_left) * 65535) / max(1, self.v_width))
            norm_vy = int(((abs_y - self.v_top) * 65535) / max(1, self.v_height))

            inp = INPUT()
            inp.type = INPUT_MOUSE
            inp.u.mi.dx = max(0, min(65535, norm_vx))
            inp.u.mi.dy = max(0, min(65535, norm_vy))
            inp.u.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK
            user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

        def mouse_button(self, button: str, action: str):
            if not isinstance(button, str) or not isinstance(action, str):
                return
            btn = button.lower()
            act = action.lower()
            flag_down = 0
            flag_up = 0
            if btn == 'left':
                flag_down = MOUSEEVENTF_LEFTDOWN
                flag_up = MOUSEEVENTF_LEFTUP
            elif btn == 'right':
                flag_down = MOUSEEVENTF_RIGHTDOWN
                flag_up = MOUSEEVENTF_RIGHTUP
            elif btn == 'middle':
                flag_down = MOUSEEVENTF_MIDDLEDOWN
                flag_up = MOUSEEVENTF_MIDDLEUP
            else:
                return

            if act == 'down':
                self._send_mouse_flag(flag_down)
            elif act == 'up':
                self._send_mouse_flag(flag_up)
            elif act == 'click':
                self._send_mouse_flag(flag_down)
                time.sleep(0.01)
                self._send_mouse_flag(flag_up)
            elif act == 'dblclick':
                self._send_mouse_flag(flag_down)
                self._send_mouse_flag(flag_up)
                time.sleep(0.04)
                self._send_mouse_flag(flag_down)
                self._send_mouse_flag(flag_up)

        def mouse_wheel(self, delta_y: float, delta_x: float = 0.0):
            dy = clamp_float(delta_y, -10.0, 10.0)
            dx = clamp_float(delta_x, -10.0, 10.0)
            if dy != 0:
                inp = INPUT()
                inp.type = INPUT_MOUSE
                inp.u.mi.dwFlags = MOUSEEVENTF_WHEEL
                inp.u.mi.mouseData = int(-dy * 120)
                user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
            if dx != 0:
                inp = INPUT()
                inp.type = INPUT_MOUSE
                inp.u.mi.dwFlags = MOUSEEVENTF_HWHEEL
                inp.u.mi.mouseData = int(dx * 120)
                user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

        def _send_mouse_flag(self, flag: int):
            inp = INPUT()
            inp.type = INPUT_MOUSE
            inp.u.mi.dwFlags = flag
            user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

        def key_event(self, code: str, action: str, key_char: Optional[str] = None):
            if not isinstance(code, str) or not isinstance(action, str):
                return
            act = action.lower()
            if act not in ('down', 'up'):
                return

            vk = VK_MAP.get(code)
            if vk:
                flags = 0
                if act == 'up':
                    flags |= KEYEVENTF_KEYUP
                if code in ("ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Home", "End", "PageUp", "PageDown", "Insert", "Delete"):
                    flags |= KEYEVENTF_EXTENDEDKEY

                inp = INPUT()
                inp.type = INPUT_KEYBOARD
                inp.u.ki.wVk = vk
                inp.u.ki.wScan = user32.MapVirtualKeyW(vk, 0)
                inp.u.ki.dwFlags = flags
                user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
            elif key_char and isinstance(key_char, str) and len(key_char) == 1:
                self.type_unicode_char(key_char, act)

        def type_unicode_char(self, char: str, action: str = 'press'):
            try:
                utf16_val = ord(char)
            except (TypeError, ValueError):
                return
            if action in ('down', 'press'):
                inp = INPUT()
                inp.type = INPUT_KEYBOARD
                inp.u.ki.wVk = 0
                inp.u.ki.wScan = utf16_val
                inp.u.ki.dwFlags = KEYEVENTF_UNICODE
                user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
            if action in ('up', 'press'):
                inp = INPUT()
                inp.type = INPUT_KEYBOARD
                inp.u.ki.wVk = 0
                inp.u.ki.wScan = utf16_val
                inp.u.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
                user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

        def lock_workstation(self):
            user32.LockWorkStation()

        def show_desktop(self):
            self.key_event("MetaLeft", "down")
            self.key_event("KeyD", "down")
            time.sleep(0.02)
            self.key_event("KeyD", "up")
            self.key_event("MetaLeft", "up")

# ==============================================================================
# macOS Implementation (CoreGraphics / ApplicationServices)
# ==============================================================================
class MacInputInjector:
    """macOS Input injector utilizing native Quartz CoreGraphics API via ctypes."""
    def __init__(self):
        self._cg = None
        try:
            import ctypes
            self._cg = ctypes.cdll.LoadLibrary('/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices')
        except Exception as e:
            print(f"[Input] macOS CoreGraphics load warning: {e}")

    def mouse_move(self, norm_x: float, norm_y: float, monitor_left: int = 0, monitor_top: int = 0, monitor_width: int = 1920, monitor_height: int = 1080):
        if not self._cg:
            return
        cx = clamp_float(norm_x, 0.0, 1.0)
        cy = clamp_float(norm_y, 0.0, 1.0)
        target_x = monitor_left + (cx * monitor_width)
        target_y = monitor_top + (cy * monitor_height)

        try:
            import ctypes
            # CGPoint (double x, double y)
            class CGPoint(ctypes.Structure):
                _fields_ = [('x', ctypes.c_double), ('y', ctypes.c_double)]

            pt = CGPoint(target_x, target_y)
            # kCGEventMouseMoved = 5
            ev = self._cg.CGEventCreateMouseEvent(None, 5, pt, 0)
            self._cg.CGEventPost(0, ev) # 0 = kCGHIDEventTap
            self._cg.CFRelease(ev)
        except Exception as e:
            print(f"[Input] macOS mouse move error: {e}")

    def mouse_button(self, button: str, action: str):
        if not self._cg:
            return
        btn = button.lower()
        act = action.lower()
        # macOS event types:
        # LeftDown=1, LeftUp=2, RightDown=3, RightUp=4, OtherDown=25, OtherUp=26
        down_type = 1 if btn == 'left' else (3 if btn == 'right' else 25)
        up_type = 2 if btn == 'left' else (4 if btn == 'right' else 26)
        btn_num = 0 if btn == 'left' else (1 if btn == 'right' else 2)

        try:
            import ctypes
            class CGPoint(ctypes.Structure):
                _fields_ = [('x', ctypes.c_double), ('y', ctypes.c_double)]

            loc = self._cg.CGEventGetLocation(self._cg.CGEventCreate(None))

            if act in ('down', 'click', 'dblclick'):
                ev = self._cg.CGEventCreateMouseEvent(None, down_type, loc, btn_num)
                self._cg.CGEventPost(0, ev)
                self._cg.CFRelease(ev)
            if act in ('up', 'click', 'dblclick'):
                ev = self._cg.CGEventCreateMouseEvent(None, up_type, loc, btn_num)
                self._cg.CGEventPost(0, ev)
                self._cg.CFRelease(ev)
            if act == 'dblclick':
                time.sleep(0.04)
                ev = self._cg.CGEventCreateMouseEvent(None, down_type, loc, btn_num)
                self._cg.CGEventPost(0, ev)
                self._cg.CFRelease(ev)
                ev2 = self._cg.CGEventCreateMouseEvent(None, up_type, loc, btn_num)
                self._cg.CGEventPost(0, ev2)
                self._cg.CFRelease(ev2)
        except Exception as e:
            print(f"[Input] macOS mouse button error: {e}")

    def mouse_wheel(self, delta_y: float, delta_x: float = 0.0):
        if not self._cg:
            return
        dy = int(clamp_float(delta_y, -10.0, 10.0) * 5)
        dx = int(clamp_float(delta_x, -10.0, 10.0) * 5)
        try:
            # kCGScrollEventUnitPixel = 0, kCGScrollEventUnitLine = 1
            ev = self._cg.CGEventCreateScrollWheelEvent(None, 1, 2, dy, dx)
            self._cg.CGEventPost(0, ev)
            self._cg.CFRelease(ev)
        except Exception as e:
            print(f"[Input] macOS scroll error: {e}")

    def key_event(self, code: str, action: str, key_char: Optional[str] = None):
        if not self._cg:
            return
        act = action.lower()
        key_down = (act == 'down')
        try:
            import ctypes
            # Simplified macOS virtual key code mapping
            mac_vk = {
                "Enter": 36, "Tab": 48, "Space": 49, "Backspace": 51, "Escape": 53,
                "MetaLeft": 55, "ShiftLeft": 56, "AltLeft": 58, "ControlLeft": 59
            }.get(code, 0)

            ev = self._cg.CGEventCreateKeyboardEvent(None, mac_vk, key_down)
            if key_char and len(key_char) == 1:
                u_str = ctypes.create_unicode_buffer(key_char)
                self._cg.CGEventKeyboardSetUnicodeString(ev, len(key_char), u_str)
            self._cg.CGEventPost(0, ev)
            self._cg.CFRelease(ev)
        except Exception as e:
            print(f"[Input] macOS key error: {e}")

    def lock_workstation(self):
        import subprocess
        # Native macOS screen lock command
        subprocess.run(["pmset", "displaysleepnow"])

    def show_desktop(self):
        import subprocess
        # Trigger Mission Control show desktop via AppleScript
        subprocess.run(["osascript", "-e", 'tell application "System Events" to key code 103'])

# ==============================================================================
# Unified Public Interface Factory
# ==============================================================================
def InputInjector():
    """Factory returning platform-native input injector."""
    if sys.platform == 'win32':
        return WinInputInjector()
    else:
        return MacInputInjector()
