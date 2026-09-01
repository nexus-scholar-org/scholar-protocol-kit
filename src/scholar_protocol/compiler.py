"""Deterministic compiler: IntentPacket → ResearchProtocol.

The compiler is a pure function with zero side effects, zero LLM calls, and
zero network calls.  Given the same IntentPacket, it always produces the same
``ResearchProtocol``, whose ``canonical_fingerprint`` must match the checked-in
``.sha256`` golden file for that fixture.

Algorithm
---------
1. Load the playbook preset for ``intent.playbook_type``.
2. Resolve every optional field:  intent value if present, else preset default.
3. Auto-generate RQ IDs (``RQ1``, ``RQ2``, …) in declaration order.
4. Auto-generate criterion IDs (``INC-01``, ``EXC-01``, …) in declaration order.
5. Construct and validate a ``ResearchProtocol``.

Conformance gate (Cycle B)
--------------------------
For every golden intent fixture ``tests/fixtures/intents/<name>.intent.json``:

    intent = IntentPacket.model_validate_json(Path(...).read_text())
    protocol = compile_protocol(intent)
    assert canonical_fingerprint(protocol) == golden_sha256

This is the hard proof that the compiler and the golden fixtures are consistent.

ID generation rules (frozen at v1.0.0)
---------------------------------------
- Research question IDs: ``RQ{n}`` where n = 1-indexed declaration position.
- Inclusion criterion IDs: ``INC-{n:02d}`` (INC-01, INC-02, …).
- Exclusion criterion IDs: ``EXC-{n:02d}`` (EXC-01, EXC-02, …).
- Dimension IDs: author-provided (semantic slugs, never auto-generated).
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

from scholar_protocol.intent import IntentPacket
from scholar_protocol.models import (
    ConceptCluster,
    EpistemologyConfig,
    MatrixDimension,
    ResearchProtocol,
    ResearchQuestion,
    ScreeningCriteria,
    ScreeningCriterion,
    SearchStrategy,
    VerificationConfig,
)
from scholar_protocol.presets import PRESETS


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve(intent_value: Any, preset_value: Any) -> Any:
    """Return intent_value if it is not None, otherwise preset_value."""
    return intent_value if intent_value is not None else preset_value


def _build_rqs(intent: IntentPacket) -> list[ResearchQuestion]:
    """Generate ResearchQuestion models with sequential IDs."""
    return [
        ResearchQuestion(
            id=f"RQ{i + 1}",
            text=rq.text,
            target_facet=rq.target_facet,
            synthesis_type=rq.synthesis_type,
            required_evidence_type=rq.required_evidence_type,
        )
        for i, rq in enumerate(intent.research_questions)
    ]


def _build_inclusion(intent: IntentPacket) -> list[ScreeningCriterion]:
    """Generate inclusion ScreeningCriterion models with sequential INC-nn IDs."""
    return [
        ScreeningCriterion(
            id=f"INC-{i + 1:02d}",
            criterion=c.criterion,
            maps_to_rqs=list(c.maps_to_rqs),
            reason_category=c.reason_category,
        )
        for i, c in enumerate(intent.inclusion_criteria)
    ]


def _build_exclusion(intent: IntentPacket) -> list[ScreeningCriterion]:
    """Generate exclusion ScreeningCriterion models with sequential EXC-nn IDs."""
    return [
        ScreeningCriterion(
            id=f"EXC-{i + 1:02d}",
            criterion=c.criterion,
            maps_to_rqs=list(c.maps_to_rqs),
            reason_category=c.reason_category,
        )
        for i, c in enumerate(intent.exclusion_criteria)
    ]


def _build_dimensions(intent: IntentPacket) -> list[MatrixDimension]:
    """Build MatrixDimension models from the intent (IDs are author-provided)."""
    return [
        MatrixDimension(
            id=d.id,
            name=d.name,
            description=d.description,
            target_section_category=d.target_section_category,
            data_type=d.data_type,
            required=d.required,
            fallback_value=d.fallback_value,
        )
        for d in intent.matrix_dimensions
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compile_protocol(intent: IntentPacket) -> ResearchProtocol:
    """Compile an IntentPacket into a validated ResearchProtocol.

    Args:
        intent: A fully parsed and validated IntentPacket.

    Returns:
        A ``ResearchProtocol`` ready for canonical serialization and
        fingerprinting.  The fingerprint must match the corresponding
        golden ``.sha256`` file.

    Raises:
        KeyError: If ``intent.playbook_type`` has no registered preset
                  (should never happen if IntentPacket validation passed).
        pydantic.ValidationError: If the compiled data fails ResearchProtocol
                                  validation (indicates a compiler bug or
                                  inconsistent intent packet).
    """
    preset = PRESETS[intent.playbook_type]

    # --- metadata -----------------------------------------------------------
    metadata: dict[str, Any] = {
        "lead_researcher": intent.lead_researcher,
        "target_venue_type": intent.target_venue_type,
        "timeline_weeks": _resolve(intent.timeline_weeks, preset.timeline_weeks),
        "title": intent.title,
    }
    # The canonical serializer sorts metadata keys alphabetically, so
    # construction order here does not affect the fingerprint.
    # We build in alphabetical order anyway for readability.

    # --- epistemology -------------------------------------------------------
    epistemology = EpistemologyConfig(
        primary_paradigm=_resolve(intent.primary_paradigm, preset.primary_paradigm),
        secondary_paradigm=intent.secondary_paradigm,
        unit_of_analysis=intent.unit_of_analysis,
        trustworthiness_framework=_resolve(
            intent.trustworthiness_framework, preset.trustworthiness_framework
        ),
        epistemological_rationale=intent.epistemological_rationale,
        incompatible_concepts=list(intent.incompatible_concepts),
    )

    # --- search strategy ----------------------------------------------------
    core_concepts = [
        ConceptCluster(
            concept=c.concept,
            synonyms=list(c.synonyms),
            boolean_operator=c.boolean_operator,
        )
        for c in intent.core_concepts
    ]
    date_range: dict[str, Any] = {
        "start_year": intent.start_year,
        "end_year": intent.end_year,
    }
    # Note: canonical.py sorts date_range → {"end_year": ..., "start_year": ...}
    pool_min = _resolve(intent.pool_min, preset.pool_min)
    pool_max = _resolve(intent.pool_max, preset.pool_max)
    pool_size: dict[str, int] = {"min": pool_min, "max": pool_max}
    # Note: canonical.py sorts pool_size → {"max": ..., "min": ...}

    search_strategy = SearchStrategy(
        core_concepts=core_concepts,
        target_databases=_resolve(intent.target_databases, list(preset.target_databases)),
        date_range=date_range,
        languages=_resolve(intent.languages, list(preset.languages)),
        open_access_preferred=_resolve(
            intent.open_access_preferred, preset.open_access_preferred
        ),
        target_candidate_pool_size=pool_size,
    )

    # --- screening criteria -------------------------------------------------
    screening_criteria = ScreeningCriteria(
        inclusion=_build_inclusion(intent),
        exclusion=_build_exclusion(intent),
        two_tier_screening=_resolve(intent.two_tier_screening, preset.two_tier_screening),
    )

    # --- verification -------------------------------------------------------
    verification = VerificationConfig(
        retraction_check_required=_resolve(
            intent.retraction_check_required, preset.retraction_check_required
        ),
        coi_and_funding_audit_required=_resolve(
            intent.coi_and_funding_audit_required, preset.coi_and_funding_audit_required
        ),
        reproducibility_das_cas_check=_resolve(
            intent.reproducibility_das_cas_check, preset.reproducibility_das_cas_check
        ),
        minimum_trust_score_threshold=float(
            _resolve(
                intent.minimum_trust_score_threshold,
                preset.minimum_trust_score_threshold,
            )
        ),
    )

    # --- assemble -----------------------------------------------------------
    data: dict[str, Any] = {
        "$schema": "schemas/v1/protocol.schema.json",
        "protocol_id": intent.protocol_id,
        "created_at": intent.genesis_timestamp,
        "project_slug": intent.project_slug,
        "playbook_type": intent.playbook_type.value,
        "metadata": metadata,
        "epistemology": epistemology.model_dump(mode="json"),
        "research_questions": [rq.model_dump(mode="json") for rq in _build_rqs(intent)],
        "search_strategy": search_strategy.model_dump(mode="json"),
        "screening_criteria": screening_criteria.model_dump(mode="json"),
        "matrix_dimensions": [d.model_dump(mode="json") for d in _build_dimensions(intent)],
        "verification": verification.model_dump(mode="json"),
    }
    return ResearchProtocol.model_validate(data)


def compile_from_file(path: pathlib.Path) -> ResearchProtocol:
    """Load an IntentPacket from a JSON file and compile it.

    Convenience wrapper used by the CLI ``compile`` command and tests.

    Args:
        path: Path to the ``.intent.json`` file.

    Returns:
        Compiled and validated ``ResearchProtocol``.
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    intent = IntentPacket.model_validate(raw)
    return compile_protocol(intent)
