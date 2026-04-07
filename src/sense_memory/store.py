"""MemoryStore — read and write sovereign memories on Nostr relays.

An agent writes encrypted notes to itself on one or more relays.
Key-value memories use NIP-78 replaceable events (write the same key = overwrite).
Journal entries also use NIP-78 with unique d-tags (append-only stream).

All content is NIP-44 encrypted — only the agent's own keypair can read them.

Multi-relay support: pass a list of relay URLs. Writes go to all relays
(best-effort fanout). Reads use the first relay that responds.
"""

import asyncio
import json

from nostrkey import Identity
from nostrkey.relay import RelayClient
from nostrkey.crypto import encrypt, decrypt

from .types import (
    Memory,
    JournalEntry,
    KIND_APP_DATA,
    KIND_DELETION,
    D_TAG_PREFIX,
    JOURNAL_D_TAG_PREFIX,
    MAX_QUERY_RESULTS,
    RELAY_TIMEOUT,
    _validate_key,
    _validate_relay_url,
)


class MemoryStore:
    """Sovereign persistence for an OpenClaw agent.

    Stores encrypted memories on Nostr relays using the agent's
    own identity. Nobody else can read them.

    Supports multi-relay: pass a list of relay URLs for redundancy.
    Writes fan out to all relays. Reads use the first to respond.
    """

    def __init__(
        self,
        identity: Identity,
        relay_url: str | list[str],
    ) -> None:
        if isinstance(relay_url, str):
            _validate_relay_url(relay_url)
            self._relay_urls = [relay_url]
        elif isinstance(relay_url, list) and len(relay_url) > 0:
            for url in relay_url:
                _validate_relay_url(url)
            self._relay_urls = list(relay_url)
        else:
            raise ValueError("relay_url must be a non-empty string or list of strings")

        self._identity = identity

    def __repr__(self) -> str:
        """Redacted repr — never expose identity secrets."""
        return (
            f"MemoryStore(pubkey={self._identity.public_key_hex[:8]}..., "
            f"relay_url={self._relay_url!r})"
        )

    @property
    def pubkey(self) -> str:
        """The agent's public key (hex)."""
        return self._identity.public_key_hex

    @property
    def relay_url(self) -> str:
        """The primary relay URL (first in list)."""
        return self._relay_urls[0]

    @property
    def relay_urls(self) -> list[str]:
        """All relay URLs."""
        return list(self._relay_urls)

    # --- Key-value memories (replaceable) ---

    async def remember(self, key: str, value: str) -> str:
        """Store a key-value memory. Overwrites if the key already exists.

        Args:
            key: Memory key (max 256 chars, no slashes or null bytes).
            value: Memory value (max 65000 chars).

        Returns:
            The event ID of the stored memory.
        """
        memory = Memory(key=key, value=value)

        payload = json.dumps({
            "type": "sense-memory:kv",
            "key": memory.key,
            "value": memory.value,
            "ts": memory.created_at,
        })

        encrypted = encrypt(
            self._identity.private_key_hex,
            self._identity.public_key_hex,
            payload,
        )

        d_tag = f"{D_TAG_PREFIX}{key}"
        signed = self._identity.sign_event(
            kind=KIND_APP_DATA,
            content=encrypted,
            tags=[["d", d_tag]],
        )

        await self._publish_to_all(signed)
        return signed.id

    async def recall(self, key: str) -> Memory | None:
        """Recall a memory by key.

        Args:
            key: The memory key to look up.

        Returns:
            The Memory if found, None otherwise.
        """
        _validate_key(key)
        d_tag = f"{D_TAG_PREFIX}{key}"

        events = await self._query({
            "kinds": [KIND_APP_DATA],
            "authors": [self._identity.public_key_hex],
            "#d": [d_tag],
            "limit": 1,
        })

        if not events:
            return None

        event = events[0]
        data = self._decrypt_content(event.content)

        # Verify the decrypted key matches what was queried
        decrypted_key = data.get("key", "")
        if decrypted_key != key:
            raise ValueError(
                f"Decrypted key {decrypted_key!r} does not match queried key {key!r}. "
                f"Event may be corrupted or tampered with."
            )

        return Memory(
            key=data["key"],
            value=data["value"],
            created_at=data.get("ts", event.created_at),
        )

    async def recall_all(self) -> list[Memory]:
        """Recall all stored memories.

        Returns:
            List of all Memory objects.
        """
        events = await self._query({
            "kinds": [KIND_APP_DATA],
            "authors": [self._identity.public_key_hex],
        })

        memories = []
        for event in events:
            # Only include sense-memory KV events (check d-tag prefix)
            d_tags = [t[1] for t in event.tags if len(t) >= 2 and t[0] == "d"]
            if not d_tags or not d_tags[0].startswith(D_TAG_PREFIX):
                continue

            try:
                data = self._decrypt_content(event.content)
                if data.get("type") == "sense-memory:kv":
                    memories.append(Memory(
                        key=data["key"],
                        value=data["value"],
                        created_at=data.get("ts", event.created_at),
                    ))
            except (ValueError, KeyError, json.JSONDecodeError):
                continue  # Skip malformed events

        return memories

    async def forget(self, key: str) -> str:
        """Delete a memory by key (NIP-09 deletion event).

        Args:
            key: The memory key to delete.

        Returns:
            The event ID of the deletion event.
        """
        _validate_key(key)
        d_tag = f"{D_TAG_PREFIX}{key}"

        signed = self._identity.sign_event(
            kind=KIND_DELETION,
            content="Forgotten",
            tags=[["a", f"{KIND_APP_DATA}:{self._identity.public_key_hex}:{d_tag}"]],
        )

        await self._publish_to_all(signed)
        return signed.id

    # --- Journal entries (append-only, NIP-78 with unique d-tags) ---

    async def journal(self, content: str) -> str:
        """Write a journal entry. Append-only — cannot be overwritten.

        Uses NIP-78 (kind 30078) with a unique d-tag per entry,
        so each journal entry is its own replaceable event that
        won't collide with other entries.

        Args:
            content: The journal entry text (max 65000 chars).

        Returns:
            The event ID of the journal entry.
        """
        entry = JournalEntry(content=content)

        payload = json.dumps({
            "type": "sense-memory:journal",
            "content": entry.content,
            "ts": entry.created_at,
        })

        encrypted = encrypt(
            self._identity.private_key_hex,
            self._identity.public_key_hex,
            payload,
        )

        # Unique d-tag per entry ensures append-only (no overwrite)
        d_tag = f"{JOURNAL_D_TAG_PREFIX}{entry.created_at}"
        signed = self._identity.sign_event(
            kind=KIND_APP_DATA,
            content=encrypted,
            tags=[["d", d_tag]],
        )

        await self._publish_to_all(signed)
        return signed.id

    async def recent(self, limit: int = 20) -> list[JournalEntry]:
        """Recall recent journal entries.

        Args:
            limit: Maximum number of entries to return (default 20, max 100).

        Returns:
            List of JournalEntry objects, newest first.
        """
        if limit < 1:
            limit = 1
        if limit > 100:
            limit = 100

        events = await self._query({
            "kinds": [KIND_APP_DATA],
            "authors": [self._identity.public_key_hex],
            "limit": limit + 50,  # over-fetch to filter non-journal events
        })

        entries = []
        for event in events:
            # Only include journal events
            d_tags = [t[1] for t in event.tags if len(t) >= 2 and t[0] == "d"]
            if not d_tags or not d_tags[0].startswith(JOURNAL_D_TAG_PREFIX):
                continue

            try:
                data = self._decrypt_content(event.content)
                if data.get("type") == "sense-memory:journal":
                    entries.append(JournalEntry(
                        content=data["content"],
                        created_at=data.get("ts", event.created_at),
                    ))
            except (ValueError, KeyError, json.JSONDecodeError):
                continue

            if len(entries) >= limit:
                break

        return entries

    # --- Relay health check ---

    async def check(self) -> dict[str, bool]:
        """Check connectivity to all configured relays.

        Returns:
            Dict mapping relay URL to reachable (True/False).
        """
        results = {}
        for url in self._relay_urls:
            try:
                async def _ping():
                    async with RelayClient(url) as relay:
                        # Simple subscribe with impossible filter to test connectivity
                        async for _ in relay.subscribe([{
                            "kinds": [KIND_APP_DATA],
                            "authors": ["0" * 64],
                            "limit": 1,
                        }]):
                            break
                await asyncio.wait_for(_ping(), timeout=5)
                results[url] = True
            except Exception:
                results[url] = False
        return results

    # --- Internal helpers ---

    async def _publish_to_all(self, signed) -> None:
        """Fan out a signed event to all configured relays.

        Best-effort: continues even if some relays fail.
        Raises if ALL relays fail.
        """
        errors = []
        for url in self._relay_urls:
            try:
                async def _pub():
                    async with RelayClient(url) as relay:
                        await relay.publish(signed)
                await asyncio.wait_for(_pub(), timeout=RELAY_TIMEOUT)
            except Exception as e:
                errors.append((url, e))

        if len(errors) == len(self._relay_urls):
            relay_list = ", ".join(url for url, _ in errors)
            raise ConnectionError(
                f"Failed to publish to all relays: {relay_list}"
            )

    async def _query(self, filters: dict) -> list:
        """Query relays with a safety cap on results.

        Tries each relay in order, returns results from the first
        that responds successfully.
        """
        for url in self._relay_urls:
            try:
                events = []

                async def _fetch():
                    async with RelayClient(url) as relay:
                        async for event in relay.subscribe([filters]):
                            events.append(event)
                            if len(events) >= MAX_QUERY_RESULTS:
                                break

                await asyncio.wait_for(_fetch(), timeout=RELAY_TIMEOUT)
                return events
            except Exception:
                continue  # Try next relay

        return []  # All relays failed

    def _decrypt_content(self, encrypted_content: str) -> dict:
        """Decrypt and parse event content."""
        decrypted = decrypt(
            self._identity.private_key_hex,
            self._identity.public_key_hex,
            encrypted_content,
        )
        return json.loads(decrypted)
