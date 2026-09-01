"""Matrix Dimension consumption API for downstream RAG integration.

This module provides the tooling to compile protocol `matrix_dimensions` into:
1. Dynamic Pydantic models (for structured LLM outputs).
2. Markdown prompt instructions (for LLM system prompts).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel, Field, create_model

from scholar_protocol.models import DimensionDataType, ResearchProtocol


def build_extraction_model(protocol: ResearchProtocol) -> Type[BaseModel]:
    """Dynamically generate a Pydantic BaseModel for row extraction.

    The returned model can be exported as a JSON schema or used directly
    with Instructor / OpenAI Structured Outputs.

    Args:
        protocol: The validated ResearchProtocol containing matrix dimensions.

    Returns:
        A dynamically generated Pydantic BaseModel subclass.
    """
    fields: Dict[str, Any] = {}

    for dim in protocol.matrix_dimensions:
        # Determine base Python type
        if dim.data_type == DimensionDataType.LIST:
            field_type: Any = List[str]
        else:
            field_type = str

        # Determine if field is required and set defaults
        if dim.required:
            default = ...
        else:
            if dim.data_type == DimensionDataType.LIST:
                # Use a default factory to avoid mutable defaults in create_model
                default = [dim.fallback_value]
            else:
                default = dim.fallback_value
            # Make the field optional at the type level as well to be safe
            field_type = Optional[field_type]

        # Construct the FieldInfo
        field_info = Field(
            default=default,
            description=f"{dim.name}: {dim.description}",
        )
        fields[dim.id] = (field_type, field_info)

    # Generate the model
    # Model name is derived from protocol ID to ensure clarity in schemas
    clean_id = protocol.protocol_id.replace("-", "_").title().replace("_", "")
    model_name = f"{clean_id}ExtractionRow"

    if not fields:
        # If no dimensions are defined, create a minimal empty model
        return create_model(model_name)

    return create_model(model_name, **fields)


def generate_extraction_prompt(protocol: ResearchProtocol) -> str:
    """Generate markdown instructions for the LLM detailing what to extract.

    Args:
        protocol: The validated ResearchProtocol.

    Returns:
        A formatted markdown string for injection into a system prompt.
    """
    if not protocol.matrix_dimensions:
        return "No matrix dimensions configured for extraction."

    md = ["### Extraction Guidelines", ""]
    md.append("Extract the following dimensions based on the provided evidence text. "
              "Adhere strictly to the requested data types and descriptions.")
    md.append("")

    for dim in protocol.matrix_dimensions:
        md.append(f"#### `{dim.id}`: {dim.name}")
        md.append(f"- **Description**: {dim.description}")
        md.append(f"- **Data Type**: `{dim.data_type.value}`")
        if dim.target_section_category:
            md.append(f"- **Preferred Section**: `{dim.target_section_category}`")
        if dim.required:
            md.append("- **Requirement**: REQUIRED")
        else:
            md.append(f"- **Requirement**: OPTIONAL (Fallback: `{dim.fallback_value}`)")
        md.append("")

    return "\n".join(md).strip() + "\n"
