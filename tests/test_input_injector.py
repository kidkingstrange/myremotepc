import pytest
from src.input_injector import clamp_float, InputInjector, VK_MAP

def test_clamp_float():
    # Standard numbers
    assert clamp_float(0.5, 0.0, 1.0) == 0.5
    assert clamp_float(-0.5, 0.0, 1.0) == 0.0
    assert clamp_float(1.5, 0.0, 1.0) == 1.0

    # NaN / Inf protection
    assert clamp_float(float('nan'), 0.0, 1.0) == 0.0
    assert clamp_float(float('inf'), 0.0, 1.0) == 0.0
    assert clamp_float(float('-inf'), 0.0, 1.0) == 0.0

    # Invalid types
    assert clamp_float("not_a_number", 0.0, 1.0) == 0.0
    assert clamp_float(None, 0.0, 1.0) == 0.0

def test_vk_map_coverage():
    # Verify core hotkeys exist
    assert "Enter" in VK_MAP
    assert "Escape" in VK_MAP
    assert "Backspace" in VK_MAP
    assert "Tab" in VK_MAP
    assert "MetaLeft" in VK_MAP
    assert "KeyA" in VK_MAP
    assert "F1" in VK_MAP

def test_input_injector_sanitization():
    injector = InputInjector()
    
    # Verify safe execution with malformed/out-of-bounds inputs without crashing
    injector.mouse_move(-999.0, 999.0)
    injector.mouse_move(float('nan'), float('inf'))
    
    injector.mouse_button("invalid_btn", "click")
    injector.mouse_button("left", "invalid_action")
    
    injector.mouse_wheel(999.0, -999.0)
    injector.key_event("InvalidKeyUnknown", "down")
    injector.type_unicode_char("A", "press")
