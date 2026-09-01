"""Data models for the Phase 0 protocol.json specification.

This module is the *sole* runtime source of truth for the schema.
The checked-in JSON Schema at schemas/v1/protocol.schema.json is derived
from these models and kept in sync by CI (see tests/test_schema_sync.py).

Field declaration order is canonical: the serializer in canonical.py
iterates model_fields in declaration order to produce stable key order.
Do NOT reorder fields without also updating the golden fixture files and
incrementing the schema version.
"""

from __future__ import annotations

import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class PlaybookType(str, Enum):
    """Canonical research playbook archetypes."""

    PRISMA_SLR = "PRISMA_SLR"
    """Exhaustive systematic review following PRISMA 2020 guidelines."""

    SCOPING_REVIEW = "SCOPING_REVIEW"
    """Broad landscape mapping (JBI / Arksey & O'Malley framework)."""

    RAPID_EVIDENCE = "RAPID_EVIDENCE"
    """Time-bounded high-precision review (24-72h REA)."""

    DESIGN_SCIENCE = "DESIGN_SCIENCE"
    """Artifact engineering & empirical benchmarking (Hevner DSR)."""

    STUDENT_DISSERTATION = "STUDENT_DISSERTATION"
    """Pedagogical starter / dissertation review."""


class EpistemologicalParadigm(str, Enum):
    """Core epistemological stances."""

    POSITIVIST = "Positivist"
    """Quantitative, generalizable, statistical."""

    INTERPRETIVIST = "Interpretivist"
    """Qualitative, human meaning, lived experience."""

    DESIGN_SCIENCE = "Design Science"
    """Computational artifacts, systems utility."""

    PRAGMATIST_MIXED = "Pragmatist / Mixed Methods"
    """Metric triangulation & operational problem-solving."""


class DimensionDataType(str, Enum):
    """Supported data types for extracted matrix dimensions."""

    FREE_TEXT = "free_text"
    """Descriptive summary (e.g. 'Limitations', 'Method summary')."""

    NUMERIC = "numeric"
    """Numbers with units (e.g. 'N = 450', '37ms latency', 'pass@1 = 78.4%')."""

    CATEGORICAL = "categorical"
    """Bounded enum (e.g. 'RCT', 'Observational', 'A/B Benchmark')."""

    LIST = "list"
    """Array of items (e.g. ['Python', 'C++', 'Go'])."""


# ---------------------------------------------------------------------------
# Sub-models (dependency order: leaf → root)
# ---------------------------------------------------------------------------


class ResearchQuestion(BaseModel):
    """A formal, refined research question."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., description="Unique identifier e.g. 'RQ1', 'RQ2'")
    text: str = Field(..., description="Formal refined research question text")
    target_facet: str = Field(
        ..., description="The conceptual facet addressed, e.g. 'evaluation_metrics'"
    )
    synthesis_type: str = Field(
        "Comparative Matrix",
        description="How findings will be synthesised, e.g. 'Comparative Matrix', 'Taxonomy', 'Narrative'",
    )
    required_evidence_type: str = Field(
        ...,
        description="Evidence class required to answer this RQ, e.g. 'Quantitative telemetry'",
    )


class ConceptCluster(BaseModel):
    """Conceptual keyword cluster with boolean operator for query expansion."""

    model_config = ConfigDict(populate_by_name=True)

    concept: str = Field(..., description="Primary conceptual term")
    synonyms: List[str] = Field(
        default_factory=list,
        description="Alternative keyword synonyms (author order preserved)",
    )
    boolean_operator: str = Field(
        "OR", description="Operator joining synonyms: 'OR' or 'AND'"
    )


class SearchStrategy(BaseModel):
    """Federated multi-provider search strategy."""

    model_config = ConfigDict(populate_by_name=True)

    core_concepts: List[ConceptCluster] = Field(
        ...,
        min_length=1,
        description="At least one concept cluster is required",
    )
    target_databases: List[str] = Field(
        default=["openalex", "semanticscholar", "crossref", "arxiv"],
        description="Target academic databases to query",
    )
    date_range: Dict[str, Optional[int]] = Field(
        default_factory=lambda: {"start_year": 2020, "end_year": 2026},
        description="Inclusive year bounds for the search window",
    )
    languages: List[str] = Field(
        default=["en"],
        description="ISO 639-1 language codes; must be non-empty",
    )
    open_access_preferred: bool = Field(
        True,
        description="Prioritise open-access sources when True",
    )
    target_candidate_pool_size: Dict[str, int] = Field(
        default_factory=lambda: {"min": 500, "max": 2000},
        description="Expected size of the initial candidate pool (min <= max)",
    )


class ScreeningCriterion(BaseModel):
    """A single inclusion or exclusion criterion."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., description="Unique criterion id e.g. 'INC-01', 'EXC-01'")
    criterion: str = Field(..., description="Explicit condition description")
    maps_to_rqs: List[str] = Field(
        default_factory=list,
        description="RQ ids this criterion serves (must reference existing RQ ids)",
    )
    reason_category: Optional[str] = Field(
        None,
        description="Optional rejection category e.g. 'WRONG_POPULATION', 'WRONG_OUTCOME'",
    )


