"""Tests for the scholar-protocol CLI exit codes and output."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile

import pytest

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
VALID_DIR = FIXTURES / "valid"
INVALID_DIR = FIXTURES / "invalid"
CANONICAL_DIR = FIXTURES / "canonical"
INTENTS_DIR = FIXTURES / "intents"

# Resolve the installed script or fall back to module invocation.
_SCRIPT = (
    pathlib.Path(sys.executable).parent / "scholar-protocol.exe"
    if sys.platform == "win32"
    else pathlib.Path(sys.executable).parent / "scholar-protocol"
)


def run(*args: str) -> subprocess.CompletedProcess:
    """Run the scholar-protocol CLI as a subprocess.

    Uses the installed entry-point script when available so that
    typer.Exit() propagates the correct exit codes.
    Falls back to module invocation for environments where the script
    has not been installed.
    """
    if _SCRIPT.exists():
        cmd = [str(_SCRIPT), *args]
    else:
        cmd = [sys.executable, "-m", "scholar_protocol.cli", *args]
    return subprocess.run(cmd, capture_output=True, text=True)


_MISSING = str(pathlib.Path(tempfile.gettempdir()) / "scholar_proto_missing_xyz.json")


# ---------------------------------------------------------------------------
# scholar-protocol validate exit codes
# ---------------------------------------------------------------------------


def test_validate_valid_exit_0() -> None:
    """validate on a valid fixture must exit with code 0."""
    result = run("validate", str(VALID_DIR / "design_science_min.json"))
    assert result.returncode == 0, (
        f"Expected exit 0, got {result.returncode}\nstderr: {result.stderr}"
    )


def test_validate_invalid_exit_1() -> None:
    """validate on an invalid fixture must exit with code 1."""
    result = run("validate", str(INVALID_DIR / "enum_bad_paradigm.json"))
    assert result.returncode == 1, (
        f"Expected exit 1, got {result.returncode}\nstderr: {result.stderr}"
    )


def test_validate_nonexistent_file_exit_2() -> None:
    """validate on a missing file must exit with code 2."""
    result = run("validate", _MISSING)
    assert result.returncode == 2, (
        f"Expected exit 2, got {result.returncode}\nstderr: {result.stderr}"
    )


def test_validate_strict_valid_no_warnings_exit_0() -> None:
    """validate --strict on a fixture with no warnings must exit 0."""
    result = run("validate", "--strict", str(VALID_DIR / "design_science_min.json"))
    assert result.returncode == 0, (
        f"Expected exit 0 in strict mode for clean fixture, got {result.returncode}\n"
        f"stderr: {result.stderr}"
    )


def test_validate_strict_with_warning_exit_1() -> None:
    """validate --strict on a fixture with warnings must exit 1."""
    # scoping_empty_matrix.json has WARN_NO_MATRIX_DIMS
    result = run(
        "validate", "--strict", str(VALID_DIR / "scoping_empty_matrix.json")
    )
    assert result.returncode == 1, (
        f"Expected exit 1 in strict mode (warnings present), got {result.returncode}\n"
        f"stderr: {result.stderr}"
    )


# ---------------------------------------------------------------------------
# scholar-protocol fingerprint
# ---------------------------------------------------------------------------


def test_fingerprint_format() -> None:
    """fingerprint must output 'sha256:<64-hex-chars>' to stdout."""
    result = run("fingerprint", str(VALID_DIR / "design_science_min.json"))
    assert result.returncode == 0, f"Unexpected exit code: {result.returncode}"
    fp = result.stdout.strip()
    assert fp.startswith("sha256:"), f"Fingerprint must start with 'sha256:', got: {fp!r}"
    assert len(fp) == len("sha256:") + 64, f"Unexpected fingerprint length: {len(fp)}"


def test_fingerprint_stable() -> None:
    """Running fingerprint twice on the same file must produce the same output."""
    path = str(VALID_DIR / "prisma_slr_full.json")
    r1 = run("fingerprint", path)
    r2 = run("fingerprint", path)
    assert r1.stdout == r2.stdout, "Fingerprint is not stable across two runs"


def test_fingerprint_nonexistent_exit_2() -> None:
    """fingerprint on a missing file must exit with code 2."""
    result = run("fingerprint", _MISSING)
    assert result.returncode == 2


# ---------------------------------------------------------------------------
# scholar-protocol canon
# ---------------------------------------------------------------------------


def test_canon_output_is_valid_json() -> None:
    """canon must output valid JSON bytes to stdout."""
    result = run("canon", str(VALID_DIR / "design_science_min.json"))
    assert result.returncode == 0
    # Must parse without error.
    parsed = json.loads(result.stdout)
    assert "$schema" in parsed


def test_canon_output_is_compact() -> None:
    """canon output must not contain ': ' or ', ' (compact separators)."""
    result = run("canon", str(VALID_DIR / "design_science_min.json"))
    assert result.returncode == 0
    assert ": " not in result.stdout
    assert ", " not in result.stdout


def test_canon_output_no_trailing_newline() -> None:
    """canon output must not end with a newline."""
    result = run("canon", str(VALID_DIR / "design_science_min.json"))
    # stdout is captured as text; check the raw bytes indirectly.
    # The CLI writes bytes directly, so result.stdout should not end with \n.
    assert not result.stdout.endswith("\n"), (
        "canon output must not end with newline"
    )


def test_canon_schema_first_key() -> None:
    """canon output must have $schema as the first JSON key."""
    result = run("canon", str(VALID_DIR / "prisma_slr_full.json"))
    assert result.returncode == 0
    pairs = json.loads(result.stdout, object_pairs_hook=list)
    assert pairs[0][0] == "$schema"


def test_canon_nonexistent_exit_2() -> None:
    """canon on a missing file must exit with code 2."""
    result = run("canon", _MISSING)
    assert result.returncode == 2


# ---------------------------------------------------------------------------
# scholar-protocol compile
# ---------------------------------------------------------------------------


def test_compile_output_is_valid_json() -> None:
    """compile must output valid JSON bytes to stdout."""
    result = run("compile", str(INTENTS_DIR / "design_science_min.intent.json"))
    assert result.returncode == 0
    # Must parse without error.
    parsed = json.loads(result.stdout)
    assert "$schema" in parsed


def test_compile_output_is_compact() -> None:
    """compile output must not contain ': ' or ', ' (compact separators)."""
    result = run("compile", str(INTENTS_DIR / "design_science_min.intent.json"))
    assert result.returncode == 0
    assert ": " not in result.stdout
    assert ", " not in result.stdout


def test_compile_output_no_trailing_newline() -> None:
    """compile output must not end with a newline."""
    result = run("compile", str(INTENTS_DIR / "design_science_min.intent.json"))
    assert not result.stdout.endswith("\n"), (
        "compile output must not end with newline"
    )


def test_compile_nonexistent_exit_2() -> None:
    """compile on a missing file must exit with code 2."""
    result = run("compile", _MISSING)
    assert result.returncode == 2


# ---------------------------------------------------------------------------
# scholar-protocol render-criteria
# ---------------------------------------------------------------------------


def test_render_criteria_output_is_markdown() -> None:
    """render-criteria must output a Markdown document with expected headers."""
    result = run("render-criteria", str(VALID_DIR / "design_science_min.json"))
    assert result.returncode == 0
    assert "# Screening Criteria: Minimal Design Science Protocol" in result.stdout
    assert "## Inclusion Criteria" in result.stdout
    assert "### INC-01" in result.stdout


def test_render_criteria_nonexistent_exit_2() -> None:
    """render-criteria on a missing file must exit with code 2."""
    result = run("render-criteria", _MISSING)
    assert result.returncode == 2


# ---------------------------------------------------------------------------
# scholar-protocol extraction-schema and extraction-prompt
# ---------------------------------------------------------------------------


def test_extraction_schema_output_is_json() -> None:
    """extraction-schema must output valid JSON Schema."""
    result = run("extraction-schema", str(VALID_DIR / "design_science_min.json"))
    assert result.returncode == 0
    parsed = json.loads(result.stdout)
    assert "type" in parsed
    assert "properties" in parsed
    # Check that benchmark_dataset dimension exists
    assert "benchmark_dataset" in parsed["properties"]


def test_extraction_schema_nonexistent_exit_2() -> None:
    """extraction-schema on a missing file must exit with code 2."""
    result = run("extraction-schema", _MISSING)
    assert result.returncode == 2


def test_extraction_prompt_output_is_markdown() -> None:
    """extraction-prompt must output expected markdown guidelines."""
    result = run("extraction-prompt", str(VALID_DIR / "design_science_min.json"))
    assert result.returncode == 0
    assert "### Extraction Guidelines" in result.stdout
    assert "#### `benchmark_dataset`: Benchmark Dataset" in result.stdout


def test_extraction_prompt_nonexistent_exit_2() -> None:
    """extraction-prompt on a missing file must exit with code 2."""
    result = run("extraction-prompt", _MISSING)
    assert result.returncode == 2



