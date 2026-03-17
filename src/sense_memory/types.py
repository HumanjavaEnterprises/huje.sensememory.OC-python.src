"""Data types for sense-memory — memories and journal entries."""

from dataclasses import dataclass, field
import time

# NIP-78 app-specific replaceable event (key-value memories)
KIND_APP_DATA = 30078

# NIP-04 encrypted DM (journal entries to self)
KIND_DM = 4

# NIP-09 event deletion
KIND_DELETION = 5

# Prefix for d-tags to namespace our memories
D_TAG_PREFIX = "sense-memory/"

# Max content length to prevent relay abuse
MAX_CONTENT_LENGTH = 65000

# Max memories per query to prevent memory exhaustion
MAX_QUERY_RESULTS = 1000

# Max key length
MAX_KEY_LENGTH = 256


def _validate_key(key: str) -> None:
    """Validate a memory key."""
    if not isinstance(key, str) or not key:
        raise ValueError("Memory key must be a non-empty string")
    if len(key) > MAX_KEY_LENGTH:
        raise ValueError(
            f"Memory key too long ({len(key)} chars). Maximum is {MAX_KEY_LENGTH}."
        )
    if "/" in key or "\x00" in key or "\\" in key:
        raise ValueError(
            f"Memory key contains invalid characters (/, \\, or null): {key!r}"
        )
    if ".." in key:
        raise ValueError(f"Memory key contains path traversal: {key!r}")


@dataclass(frozen=True)
class Memory:
    """A key-value memory stored as a replaceable event.

    Stored as kind 30078 (NIP-78) with d-tag "sense-memory/{key}".
    Content is NIP-44 encrypted — only the agent can read it.
    Writing the same key overwrites the previous value.
    """
    key: str
    value: str
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        _validate_key(self.key)
        if not isinstance(self.value, str):
            raise ValueError(f"Memory value must be a string, got {type(self.value).__name__}")
        if len(self.value) > MAX_CONTENT_LENGTH:
            raise ValueError(
                f"Memory value too long ({len(self.value)} chars). "
                f"Maximum is {MAX_CONTENT_LENGTH}."
            )


@dataclass(frozen=True)
class JournalEntry:
    """An append-only journal entry stored as a DM to self.

    Stored as kind 4 (NIP-04 DM) where both author and recipient
    are the agent's own pubkey. Content is NIP-44 encrypted.
    Journal entries are append-only — they cannot be overwritten.
    """
    content: str
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not isinstance(self.content, str) or not self.content:
            raise ValueError("Journal entry content must be a non-empty string")
        if len(self.content) > MAX_CONTENT_LENGTH:
            raise ValueError(
                f"Journal entry too long ({len(self.content)} chars). "
                f"Maximum is {MAX_CONTENT_LENGTH}."
            )