class ScreeningCriteria(BaseModel):
    """Two-tier PRISMA screening configuration."""

    model_config = ConfigDict(populate_by_name=True)

    inclusion: List[ScreeningCriterion] = Field(
        ...,
        min_length=1,
        description="At least one inclusion criterion is required",
    )
    exclusion: List[ScreeningCriterion] = Field(
        ...,
        min_length=1,
        description="At least one exclusion criterion is required",
    )
    two_tier_screening: bool = Field(
        True,
        description="When True: Tier 1 = Title/Abstract screen, Tier 2 = Full Text",
    )


class MatrixDimension(BaseModel):
    """Dynamic, domain-customisable matrix extraction dimension.

    These dimensions drive the RAG extractor in Phase 2.  They are inert
    configuration in Cycle A — no pipeline reads them yet.  ``matrix_dimensions``
    defaults to an empty list, which is a valid (warnings-only) state.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(
        ...,
        description="Unique slug used as the extraction column key, e.g. 'sample_size'",
    )
    name: str = Field(
        ...,
        description="Human-readable column header, e.g. 'Sample Size (N)'",
    )
    description: str = Field(
        ...,
        description="Guidance to the RAG extractor on what text to capture",
    )
    target_section_category: Optional[str] = Field(
        None,
        description=(
            "Preferred source section: 'methodology', 'results_empirical', "
            "'discussion_limitations', or 'abstract_intro'.  Null = search all sections."
        ),
    )
    data_type: DimensionDataType = Field(
        DimensionDataType.FREE_TEXT,
        description="Expected data type of the extracted value",
    )
    required: bool = Field(
        False,
        description="When True the extractor flags papers that omit this dimension",
    )
    fallback_value: str = Field(
        "Not Reported",
        description="Placeholder used when the paper does not report this dimension",
    )


class EpistemologyConfig(BaseModel):
    """Epistemological stance, rigor standard, and vocabulary boundaries."""

    model_config = ConfigDict(populate_by_name=True)

    primary_paradigm: EpistemologicalParadigm = Field(
        ...,
        description="The dominant epistemological stance for this research",
    )
    secondary_paradigm: Optional[EpistemologicalParadigm] = Field(
        None,
        description="Optional supplementary paradigm (e.g. for mixed-methods designs)",
    )
    unit_of_analysis: str = Field(
        ...,
        description="The concrete entity being studied, e.g. 'Software developer commit diffs'",
    )
    trustworthiness_framework: str = Field(
        ...,
        description="Quality / rigor framework, e.g. 'PRISMA 2020', 'Lincoln & Guba', 'Hevner DSR'",
    )
    epistemological_rationale: str = Field(
        ...,
        description="Narrative justification for the paradigm choice",
    )
    incompatible_concepts: List[str] = Field(
        default_factory=list,
        description="Terms suppressed from search / synthesis under this paradigm",
    )


class VerificationConfig(BaseModel):
    """Phase 4 Trust verification audit flags."""

    model_config = ConfigDict(populate_by_name=True)

    retraction_check_required: bool = Field(
        True,
        description="Require retraction watch scan before inclusion",
    )
    coi_and_funding_audit_required: bool = Field(
        True,
        description="Require conflict-of-interest and funding disclosure audit",
    )
    reproducibility_das_cas_check: bool = Field(
        True,
        description="Require data-availability and code-availability statement check",
    )
    minimum_trust_score_threshold: float = Field(
        5.0,
        ge=0.0,
        le=10.0,
        description="Minimum Phase 4 trust score [0.0, 10.0] for a paper to be included",
    )


# ---------------------------------------------------------------------------
# Root model
# ---------------------------------------------------------------------------


class ResearchProtocol(BaseModel):
    """The master Phase 0 research protocol.

    Field declaration order is the canonical serialization order.
    The ``$schema`` field is aliased to ``schema_version`` so that JSON
    output contains the ``$schema`` key required by the JSON Schema spec,
    while Python code uses the valid Python identifier ``schema_version``.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        # Serialisation uses alias ("$schema") in JSON output.
        # Python callers may use schema_version= OR **{"$schema": ...}.
    )

    schema_version: str = Field(
        "schemas/v1/protocol.schema.json",
        alias="$schema",
        description="URI of the JSON Schema (relative kit path, resolved locally by the validator)",
    )
    protocol_id: str = Field(
        ...,
        description="Unique protocol identifier, e.g. 'proto-20260901-ai-dev'",
    )
    created_at: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(),
        description="ISO-8601 timestamp of protocol creation (UTC)",
    )
    project_slug: str = Field(
        ...,
        description="Workspace directory slug, e.g. 'ai-developer-productivity'",
    )
    playbook_type: PlaybookType = Field(
        ...,
        description="Canonical research archetype driving default parameters",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=lambda: {
            "title": "",
            "lead_researcher": "",
            "target_venue_type": "",
            "timeline_weeks": 4,
        },
        description="Freeform project metadata (title, researcher, venue, timeline)",
    )
    epistemology: EpistemologyConfig
    research_questions: List[ResearchQuestion] = Field(
        ...,
        min_length=1,
        description="At least one research question is required",
    )
    search_strategy: SearchStrategy
    screening_criteria: ScreeningCriteria
    matrix_dimensions: List[MatrixDimension] = Field(
        default_factory=list,
        description="Custom extraction dimensions (empty list = no extraction configured)",
    )
    verification: VerificationConfig = Field(
        default_factory=VerificationConfig,
    )
