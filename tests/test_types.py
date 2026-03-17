"""Tests for sense-memory data types."""

import pytest

from sense_memory.types import Memory, JournalEntry, _validate_key


def test_memory_roundtrip():
    m = Memory(key="user_tz", value="America/Vancouver")
    assert m.key == "user_tz"
    assert m.value == "America/Vancouver"
    assert m.created_at > 0


def test_memory_rejects_empty_key():
    with pytest.raises(ValueError, match="non-empty"):
        Memory(key="", value="test")


def test_memory_rejects_slash_in_key():
    with pytest.raises(ValueError, match="invalid characters"):
        Memory(key="foo/bar", value="test")


def test_memory_rejects_null_in_key():
    with pytest.raises(ValueError, match="invalid characters"):
        Memory(key="foo\x00bar", value="test")


def test_memory_rejects_backslash_in_key():
    with pytest.raises(ValueError, match="invalid characters"):
        Memory(key="foo\\bar", value="test")


def test_memory_rejects_path_traversal():
    with pytest.raises(ValueError, match="path traversal"):
        Memory(key="..secret", value="test")


def test_memory_rejects_long_key():
    with pytest.raises(ValueError, match="too long"):
        Memory(key="x" * 257, value="test")


def test_memory_rejects_long_value():
    with pytest.raises(ValueError, match="too long"):
        Memory(key="k", value="x" * 65001)


def test_memory_rejects_non_string_value():
    with pytest.raises(ValueError, match="must be a string"):
        Memory(key="k", value=123)


def test_memory_is_frozen():
    m = Memory(key="k", value="v")
    with pytest.raises(AttributeError):
        m.key = "other"


def test_journal_entry_basic():
    e = JournalEntry(content="Had a good conversation today")
    assert e.content == "Had a good conversation today"
    assert e.created_at > 0


def test_journal_rejects_empty():
    with pytest.raises(ValueError, match="non-empty"):
        JournalEntry(content="")


def test_journal_rejects_non_string():
    with pytest.raises(ValueError, match="non-empty"):
        JournalEntry(content=None)


def test_journal_rejects_long_content():
    with pytest.raises(ValueError, match="too long"):
        JournalEntry(content="x" * 65001)


def test_journal_is_frozen():
    e = JournalEntry(content="test")
    with pytest.raises(AttributeError):
        e.content = "other"


def test_validate_key_accepts_valid():
    _validate_key("user_preference")
    _validate_key("timezone")
    _validate_key("conversation-2026-03-17")
    _validate_key("a")
    _validate_key("x" * 256)


def test_validate_key_rejects_invalid():
    for bad in ["", "a/b", "a\\b", "a\x00b", "..", "..foo", None]:
        with pytest.raises(ValueError):
            _validate_key(bad)
