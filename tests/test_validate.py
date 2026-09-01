"""Tests for the validate_protocol function and error/warning taxonomy."""

from __future__ import annotations

import json
import pathlib
import tempfile

import pytest

from scholar_protocol.validate import validate_protocol

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
VALID_DIR = FIXTURES / "valid"
INVALID_DIR = FIXTURES / "invalid"
CANONICAL_DIR = FIXTURES / "canonical"


def _write_tmp(data: dict) -> pathlib.Path:
    """Write a dict as JSON to a temp file and return the path."""
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    )
    json.dump(data, f, ensure_ascii=True)
    f.close()
    return pathlib.Path(f.name)


def _load(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Golden valid fixtures — no errors
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture_name",
    [
        "design_science_min.json",
        "prisma_slr_full.json",
        "interpretivist_min.json",
    ],
)
def test_valid_golden_fixtures_pass(fixture_name: str) -> None:
    """Golden valid fixtures must produce ValidationReport with no errors."""
    report = validate_protocol(VALID_DIR / fixture_name)
    error_codes = [f.code for f in report.errors]
    assert report.is_valid, (
        f"{fixture_name} should be valid but got errors: {error_codes}\n"
        f"Full findings: {report.findings}"
    )


def test_scoping_empty_matrix_valid_with_warning() -> None:
    """scoping_empty_matrix.json is valid but must produce WARN_NO_MATRIX_DIMS warning."""
    report = validate_protocol(VALID_DIR / "scoping_empty_matrix.json")
    assert report.is_valid, f"Unexpected errors: {report.errors}"
    warning_codes = [f.code for f in report.warnings]
    assert "WARN_NO_MATRIX_DIMS" in warning_codes, (
        f"Expected WARN_NO_MATRIX_DIMS in warnings, got: {warning_codes}"
    )


# ---------------------------------------------------------------------------
# Invalid fixtures — specific error codes
# ---------------------------------------------------------------------------


def test_enum_bad_paradigm_gives_structural_error() -> None:
    """enum_bad_paradigm.json must produce a STRUCTURAL error."""
    report = validate_protocol(INVALID_DIR / "enum_bad_paradigm.json")
    assert not report.is_valid
    error_codes = [f.code for f in report.errors]
    assert "STRUCTURAL" in error_codes, f"Expected STRUCTURAL, got: {error_codes}"


def test_bad_rq_ref_gives_cross_field_error() -> None:
    """bad_rq_ref.json must produce a CROSS_FIELD_RQ_REF error."""
    report = validate_protocol(INVALID_DIR / "bad_rq_ref.json")
    assert not report.is_valid
    error_codes = [f.code for f in report.errors]
    assert "CROSS_FIELD_RQ_REF" in error_codes, (
        f"Expected CROSS_FIELD_RQ_REF, got: {error_codes}"
    )


def test_empty_criteria_gives_structural_error() -> None:
    """empty_criteria.json must produce a STRUCTURAL error for min_length."""
    report = validate_protocol(INVALID_DIR / "empty_criteria.json")
    assert not report.is_valid
    error_codes = [f.code for f in report.errors]
    assert "STRUCTURAL" in error_codes, f"Expected STRUCTURAL, got: {error_codes}"


def test_threshold_oob_gives_structural_error() -> None:
    """threshold_oob.json must produce a STRUCTURAL error for bounds violation."""
    report = validate_protocol(INVALID_DIR / "threshold_oob.json")
    assert not report.is_valid
    error_codes = [f.code for f in report.errors]
    assert "STRUCTURAL" in error_codes, f"Expected STRUCTURAL, got: {error_codes}"


# ---------------------------------------------------------------------------
# Cross-field rules — synthetic cases
# ---------------------------------------------------------------------------


def test_duplicate_rq_ids_gives_error() -> None:
    """Two RQs with the same id must produce DUPLICATE_RQ_ID."""
    base = _load(VALID_DIR / "design_science_min.json")
    base["research_questions"].append(base["research_questions"][0].copy())
    tmp = _write_tmp(base)
    report = validate_protocol(tmp)
    assert not report.is_valid
    error_codes = [f.code for f in report.errors]
    assert "DUPLICATE_RQ_ID" in error_codes


def test_duplicate_criterion_ids_gives_error() -> None:
    """Duplicate criterion ids across inclusion+exclusion must produce DUPLICATE_CRITERION_ID."""
    base = _load(VALID_DIR / "design_science_min.json")
    # Make EXC-01 use the same id as INC-01.
    base["screening_criteria"]["exclusion"][0]["id"] = "INC-01"
    tmp = _write_tmp(base)
    report = validate_protocol(tmp)
    assert not report.is_valid
    error_codes = [f.code for f in report.errors]
    assert "DUPLICATE_CRITERION_ID" in error_codes


def test_duplicate_dimension_ids_gives_error() -> None:
    """Two MatrixDimensions with the same id must produce DUPLICATE_DIMENSION_ID."""
    base = _load(VALID_DIR / "prisma_slr_full.json")
    base["matrix_dimensions"].append(base["matrix_dimensions"][0].copy())
    tmp = _write_tmp(base)
    report = validate_protocol(tmp)
    assert not report.is_valid
    error_codes = [f.code for f in report.errors]
    assert "DUPLICATE_DIMENSION_ID" in error_codes


