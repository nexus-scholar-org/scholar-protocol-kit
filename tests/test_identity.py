"""Tests for ProtocolIdentity adapter, PRT-* minting, and canonical invariance."""

from __future__ import annotations

import json
import pathlib

import pytest
from typer.testing import CliRunner

from scholar_protocol.canonical import canonical_fingerprint, canonical_json
from scholar_protocol.cli import app
from scholar_protocol.identity import (
    ProtocolIdentity,
    ProtocolProducer,
    get_protocol_identity,
    mint_or_accept_protocol_id,
    resolve_producer_commit,
)
from scholar_protocol.models import ResearchProtocol

CANONICAL_DIR = (
    pathlib.Path(__file__).parent / "fixtures" / "canonical"
)
VALID_DIR = pathlib.Path(__file__).parent / "fixtures" / "valid"

runner = CliRunner()


def _load_json(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_identity_adapter_from_pydantic_model() -> None:
    path = CANONICAL_DIR / "identity_base.json"
    protocol = ResearchProtocol.model_validate(_load_json(path))

    ident = get_protocol_identity(protocol)
    assert isinstance(ident, ProtocolIdentity)
    assert ident.protocol_id == "PRT-019a2b3c4d5e6f7a8b9c0d1e2f3a4b5c"
    assert ident.protocol_fingerprint == canonical_fingerprint(protocol)
    assert ident.schema_version == "1.0.0"
    assert ident.producer.package == "scholar-protocol-kit"
    assert ident.producer.version == "1.0.0"
    assert len(ident.producer.commit) >= 7
    assert ident.canonical_bytes == canonical_json(protocol)

    ctx = ident.as_envelope_context()
    assert ctx["protocol_id"] == ident.protocol_id
    assert ctx["protocol_fingerprint"] == ident.protocol_fingerprint


def test_identity_adapter_from_various_inputs() -> None:
    path = CANONICAL_DIR / "identity_base.json"
    raw_dict = _load_json(path)
    raw_text = path.read_text(encoding="utf-8")
    raw_bytes = raw_text.encode("utf-8")

    from_path = get_protocol_identity(path)
    from_dict = get_protocol_identity(raw_dict)
    from_str = get_protocol_identity(raw_text)
    from_bytes = get_protocol_identity(raw_bytes)

    assert from_path.protocol_id == from_dict.protocol_id == from_str.protocol_id == from_bytes.protocol_id
    assert from_path.protocol_fingerprint == from_dict.protocol_fingerprint == from_str.protocol_fingerprint == from_bytes.protocol_fingerprint
    assert from_path.canonical_bytes == from_dict.canonical_bytes == from_str.canonical_bytes == from_bytes.canonical_bytes


def test_identity_accepts_valid_authored_prt_id() -> None:
    path = CANONICAL_DIR / "identity_base.json"
    ident = get_protocol_identity(path)
    # Authored PRT-* in identity_base.json must be preserved exactly
    assert ident.protocol_id == "PRT-019a2b3c4d5e6f7a8b9c0d1e2f3a4b5c"


def test_identity_mints_deterministic_prt_id_from_legacy_id() -> None:
    path = VALID_DIR / "scoping_empty_matrix.json"
    raw = _load_json(path)
    assert raw["protocol_id"].startswith("proto-")

    ident1 = get_protocol_identity(path)
    ident2 = get_protocol_identity(path)

    assert ident1.protocol_id.startswith("PRT-")
    assert len(ident1.protocol_id) == len("PRT-") + 32
    # Minting must be deterministic
    assert ident1.protocol_id == ident2.protocol_id

    # Minted ID must equal PRT- + first 32 chars of canonical sha256 digest
    digest = ident1.protocol_fingerprint.removeprefix("sha256:")[:32]
    assert ident1.protocol_id == f"PRT-{digest}"

    # Verify that the underlying protocol fingerprint is unchanged
    model = ResearchProtocol.model_validate(raw)
    assert ident1.protocol_fingerprint == canonical_fingerprint(model)


def test_identity_formatting_invariance() -> None:
    base_path = CANONICAL_DIR / "identity_base.json"
    variant_path = CANONICAL_DIR / "identity_formatting_variant.json"
    expected_sha_path = CANONICAL_DIR / "identity_base.json.sha256"

    ident_base = get_protocol_identity(base_path)
    ident_variant = get_protocol_identity(variant_path)
    expected_fp = expected_sha_path.read_text(encoding="utf-8").strip()

    assert ident_base.protocol_fingerprint == expected_fp
    assert ident_variant.protocol_fingerprint == expected_fp
    assert ident_base.protocol_fingerprint == ident_variant.protocol_fingerprint
    assert ident_base.canonical_bytes == ident_variant.canonical_bytes
    assert ident_base.protocol_id == ident_variant.protocol_id


def test_identity_semantic_sensitivity() -> None:
    base_path = CANONICAL_DIR / "identity_base.json"
    semantic_path = CANONICAL_DIR / "identity_semantic_variant.json"

    ident_base = get_protocol_identity(base_path)
    ident_semantic = get_protocol_identity(semantic_path)

    assert ident_base.protocol_fingerprint != ident_semantic.protocol_fingerprint
    assert ident_base.canonical_bytes != ident_semantic.canonical_bytes

    # Minting from legacy versions of both would also differ
    raw_base = _load_json(base_path)
    raw_semantic = _load_json(semantic_path)
    raw_base["protocol_id"] = "proto-base"
    raw_semantic["protocol_id"] = "proto-semantic"

    minted_base = mint_or_accept_protocol_id(raw_base)
    minted_semantic = mint_or_accept_protocol_id(raw_semantic)
    assert minted_base != minted_semantic


def test_resolve_producer_commit_explicit_and_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # Explicit commit
    assert resolve_producer_commit("1234567890abcdef") == "1234567890abcdef"

    # Environment variable override
    monkeypatch.setenv("SCHOLAR_PROTOCOL_COMMIT", "envcommit1234567890")
    assert resolve_producer_commit() == "envcommit1234567890"

    monkeypatch.delenv("SCHOLAR_PROTOCOL_COMMIT", raising=False)
    monkeypatch.setenv("GIT_COMMIT", "gitcommit0987654321")
    assert resolve_producer_commit() == "gitcommit0987654321"


def test_cli_identity_command_human_and_json() -> None:
    path = CANONICAL_DIR / "identity_base.json"

    # Human output
    result_human = runner.invoke(app, ["identity", str(path)])
    assert result_human.exit_code == 0
    assert "protocol_id: PRT-019a2b3c4d5e6f7a8b9c0d1e2f3a4b5c" in result_human.stdout
    assert "protocol_fingerprint: sha256:4442ddb7e6ee4416371d92256ddfc0e4" in result_human.stdout

    # JSON output
    result_json = runner.invoke(app, ["identity", str(path), "--json"])
    assert result_json.exit_code == 0
    data = json.loads(result_json.stdout)
    assert data["protocol_id"] == "PRT-019a2b3c4d5e6f7a8b9c0d1e2f3a4b5c"
    assert data["protocol_fingerprint"].startswith("sha256:")
    assert data["schema_version"] == "1.0.0"
    assert data["producer"]["package"] == "scholar-protocol-kit"


def test_cli_identity_missing_file_exits_2() -> None:
    result = runner.invoke(app, ["identity", "nonexistent_file.json"])
    assert result.exit_code == 2
