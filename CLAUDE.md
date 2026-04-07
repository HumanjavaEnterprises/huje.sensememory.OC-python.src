# sense-memory

Sovereign persistence for OpenClaw AI agents. Part of the huje.tools ecosystem.

## Build & Test

```bash
pip install -e ".[dev]"
pytest -v
```

## Structure

- `src/sense_memory/` — package source
  - `types.py` — Memory, JournalEntry, constants, key validation
  - `store.py` — MemoryStore (main entry point — remember, recall, journal, forget)
- `tests/` — pytest suite
- `clawhub/` — OpenClaw skill metadata
- `examples/` — runnable examples

## Publish

```bash
# PyPI (needs API token + OTP)
python3 -m build
python3 -m twine upload dist/sense_memory-X.Y.Z*

# ClawHub
npx clawhub publish ./clawhub --slug sense-memory --name "sense-memory" --version X.Y.Z --tags latest --changelog "..."
```

Version must be bumped in 3 places: `pyproject.toml`, `__init__.py`, `clawhub/metadata.json`

## Conventions

- Python 3.10+, hatchling build, ruff linter (100 char line length)
- Dependency: `nostrkey>=0.3.0` only
- Import matches package name: `pip install sense-memory` → `from sense_memory import MemoryStore`
- Key-value memories use NIP-78 (kind 30078) replaceable events with d-tag `sense-memory/{key}`
- Journal entries use NIP-04 (kind 4) DMs to self (author = recipient = agent pubkey)
- All content NIP-44 encrypted — only the agent can read its own memories
- Memory keys: max 256 chars, no slashes/backslashes/null bytes/path traversal
- Content length capped at 65000 chars
- Relay queries capped at 1000 events (memory exhaustion prevention)
- Frozen dataclasses for Memory and JournalEntry
- Version must be bumped in 3 places: pyproject.toml, __init__.py, clawhub/metadata.json

## TODO — Before Next Push

- [ ] Red team security audit (follow social-value pattern from 2026-03-19)
  - SecretStr wrapper for nsec/passphrase fields (prevent repr/traceback leaks)
  - Sanitized exceptions (SenseMemoryError) — never leak nsec in stack traces
  - Input validation helpers (_validate_key, _validate_content) on all entry points
  - __repr__ redaction on MemoryStore (redact nsec, passphrase)
  - Path traversal hardening on relay URLs
  - Tests proving each security property (repr redaction, input rejection, error sanitization)
  - Target: match social-value's 57-test / 19-finding audit standard
- [x] Security hardening (2026-03-19)
  - Added `__repr__` redaction on MemoryStore — never exposes nsec, private_key_hex, or identity secrets
  - Repr shows truncated pubkey (first 8 chars) + relay_url for safe identification
  - Error messages verified clean of secret values
  - Added `tests/test_security.py` with repr redaction and error sanitization tests
  - Updated nostrkey dependency to `>=0.3.0`
