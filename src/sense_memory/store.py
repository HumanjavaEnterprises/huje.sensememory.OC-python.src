"""MemoryStore — read and write sovereign memories on Nostr relays.

An agent writes encrypted notes to itself on a relay. Key-value memories
use NIP-78 replaceable events (write the same key = overwrite). Journal
entries use NIP-04 DMs to self (append-only stream).

Both are NIP-44 encrypted — only the agent's own keypair can read them.
"""

import json

from nostrkey import Identity
from nostrkey.relay import RelayClient
from nostrkey.crypto import encrypt, decrypt

from .types import (
    Memory,
    JournalEntry,
    KIND_APP_DATA,
    KIND_DM,
    KIND_DELETION,
    D_TAG_PREFIX,
    MAX_QUERY_RESULTS,
    _validate_key,
)


class MemoryStore:
    """Sovereign persistence for an OpenClaw agent.

    Stores encrypted memories on a Nostr relay using the agent's
    own identity. Nobody else can read them.
    """

    def __init__(self, identity: Identity, relay_url: str) -> None:
        if not relay_url:
            raise ValueError("relay_url must be a non-empty string")
        self._identity = identity
        self._relay_url = relay_url

    @property
    def pubkey(self) -> str:
        """The agent's public key (hex)."""
        return self._identity.public_key_hex

    @property
    def relay_url(self) -> str:
        """The relay URL for persistence."""
        return self._relay_url

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

        async with RelayClient(self._relay_url) as relay:
            await relay.publish(signed)

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
            # Only include sense-memory events (check d-tag prefix)
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

        async with RelayClient(self._relay_url) as relay:
            await relay.publish(signed)

        return signed.id

    # --- Journal entries (append-only) ---

    async def journal(self, content: str) -> str:
        """Write a journal entry. Append-only — cannot be overwritten.

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

        signed = self._identity.sign_event(
            kind=KIND_DM,
            content=encrypted,
            tags=[["p", self._identity.public_key_hex]],
        )

        async with RelayClient(self._relay_url) as relay:
            await relay.publish(signed)

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
            "kinds": [KIND_DM],
            "authors": [self._identity.public_key_hex],
            "#p": [self._identity.public_key_hex],
            "limit": limit,
        })

        entries = []
        for event in events:
            try:
                data = self._decrypt_content(event.content)
                if data.get("type") == "sense-memory:journal":
                    entries.append(JournalEntry(
                        content=data["content"],
                        created_at=data.get("ts", event.created_at),
                    ))
            except (ValueError, KeyError, json.JSONDecodeError):
                continue

        return entries

    # --- Internal helpers ---

    async def _query(self, filters: dict) -> list:
        """Query the relay with a safety cap on results."""
        events = []
        async with RelayClient(self._relay_url) as relay:
            async for event in relay.subscribe([filters]):
                events.append(event)
                if len(events) >= MAX_QUERY_RESULTS:
                    break
        return events

    def _decrypt_content(self, encrypted_content: str) -> dict:
        """Decrypt and parse event content."""
        decrypted = decrypt(
            self._identity.private_key_hex,
            self._identity.public_key_hex,
            encrypted_content,
        )
        return json.loads(decrypted)
