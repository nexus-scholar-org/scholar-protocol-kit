"""Validation engine for protocol.json files.

Two validation layers
---------------------
1. **Structural (Pydantic)** — field types, enums, ``min_length``, numeric
   bounds, required vs optional.  Handled automatically by
   ``ResearchProtocol.model_validate``.

2. **Cross-field (hand-written)** — semantic invariants that Pydantic alone
   cannot express:
   - Every ``ScreeningCriterion.maps_to_rqs`` entry names an existing RQ id.
   - ``MatrixDimension.id`` values are globally unique.
   - ``ResearchQuestion.id`` values are unique.
   - Criterion ids unique across inclusion ∪ exclusion.
   - ``date_range.start_year <= end_year`` and both within [1960, current+5].
   - ``target_candidate_pool_size.min <= max`` and both >= 0.
   - Non-empty ``languages`` list.
   - Warnings (non-fatal) for common oversights.

Error / Warning taxonomy
------------------------
Every finding has a ``code`` string so the CLI and Cycle B's compiler can
grade output deterministically.  Codes are SCREAMING_SNAKE_CASE.

Error codes (fatal — raise exit code 1)
    CROSS_FIELD_RQ_REF          maps_to_rqs references nonexistent RQ id
    DUPLICATE_RQ_ID             ResearchQuestion.id collision
    DUPLICATE_CRITERION_ID      ScreeningCriterion.id collision
    DUPLICATE_DIMENSION_ID      MatrixDimension.id collision
    DATE_RANGE_INCOHERENT       start_year > end_year or year out of band
    POOL_SIZE_INCOHERENT        min > max or negative values
    LANGUAGES_EMPTY             languages list is empty
    STRUCTURAL                  Pydantic validation error (field/type/bound)

Warning codes (non-fatal — surfaced but exit code 0; promoted to 1 with --strict)
    WARN_NO_MATRIX_DIMS         matrix_dimensions empty + two_tier_screening True
    WARN_PARADIGM_PLAYBOOK      questionable paradigm ↔ playbook combination
    WARN_VERIFICATION_FLAGS     all verification flags disabled
    WARN_SHORT_RATIONALE        epistemological_rationale < 20 chars
"""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass, field
from typing import List

from pydantic import ValidationError

from scholar_protocol.models import ResearchProtocol


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class Finding:
    """A single validation finding (error or warning)."""

    severity: str  # "error" or "warning"
    code: str
    message: str
    location: str = ""  # JSON-path-like hint, e.g. "screening_criteria.inclusion[0].maps_to_rqs"

    def __str__(self) -> str:
        loc = f" @ {self.location}" if self.location else ""
        return f"[{self.severity.upper()}] {self.code}{loc}: {self.message}"