def test_date_range_incoherent_start_gt_end() -> None:
    """start_year > end_year must produce DATE_RANGE_INCOHERENT."""
    base = _load(VALID_DIR / "design_science_min.json")
    base["search_strategy"]["date_range"]["start_year"] = 2027
    base["search_strategy"]["date_range"]["end_year"] = 2020
    tmp = _write_tmp(base)
    report = validate_protocol(tmp)
    assert not report.is_valid
    error_codes = [f.code for f in report.errors]
    assert "DATE_RANGE_INCOHERENT" in error_codes


def test_pool_size_min_gt_max() -> None:
    """target_candidate_pool_size min > max must produce POOL_SIZE_INCOHERENT."""
    base = _load(VALID_DIR / "design_science_min.json")
    base["search_strategy"]["target_candidate_pool_size"] = {"min": 1000, "max": 100}
    tmp = _write_tmp(base)
    report = validate_protocol(tmp)
    assert not report.is_valid
    error_codes = [f.code for f in report.errors]
    assert "POOL_SIZE_INCOHERENT" in error_codes


def test_empty_languages_gives_error() -> None:
    """Empty languages list must produce LANGUAGES_EMPTY."""
    base = _load(VALID_DIR / "design_science_min.json")
    base["search_strategy"]["languages"] = []
    tmp = _write_tmp(base)
    report = validate_protocol(tmp)
    assert not report.is_valid
    error_codes = [f.code for f in report.errors]
    assert "LANGUAGES_EMPTY" in error_codes


# ---------------------------------------------------------------------------
# Warnings
# ---------------------------------------------------------------------------


def test_warn_short_rationale() -> None:
    """A rationale shorter than 20 chars must produce WARN_SHORT_RATIONALE."""
    base = _load(VALID_DIR / "design_science_min.json")
    base["epistemology"]["epistemological_rationale"] = "Short."
    tmp = _write_tmp(base)
    report = validate_protocol(tmp)
    assert report.is_valid  # still valid — warnings don't fail
    warning_codes = [f.code for f in report.warnings]
    assert "WARN_SHORT_RATIONALE" in warning_codes


def test_warn_paradigm_playbook_mismatch() -> None:
    """PRISMA_SLR with Design Science paradigm should produce WARN_PARADIGM_PLAYBOOK."""
    base = _load(VALID_DIR / "design_science_min.json")
    base["playbook_type"] = "PRISMA_SLR"
    base["epistemology"]["primary_paradigm"] = "Design Science"
    tmp = _write_tmp(base)
    report = validate_protocol(tmp)
    assert report.is_valid  # warning only
    warning_codes = [f.code for f in report.warnings]
    assert "WARN_PARADIGM_PLAYBOOK" in warning_codes


def test_warn_verification_all_flags_off() -> None:
    """All verification flags off must produce WARN_VERIFICATION_FLAGS."""
    base = _load(VALID_DIR / "design_science_min.json")
    v = base["verification"]
    v["retraction_check_required"] = False
    v["coi_and_funding_audit_required"] = False
    v["reproducibility_das_cas_check"] = False
    tmp = _write_tmp(base)
    report = validate_protocol(tmp)
    assert report.is_valid
    warning_codes = [f.code for f in report.warnings]
    assert "WARN_VERIFICATION_FLAGS" in warning_codes


# ---------------------------------------------------------------------------
# is_valid_strict
# ---------------------------------------------------------------------------


def test_strict_mode_with_warnings_fails() -> None:
    """A protocol with warnings only must fail is_valid_strict()."""
    base = _load(VALID_DIR / "scoping_empty_matrix.json")  # has WARN_NO_MATRIX_DIMS
    tmp = _write_tmp(base)
    report = validate_protocol(tmp)
    assert report.is_valid             # passes normal validation
    assert not report.is_valid_strict()  # fails strict


# ---------------------------------------------------------------------------
# ValidationReport path
# ---------------------------------------------------------------------------


def test_report_path_matches_input() -> None:
    """ValidationReport.path must match the path argument."""
    p = VALID_DIR / "design_science_min.json"
    report = validate_protocol(p)
    assert report.path == str(p)


# ---------------------------------------------------------------------------
# File not found / bad JSON
# ---------------------------------------------------------------------------


def test_nonexistent_file_gives_structural_error() -> None:
    """A non-existent file must produce a STRUCTURAL error."""
    report = validate_protocol("/tmp/this-file-does-not-exist-xyz.json")
    assert not report.is_valid
    assert any(f.code == "STRUCTURAL" for f in report.errors)


def test_bad_json_gives_structural_error() -> None:
    """Malformed JSON must produce a STRUCTURAL error."""
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    )
    f.write("{not valid json")
    f.close()
    report = validate_protocol(f.name)
    assert not report.is_valid
    assert any(f.code == "STRUCTURAL" for f in report.errors)
