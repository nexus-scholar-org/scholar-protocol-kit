"""scholar_protocol — Phase 0 protocol.json schema, validation, and canonical serialization.

Public API
----------
from scholar_protocol import (
    ResearchProtocol,
    PlaybookType,
    EpistemologicalParadigm,
    DimensionDataType,
    canonical_json,
    canonical_fingerprint,
    validate_protocol,
    ValidationReport,
    IntentPacket,
    compile_protocol,
)
"""

from scholar_protocol.models import (
    ConceptCluster,
    DimensionDataType,
    EpistemologicalParadigm,
    EpistemologyConfig,
    MatrixDimension,
    PlaybookType,
    ResearchProtocol,
    ResearchQuestion,
    ScreeningCriteria,
    ScreeningCriterion,
    SearchStrategy,
    VerificationConfig,
)
from scholar_protocol.canonical import canonical_fingerprint, canonical_json
from scholar_protocol.validate import ValidationReport, validate_protocol
from scholar_protocol.intent import IntentPacket
from scholar_protocol.compiler import compile_protocol

__version__ = "1.0.0"

__all__ = [
    # Models
    "ConceptCluster",
    "DimensionDataType",
    "EpistemologicalParadigm",
    "EpistemologyConfig",
    "MatrixDimension",
    "PlaybookType",
    "ResearchProtocol",
    "ResearchQuestion",
    "ScreeningCriteria",
    "ScreeningCriterion",
    "SearchStrategy",
    "VerificationConfig",
    # Canonical serialization
    "canonical_json",
    "canonical_fingerprint",
    # Validation
    "validate_protocol",
    "ValidationReport",
    # Compiler
    "IntentPacket",
    "compile_protocol",
    # Version
    "__version__",
]
