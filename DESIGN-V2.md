# sense-memory v2 — Sovereign Memory with Palace Structure, Decay, and Introspection

## Philosophy

Human memory isn't a database. It's a living system where knowledge ages, connections strengthen recall, contradictions trigger revision, and forgetting is as important as remembering. sense-memory v2 models this.

An AI agent's memory should:
- **Organize** — not flat key-value, but structured by domain and type
- **Compress** — load months of context efficiently for LLM consumption
- **Decay** — unused knowledge fades over time, keeping active memory lean
- **Connect** — memories that reference each other strengthen each other
- **Contradict** — newer knowledge can supersede older beliefs
- **Introspect** — periodically review what it knows, prune what's stale, surface what's contradictory

## v1 → v2 Compatibility

v1 API stays unchanged:
- `remember(key, value)` — still works, stores in the "flat" wing
- `recall(key)` — still works
- `recall_all()` — still works
- `forget(key)` — still works
- `journal(content)` — still works
- `recent(limit)` — still works

v2 adds new methods alongside v1. No breaking changes.

---

## Palace Structure

Inspired by the ancient Greek memory palace technique and MemPalace's implementation. Memories are organized into a three-level hierarchy stored in NIP-78 d-tags.

### Levels

```
Wing (domain)
  └── Hall (type)
       └── Room (specific memory)
```

**Wings** — broad domains of knowledge:
- `self` — who the agent is, its values, its identity
- `people` — people the agent knows, their preferences, relationships
- `projects` — ongoing work, decisions, progress
- `world` — facts, references, external knowledge
- `skills` — capabilities, tools, procedures the agent has learned

**Halls** — types of knowledge within a wing:
- `facts` — declarative knowledge ("Vergel prefers conventional commits")
- `beliefs` — opinions and interpretations ("This architecture is better because...")
- `decisions` — choices made and why ("We chose Orpheus over Kokoro because...")
- `procedures` — how to do things ("Deploy VoxRelay: npm run build, wrangler deploy")
- `emotions` — felt experiences ("The breakthrough on March 28 felt significant")

**Rooms** — individual memories with a unique key.

### Storage Format

d-tag: `sense-memory/persona/{wing}/{hall}/{room-key}`

Example: `sense-memory/persona/people/facts/vergel-prefers-vanilla-js`

v1 memories (flat): `sense-memory/{key}` (unchanged, treated as wing="flat")

---

## Knowledge Halflife

Every memory has a relevance score that decays over time unless reinforced.

### Scoring

```python
@dataclass
class PersonaMemory:
    wing: str
    hall: str
    key: str
    value: str

    # Lifecycle
    relevance: float = 1.0       # starts at 1.0
    halflife_days: float = 30.0  # score halves every 30 days by default
    last_accessed: float         # timestamp of last recall
    last_reinforced: float       # timestamp of last connection/reference
    access_count: int = 0        # total times recalled

    # Connections
    connections: list[str] = []  # keys of related memories
    contradicts: list[str] = []  # keys of contradicted memories
    superseded_by: str | None = None  # if newer memory replaces this

    # Metadata
    themes: list[str] = []       # searchable themes
    source: str = ""             # where this knowledge came from
    confidence: float = 1.0      # how confident the agent is (0-1)
    state: str = "active"        # active | fading | forgotten | dissolved

    created_at: float
```

### Decay Function

```python
def current_relevance(memory: PersonaMemory, now: float) -> float:
    """Calculate current relevance based on time decay."""
    days_since_access = (now - memory.last_accessed) / 86400
    decay = 0.5 ** (days_since_access / memory.halflife_days)

    # Boost for connections (each connection adds 10% to halflife)
    connection_boost = 1.0 + (len(memory.connections) * 0.1)

    # Penalty for contradictions
    contradiction_penalty = 0.5 ** len(memory.contradicts)

    # Superseded memories decay 4x faster
    if memory.superseded_by:
        decay = decay ** 4

    return memory.relevance * decay * connection_boost * contradiction_penalty
```

### State Transitions

```
Active (relevance > 0.3)
  → in search results, loaded in context, fully accessible
  → accessing resets relevance to 1.0

Fading (0.1 - 0.3)
  → in search results only if directly relevant
  → not auto-loaded in context
  → can be accessed (which revives to Active)

Forgotten (0.01 - 0.1)
  → NOT in search results
  → still on relay, encrypted, recoverable
  → explicit recall by exact key still works
  → introspection can surface forgotten memories

Dissolved (< 0.01)
  → deletion event published after 30 days in this state
  → gone from relay
  → cannot be recovered
```

---

## Compression

For loading memory context into an LLM prompt, memories are compressed into a structured shorthand.

### Compressed Format

```
[wing:people/hall:facts]
vergel: vanilla-js, conventional-commits, no-coauthor, accessibility-first
lisa: artist, teaches-workshops, partner
ruca: dog, walking-companion, idea-catalyst

[wing:projects/hall:decisions]
voxrelay-voice: orpheus-3b>kokoro (warmth, 3B params, emotion tags)
voxrelay-pricing: lite-55/parttime-85/business-179/practice-349 (1% gross rev)
nostrkeep-memory: build-own>fork-mempalace (paid service, no dependency)

[wing:self/hall:beliefs]
sovereign-ai: every process needs its own nostr keypair
aspirational-language: mirror the user's journey, never make them feel small
```

### Compression Rules
- Wing/hall as bracketed headers, not repeated per line
- Key: compressed-value format (no full sentences)
- Comparisons use `>` for "chosen over"
- Parenthetical for reasoning
- Skip fading/forgotten memories — only active
- Target: entire active memory in < 500 tokens

