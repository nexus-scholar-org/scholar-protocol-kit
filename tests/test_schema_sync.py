"""CI guard: the checked-in JSON Schema must be in sync with models.py.

This test is the enforcement for the invariant stated in models.py:
    "The checked-in JSON Schema at schemas/v1/protocol.schema.json is derived
    from these models and kept in sync by CI."

How it works
------------
1. Generate the expected schema from the live Pydantic models using the
   same post-processing pipeline as scripts/generate_schema.py.
2. Load the checked-in schemas/v1/protocol.schema.json.
3. Assert they are identical (string-equal after canonical serialization).

If the test fails, regenerate with:
    python scripts/generate_schema.py

Why this matters
----------------
The models.py is the sole runtime authority; the JSON Schema is a static
artefact used by IDE validators, CI linters, and external consumers.
Without this test, the two can silently drift — exactly the bug Reviewer 1
identified in the Cycle A delivery.

Invariant: any change to models.py that changes the schema surface
(new field, new enum value, changed bounds, new required field) will cause
this test to fail and force the developer to regenerate and check in the
updated schema.
"""

from __future__ import annotations

import json
import pathlib
import sys

import pytest

# Resolve the generate_schema module without requiring it to be installed.
_KIT_ROOT = pathlib.Path(__file__).parent.parent
_SCRIPTS = _KIT_ROOT / "scripts"
sys.path.insert(0, str(_SCRIPTS))

from generate_schema import generate_schema, schema_to_str  # noqa: E402

_CHECKED_IN = _KIT_ROOT / "schemas" / "v1" / "protocol.schema.json"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_checked_in_schema_exists() -> None:
    """The checked-in schema file must exist."""
    assert _CHECKED_IN.exists(), (
        f"Checked-in schema not found at {_CHECKED_IN}. "
        "Run: python scripts/generate_schema.py"
    )


def test_schema_in_sync_with_models() -> None:
    """Generated schema must be byte-identical to the checked-in schema.

    If this test fails, regenerate the schema:
        python scripts/generate_schema.py

    Then review the diff, update CHANGELOG if the change is intentional,
    and commit the updated schema alongside the models.py change.
    """
    generated = schema_to_str(generate_schema())
    checked_in = _CHECKED_IN.read_text(encoding="utf-8")

    if generated != checked_in:
        # Produce a human-readable diff to help debug the failure.
        import difflib

        diff = "\n".join(
            difflib.unified_diff(
                checked_in.splitlines(),
                generated.splitlines(),
                fromfile=str(_CHECKED_IN.relative_to(_KIT_ROOT)),
                tofile="<generated from models.py>",
                lineterm="",
            )
        )
        pytest.fail(
            "models.py and schemas/v1/protocol.schema.json have drifted.\n"
            "Regenerate with: python scripts/generate_schema.py\n\n"
            f"Diff:\n{diff}"
        )


def test_schema_is_valid_json() -> None:
    """The checked-in schema must be valid JSON."""
    raw = _CHECKED_IN.read_text(encoding="utf-8")
    schema = json.loads(raw)
    assert isinstance(schema, dict)
    assert "$schema" in schema


def test_schema_contains_all_required_fields() -> None:
    """The generated schema must declare the correct required fields."""
    schema = generate_schema()
    required = set(schema.get("required", []))
    # These are the fields without a default — they must always be in required.
    must_be_required = {
        "protocol_id",
        "project_slug",
        "playbook_type",
        "epistemology",
        "research_questions",
        "search_strategy",
        "screening_criteria",
    }
    missing = must_be_required - required
    assert not missing, (
        f"Fields {missing} should be in 'required' but are not. "
        "Check models.py for unintended defaults."
    )


def test_schema_enum_values_match_models() -> None:
    """Enum values in the schema must match the Pydantic model enum members."""
    from scholar_protocol.models import (
        DimensionDataType,
        EpistemologicalParadigm,
        PlaybookType,
    )

    schema = generate_schema()
    defs = schema.get("definitions", {})

    # PlaybookType
    pt_values = set(defs["PlaybookType"]["enum"])
    expected_pt = {m.value for m in PlaybookType}
    assert pt_values == expected_pt, (
        f"PlaybookType enum mismatch.\nSchema: {pt_values}\nModels: {expected_pt}"
    )

    # EpistemologicalParadigm
    ep_values = set(defs["EpistemologicalParadigm"]["enum"])
    expected_ep = {m.value for m in EpistemologicalParadigm}
    assert ep_values == expected_ep, (
        f"EpistemologicalParadigm enum mismatch.\nSchema: {ep_values}\nModels: {expected_ep}"
    )

    # DimensionDataType
    dt_values = set(defs["DimensionDataType"]["enum"])
    expected_dt = {m.value for m in DimensionDataType}
    assert dt_values == expected_dt, (
        f"DimensionDataType enum mismatch.\nSchema: {dt_values}\nModels: {expected_dt}"
    )


def test_schema_trust_score_bounds_match_models() -> None:
    """minimum_trust_score_threshold bounds must match the Pydantic model (0.0-10.0)."""
    schema = generate_schema()
    defs = schema.get("definitions", {})
    vc_props = defs["VerificationConfig"]["properties"]
    threshold = vc_props["minimum_trust_score_threshold"]
    assert threshold["minimum"] == 0.0, f"Expected minimum=0.0, got {threshold['minimum']}"
    assert threshold["maximum"] == 10.0, f"Expected maximum=10.0, got {threshold['maximum']}"


def test_schema_metadata_is_open() -> None:
    """metadata must have additionalProperties: true (intentionally open dict)."""
    schema = generate_schema()
    meta = schema["properties"]["metadata"]
    assert meta.get("additionalProperties") is True, (
        "metadata must be open (additionalProperties: true) since the model is Dict[str, Any]. "
        "If you want to restrict it, add a typed MetadataConfig model instead."
    )


def test_generate_schema_is_idempotent() -> None:
    """Running generate_schema() twice must produce identical output."""
    s1 = schema_to_str(generate_schema())
    s2 = schema_to_str(generate_schema())
    assert s1 == s2, "generate_schema() is not idempotent — fix the generator."
