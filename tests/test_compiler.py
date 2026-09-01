"""Cycle B conformance tests: compile_protocol(intent) fingerprint == golden sha256.

This test file is the hard proof that the deterministic compiler and the
hand-authored golden protocol.json fixtures are consistent.

Each parametrized test loads an intent packet from ``tests/fixtures/intents/``,
compiles it into a ``ResearchProtocol``, and asserts that its canonical
fingerprint matches the checked-in ``.sha256`` sibling of the corresponding
golden fixture in ``tests/fixtures/valid/``.

If any test fails it means one of:
  1. The compiler has a bug (most likely during initial Cycle B development).
  2. The intent packet does not faithfully represent the golden fixture.
  3. The canonical serializer changed without updating the .sha256 files.

Conformance gate (the central Cycle B invariant)
-------------------------------------------------
    compile(intent) → ResearchProtocol → canonical_fingerprint
    must equal
    golden .sha256 (checked-in, immutable)

This gate proves: given the same structured intent, the compiler always
produces the same byte-identical protocol.json.  The nondeterministic
Socratic interview is outside this closure; the compiler itself is pure.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from scholar_protocol.canonical import canonical_fingerprint
from scholar_protocol.compiler import compile_protocol
from scholar_protocol.intent import IntentPacket
from scholar_protocol.validate import validate_protocol

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
VALID_DIR = FIXTURES / "valid"
INTENTS_DIR = FIXTURES / "intents"

# Mapping: intent file stem → expected .sha256 sibling in valid/
_CONFORMANCE_PAIRS = [
    ("design_science_min", "design_science_min"),
    ("prisma_slr_full", "prisma_slr_full"),
    ("scoping_empty_matrix", "scoping_empty_matrix"),
    ("interpretivist_min", "interpretivist_min"),
]


def _load_intent(stem: str) -> IntentPacket:
    path = INTENTS_DIR / f"{stem}.intent.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return IntentPacket.model_validate(raw)


def _read_golden_fp(stem: str) -> str:
    return (VALID_DIR / f"{stem}.json.sha256").read_text(encoding="utf-8").strip()


# ---------------------------------------------------------------------------
# Conformance: fingerprint(compile(intent)) == golden sha256
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("intent_stem,golden_stem", _CONFORMANCE_PAIRS)
def test_compiler_conformance_fingerprint(intent_stem: str, golden_stem: str) -> None:
    """The compiled protocol fingerprint must match the checked-in golden hash.

    This is THE Cycle B gate.  Failure means the compiler does not faithfully
    reproduce the golden protocol.json from its corresponding intent packet.
    """
    intent = _load_intent(intent_stem)
    protocol = compile_protocol(intent)
    actual_fp = canonical_fingerprint(protocol)
    expected_fp = _read_golden_fp(golden_stem)
    assert actual_fp == expected_fp, (
        f"Conformance FAILED for intent '{intent_stem}'.\n"
        f"  Expected (golden .sha256): {expected_fp}\n"
        f"  Actual   (compile output): {actual_fp}\n"
        "\nThis means the compiler does not reproduce the golden fixture.\n"
        "Check: intent packet fields, preset values, ID generation, and "
        "any canonical serializer changes."
    )


# ---------------------------------------------------------------------------
# Validation: compiled protocols must pass the validator
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("intent_stem,_", _CONFORMANCE_PAIRS)
def test_compiled_protocol_is_valid(intent_stem: str, _: str) -> None:
    """compile_protocol() must produce a protocol that passes validate_protocol()."""
    intent = _load_intent(intent_stem)
    protocol = compile_protocol(intent)
    # Write to a temp JSON to validate through the file-based validator.
    import json
    import tempfile

    from scholar_protocol.canonical import canonical_json

    with tempfile.NamedTemporaryFile(
        mode="wb", suffix=".json", delete=False
    ) as f:
        f.write(canonical_json(protocol))
        tmp_path = pathlib.Path(f.name)

    try:
        report = validate_protocol(tmp_path)
        assert report.is_valid, (
            f"Compiled protocol for intent '{intent_stem}' failed validation:\n"
            + "\n".join(f"  [{e.code}] {e.message}" for e in report.errors)
        )
    finally:
        tmp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Round-trip: compile → canonical bytes → parse → compile → same fingerprint
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("intent_stem,_", _CONFORMANCE_PAIRS)
def test_compile_is_idempotent(intent_stem: str, _: str) -> None:
    """compile(intent) must be idempotent: two calls produce the same fingerprint."""
    intent = _load_intent(intent_stem)
    fp1 = canonical_fingerprint(compile_protocol(intent))
    fp2 = canonical_fingerprint(compile_protocol(intent))
    assert fp1 == fp2, (
        f"compile_protocol() is not idempotent for intent '{intent_stem}'."
    )


# ---------------------------------------------------------------------------
# Intent validation: all intent packets must parse without error
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("intent_stem,_", _CONFORMANCE_PAIRS)
def test_intent_packet_is_valid(intent_stem: str, _: str) -> None:
    """Every intent fixture must parse into a valid IntentPacket."""
    intent = _load_intent(intent_stem)  # raises ValidationError if invalid
    assert intent.protocol_id
    assert intent.genesis_timestamp
    assert len(intent.research_questions) >= 1
    assert len(intent.inclusion_criteria) >= 1
    assert len(intent.exclusion_criteria) >= 1


# ---------------------------------------------------------------------------
# ID generation: verify correct RQ and criterion IDs
# ---------------------------------------------------------------------------


def test_rq_ids_are_sequential() -> None:
    """Compiled RQ IDs must be RQ1, RQ2, … in declaration order."""
    intent = _load_intent("prisma_slr_full")  # has 3 RQs
    protocol = compile_protocol(intent)
    ids = [rq.id for rq in protocol.research_questions]
    assert ids == ["RQ1", "RQ2", "RQ3"]


def test_criterion_ids_are_sequential() -> None:
    """Compiled criterion IDs must be INC-01… and EXC-01… in declaration order."""
    intent = _load_intent("prisma_slr_full")  # 3 INC, 3 EXC
    protocol = compile_protocol(intent)
    inc_ids = [c.id for c in protocol.screening_criteria.inclusion]
    exc_ids = [c.id for c in protocol.screening_criteria.exclusion]
    assert inc_ids == ["INC-01", "INC-02", "INC-03"]
    assert exc_ids == ["EXC-01", "EXC-02", "EXC-03"]


# ---------------------------------------------------------------------------
# Preset application: verify preset defaults are correctly applied
# ---------------------------------------------------------------------------


def test_preset_databases_applied_when_not_overridden() -> None:
    """design_science_min does not override target_databases → uses preset default."""
    intent = _load_intent("design_science_min")
    protocol = compile_protocol(intent)
    assert protocol.search_strategy.target_databases == [
        "openalex", "semanticscholar", "crossref", "arxiv"
    ]


def test_intent_databases_override_preset() -> None:
    """prisma_slr_full overrides target_databases → not the preset default order."""
    intent = _load_intent("prisma_slr_full")
    protocol = compile_protocol(intent)
    assert protocol.search_strategy.target_databases == [
        "arxiv", "semanticscholar", "crossref", "openalex"
    ]


def test_preset_threshold_applied_for_design_science() -> None:
    """DESIGN_SCIENCE preset threshold is 5.0."""
    intent = _load_intent("design_science_min")
    protocol = compile_protocol(intent)
    assert protocol.verification.minimum_trust_score_threshold == 5.0


def test_preset_threshold_applied_for_prisma() -> None:
    """PRISMA_SLR preset threshold is 6.0."""
    intent = _load_intent("prisma_slr_full")
    protocol = compile_protocol(intent)
    assert protocol.verification.minimum_trust_score_threshold == 6.0


def test_reproducibility_override_applied() -> None:
    """scoping_empty_matrix overrides reproducibility_das_cas_check to False."""
    intent = _load_intent("scoping_empty_matrix")
    protocol = compile_protocol(intent)
    assert protocol.verification.reproducibility_das_cas_check is False


def test_empty_matrix_dimensions() -> None:
    """scoping_empty_matrix intent produces an empty matrix_dimensions list."""
    intent = _load_intent("scoping_empty_matrix")
    protocol = compile_protocol(intent)
    assert protocol.matrix_dimensions == []


def test_interpretivist_paradigm_overrides_scoping_preset() -> None:
    """interpretivist_min uses SCOPING_REVIEW playbook but overrides to Interpretivist."""
    intent = _load_intent("interpretivist_min")
    protocol = compile_protocol(intent)
    from scholar_protocol.models import EpistemologicalParadigm
    assert protocol.epistemology.primary_paradigm == EpistemologicalParadigm.INTERPRETIVIST


def test_pool_size_override() -> None:
    """interpretivist_min overrides pool to min=80, max=600."""
    intent = _load_intent("interpretivist_min")
    protocol = compile_protocol(intent)
    ps = protocol.search_strategy.target_candidate_pool_size
    assert ps["min"] == 80
    assert ps["max"] == 600
