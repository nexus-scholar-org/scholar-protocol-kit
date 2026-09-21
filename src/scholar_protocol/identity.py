"""Protocol identity adapter for Nexus Scholar Contract v1.

Exposes deterministic protocol identity, canonical fingerprints, PRT-* protocol
identifiers, and producer provenance metadata to downstream envelopes.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import pathlib
import re
import subprocess
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from scholar_protocol.canonical import canonical_fingerprint, canonical_json
from scholar_protocol.models import ResearchProtocol

_PACKAGE_NAME = "scholar-protocol-kit"
try:
    _PACKAGE_VERSION = importlib.metadata.version(_PACKAGE_NAME)
except importlib.metadata.PackageNotFoundError:
    _PACKAGE_VERSION = "0+unknown"
_PRT_ID_RE = re.compile(r"^PRT-[A-Za-z0-9][A-Za-z0-9._-]*$")
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class ProtocolProducer(BaseModel):
    """Provenance metadata describing the protocol producer."""

    model_config = ConfigDict(extra="allow")

    package: str = Field(_PACKAGE_NAME, min_length=1)
    version: str = Field(_PACKAGE_VERSION, min_length=1)
    commit: str = Field(..., min_length=1)


class ProtocolIdentity(BaseModel):
    """Typed protocol identity output for downstream Contract v1 envelopes."""

    model_config = ConfigDict(extra="allow")

    protocol_id: str = Field(..., pattern=r"^PRT-[A-Za-z0-9][A-Za-z0-9._-]*$")
    protocol_fingerprint: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    schema_version: str = Field("1.0.0", min_length=1)
    producer: ProtocolProducer
    project_slug: str = ""
    canonical_bytes: bytes = Field(default=b"", repr=False, exclude=True)

    def as_envelope_context(self) -> dict[str, str]:
        """Return context fields required by downstream artifact envelopes."""
        return {
            "protocol_id": self.protocol_id,
            "protocol_fingerprint": self.protocol_fingerprint,
        }

    def to_dict(self) -> dict[str, Any]:
        """Emit a JSON-serializable dictionary."""
        return self.model_dump(mode="json")


def resolve_producer_commit(explicit_commit: str | None = None) -> str:
    """Resolve the git commit hash for scholar-protocol-kit."""
    if explicit_commit and explicit_commit.strip():
        return explicit_commit.strip()

    for env_key in ("SCHOLAR_PROTOCOL_COMMIT", "NEXUS_SCHOLAR_COMMIT", "GIT_COMMIT"):
        val = os.environ.get(env_key, "").strip()
        if val:
            return val

    # A vendored checkout belongs to the harness Git repository, so asking Git
    # for HEAD there reports the harness revision. Prefer its exact kit pin.
    try:
        monorepo_root = pathlib.Path(__file__).resolve().parents[4]
        plugins_json = monorepo_root / ".agents" / "plugins" / "nexus-scholar" / "plugins.json"
        if plugins_json.is_file():
            data = json.loads(plugins_json.read_text(encoding="utf-8"))
            for p in data.get("plugins", []):
                if p.get("name") == "scholar-protocol-kit":
                    rev = p.get("default_rev", "").strip()
                    if rev:
                        return rev
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        pass

    try:
        pkg_dir = pathlib.Path(__file__).resolve().parent
        res = subprocess.run(
            ["git", "-C", str(pkg_dir), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except OSError:
        pass

    return "unknown"


def mint_or_accept_protocol_id(
    protocol: ResearchProtocol | Mapping[str, Any] | str,
    canonical_bytes: bytes | None = None,
) -> str:
    """Accept an authored PRT-* protocol identifier or deterministically mint one.

    If protocol already declares a valid PRT-* ID, it is returned unmodified.
    Otherwise, a stable PRT-* identifier is minted from the SHA-256 hash of the
    canonical bytes, preserving protocol fingerprint semantics without mutation.
    """
    raw_id: str | None = None
    if isinstance(protocol, ResearchProtocol):
        raw_id = protocol.protocol_id
    elif isinstance(protocol, Mapping):
        raw_id = protocol.get("protocol_id")
    elif isinstance(protocol, str):
        if _PRT_ID_RE.match(protocol):
            return protocol
        raw_id = protocol

    if raw_id and _PRT_ID_RE.match(raw_id):
        return raw_id

    if canonical_bytes is None:
        if isinstance(protocol, ResearchProtocol):
            canonical_bytes = canonical_json(protocol)
        elif isinstance(protocol, Mapping):
            model = ResearchProtocol.model_validate(protocol)
            canonical_bytes = canonical_json(model)
        else:
            raise ValueError(
                "canonical_bytes required when protocol is not a model or mapping"
            )

    digest = hashlib.sha256(canonical_bytes).hexdigest()[:32]
    return f"PRT-{digest}"


def get_protocol_identity(
    protocol: ResearchProtocol | Mapping[str, Any] | pathlib.Path | str | bytes,
    *,
    commit: str | None = None,
    schema_version: str = "1.0.0",
) -> ProtocolIdentity:
    """Extract or construct a ProtocolIdentity from any supported protocol input.

    Parameters
    ----------
    protocol:
        A ResearchProtocol instance, mapping, pathlib.Path to protocol.json,
        or raw JSON bytes/str.
    commit:
        Optional explicit commit hash for producer provenance.
    schema_version:
        Contract schema version (default: '1.0.0').

    Returns
    -------
    ProtocolIdentity:
        Validated protocol identity with PRT-* ID, canonical fingerprint,
        and producer metadata.
    """
    model: ResearchProtocol

    if isinstance(protocol, ResearchProtocol):
        model = protocol
    elif isinstance(protocol, pathlib.Path) or (
        isinstance(protocol, str)
        and not protocol.strip().startswith("{")
        and "\n" not in protocol
    ):
        path = pathlib.Path(protocol)
        if not path.is_file():
            raise FileNotFoundError(f"Protocol file not found: {path}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        model = ResearchProtocol.model_validate(raw)
    elif isinstance(protocol, str):
        raw = json.loads(protocol)
        model = ResearchProtocol.model_validate(raw)
    elif isinstance(protocol, (bytes, bytearray)):
        raw = json.loads(protocol.decode("utf-8"))
        model = ResearchProtocol.model_validate(raw)
    elif isinstance(protocol, Mapping):
        model = ResearchProtocol.model_validate(protocol)
    else:
        raise TypeError(f"Unsupported protocol type: {type(protocol).__name__}")

    raw_canon = canonical_json(model)
    fp = canonical_fingerprint(model)
    proto_id = mint_or_accept_protocol_id(model, canonical_bytes=raw_canon)
    producer_info = ProtocolProducer(
        package=_PACKAGE_NAME,
        version=_PACKAGE_VERSION,
        commit=resolve_producer_commit(commit),
    )

    return ProtocolIdentity(
        protocol_id=proto_id,
        protocol_fingerprint=fp,
        schema_version=schema_version,
        producer=producer_info,
        project_slug=model.project_slug,
        canonical_bytes=raw_canon,
    )
