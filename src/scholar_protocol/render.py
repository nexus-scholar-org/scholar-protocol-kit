"""Renderer for generating human-readable Markdown documents from a ResearchProtocol.

Cycle C provides the `render_screening_criteria` function, which translates
a compiled, validated ``ResearchProtocol`` into a formatted ``SCREENING_CRITERIA.md``
file.  This markdown file is the primary artifact handed to a human researcher
or imported into manual screening tools like Rayyan and Covidence.
"""

from __future__ import annotations

from scholar_protocol.models import ResearchProtocol


def render_screening_criteria(protocol: ResearchProtocol) -> str:
    """Render a protocol into a Markdown document for screening guidance.

    Args:
        protocol: The validated ResearchProtocol.

    Returns:
        A Markdown-formatted string representing the screening criteria.
    """
    md = []

    # 1. Header & Identity
    md.append(f"# Screening Criteria: {protocol.metadata.get('title') or 'Untitled Project'}")
    md.append("")
    md.append(f"**Protocol ID**: `{protocol.protocol_id}`")
    lead = protocol.metadata.get("lead_researcher")
    if lead:
        md.append(f"**Lead Researcher**: {lead}")
    md.append(f"**Playbook**: {protocol.playbook_type.value}")
    md.append(f"**Paradigm**: {protocol.epistemology.primary_paradigm.value}")
    md.append("")
    
    # 2. Epistemological Rationale (Context)
    md.append("## Context & Rationale")
    md.append(f"**Unit of Analysis**: {protocol.epistemology.unit_of_analysis}")
    md.append("")
    md.append(protocol.epistemology.epistemological_rationale)
    md.append("")

    # 3. Research Questions
    md.append("## Research Questions")
    md.append("")
    for rq in protocol.research_questions:
        md.append(f"### {rq.id}")
        md.append(f"**Question**: {rq.text}")
        md.append(f"- **Required Evidence**: {rq.required_evidence_type}")
        md.append(f"- **Synthesis Type**: {rq.synthesis_type}")
        md.append("")

    # 4. Inclusion Criteria
    md.append("## Inclusion Criteria")
    md.append("")
    for inc in protocol.screening_criteria.inclusion:
        md.append(f"### {inc.id}")
        md.append(f"**Criterion**: {inc.criterion}")
        if inc.maps_to_rqs:
            md.append(f"**Serves**: {', '.join(inc.maps_to_rqs)}")
        md.append("")

    # 5. Exclusion Criteria
    md.append("## Exclusion Criteria")
    md.append("")
    for exc in protocol.screening_criteria.exclusion:
        md.append(f"### {exc.id}")
        md.append(f"**Criterion**: {exc.criterion}")
        if exc.reason_category:
            md.append(f"**Rejection Reason Code**: `{exc.reason_category}`")
        if exc.maps_to_rqs:
            md.append(f"**Serves**: {', '.join(exc.maps_to_rqs)}")
        md.append("")

    # 6. Verification Overrides (if applicable)
    v = protocol.verification
    if (v.retraction_check_required or v.coi_and_funding_audit_required or v.reproducibility_das_cas_check):
        md.append("## Verification Constraints")
        md.append("")
        if v.retraction_check_required:
            md.append("- [x] Retraction check required")
        if v.coi_and_funding_audit_required:
            md.append("- [x] Conflict of Interest & Funding audit required")
        if v.reproducibility_das_cas_check:
            md.append("- [x] Reproducibility (Data/Code Availability) check required")
        md.append(f"- Minimum Trust Score: {v.minimum_trust_score_threshold}")
        md.append("")

    return "\n".join(md).strip() + "\n"
