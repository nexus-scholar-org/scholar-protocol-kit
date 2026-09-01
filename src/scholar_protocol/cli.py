"""CLI for scholar-protocol-kit.

Commands
--------
scholar-protocol validate <path> [--strict]
    Validate a protocol.json file.
    Exit 0 = valid (no errors).
    Exit 1 = invalid (errors present, or warnings present with --strict).
    Exit 2 = usage error (bad path, unparseable JSON).

scholar-protocol fingerprint <path>
    Print the canonical sha256:<hex> fingerprint of a protocol.json file.
    Exit 0 = success.  Exit 2 = read/parse failure.

scholar-protocol canon <path>
    Print canonical JSON bytes to stdout.  Useful for diffing generator output
    against golden fixtures.
    Exit 0 = success.  Exit 2 = read/parse failure.
"""

from __future__ import annotations

import json
import pathlib
import sys

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from scholar_protocol.canonical import canonical_fingerprint, canonical_json
from scholar_protocol.models import ResearchProtocol
from scholar_protocol.validate import validate_protocol

app = typer.Typer(
    name="scholar-protocol",
    help="Phase 0 protocol.json validation and canonical serialization toolkit.",
    no_args_is_help=True,
    # Ensure typer.Exit codes propagate correctly when invoked as a module.
    pretty_exceptions_enable=False,
)

console = Console(stderr=True)  # diagnostics → stderr; data (fingerprint, canon) → stdout


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_protocol(path: pathlib.Path) -> ResearchProtocol:
    """Load and parse a protocol.json, exiting with code 2 on failure."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return ResearchProtocol.model_validate(raw)
    except Exception as exc:
        console.print(f"[bold red]Error:[/] Cannot load {path}: {exc}")
        raise typer.Exit(2) from exc


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command()
def validate(
    path: pathlib.Path = typer.Argument(..., help="Path to protocol.json"),
    strict: bool = typer.Option(
        False, "--strict", help="Promote warnings to errors (exit 1 on any warning)"
    ),
) -> None:
    """Validate a protocol.json file against the schema and cross-field rules."""
    if not path.exists():
        console.print(f"[bold red]Error:[/] File not found: {path}")
        raise typer.Exit(2)

    report = validate_protocol(path)

    # Print all findings.
    for finding in report.findings:
        colour = "red" if finding.severity == "error" else "yellow"
        loc_hint = f" [dim]({finding.location})[/dim]" if finding.location else ""
        console.print(
            f"  [{colour}]{finding.severity.upper()}[/] "
            f"[bold]{finding.code}[/]{loc_hint}: {finding.message}"
        )

    # Summary panel.
    n_errors = len(report.errors)
    n_warnings = len(report.warnings)
    if strict:
        ok = report.is_valid_strict()
    else:
        ok = report.is_valid

    status_colour = "green" if ok else "red"
    status_label = "VALID" if ok else "INVALID"
    summary = Text(
        f"{status_label} — {n_errors} error(s), {n_warnings} warning(s)"
        + (" [strict mode]" if strict else ""),
        style=f"bold {status_colour}",
    )
    console.print(Panel(summary, title=str(path), expand=False))

    raise typer.Exit(0 if ok else 1)


@app.command()
def fingerprint(
    path: pathlib.Path = typer.Argument(..., help="Path to protocol.json"),
) -> None:
    """Print the canonical sha256:<hex> fingerprint of a protocol.json."""
    if not path.exists():
        console.print(f"[bold red]Error:[/] File not found: {path}")
        raise typer.Exit(2)

    protocol = _load_protocol(path)
    fp = canonical_fingerprint(protocol)
    # Fingerprint goes to stdout (not stderr) so it can be captured/compared in scripts.
    print(fp)


@app.command()
def canon(
    path: pathlib.Path = typer.Argument(..., help="Path to protocol.json"),
) -> None:
    """Print the canonical JSON bytes of a protocol.json to stdout.

    Useful for diffing generator output against golden fixtures:
        diff <(scholar-protocol canon golden.json) <(scholar-protocol canon generated.json)
    """
    if not path.exists():
        console.print(f"[bold red]Error:[/] File not found: {path}")
        raise typer.Exit(2)

    protocol = _load_protocol(path)
    # Write bytes directly to stdout buffer; no trailing newline per spec.
    sys.stdout.buffer.write(canonical_json(protocol))


if __name__ == "__main__":
    app()
