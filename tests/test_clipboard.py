import pytest
from src.clipboard import get_clipboard_text, set_clipboard_text, MAX_CLIPBOARD_TEXT_CHARS

def test_clipboard_set_get_roundtrip():
    test_str = "MyRemotePC Automated Test Clipboard String 12345"
    success = set_clipboard_text(test_str)
    assert success is True
    read_str = get_clipboard_text()
    assert test_str in read_str

def test_clipboard_length_truncation():
    oversized = "A" * (MAX_CLIPBOARD_TEXT_CHARS + 500)
    success = set_clipboard_text(oversized)
    assert success is True
    read_str = get_clipboard_text()
    assert len(read_str) <= MAX_CLIPBOARD_TEXT_CHARS

def test_clipboard_invalid_input():
    assert set_clipboard_text(None) is False
