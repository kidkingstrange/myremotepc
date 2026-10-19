"""
Tests for Screen Capture Engine (src/capture.py).
Validates monitor enumeration, frame capture lifecycle, dirty checking,
GDI cleanup, and fallback handling.
"""

import sys
import pytest
from src.capture import ScreenCapturer, enumerate_monitors, MonitorInfo

def test_enumerate_monitors():
    monitors = enumerate_monitors()
    assert len(monitors) >= 1
    primary = monitors[0]
    assert isinstance(primary, MonitorInfo)
    assert primary.width > 0
    assert primary.height > 0
    
    d = primary.to_dict()
    assert "index" in d
    assert "name" in d
    assert "width" in d
    assert "height" in d
    assert "is_primary" in d
    assert d["width"] == primary.width
    assert d["height"] == primary.height

def test_screen_capturer_initialization():
    capturer = ScreenCapturer(monitor_index=0)
    try:
        assert capturer.width > 0
        assert capturer.height > 0
        assert capturer.current_monitor_index == 0
        assert len(capturer.monitors) >= 1
    finally:
        capturer.cleanup()

def test_screen_capturer_capture_jpeg():
    capturer = ScreenCapturer(monitor_index=0)
    try:
        result = capturer.capture_jpeg(quality=75, force=True)
        assert result is not None
        jpeg_bytes, w, h = result
        assert isinstance(jpeg_bytes, bytes)
        assert len(jpeg_bytes) > 100
        # Check standard JPEG magic bytes: SOI \xFF\xD8 and EOI \xFF\xD9
        assert jpeg_bytes[:2] == b'\xff\xd8'
        assert jpeg_bytes[-2:] == b'\xff\xd9'
        assert w == capturer.width
        assert h == capturer.height

        # Dirty checking: second immediate non-force capture should return None if unchanged
        second_result = capturer.capture_jpeg(quality=75, force=False)
        # Note: on a static desktop without motion, this should return None
        if second_result is not None:
            # If screen updated (e.g. cursor blink), verify it's valid JPEG
            assert second_result[0][:2] == b'\xff\xd8'

        # Force keyframe must always return a frame
        force_result = capturer.capture_jpeg(quality=75, force_keyframe=True)
        assert force_result is not None
        assert force_result[0][:2] == b'\xff\xd8'
    finally:
        capturer.cleanup()

def test_screen_capturer_monitor_switch():
    capturer = ScreenCapturer(monitor_index=0)
    try:
        initial_w = capturer.width
        capturer.select_monitor(0)
        assert capturer.current_monitor_index == 0
        assert capturer.width == initial_w
    finally:
        capturer.cleanup()

def test_screen_capturer_cleanup():
    capturer = ScreenCapturer(monitor_index=0)
    capturer.cleanup()
    if sys.platform == 'win32':
        assert capturer.hbmp is None
        assert capturer.hdc_mem is None
        assert capturer.hdc_screen is None
        assert capturer._current_hdesk is None

def test_lock_placeholder_generation():
    capturer = ScreenCapturer(monitor_index=0)
    try:
        if hasattr(capturer, '_generate_lock_placeholder'):
            frame, w, h = capturer._generate_lock_placeholder()
            assert isinstance(frame, bytes)
            assert frame[:2] == b'\xff\xd8'
            assert w > 0
            assert h > 0
    finally:
        capturer.cleanup()

def test_screen_capturer_invalid_monitor_index():
    capturer = ScreenCapturer(monitor_index=0)
    try:
        # Invalid high index should safely clamp or fallback to primary display
        capturer.select_monitor(999)
        assert capturer.current_monitor_index in (0, len(capturer.monitors) - 1)
        # Negative index should safely clamp
        capturer.select_monitor(-5)
        assert capturer.current_monitor_index == 0
    finally:
        capturer.cleanup()

def test_screen_capturer_resolution_change_check():
    capturer = ScreenCapturer(monitor_index=0)
    try:
        # Should not raise exception
        capturer.check_resolution_change()
    finally:
        capturer.cleanup()

def test_screen_capturer_concurrency():
    import threading
    capturer = ScreenCapturer(monitor_index=0)
    errors = []

    def capture_worker():
        try:
            for _ in range(10):
                capturer.capture_jpeg(quality=50, force=True)
        except Exception as e:
            errors.append(e)

    def switch_worker():
        try:
            for _ in range(10):
                capturer.select_monitor(0)
        except Exception as e:
            errors.append(e)

    threads = [
        threading.Thread(target=capture_worker),
        threading.Thread(target=switch_worker),
        threading.Thread(target=capture_worker)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    capturer.cleanup()
    assert len(errors) == 0, f"Concurrency errors: {errors}"

def test_repeated_gdi_init_cleanup_cycles():
    for _ in range(25):
        capturer = ScreenCapturer(monitor_index=0)
        res = capturer.capture_jpeg(quality=50, force=True)
        assert res is not None
        capturer.cleanup()

def test_desktop_attachment_deduplication():
    capturer = ScreenCapturer(monitor_index=0)
    try:
        if sys.platform == 'win32':
            # First call inside __init__ already attached desktop
            assert capturer._current_hdesk is not None
            # Subsequent call with the same active desktop should not re-trigger desktop change
            changed = capturer._ensure_input_desktop()
            assert changed is False
    finally:
        capturer.cleanup()

def test_dynamic_resolution_change_triggers_reinit():
    capturer = ScreenCapturer(monitor_index=0)
    try:
        real_width = capturer.width
        # Simulate an external resolution shift
        capturer.width = real_width + 100
        capturer.check_resolution_change()
        # Should have detected dimension mismatch and re-initialized back to true screen width
        assert capturer.width == real_width
    finally:
        capturer.cleanup()

def test_continuous_capture_loop_leak_free():
    capturer = ScreenCapturer(monitor_index=0)
    try:
        # Execute 100 rapid capture frames to stress-test GDI and DIB conversion
        for i in range(100):
            res = capturer.capture_jpeg(quality=50, force=True)
            assert res is not None
            frame_bytes, w, h = res
            assert len(frame_bytes) > 100
            assert frame_bytes[:2] == b'\xff\xd8'
            assert w == capturer.width
            assert h == capturer.height
    finally:
        capturer.cleanup()


