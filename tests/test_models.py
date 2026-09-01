"""Tests for Pydantic model parsing, enum validation, bounds, and defaults."""

from __future__ import annotations

import json
import pathlib

import pytest

from scholar_protocol.models import (
    DimensionDataType,
    EpistemologicalParadigm,
    MatrixDimension,
    PlaybookType,
    ResearchProtocol,
    VerificationConfig,
)

# ---------------------------------------------------------------------------
# Fixtures root
# ---------------------------------------------------------------------------

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
VALID_DIR = FIXTURES / "valid"
INVALID_DIR = FIXTURES / "invalid"
CANONICAL_DIR = FIXTURES / "canonical"


def _load(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Golden valid fixtures parse without error
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
def test_valid_fixtures_parse(fixture_name: str) -> None:
    """All valid golden fixtures must be parseable into ResearchProtocol."""
    raw = _load(VALID_DIR / fixture_name)
    protocol = ResearchProtocol.model_validate(raw)
    assert protocol.protocol_id is not None


# ---------------------------------------------------------------------------
# Enum rejection
# ---------------------------------------------------------------------------


def test_bad_paradigm_enum_rejected() -> None:
    """Unknown EpistemologicalParadigm value must raise ValidationError."""
    from pydantic import ValidationError

    raw = _load(INVALID_DIR / "enum_bad_paradigm.json")
    with pytest.raises(ValidationError):
        ResearchProtocol.model_validate(raw)


def test_playbook_enum_accepts_all_valid_values() -> None:
    """All PlaybookType members must parse from their string value."""
    for member in PlaybookType:
        assert PlaybookType(member.value) == member


def test_paradigm_enum_accepts_all_valid_values() -> None:
    """All EpistemologicalParadigm members must parse from their string value."""
    for member in EpistemologicalParadigm:
        assert EpistemologicalParadigm(member.value) == member


def test_dimension_data_type_enum() -> None:
    """All DimensionDataType members must parse."""
    for member in DimensionDataType:
        assert DimensionDataType(member.value) == member


# ---------------------------------------------------------------------------
# min_length rejections
# ---------------------------------------------------------------------------


def test_empty_criteria_rejected() -> None:
    """Empty inclusion or exclusion list must raise ValidationError."""
    from pydantic import ValidationError

    raw = _load(INVALID_DIR / "empty_criteria.json")
    with pytest.raises(ValidationError):
        ResearchProtocol.model_validate(raw)


def test_empty_research_questions_rejected() -> None:
    """Empty research_questions list must raise ValidationError."""
    from pydantic import ValidationError

    base = _load(VALID_DIR / "design_science_min.json")
    base["research_questions"] = []
    with pytest.raises(ValidationError):
        ResearchProtocol.model_validate(base)


def test_empty_core_concepts_rejected() -> None:
    """Empty core_concepts list must raise ValidationError."""
    from pydantic import ValidationError

    base = _load(VALID_DIR / "design_science_min.json")
    base["search_strategy"]["core_concepts"] = []
    with pytest.raises(ValidationError):
        ResearchProtocol.model_validate(base)


# ---------------------------------------------------------------------------
# Bounds
# ---------------------------------------------------------------------------


def test_threshold_oob_rejected() -> None:
    """Trust threshold > 10.0 must raise ValidationError."""
    from pydantic import ValidationError

    raw = _load(INVALID_DIR / "threshold_oob.json")
    with pytest.raises(ValidationError):
        ResearchProtocol.model_validate(raw)


def test_threshold_negative_rejected() -> None:
    """Trust threshold < 0.0 must raise ValidationError."""
    from pydantic import ValidationError

    base = _load(VALID_DIR / "design_science_min.json")
    base["verification"]["minimum_trust_score_threshold"] = -1.0
    with pytest.raises(ValidationError):
        ResearchProtocol.model_validate(base)


def test_threshold_boundary_values_accepted() -> None:
    """Trust threshold == 0.0 and == 10.0 are both valid."""
    base = _load(VALID_DIR / "design_science_min.json")
    for boundary in [0.0, 10.0]:
        base["verification"]["minimum_trust_score_threshold"] = boundary
        p = ResearchProtocol.model_validate(base)
        assert p.verification.minimum_trust_score_threshold == boundary


# ---------------------------------------------------------------------------
# Defaults materialise correctly
# ---------------------------------------------------------------------------


def test_matrix_dimensions_default_empty() -> None:
    """matrix_dimensions defaults to [] when omitted."""
    base = _load(VALID_DIR / "design_science_min.json")
    base.pop("matrix_dimensions", None)
    p = ResearchProtocol.model_validate(base)
    assert p.matrix_dimensions == []


def test_verification_default_factory() -> None:
    """verification defaults to a VerificationConfig with sensible values."""
    base = _load(VALID_DIR / "design_science_min.json")
    base.pop("verification", None)
    p = ResearchProtocol.model_validate(base)
    assert p.verification.retraction_check_required is True
    assert p.verification.minimum_trust_score_threshold == 5.0


def test_dimension_defaults() -> None:
    """MatrixDimension defaults: data_type=FREE_TEXT, required=False, fallback='Not Reported'."""
    dim = MatrixDimension(id="x", name="X", description="desc")
    assert dim.data_type == DimensionDataType.FREE_TEXT
    assert dim.required is False
    assert dim.fallback_value == "Not Reported"
    assert dim.target_section_category is None


def test_synthesis_type_default() -> None:
    """ResearchQuestion.synthesis_type defaults to 'Comparative Matrix'."""
    base = _load(VALID_DIR / "design_science_min.json")
    # Remove synthesis_type from RQ1
    del base["research_questions"][0]["synthesis_type"]
    p = ResearchProtocol.model_validate(base)
    assert p.research_questions[0].synthesis_type == "Comparative Matrix"


# ---------------------------------------------------------------------------
# Optional fields
# ---------------------------------------------------------------------------


def test_secondary_paradigm_null() -> None:
    """secondary_paradigm=null is accepted."""
    base = _load(VALID_DIR / "design_science_min.json")
    base["epistemology"]["secondary_paradigm"] = None
    p = ResearchProtocol.model_validate(base)
    assert p.epistemology.secondary_paradigm is None


def test_secondary_paradigm_valid_value() -> None:
    """secondary_paradigm with a valid enum value is accepted."""
    base = _load(VALID_DIR / "design_science_min.json")
    base["epistemology"]["secondary_paradigm"] = "Positivist"
    p = ResearchProtocol.model_validate(base)
    assert p.epistemology.secondary_paradigm == EpistemologicalParadigm.POSITIVIST
