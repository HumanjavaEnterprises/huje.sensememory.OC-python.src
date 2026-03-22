"""Data types for sense-memory — memories and journal entries."""

from dataclasses import dataclass, field
import time

# NIP-78 app-specific replaceable event (key-value memories AND journal)
KIND_APP_DATA = 30078

# NIP-09 event deletion
KIND_DELETION = 5

# Prefix for d-tags to namespace our memories
D_TAG_PREFIX = "sense-memory/"

# Prefix for journal entries (also NIP-78, append-only via unique d-tags)
JOURNAL_D_TAG_PREFIX = "sense-journal/"

# Max content length to prevent relay abuse
MAX_CONTENT_LENGTH = 65000

# Max memories per query to prevent memory exhaustion
MAX_QUERY_RESULTS = 1000

# Max key length
MAX_KEY_LENGTH = 256

# Relay operation timeout (seconds)
RELAY_TIMEOUT = 15


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


def _validate_relay_url(relay_url: str) -> None:
    """Reject relay URLs that are not secure WebSocket (SSRF prevention)."""
    if not isinstance(relay_url, str) or not relay_url.startswith("wss://"):
        raise ValueError(
            f"relay_url must start with wss://, got {str(relay_url)[:40]!r}"
        )


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
    """An append-only journal entry.

    Stored as kind 30078 (NIP-78) with d-tag "sense-journal/{timestamp}".
    Content is NIP-44 encrypted. Journal entries are append-only —
    each gets a unique d-tag so they don't overwrite each other.
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
