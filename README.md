# scholar-protocol-kit

> **Phase 0 — Cycle A** of the Nexus Scholar harness.  
> Pure Python. Zero LLM. Zero network. Fully deterministic.

## What this kit does

`scholar-protocol-kit` is the **contract spine** of the Nexus Scholar research pipeline.

It provides:

1. **Pydantic v2 models** (`models.py`) — the sole runtime source of truth for `protocol.json`.
2. **Canonical serializer** (`canonical.py`) — deterministic JSON bytes + `sha256` fingerprint.
3. **Validation engine** (`validate.py`) — structural (Pydantic) + cross-field rules.
4. **CLI** (`cli.py`) — `scholar-protocol validate / fingerprint / canon`.

Every downstream kit (`scholar-search-kit`, `scholar-rag-kit`, Phase 4 Trust) reads `protocol.json` validated by this kit.

---

## Installation

```bash
# From the harness root (recommended — uses shared .venv)
uv pip install -e tools/scholar-protocol-kit

# Or from within the kit directory
cd tools/scholar-protocol-kit
uv pip install -e .
```

---

## CLI Usage

```bash
# Validate a protocol.json (exit 0 = valid, 1 = invalid, 2 = usage error)
scholar-protocol validate workspaces/my-project/protocol.json

# Strict mode: warnings become errors
scholar-protocol validate --strict workspaces/my-project/protocol.json

# Print the canonical sha256 fingerprint
scholar-protocol fingerprint workspaces/my-project/protocol.json
# Output: sha256:a3f9...

# Print canonical JSON bytes (for diffing generator output)
scholar-protocol canon workspaces/my-project/protocol.json | diff - golden.json
```

---

## Python API

```python
from scholar_protocol import (
    ResearchProtocol,
    validate_protocol,
    canonical_json,
    canonical_fingerprint,
)

# Parse and validate
report = validate_protocol("workspaces/my-project/protocol.json")
if not report.is_valid:
    for err in report.errors:
        print(err)

# Get canonical bytes and fingerprint
protocol = ResearchProtocol.model_validate_json(open("protocol.json").read())
fp = canonical_fingerprint(protocol)   # "sha256:a3f9..."
raw = canonical_json(protocol)         # b'{"$schema":...}'
```

---

## Canonical Serialization Rules

The following rules are **frozen at schema v1.0.0** and must not change without a version bump:

| Rule | Detail |
|:-----|:-------|
| Key order | Pydantic declaration order (stable) |
| `metadata` keys | Sorted alphabetically |
| `date_range` keys | Sorted alphabetically |
| Float format | `minimum_trust_score_threshold` always has a decimal point (e.g. `5.0` not `5`) |
| Whitespace | Compact — `separators=(",", ":")` |
| Encoding | `ensure_ascii=True`, UTF-8 bytes |
| Trailing newline | None |
| Fingerprint | `sha256:<hexdigest>` of canonical bytes |

---

## Running Tests

```bash
cd tools/scholar-protocol-kit
uv pip install -e ".[dev]"
pytest
```

All tests are deterministic. No network calls, no LLM, no mocks needed.

---

## Schema Versions

| Version | File | Status |
|:--------|:-----|:-------|
| 1.0.0 | `schemas/v1/protocol.schema.json` | Active |

---

## Directory Layout

```
scholar-protocol-kit/
├── pyproject.toml
├── src/scholar_protocol/
│   ├── __init__.py       # Public API re-exports
│   ├── models.py         # Pydantic v2 models (sole source of truth)
│   ├── canonical.py      # Deterministic serializer + sha256 fingerprint
│   ├── validate.py       # Structural + cross-field validation
│   └── cli.py            # Typer + Rich CLI
├── schemas/
│   └── v1/
│       └── protocol.schema.json   # Checked-in JSON Schema
└── tests/
    ├── fixtures/
    │   ├── valid/         # Golden fixtures (hand-authored ground truth)
    │   ├── invalid/       # Must-reject fixtures with expected error codes
    │   └── canonical/     # Round-trip canonicalization fixtures
    ├── test_models.py
    ├── test_canonical.py
    ├── test_validate.py
    └── test_cli.py
```