---

## Semantic Search

When exact key recall isn't enough — find memories by meaning.

### Approach

Use theme-based scoring (inspired by sense-wonder's `reflect()`):
- Each memory has a `themes` list
- Search query is matched against: key (weight 3), themes (weight 2), value (weight 1)
- Results sorted by combined score × relevance

### Future: Embedding-Based Search

When Workers AI embeddings are available:
- Store embedding alongside each memory (as a separate NIP-78 event: `sense-memory/embed/{key}`)
- Cosine similarity search across embeddings
- Hybrid: theme score + embedding similarity + relevance decay

---

## Introspection

Periodic self-review of the memory palace. Can be triggered by the agent or run on a schedule.

### `introspect() → IntrospectionReport`

```python
@dataclass
class IntrospectionReport:
    total_memories: int
    active: int
    fading: int
    forgotten: int

    # What needs attention
    contradictions: list[tuple[PersonaMemory, PersonaMemory]]  # pairs that contradict
    stale_beliefs: list[PersonaMemory]   # beliefs with low confidence + low relevance
    orphaned: list[PersonaMemory]        # memories with no connections
    overloaded_halls: list[str]         # halls with too many active memories

    # Suggestions
    suggested_connections: list[tuple[PersonaMemory, PersonaMemory]]  # memories that should be linked
    suggested_revisions: list[PersonaMemory]   # beliefs that may need updating
    suggested_compressions: list[str]         # wings that could be compressed
```

### Contradiction Detection

When storing a new memory:
1. Check existing memories in the same wing/hall for semantic overlap
2. If the new value contradicts an existing one (detected by theme overlap + opposing sentiment):
   - Mark the old memory's `contradicts` list
   - Set `superseded_by` on the old memory
   - The old memory decays 4x faster
   - The new memory starts at full relevance

### Connection Discovery

During introspection:
1. Find memories that share 2+ themes but aren't connected
2. Suggest connections to the agent
3. Agent can accept (creates bidirectional link) or dismiss

---

## API (v2 additions)

```python
class MemoryStore:
    # v1 (unchanged)
    async def remember(key, value) -> str
    async def recall(key) -> Memory | None
    async def recall_all() -> list[Memory]
    async def forget(key) -> str
    async def journal(content) -> str
    async def recent(limit) -> list[JournalEntry]

    # v2 — Persona
    async def persona_remember(wing, hall, key, value, themes=[], connections=[]) -> str
    async def persona_recall(wing=None, hall=None, key=None) -> list[PersonaMemory]
    async def persona_search(query, limit=10) -> list[PersonaMemory]
    async def persona_connect(key1, key2) -> None
    async def persona_contradict(old_key, new_key) -> None

    # v2 — Lifecycle
    async def persona_introspect() -> IntrospectionReport
    async def persona_compress(wing=None) -> str  # compressed format for LLM context
    async def persona_prune() -> int  # move fading→forgotten, dissolved→deleted. Returns count.

    # v2 — Metadata
    async def persona_wings() -> list[str]  # list all wings
    async def persona_halls(wing) -> list[str]  # list halls in a wing
    async def persona_stats() -> dict  # total memories, per-state counts, per-wing counts
```

---

## Storage on Nostr

All v2 data stored as NIP-78 (kind 30078) events, NIP-44 encrypted.

### Event Layout

| What | d-tag | Content (encrypted JSON) |
|------|-------|--------------------------|
| Persona memory | `sense-memory/persona/{wing}/{hall}/{key}` | `{ type, wing, hall, key, value, relevance, halflife_days, last_accessed, access_count, connections, contradicts, superseded_by, themes, source, confidence, state, created_at }` |
| Embedding | `sense-memory/embed/{key}` | `{ key, embedding: float[], model, created_at }` |
| Flat memory (v1) | `sense-memory/{key}` | `{ type, key, value, ts }` (unchanged) |
| Journal (v1) | kind 4 DM to self | `{ type, content, ts }` (unchanged) |
| Introspection log | `sense-memory/introspection/{timestamp}` | `{ report: IntrospectionReport }` |

### NostrKeep Tier Mapping

| Feature | Free (huje.tools) | Keep ($7/mo) |
|---------|-------------------|--------------|
| Flat key-value (v1) | Yes | Yes |
| Journal (v1) | Yes | Yes |
| Persona structure | 1 wing, 1 hall | Unlimited |
| Compression | Basic | Full AAAK-style |
| Semantic search | Theme-based only | Theme + embedding |
| Introspection | Manual only | Scheduled + manual |
| Knowledge halflife | Fixed 30-day | Configurable per memory |
| Max memories | 100 | 10,000 |

---

## Build Order

1. **PersonaMemory type** — dataclass with all fields, validation, serialization
2. **persona_remember / persona_recall** — store and retrieve with d-tag hierarchy
3. **Relevance decay** — current_relevance() function, state transitions
4. **persona_search** — theme-based scoring (no embeddings yet)
5. **persona_compress** — compressed format output
6. **persona_connect / persona_contradict** — relationship management
7. **persona_introspect** — contradiction detection, orphan finding, suggestions
8. **persona_prune** — state transitions, dissolution
9. **Embeddings** — Workers AI integration for semantic search (future)
10. **Introspection scheduling** — automated periodic review (future)

---

## References

- MemPalace (milla-jovovich/mempalace) — inspiration for persona structure and AAAK compression concept
- sense-wonder `reflect()` — weighted theme scoring model
- NIP-78 (kind 30078) — replaceable events for structured app data
- NIP-44 — ChaCha20-Poly1305 encryption
- Archon Object Model — wings map to archon attribute domains
