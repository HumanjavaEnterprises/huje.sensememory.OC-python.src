"""Tests for MemoryStore — validation and construction (no relay needed)."""

import pytest

from sense_memory.store import MemoryStore
from sense_memory.types import D_TAG_PREFIX


class FakeIdentity:
    """Minimal identity stub for testing store construction."""
    public_key_hex = "a" * 64
    private_key_hex = "b" * 64


def test_store_creation():
    store = MemoryStore(FakeIdentity(), "wss://relay.example.com")
    assert store.pubkey == "a" * 64
    assert store.relay_url == "wss://relay.example.com"


def test_store_rejects_empty_relay():
    with pytest.raises(ValueError, match="non-empty"):
        MemoryStore(FakeIdentity(), "")


def test_d_tag_prefix():
    assert D_TAG_PREFIX == "sense-memory/"
    assert f"{D_TAG_PREFIX}user_tz" == "sense-memory/user_tz"
