---
name: sense-memory
description: Sovereign persistence for AI agents — encrypted key-value memories and journal entries on Nostr relays
version: 0.1.0
metadata:
  openclaw:
    requires:
      bins:
        - pip
    install:
      - kind: uv
        package: sense-memory
        bins: []
    homepage: https://github.com/HumanjavaEnterprises/huje.sensememory.OC-python.src
---

# sense-memory -- Sovereign Persistence for AI Agents

Give your AI agent persistent memory using Nostr relays. Memories are encrypted with NIP-44 using the agent's own keypair -- nobody else can read them. Two modes: key-value (replaceable, for preferences and state) and journal (append-only, for logs and observations). Every memory is a signed Nostr event, so it works on any relay with zero custom infrastructure.

> **Import:** `pip install sense-memory` -> `from sense_memory import MemoryStore`

## Install

```bash
pip install sense-memory
```

Depends on `nostrkey` for identity and cryptography. Installed automatically as a dependency.

## Quickstart

```python
import asyncio, os
from nostrkey import Identity
from sense_memory import MemoryStore

identity = Identity.from_nsec(os.environ["NOSTR_NSEC"])
store = MemoryStore(identity, os.environ.get("NOSTR_RELAY", "wss://relay.nostrkeep.com"))

async def main():
    # Key-value: store and recall
    await store.remember("user_timezone", "America/Vancouver")
    mem = await store.recall("user_timezone")
    print(mem.value)  # "America/Vancouver"

    # Journal: append-only log
    await store.journal("User prefers concise responses")
    entries = await store.recent(limit=5)
    for e in entries:
        print(e.content)

asyncio.run(main())
```

## Core Capabilities

### 1. Remember (Key-Value)

Store a value by key. Writing the same key overwrites the previous value.

```python
from sense_memory import MemoryStore

await store.remember("user_name", "Vergel")
await store.remember("preferred_model", "claude-opus-4-6")
await store.remember("last_topic", "scheduling")
```

Stored as NIP-78 replaceable events (kind 30078) with d-tag `sense-memory/{key}`. Content is NIP-44 encrypted.

### 2. Recall

Retrieve a memory by key, or get all memories.

```python
# Single key
mem = await store.recall("user_name")
if mem:
    print(f"{mem.key} = {mem.value}")  # "user_name = Vergel"

# All memories
all_memories = await store.recall_all()
for m in all_memories:
    print(f"{m.key}: {m.value}")
```

Returns `None` if the key doesn't exist.

### 3. Forget

Delete a memory by key using NIP-09 deletion events.

```python
await store.forget("last_topic")
```

### 4. Journal

Write append-only entries -- conversation logs, observations, insights.

```python
await store.journal("User mentioned they're traveling next week")
await store.journal("Scheduled meeting with Alice for Monday 10am")
```

Stored as NIP-04 DMs to self (kind 4, author = recipient = agent's pubkey). Content is NIP-44 encrypted.

### 5. Recent

Retrieve recent journal entries (newest first).

```python
entries = await store.recent(limit=10)
for entry in entries:
    print(f"[{entry.created_at}] {entry.content}")
```

## When to Use Each Mode

| Mode | Kind | Behavior | Use Case |
|------|------|----------|----------|
| Key-value | 30078 (NIP-78) | Replaceable by key | User preferences, agent state, facts |
| Journal | 4 (NIP-04 DM) | Append-only stream | Conversation logs, observations, insights |

## Response Format

### Memory (returned by `recall()` and `recall_all()`)

| Field | Type | Description |
|-------|------|-------------|
| `key` | `str` | Memory key |
| `value` | `str` | Memory value |
| `created_at` | `float` | Unix timestamp when stored |

### JournalEntry (returned by `recent()`)

| Field | Type | Description |
|-------|------|-------------|
| `content` | `str` | Journal entry text |
| `created_at` | `float` | Unix timestamp when written |

### Return Types by Function

| Function | Returns | Description |
|----------|---------|-------------|
| `remember(key, value)` | `str` | Event ID of stored memory |
| `recall(key)` | `Memory \| None` | Memory if found, None otherwise |
| `recall_all()` | `list[Memory]` | All stored memories |
| `forget(key)` | `str` | Event ID of deletion event |
| `journal(content)` | `str` | Event ID of journal entry |
| `recent(limit=20)` | `list[JournalEntry]` | Recent entries, newest first |

## Common Patterns

### Async Usage

All functions are async. Wrap in `asyncio.run()` for scripts.

```python
import asyncio

async def persist():
    await store.remember("key", "value")
    mem = await store.recall("key")
    print(mem.value)

asyncio.run(persist())
```

### Error Handling

```python
try:
    await store.remember("key", "value")
except ValueError as e:
    print(f"Validation failed: {e}")  # bad key, value too long, etc.
except ConnectionError as e:
    print(f"Relay unreachable: {e}")
```

### Environment Variables for Identity

```python
import os
from nostrkey import Identity

identity = Identity.from_nsec(os.environ["NOSTR_NSEC"])
# The agent needs its own keypair -- mutual recognition principle
```

## Security

- **Never hardcode an nsec.** Load from environment variable or encrypted file.
- **All content is NIP-44 encrypted.** Only the agent's own keypair can decrypt.
- **Memory keys are validated.** No slashes, backslashes, null bytes, or path traversal.
- **Content length capped.** Max 65000 characters per memory/entry.
- **Relay queries capped.** Max 1000 events per query to prevent memory exhaustion.
- **No telemetry.** No network calls except to the relay you configure.

## Configuration

### MemoryStore Constructor

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `identity` | `Identity` | Yes | NostrKey identity for signing and encryption |
| `relay_url` | `str` | Yes | Nostr relay URL (wss://) |

### Memory Key Constraints

| Constraint | Limit |
|-----------|-------|
| Max length | 256 characters |
| Forbidden chars | `/`, `\`, null byte |
| Forbidden patterns | `..` (path traversal) |

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `NOSTR_NSEC` | Yes | Your nsec private key (bech32 or hex) |
| `NOSTR_RELAY` | No | Relay URL (default: `wss://relay.nostrkeep.com`) |

## Nostr NIPs Used

| NIP | Purpose |
|-----|---------|
| NIP-01 | Basic event structure and relay protocol |
| NIP-04 | DM to self (journal entries) |
| NIP-09 | Event deletion (forget) |
| NIP-44 | Encryption for all stored content |
| NIP-78 | App-specific replaceable data (key-value memories) |

## Links

- [PyPI](https://pypi.org/project/sense-memory/)
- [GitHub](https://github.com/HumanjavaEnterprises/huje.sensememory.OC-python.src)
- [huje.tools](https://huje.tools)
- [ClawHub](https://clawhub.ai/u/vveerrgg)

License: MIT
