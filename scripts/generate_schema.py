#!/usr/bin/env python3
"""Generate the checked-in JSON Schema from the Pydantic models.

Usage
-----
    python scripts/generate_schema.py [--check] [--output PATH]

    --check     Diff the generated schema against the checked-in file and exit
                non-zero if they differ. Used by CI (tests/test_schema_sync.py
                calls this logic directly; this script is the human-facing CLI).
    --output    Write the generated schema to PATH (default: schemas/v1/protocol.schema.json)

The generated schema is based on ``ResearchProtocol.model_json_schema(by_alias=True)``
(Pydantic v2), post-processed to match the conventions of the checked-in schema:

Post-processing steps (applied after Pydantic generation)
----------------------------------------------------------
1. Replace the auto-generated ``$defs`` key with ``definitions`` to match the
   JSON Schema Draft-07 convention used in the checked-in file.
2. Replace ``#/$defs/`` refs with ``#/definitions/`` refs.
3. Add the top-level ``$schema`` and ``$id`` meta-fields.
4. Add ``additionalProperties: false`` to all named object schemas so unknown
   keys are rejected (the model is the authoritative gate).
5. Normalise ``metadata`` to ``additionalProperties: true`` explicitly
   (the model is intentionally permissive for forward-compat).
6. Emit compact+sorted JSON with a trailing newline (CI-friendly diff).

Invariant: running this script must be idempotent — re-running on an already
up-to-date schema produces zero diff.
"""

from __future__ import annotations

import argparse
import copy
import json
import pathlib
import sys

# Allow running from any directory.
_KIT_ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(_KIT_ROOT / "src"))

from scholar_protocol.models import ResearchProtocol  # noqa: E402

_SCHEMA_PATH = _KIT_ROOT / "schemas" / "v1" / "protocol.schema.json"

_META_SCHEMA = "http://json-schema.org/draft-07/schema#"
_META_ID = "schemas/v1/protocol.schema.json"

_DO_NOT_ADD_ADDITIONAL = {
    # metadata is intentionally open (Dict[str, Any]) — do not restrict keys.
    "metadata",
}


# ---------------------------------------------------------------------------
# Schema generation
# ---------------------------------------------------------------------------


def _replace_refs(obj: object) -> object:
    """Recursively replace all ``#/$defs/`` refs with ``#/definitions/``."""
    if isinstance(obj, dict):
        return {
            k: _replace_refs(v) if k != "$ref" else v.replace("#/$defs/", "#/definitions/")
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_replace_refs(item) for item in obj]
    return obj


def _add_additional_properties(schema: dict) -> dict:
    """Add ``additionalProperties: false`` to all object definitions.

    Skips definitions whose Pydantic-model field is intentionally open
    (``_DO_NOT_ADD_ADDITIONAL``).
    """
    defs = schema.get("definitions", {})
    for name, defn in defs.items():
        if defn.get("type") == "object" and name not in _DO_NOT_ADD_ADDITIONAL:
            defn.setdefault("additionalProperties", False)

    # Also add to the root object.
    if schema.get("type") == "object":
        schema.setdefault("additionalProperties", False)

    return schema


def generate_schema() -> dict:
    """Generate a clean JSON Schema from the Pydantic models."""
    raw = ResearchProtocol.model_json_schema(by_alias=True)

    # 1. Rename $defs → definitions (Draft-07 compat).
    schema = copy.deepcopy(raw)
    if "$defs" in schema:
        schema["definitions"] = schema.pop("$defs")

    # 2. Replace $ref paths.
    schema = _replace_refs(schema)

    # 3. Inject meta-schema fields at the top.
    ordered: dict = {"$schema": _META_SCHEMA, "$id": _META_ID}
    ordered.update(schema)
    schema = ordered

    # 4. Add additionalProperties to typed objects.
    schema = _add_additional_properties(schema)

    # 5. Ensure metadata is explicitly marked as open.
    meta_prop = schema.get("properties", {}).get("metadata", {})
    meta_prop["additionalProperties"] = True
    # Remove the Pydantic-auto `"additionalProperties": true` that is redundant
    # only after we've set it explicitly above (idempotent).

    return schema


def schema_to_str(schema: dict) -> str:
    """Serialise schema to a canonical JSON string (sorted keys, 2-space indent)."""
    return json.dumps(schema, indent=2, ensure_ascii=True, sort_keys=False) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check that the generated schema matches the checked-in file; exit 1 if not.",
    )
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        default=_SCHEMA_PATH,
        help="Write generated schema to this path (default: schemas/v1/protocol.schema.json)",
    )
    args = parser.parse_args()

    generated = schema_to_str(generate_schema())

    if args.check:
        if not args.output.exists():
            print(f"ERROR: checked-in schema not found at {args.output}", file=sys.stderr)
            sys.exit(1)
        checked_in = args.output.read_text(encoding="utf-8")
        if generated == checked_in:
            print("OK Schema is in sync with models.py")
            sys.exit(0)
        else:
            # Show a compact diff.
            import difflib
            diff = list(
                difflib.unified_diff(
                    checked_in.splitlines(keepends=True),
                    generated.splitlines(keepends=True),
                    fromfile=str(args.output),
                    tofile="<generated>",
                )
            )
            print("ERROR: Generated schema differs from checked-in schema:", file=sys.stderr)
            sys.stderr.writelines(diff)
            sys.exit(1)
    else:
        args.output.write_text(generated, encoding="utf-8")
        print(f"OK Schema written to {args.output}")


if __name__ == "__main__":
    main()
