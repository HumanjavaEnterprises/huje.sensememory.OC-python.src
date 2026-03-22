"""Tests for MemoryStore — validation and construction (no relay needed)."""

import pytest

from sense_memory.store import MemoryStore
from sense_memory.types import D_TAG_PREFIX, JOURNAL_D_TAG_PREFIX


class FakeIdentity:
    """Minimal identity stub for testing store construction."""
    public_key_hex = "a" * 64
    private_key_hex = "b" * 64


def test_store_creation():
    store = MemoryStore(FakeIdentity(), "wss://relay.example.com")
    assert store.pubkey == "a" * 64
    assert store.relay_url == "wss://relay.example.com"


def test_store_multi_relay():
    store = MemoryStore(FakeIdentity(), [
        "wss://relay1.example.com",
        "wss://relay2.example.com",
    ])
    assert store.relay_url == "wss://relay1.example.com"
    assert len(store.relay_urls) == 2


def test_store_rejects_empty_relay():
    with pytest.raises(ValueError, match="wss://"):
        MemoryStore(FakeIdentity(), "")


def test_store_rejects_insecure_relay():
    with pytest.raises(ValueError, match="wss://"):
        MemoryStore(FakeIdentity(), "ws://relay.example.com")


def test_store_rejects_http_relay():
    with pytest.raises(ValueError, match="wss://"):
        MemoryStore(FakeIdentity(), "http://relay.example.com")


def test_store_rejects_empty_list():
    with pytest.raises(ValueError, match="non-empty"):
        MemoryStore(FakeIdentity(), [])


def test_d_tag_prefix():
    assert D_TAG_PREFIX == "sense-memory/"
    assert f"{D_TAG_PREFIX}user_tz" == "sense-memory/user_tz"


def test_journal_d_tag_prefix():
    assert JOURNAL_D_TAG_PREFIX == "sense-journal/"
