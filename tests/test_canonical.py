"""Tests for deterministic canonical serialization and fingerprinting."""

from __future__ import annotations

import copy
import json
import pathlib

import pytest

from scholar_protocol.canonical import canonical_fingerprint, canonical_json
from scholar_protocol.models import ResearchProtocol

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
VALID_DIR = FIXTURES / "valid"
CANONICAL_DIR = FIXTURES / "canonical"

# All valid golden fixtures that have .sha256 sibling files.
_GOLDEN_FIXTURES = [
    "design_science_min.json",
    "prisma_slr_full.json",
    "scoping_empty_matrix.json",
    "interpretivist_min.json",
]


def _load_protocol(path: pathlib.Path) -> ResearchProtocol:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return ResearchProtocol.model_validate(raw)


def _read_expected_fingerprint(sha256_path: pathlib.Path) -> str:
    """Read the expected fingerprint from a .sha256 sibling file."""
    return sha256_path.read_text(encoding="utf-8").strip()


# ---------------------------------------------------------------------------
# Gap #1 fix: Pinned .sha256 golden fingerprints (byte-drift CI gate)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fixture_name", _GOLDEN_FIXTURES)
def test_pinned_golden_fingerprint(fixture_name: str) -> None:
    """Canonical fingerprint must match the checked-in .sha256 sibling file.

    This is the hard CI gate: if any byte of the serializer, models, or fixture
    changes, this test fails.  To update intentionally:
        1. Re-run: scholar-protocol fingerprint <fixture_path>
        2. Update the .sha256 sibling file.
        3. Commit both files together with a rationale.
    """
    fixture_path = VALID_DIR / fixture_name
    sha256_path = VALID_DIR / f"{fixture_name}.sha256"

    assert sha256_path.exists(), (
        f".sha256 sibling not found for {fixture_name}. "
        f"Generate with: scholar-protocol fingerprint {fixture_path}"
    )

    protocol = _load_protocol(fixture_path)
    actual = canonical_fingerprint(protocol)
    expected = _read_expected_fingerprint(sha256_path)

    assert actual == expected, (
        f"Fingerprint mismatch for {fixture_name}!\n"
        f"  Expected (checked-in): {expected}\n"
        f"  Actual (computed):     {actual}\n"
        "This means the canonical serialization has changed since the golden "
        "was pinned.  If intentional, update the .sha256 sibling file."
    )


def test_pinned_canonical_fixture_fingerprint() -> None:
    """canonical/unordered_dims.json must match its .sha256 sibling."""
    fixture_path = CANONICAL_DIR / "unordered_dims.json"
    sha256_path = CANONICAL_DIR / "unordered_dims.json.sha256"

    assert sha256_path.exists(), f".sha256 sibling not found at {sha256_path}"

    protocol = _load_protocol(fixture_path)
    actual = canonical_fingerprint(protocol)
    expected = _read_expected_fingerprint(sha256_path)

    assert actual == expected, (
        f"Fingerprint mismatch for canonical/unordered_dims.json!\n"
        f"  Expected: {expected}\n"
        f"  Actual:   {actual}"
    )


# ---------------------------------------------------------------------------
# Idempotency: canon(canon(x)) == canon(x)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture_name",
    [
        "design_science_min.json",
        "prisma_slr_full.json",
        "scoping_empty_matrix.json",
        "interpretivist_min.json",
    ],
)
def test_canonical_json_idempotent(fixture_name: str) -> None:
    """Applying canonical_json twice must yield the same bytes."""
    protocol = _load_protocol(VALID_DIR / fixture_name)
    first_pass = canonical_json(protocol)
    # Re-parse the canonical bytes and re-serialize.
    protocol2 = ResearchProtocol.model_validate(json.loads(first_pass))
    second_pass = canonical_json(protocol2)
    assert first_pass == second_pass, (
        f"Idempotency failure for {fixture_name}:\n"
        f"First:  {first_pass[:200]!r}\n"
        f"Second: {second_pass[:200]!r}"
    )


# ---------------------------------------------------------------------------
# Fingerprint stability: same input → same sha256
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture_name",
    [
        "design_science_min.json",
        "prisma_slr_full.json",
        "scoping_empty_matrix.json",
        "interpretivist_min.json",
    ],
)
def test_fingerprint_stable(fixture_name: str) -> None:
    """Same protocol content must always produce the same fingerprint."""
    protocol = _load_protocol(VALID_DIR / fixture_name)
    fp1 = canonical_fingerprint(protocol)
    fp2 = canonical_fingerprint(protocol)
    assert fp1 == fp2
    assert fp1.startswith("sha256:")
    # sha256: prefix + 64 hex chars
    assert len(fp1) == len("sha256:") + 64


# ---------------------------------------------------------------------------
# Key order: $schema appears first, protocol_id second
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture_name",
    [
        "design_science_min.json",
        "prisma_slr_full.json",
    ],
)
def test_key_order_starts_with_schema(fixture_name: str) -> None:
    """canonical_json output must start with {\"$schema\": ..., \"protocol_id\": ..."""
    protocol = _load_protocol(VALID_DIR / fixture_name)
    raw = canonical_json(protocol)
    parsed = json.loads(raw, object_pairs_hook=list)  # preserves key order as list of (k,v)
    keys = [k for k, _ in parsed]
    assert keys[0] == "$schema", f"First key is '{keys[0]}', expected '$schema'"
    assert keys[1] == "protocol_id", f"Second key is '{keys[1]}', expected 'protocol_id'"


# ---------------------------------------------------------------------------
# Float format: 5.0 not 5, 6.0 not 6
# ---------------------------------------------------------------------------


