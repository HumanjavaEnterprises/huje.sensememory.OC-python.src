# sense-memory

**Give your AI agent a memory.**

Sovereign persistence for OpenClaw agents — encrypted memories stored on Nostr relays using the agent's own keypair. Nobody else can read them.

## Why?

AI agents forget everything between conversations. Every tool that fixes this puts your agent's memories on someone else's server, behind someone else's API key.

sense-memory takes a different approach: your agent already has a cryptographic identity (via [NostrKey](https://pypi.org/project/nostrkey/)). That identity can sign and encrypt Nostr events. So instead of storing memories in a database you manage, the agent writes encrypted notes to itself on a Nostr relay — the same way it would send a DM to another agent, except the recipient is itself.

The result: **persistent memory that only the agent can read, stored on infrastructure that already exists, using a protocol that's open and sovereign.**

## How It Fits Together

sense-memory is part of the [NSE](https://nse.dev) sovereign identity ecosystem:

- **[NostrKey](https://pypi.org/project/nostrkey/)** gives the agent its identity — a Nostr keypair it owns
- **sense-memory** uses that identity to encrypt and store memories on any relay
- **[NostrCalendar](https://pypi.org/project/nostrcalendar/)** uses the same identity for scheduling
- **[NostrSocial](https://pypi.org/project/nostrsocial/)** uses it for the social graph
- **[NSE Orchestrator](https://pypi.org/project/nse-orchestrator/)** wires all five pillars into a coherent whole

The agent's keypair is the thread that runs through everything. One identity, many capabilities — and now, persistent memory.

## Install

```bash
pip install sense-memory
```

## Quick Start

```python
import asyncio, os
from nostrkey import Identity
from sense_memory import MemoryStore

async def main():
    identity = Identity.from_nsec(os.environ["NOSTR_NSEC"])
    store = MemoryStore(identity, "wss://relay.nostrkeep.com")

    # Remember something
    await store.remember("user_timezone", "America/Vancouver")

    # Recall it later
    memory = await store.recall("user_timezone")
    print(memory.value)  # "America/Vancouver"

    # Write a journal entry
    await store.journal("Had a great conversation about scheduling today")

    # Read recent journal
    entries = await store.recent(limit=5)
    for entry in entries:
        print(entry.content)

    # Forget a memory
    await store.forget("user_timezone")

asyncio.run(main())
```

## How It Works

| Mode | Nostr Kind | Behavior | Use Case |
|------|-----------|----------|----------|
| Key-value | 30078 (NIP-78) | Replaceable by key | Preferences, state, facts |
| Journal | 4 (NIP-04 DM to self) | Append-only | Conversation logs, observations |

Both modes encrypt content with NIP-44. Only the agent's keypair can decrypt. Any Nostr relay that supports these event kinds will work — no custom infrastructure needed.

## API

| Function | Returns | Description |
|----------|---------|-------------|
| `remember(key, value)` | `str` | Store or overwrite a memory. Returns event ID. |
| `recall(key)` | `Memory \| None` | Retrieve a memory by key. |
| `recall_all()` | `list[Memory]` | Retrieve all stored memories. |
| `forget(key)` | `str` | Delete a memory (NIP-09). Returns event ID. |
| `journal(content)` | `str` | Write an append-only journal entry. Returns event ID. |
| `recent(limit=20)` | `list[JournalEntry]` | Retrieve recent journal entries. |

## NIPs Used

| NIP | Purpose |
|-----|---------|
| NIP-01 | Basic event structure and relay protocol |
| NIP-04 | DM to self (journal entries) |
| NIP-09 | Event deletion (forget) |
| NIP-44 | Encryption for all stored content |
| NIP-78 | App-specific replaceable data (key-value memories) |

## OpenClaw Skill

sense-memory is published on [ClawHub](https://clawhub.ai) as the `sense-memory` skill. It's part of the [huje.tools](https://huje.tools) collection — open-source tools for the agentic age.

## License

MIT — Humanjava Enterprises Inc.
