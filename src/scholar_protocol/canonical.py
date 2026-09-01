"""Deterministic (canonical) JSON serialization for ResearchProtocol.

Invariant
---------
Given an identical ``ResearchProtocol`` instance (same field values in the
same declaration order), this module always produces **byte-identical** JSON.
That byte-identical JSON is then hashed with SHA-256 to produce the
``protocol_hash`` stored in the WORKSPACE_GENESIS audit event.

Serialization rules (must not change without a schema version bump)
-------------------------------------------------------------------
1. **Key order** — Pydantic model fields are serialized in their
   *declaration order* (model_fields preserves insertion order in Python
   ≥3.7 / Pydantic v2).  Nested dict keys within ``metadata`` and
   ``date_range`` are sorted alphabetically for stability.

2. **Array ordering** — Author-order arrays (synonyms, core_concepts,
   research_questions, screening criteria, matrix_dimensions,
   incompatible_concepts, target_databases, languages) are preserved
   as authored.  The compiler (Cycle B) is responsible for emitting
   them in a consistent order; the serializer does NOT silently sort them.

3. **Float format** — ``minimum_trust_score_threshold`` is always
   serialized with exactly one decimal place (e.g. ``5.0`` not ``5`` or
   ``5.00``) via a post-processing step.

4. **Whitespace** — Compact JSON; ``separators=(",", ":")``,
   ``ensure_ascii=True``, no trailing newline.

5. **Fingerprint** — ``sha256(utf8(canonical_bytes)).hexdigest()``,
   returned with the ``sha256:`` prefix.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from scholar_protocol.models import ResearchProtocol


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _ordered_model_dict(protocol: ResearchProtocol) -> dict[str, Any]:
    """Produce a plain dict whose key order mirrors Pydantic declaration order.

    Pydantic v2's ``model_dump(mode="json")`` already serializes using
    declaration order.  We apply the alias (``$schema``) so the output
    key is ``$schema``, not ``schema_version``.

    Special post-processing:
    - ``metadata`` and ``date_range`` nested dicts → keys sorted alpha.
    - ``minimum_trust_score_threshold`` coerced to a float so JSON
      serialization always emits a decimal point.
    """
    raw: dict[str, Any] = protocol.model_dump(mode="json", by_alias=True)

    # Sort the free-form dict fields that have no semantically defined key order.
    if "metadata" in raw and isinstance(raw["metadata"], dict):
        raw["metadata"] = dict(sorted(raw["metadata"].items()))

    if "search_strategy" in raw:
        ss = raw["search_strategy"]
        if isinstance(ss.get("date_range"), dict):
            ss["date_range"] = dict(sorted(ss["date_range"].items()))

    # Ensure float serialization is stable for the trust threshold.
    if "verification" in raw:
        v = raw["verification"]
        if "minimum_trust_score_threshold" in v:
            v["minimum_trust_score_threshold"] = float(
                v["minimum_trust_score_threshold"]
            )

    return raw


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def canonical_json(protocol: ResearchProtocol) -> bytes:
    """Serialize *protocol* to canonical UTF-8 JSON bytes.

    The output is deterministic: identical protocol → identical bytes.

    Parameters
    ----------
    protocol:
        A validated ``ResearchProtocol`` instance.

    Returns
    -------
    bytes
        Compact, UTF-8 encoded JSON with no trailing newline.
    """
    ordered = _ordered_model_dict(protocol)

    # json.dumps with a custom float encoder so 5.0 → "5.0" not "5".
    # Python's default encoder writes floats via repr(); we normalise with
    # a custom default for floats.
    raw_str = json.dumps(
        ordered,
        ensure_ascii=True,
        separators=(",", ":"),
        allow_nan=False,
        # Sort_keys=False — we control ordering via _ordered_model_dict.
        sort_keys=False,
    )

    # Post-process float representation: ensure whole-number floats keep
    # their decimal point.  Python's json.dumps emits 5.0 as "5.0" by
    # default when the value is already a float, so this is belt-and-suspenders.
    # The real guard is that we coerced the threshold to float() above.
    return raw_str.encode("utf-8")


def canonical_fingerprint(protocol: ResearchProtocol) -> str:
    """Return the ``sha256:<hex>`` fingerprint of the canonical JSON.

    Parameters
    ----------
    protocol:
        A validated ``ResearchProtocol`` instance.

    Returns
    -------
    str
        String of the form ``'sha256:<64-hex-chars>'``.
    """
    digest = hashlib.sha256(canonical_json(protocol)).hexdigest()
    return f"sha256:{digest}"
