"""Playbook presets — default field values per ``PlaybookType``.

A preset supplies every field that a researcher need not re-specify from
scratch when they choose a recognised research archetype.  The compiler
applies the preset first and then overlays any intent-packet overrides.

Frozen at schema v1.0.0.  Adding a new preset key or changing a default
is a **non-patch change** — it alters the canonical bytes of any protocol
compiled without an explicit override for that field.

Preset field semantics
----------------------
- ``primary_paradigm``         → ``epistemology.primary_paradigm``
- ``trustworthiness_framework`` → ``epistemology.trustworthiness_framework``
- ``two_tier_screening``        → ``screening_criteria.two_tier_screening``
- ``target_databases``          → ``search_strategy.target_databases``
- ``languages``                 → ``search_strategy.languages``
- ``open_access_preferred``     → ``search_strategy.open_access_preferred``
- ``pool_min`` / ``pool_max``   → ``search_strategy.target_candidate_pool_size``
- ``timeline_weeks``            → ``metadata.timeline_weeks``
- ``retraction_check_required`` → ``verification.retraction_check_required``
- ``coi_and_funding_audit_required`` → ``verification.coi_and_funding_audit_required``
- ``reproducibility_das_cas_check``  → ``verification.reproducibility_das_cas_check``
- ``minimum_trust_score_threshold``  → ``verification.minimum_trust_score_threshold``
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from scholar_protocol.models import EpistemologicalParadigm, PlaybookType

# ---------------------------------------------------------------------------
# Preset dataclass
# ---------------------------------------------------------------------------

_DEFAULT_DATABASES: List[str] = [
    "openalex",
    "semanticscholar",
    "crossref",
    "arxiv",
]


@dataclass(frozen=True)
class PlaybookPreset:
    """Immutable default values for one research archetype."""

    primary_paradigm: EpistemologicalParadigm
    trustworthiness_framework: str
    two_tier_screening: bool
    target_databases: List[str]
    languages: List[str]
    open_access_preferred: bool
    pool_min: int
    pool_max: int
    timeline_weeks: int
    retraction_check_required: bool
    coi_and_funding_audit_required: bool
    reproducibility_das_cas_check: bool
    minimum_trust_score_threshold: float


# ---------------------------------------------------------------------------
# Preset registry
# ---------------------------------------------------------------------------

PRESETS: dict[PlaybookType, PlaybookPreset] = {
    PlaybookType.PRISMA_SLR: PlaybookPreset(
        primary_paradigm=EpistemologicalParadigm.POSITIVIST,
        trustworthiness_framework="PRISMA 2020",
        two_tier_screening=True,
        target_databases=_DEFAULT_DATABASES,
        languages=["en"],
        open_access_preferred=True,
        pool_min=500,
        pool_max=2000,
        timeline_weeks=12,
        retraction_check_required=True,
        coi_and_funding_audit_required=True,
        reproducibility_das_cas_check=True,
        minimum_trust_score_threshold=6.0,
    ),
    PlaybookType.SCOPING_REVIEW: PlaybookPreset(
        primary_paradigm=EpistemologicalParadigm.PRAGMATIST_MIXED,
        trustworthiness_framework="JBI Scoping Review Framework",
        two_tier_screening=True,
        target_databases=_DEFAULT_DATABASES,
        languages=["en"],
        open_access_preferred=True,
        pool_min=200,
        pool_max=1000,
        timeline_weeks=6,
        retraction_check_required=True,
        coi_and_funding_audit_required=True,
        reproducibility_das_cas_check=True,
        minimum_trust_score_threshold=5.0,
    ),
    PlaybookType.RAPID_EVIDENCE: PlaybookPreset(
        primary_paradigm=EpistemologicalParadigm.POSITIVIST,
        trustworthiness_framework="REA Guidelines",
        two_tier_screening=False,
        target_databases=_DEFAULT_DATABASES,
        languages=["en"],
        open_access_preferred=True,
        pool_min=50,
        pool_max=200,
        timeline_weeks=2,
        retraction_check_required=True,
        coi_and_funding_audit_required=False,
        reproducibility_das_cas_check=False,
        minimum_trust_score_threshold=5.0,
    ),
    PlaybookType.DESIGN_SCIENCE: PlaybookPreset(
        primary_paradigm=EpistemologicalParadigm.DESIGN_SCIENCE,
        trustworthiness_framework="Hevner DSR",
        two_tier_screening=True,
        target_databases=_DEFAULT_DATABASES,
        languages=["en"],
        open_access_preferred=True,
        pool_min=50,
        pool_max=200,
        timeline_weeks=4,
        retraction_check_required=True,
        coi_and_funding_audit_required=True,
        reproducibility_das_cas_check=True,
        minimum_trust_score_threshold=5.0,
    ),
    PlaybookType.STUDENT_DISSERTATION: PlaybookPreset(
        primary_paradigm=EpistemologicalParadigm.PRAGMATIST_MIXED,
        trustworthiness_framework="APA / JBI Adapted Guidelines",
        two_tier_screening=False,
        target_databases=_DEFAULT_DATABASES,
        languages=["en"],
        open_access_preferred=True,
        pool_min=50,
        pool_max=200,
        timeline_weeks=4,
        retraction_check_required=False,
        coi_and_funding_audit_required=False,
        reproducibility_das_cas_check=False,
        minimum_trust_score_threshold=4.0,
    ),
}
