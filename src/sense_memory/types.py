"""Data types for sense-memory — memories, journal entries, and persona memory."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
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


# ─── v2: Persona Memory ─────────────────────────────────────────────

# Prefix for persona memories
PERSONA_D_TAG_PREFIX = "sense-memory/persona/"

# Introspection log prefix
INTROSPECTION_D_TAG_PREFIX = "sense-memory/introspection/"

# Default domains
DEFAULT_DOMAINS = ("self", "people", "projects", "world", "skills")

# Default facets
DEFAULT_FACETS = ("facts", "beliefs", "decisions", "procedures", "emotions")

# Memory states
STATE_ACTIVE = "active"
STATE_FADING = "fading"
STATE_FORGOTTEN = "forgotten"
STATE_DISSOLVED = "dissolved"
VALID_STATES = (STATE_ACTIVE, STATE_FADING, STATE_FORGOTTEN, STATE_DISSOLVED)

# Default halflife (days)
DEFAULT_HALFLIFE_DAYS = 30.0

# State thresholds
THRESHOLD_FADING = 0.3
THRESHOLD_FORGOTTEN = 0.1
THRESHOLD_DISSOLVED = 0.01

# Max domain/facet name length
MAX_TAXONOMY_LENGTH = 64


def _validate_taxonomy(name: str, kind: str = "name") -> None:
    """Validate a domain or facet name."""
    if not isinstance(name, str) or not name:
        raise ValueError(f"{kind} must be a non-empty string")
    if len(name) > MAX_TAXONOMY_LENGTH:
        raise ValueError(f"{kind} too long ({len(name)} chars). Max is {MAX_TAXONOMY_LENGTH}.")
    if "/" in name or "\x00" in name or "\\" in name:
        raise ValueError(f"{kind} contains invalid characters: {name!r}")
    if ".." in name:
        raise ValueError(f"{kind} contains path traversal: {name!r}")


@dataclass(frozen=True)
class PersonaMemory:
    """A structured memory in the persona's knowledge system.

    Organized by domain (broad area) and facet (type of knowledge).
    Has a relevance score that decays over time unless accessed or connected.

    Stored as kind 30078 (NIP-78) with d-tag:
        sense-memory/persona/{domain}/{facet}/{key}
    Content is NIP-44 encrypted.
    """
    domain: str
    facet: str
    key: str
    value: str

    # Lifecycle
    relevance: float = 1.0
    halflife_days: float = DEFAULT_HALFLIFE_DAYS
    last_accessed: float = field(default_factory=time.time)
    last_reinforced: float = field(default_factory=time.time)
    access_count: int = 0

    # Connections
    connections: tuple[str, ...] = ()
    contradicts: tuple[str, ...] = ()
    superseded_by: str | None = None

    # Metadata
    themes: tuple[str, ...] = ()
    source: str = ""
    confidence: float = 1.0
    state: str = STATE_ACTIVE

    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        _validate_taxonomy(self.domain, "Domain")
        _validate_taxonomy(self.facet, "Facet")
        _validate_key(self.key)
        if not isinstance(self.value, str):
            raise ValueError(f"value must be a string, got {type(self.value).__name__}")
        if len(self.value) > MAX_CONTENT_LENGTH:
            raise ValueError(f"value too long ({len(self.value)} chars). Max is {MAX_CONTENT_LENGTH}.")
        if self.state not in VALID_STATES:
            raise ValueError(f"state must be one of {VALID_STATES}, got {self.state!r}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be 0.0-1.0, got {self.confidence}")
        if self.halflife_days <= 0:
            raise ValueError(f"halflife_days must be positive, got {self.halflife_days}")

    @property
    def d_tag(self) -> str:
        """The NIP-78 d-tag for this memory."""
        return f"{PERSONA_D_TAG_PREFIX}{self.domain}/{self.facet}/{self.key}"

    def current_relevance(self, now: float | None = None) -> float:
        """Calculate current relevance based on time decay and connections.

        Relevance decays with a halflife. Connections boost it.
        Contradictions penalize it. Superseded memories decay 4x faster.
        """
        if now is None:
            now = time.time()

        days_since_access = (now - self.last_accessed) / 86400.0
        if days_since_access < 0:
            days_since_access = 0

        # Base decay
        decay = 0.5 ** (days_since_access / self.halflife_days)

        # Connection boost (each connection adds 10% to effective halflife)
        connection_boost = 1.0 + (len(self.connections) * 0.1)

        # Contradiction penalty
        contradiction_penalty = 0.5 ** len(self.contradicts)

        # Superseded memories decay 4x faster
        if self.superseded_by:
            decay = decay ** 4

        return self.relevance * decay * connection_boost * contradiction_penalty

    def compute_state(self, now: float | None = None) -> str:
        """Determine what state this memory should be in based on current relevance."""
        score = self.current_relevance(now)
        if score >= THRESHOLD_FADING:
            return STATE_ACTIVE
        if score >= THRESHOLD_FORGOTTEN:
            return STATE_FADING
        if score >= THRESHOLD_DISSOLVED:
            return STATE_FORGOTTEN
        return STATE_DISSOLVED

    def to_dict(self) -> dict:
        """Serialize to a dict for JSON storage in Nostr events."""
        return {
            "type": "sense-memory:persona",
            "domain": self.domain,
            "facet": self.facet,
            "key": self.key,
            "value": self.value,
            "relevance": self.relevance,
            "halflife_days": self.halflife_days,
            "last_accessed": self.last_accessed,
            "last_reinforced": self.last_reinforced,
            "access_count": self.access_count,
            "connections": list(self.connections),
            "contradicts": list(self.contradicts),
            "superseded_by": self.superseded_by,
            "themes": list(self.themes),
            "source": self.source,
            "confidence": self.confidence,
            "state": self.state,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> PersonaMemory:
        """Deserialize from a dict (from Nostr event content)."""
        return cls(
            domain=data["domain"],
            facet=data["facet"],
            key=data["key"],
            value=data["value"],
            relevance=data.get("relevance", 1.0),
            halflife_days=data.get("halflife_days", DEFAULT_HALFLIFE_DAYS),
            last_accessed=data.get("last_accessed", data.get("created_at", time.time())),
            last_reinforced=data.get("last_reinforced", data.get("created_at", time.time())),
            access_count=data.get("access_count", 0),
            connections=tuple(data.get("connections", ())),
            contradicts=tuple(data.get("contradicts", ())),
            superseded_by=data.get("superseded_by"),
            themes=tuple(data.get("themes", ())),
            source=data.get("source", ""),
            confidence=data.get("confidence", 1.0),
            state=data.get("state", STATE_ACTIVE),
            created_at=data.get("created_at", time.time()),
        )


@dataclass(frozen=True)
class IntrospectionReport:
    """Result of a persona memory introspection cycle."""
    total_memories: int = 0
    active: int = 0
    fading: int = 0
    forgotten: int = 0
    dissolved: int = 0

    # What needs attention
    contradictions: tuple[tuple[str, str], ...] = ()  # pairs of keys that contradict
    stale_beliefs: tuple[str, ...] = ()               # keys of beliefs with low confidence + low relevance
    orphaned: tuple[str, ...] = ()                    # keys with no connections
    overloaded_facets: tuple[str, ...] = ()           # domain/facet combos with too many active memories

    # Suggestions
    suggested_connections: tuple[tuple[str, str], ...] = ()  # pairs that should be linked
    suggested_revisions: tuple[str, ...] = ()                # keys of beliefs needing update
    pruned_count: int = 0                                     # how many memories changed state

    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        """Serialize for storage."""
        return {
            "type": "sense-memory:introspection",
            "total_memories": self.total_memories,
            "active": self.active,
            "fading": self.fading,
            "forgotten": self.forgotten,
            "dissolved": self.dissolved,
            "contradictions": [list(c) for c in self.contradictions],
            "stale_beliefs": list(self.stale_beliefs),
            "orphaned": list(self.orphaned),
            "overloaded_facets": list(self.overloaded_facets),
            "suggested_connections": [list(c) for c in self.suggested_connections],
            "suggested_revisions": list(self.suggested_revisions),
            "pruned_count": self.pruned_count,
            "timestamp": self.timestamp,
        }
