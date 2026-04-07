"""sense-memory — Sovereign persistence for OpenClaw AI agents."""

from .types import (
    Memory,
    JournalEntry,
    PersonaMemory,
    IntrospectionReport,
    DEFAULT_DOMAINS,
    DEFAULT_FACETS,
    STATE_ACTIVE,
    STATE_FADING,
    STATE_FORGOTTEN,
    STATE_DISSOLVED,
)
from .store import MemoryStore

__version__ = "0.2.0"

__all__ = [
    "Memory",
    "JournalEntry",
    "PersonaMemory",
    "IntrospectionReport",
    "MemoryStore",
    "DEFAULT_DOMAINS",
    "DEFAULT_FACETS",
    "STATE_ACTIVE",
    "STATE_FADING",
    "STATE_FORGOTTEN",
    "STATE_DISSOLVED",
]