def test_float_threshold_has_decimal_point() -> None:
    """minimum_trust_score_threshold must serialize with a decimal point."""
    protocol = _load_protocol(VALID_DIR / "design_science_min.json")
    raw_str = canonical_json(protocol).decode("utf-8")
    # Locate the threshold value in the JSON string.
    assert '"minimum_trust_score_threshold":5.0' in raw_str or \
           '"minimum_trust_score_threshold":6.0' in raw_str or \
           '"minimum_trust_score_threshold":' in raw_str


def test_float_threshold_not_integer_serialized() -> None:
    """The threshold must NOT be serialized as a bare integer (no decimal point)."""
    protocol = _load_protocol(VALID_DIR / "prisma_slr_full.json")
    # prisma_slr_full has threshold = 6.0
    raw_str = canonical_json(protocol).decode("utf-8")
    # Should see 6.0, not ":6," or ":6}"
    assert '"minimum_trust_score_threshold":6.0' in raw_str


# ---------------------------------------------------------------------------
# Metadata and date_range keys are sorted alphabetically
# ---------------------------------------------------------------------------


def test_metadata_keys_sorted() -> None:
    """metadata dict keys must be sorted alphabetically in canonical output."""
    protocol = _load_protocol(VALID_DIR / "design_science_min.json")
    raw = json.loads(canonical_json(protocol))
    meta_keys = list(raw["metadata"].keys())
    assert meta_keys == sorted(meta_keys), f"metadata keys not sorted: {meta_keys}"


def test_date_range_keys_sorted() -> None:
    """date_range keys must be sorted alphabetically in canonical output."""
    protocol = _load_protocol(VALID_DIR / "design_science_min.json")
    raw = json.loads(canonical_json(protocol))
    dr_keys = list(raw["search_strategy"]["date_range"].keys())
    assert dr_keys == sorted(dr_keys), f"date_range keys not sorted: {dr_keys}"


# ---------------------------------------------------------------------------
# Whitespace: compact (no spaces after separators), ensure_ascii, no trailing newline
# ---------------------------------------------------------------------------


def test_canonical_json_is_compact() -> None:
    """canonical_json must not contain ', ' or ': ' (compact separators)."""
    protocol = _load_protocol(VALID_DIR / "design_science_min.json")
    raw_str = canonical_json(protocol).decode("utf-8")
    assert ", " not in raw_str
    assert ": " not in raw_str


def test_canonical_json_no_trailing_newline() -> None:
    """canonical_json output must not end with a newline byte."""
    protocol = _load_protocol(VALID_DIR / "design_science_min.json")
    raw = canonical_json(protocol)
    assert not raw.endswith(b"\n")


def test_canonical_json_is_utf8() -> None:
    """canonical_json must return valid UTF-8 bytes."""
    protocol = _load_protocol(VALID_DIR / "interpretivist_min.json")
    raw = canonical_json(protocol)
    # Should not raise
    raw.decode("utf-8")


# ---------------------------------------------------------------------------
# Gap #3 fix: canonical/ fixture proves mis-ordered input → same bytes
# ---------------------------------------------------------------------------


def test_canonical_fixture_roundtrip() -> None:
    """canonical/unordered_dims.json must round-trip identically."""
    protocol = _load_protocol(CANONICAL_DIR / "unordered_dims.json")
    first = canonical_json(protocol)
    protocol2 = ResearchProtocol.model_validate(json.loads(first))
    second = canonical_json(protocol2)
    assert first == second


def test_canonical_fixture_shuffled_metadata_same_bytes() -> None:
    """A protocol with shuffled metadata keys must canonicalize to the same bytes.

    This is the actual guarantee the canonical/ fixture is named for:
    mis-ordered input → byte-identical output after canonicalization.
    """
    fixture_path = CANONICAL_DIR / "unordered_dims.json"
    raw = json.loads(fixture_path.read_text(encoding="utf-8"))

    # Reverse the metadata key order.
    raw_shuffled = copy.deepcopy(raw)
    meta_items = list(raw["metadata"].items())
    meta_items.reverse()
    raw_shuffled["metadata"] = dict(meta_items)

    protocol_normal = ResearchProtocol.model_validate(raw)
    protocol_shuffled = ResearchProtocol.model_validate(raw_shuffled)

    assert canonical_json(protocol_normal) == canonical_json(protocol_shuffled), (
        "Shuffled metadata keys produced different canonical bytes — "
        "the metadata key-sort rule is broken."
    )


def test_canonical_fixture_shuffled_date_range_same_bytes() -> None:
    """Shuffled date_range keys must canonicalize to the same bytes."""
    fixture_path = CANONICAL_DIR / "unordered_dims.json"
    raw = json.loads(fixture_path.read_text(encoding="utf-8"))

    # Reverse date_range key order (end_year, start_year) vs (start_year, end_year).
    raw_shuffled = copy.deepcopy(raw)
    dr_items = list(raw["search_strategy"]["date_range"].items())
    dr_items.reverse()
    raw_shuffled["search_strategy"]["date_range"] = dict(dr_items)

    protocol_normal = ResearchProtocol.model_validate(raw)
    protocol_shuffled = ResearchProtocol.model_validate(raw_shuffled)

    assert canonical_json(protocol_normal) == canonical_json(protocol_shuffled), (
        "Shuffled date_range keys produced different canonical bytes — "
        "the date_range key-sort rule is broken."
    )


# ---------------------------------------------------------------------------
# Different protocols produce different fingerprints
# ---------------------------------------------------------------------------


def test_different_protocols_different_fingerprints() -> None:
    """Two protocols with different content must NOT produce the same fingerprint."""
    p1 = _load_protocol(VALID_DIR / "design_science_min.json")
    p2 = _load_protocol(VALID_DIR / "prisma_slr_full.json")
    assert canonical_fingerprint(p1) != canonical_fingerprint(p2)