@dataclass
class ValidationReport:
    """Aggregated validation result for one protocol.json file."""

    path: str
    findings: List[Finding] = field(default_factory=list)

    # ---- computed properties ------------------------------------------------

    @property
    def errors(self) -> List[Finding]:
        return [f for f in self.findings if f.severity == "error"]

    @property
    def warnings(self) -> List[Finding]:
        return [f for f in self.findings if f.severity == "warning"]

    @property
    def is_valid(self) -> bool:
        """True when there are no errors (warnings do not affect validity)."""
        return len(self.errors) == 0

    def is_valid_strict(self) -> bool:
        """True when there are no errors AND no warnings (for --strict mode)."""
        return len(self.findings) == 0

    # ---- helpers ------------------------------------------------------------

    def add_error(self, code: str, message: str, location: str = "") -> None:
        self.findings.append(Finding("error", code, message, location))

    def add_warning(self, code: str, message: str, location: str = "") -> None:
        self.findings.append(Finding("warning", code, message, location))

    def __str__(self) -> str:
        lines = [f"Validation report for: {self.path}"]
        if not self.findings:
            lines.append("  ✓ No issues found.")
        else:
            for f in self.findings:
                lines.append(f"  {f}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Cross-field rules
# ---------------------------------------------------------------------------


def _check_cross_field(protocol: ResearchProtocol, report: ValidationReport) -> None:
    """Apply all hand-written cross-field validation rules."""

    # --- Unique RQ ids -------------------------------------------------------
    rq_ids: list[str] = [rq.id for rq in protocol.research_questions]
    seen_rq: set[str] = set()
    for rq_id in rq_ids:
        if rq_id in seen_rq:
            report.add_error(
                "DUPLICATE_RQ_ID",
                f"ResearchQuestion id '{rq_id}' appears more than once",
                "research_questions",
            )
        seen_rq.add(rq_id)
    rq_id_set: set[str] = seen_rq  # for reference checks below

    # --- Criterion ids unique across inclusion ∪ exclusion -------------------
    sc = protocol.screening_criteria
    all_criteria = list(sc.inclusion) + list(sc.exclusion)
    seen_crit: set[str] = set()
    for crit in all_criteria:
        if crit.id in seen_crit:
            report.add_error(
                "DUPLICATE_CRITERION_ID",
                f"ScreeningCriterion id '{crit.id}' appears more than once "
                f"(ids must be unique across inclusion and exclusion)",
                "screening_criteria",
            )
        seen_crit.add(crit.id)

    # --- maps_to_rqs references ----------------------------------------------
    for section_name, criteria in [
        ("inclusion", sc.inclusion),
        ("exclusion", sc.exclusion),
    ]:
        for i, crit in enumerate(criteria):
            for ref in crit.maps_to_rqs:
                if ref not in rq_id_set:
                    report.add_error(
                        "CROSS_FIELD_RQ_REF",
                        f"Criterion '{crit.id}' references RQ id '{ref}' which does not exist "
                        f"(known RQ ids: {sorted(rq_id_set)})",
                        f"screening_criteria.{section_name}[{i}].maps_to_rqs",
                    )

    # --- Unique MatrixDimension ids ------------------------------------------
    seen_dim: set[str] = set()
    for i, dim in enumerate(protocol.matrix_dimensions):
        if dim.id in seen_dim:
            report.add_error(
                "DUPLICATE_DIMENSION_ID",
                f"MatrixDimension id '{dim.id}' appears more than once",
                f"matrix_dimensions[{i}]",
            )
        seen_dim.add(dim.id)

    # --- date_range coherence ------------------------------------------------
    import datetime as dt
    current_year = dt.datetime.now(dt.timezone.utc).year
    dr = protocol.search_strategy.date_range
    start = dr.get("start_year")
    end = dr.get("end_year")
    if start is not None and end is not None:
        if start > end:
            report.add_error(
                "DATE_RANGE_INCOHERENT",
                f"search_strategy.date_range.start_year ({start}) > end_year ({end})",
                "search_strategy.date_range",
            )
        for year, label in [(start, "start_year"), (end, "end_year")]:
            if not (1960 <= year <= current_year + 5):
                report.add_error(
                    "DATE_RANGE_INCOHERENT",
                    f"search_strategy.date_range.{label} = {year} is outside "
                    f"the valid band [1960, {current_year + 5}]",
                    f"search_strategy.date_range.{label}",
                )

    # --- pool size coherence -------------------------------------------------
    pool = protocol.search_strategy.target_candidate_pool_size
    p_min = pool.get("min", 0)
    p_max = pool.get("max", 0)
    if p_min < 0 or p_max < 0:
        report.add_error(
            "POOL_SIZE_INCOHERENT",
            "target_candidate_pool_size min and max must be >= 0",
            "search_strategy.target_candidate_pool_size",
        )
    elif p_min > p_max:
        report.add_error(
            "POOL_SIZE_INCOHERENT",
            f"target_candidate_pool_size.min ({p_min}) > max ({p_max})",
            "search_strategy.target_candidate_pool_size",
        )

    # --- languages non-empty -------------------------------------------------
    if not protocol.search_strategy.languages:
        report.add_error(
            "LANGUAGES_EMPTY",
            "search_strategy.languages must contain at least one language code",
            "search_strategy.languages",
        )

    # ---- Warnings -----------------------------------------------------------

    # Warn when matrix_dimensions is empty and two_tier_screening is active.
    if not protocol.matrix_dimensions and sc.two_tier_screening:
        report.add_warning(
            "WARN_NO_MATRIX_DIMS",
            "matrix_dimensions is empty while two_tier_screening is True; "
            "the RAG extractor will have nothing to extract in Phase 2",
            "matrix_dimensions",
        )

    # Warn on questionable paradigm ↔ playbook combinations.
    ep = protocol.epistemology.primary_paradigm
    pt = protocol.playbook_type
    from scholar_protocol.models import EpistemologicalParadigm, PlaybookType

    QUESTIONABLE_PAIRS = {
        (PlaybookType.SCOPING_REVIEW, EpistemologicalParadigm.DESIGN_SCIENCE),
        (PlaybookType.PRISMA_SLR, EpistemologicalParadigm.DESIGN_SCIENCE),
    }
    if (pt, ep) in QUESTIONABLE_PAIRS:
        report.add_warning(
            "WARN_PARADIGM_PLAYBOOK",
            f"Playbook '{pt.value}' with paradigm '{ep.value}' is an unusual combination; "
            "DESIGN_SCIENCE paradigm is typically paired with DESIGN_SCIENCE playbook",
            "epistemology.primary_paradigm",
        )

    # Warn when all verification flags are disabled.
    v = protocol.verification
    all_off = not (
        v.retraction_check_required
        or v.coi_and_funding_audit_required
        or v.reproducibility_das_cas_check
    )
    if all_off:
        report.add_warning(
            "WARN_VERIFICATION_FLAGS",
            "All verification flags (retraction_check, coi_audit, reproducibility_check) "
            "are disabled; Phase 4 trust audits will be skipped",
            "verification",
        )

    # Warn on suspiciously short epistemological rationale.
    rationale = protocol.epistemology.epistemological_rationale.strip()
    if len(rationale) < 20:
        report.add_warning(
            "WARN_SHORT_RATIONALE",
            f"epistemological_rationale is very short ({len(rationale)} chars); "
            "a meaningful rationale is expected",
            "epistemology.epistemological_rationale",
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_protocol(path: str | pathlib.Path) -> ValidationReport:
    """Validate a ``protocol.json`` file and return a ``ValidationReport``.

    Parameters
    ----------
    path:
        Filesystem path to the ``protocol.json`` file.

    Returns
    -------
    ValidationReport
        Contains all errors and warnings found.  ``report.is_valid`` is
        ``True`` when there are no errors (warnings do not fail validation).
    """
    path = pathlib.Path(path)
    report = ValidationReport(path=str(path))

    # --- Parse JSON ----------------------------------------------------------
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        report.add_error("STRUCTURAL", f"Cannot read/parse JSON: {exc}")
        return report

    # --- Structural (Pydantic) validation ------------------------------------
    try:
        protocol = ResearchProtocol.model_validate(raw)
    except ValidationError as exc:
        for err in exc.errors():
            loc = ".".join(str(p) for p in err["loc"])
            report.add_error(
                "STRUCTURAL",
                f"{err['msg']} (type={err['type']})",
                loc,
            )
        return report  # can't run cross-field checks on an invalid model

    # --- Cross-field rules ---------------------------------------------------
    _check_cross_field(protocol, report)

    return report
