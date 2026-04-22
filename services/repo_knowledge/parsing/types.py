from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ParsedSymbol:
    """Parsed symbol discovered in a file."""

    subject_type: str
    symbol_name: str
    symbol_qualname: str
    line: int | None = None
    column: int | None = None


@dataclass(slots=True)
class ParsedEdge:
    """Parsed dependency edge generated from AST analysis."""

    edge_type: str
    from_symbol_ref: str | None
    to_symbol_ref: str | None
    from_file: str
    to_file_or_external: str | None
    line: int | None = None
    column: int | None = None
    evidence: str | None = None


@dataclass(slots=True)
class ExternalRef:
    """A reference that could not be resolved to an in-repo subject."""

    ref: str
    ref_type: str


@dataclass(slots=True)
class ParseDiagnostic:
    """Non-fatal parser diagnostic."""

    message: str
    severity: str = "warning"
    line: int | None = None
    column: int | None = None


@dataclass(slots=True)
class ParsedFileGraph:
    """Aggregated parse output for one file."""

    symbols: list[ParsedSymbol] = field(default_factory=list)
    edges: list[ParsedEdge] = field(default_factory=list)
    external_refs: list[ExternalRef] = field(default_factory=list)
    diagnostics: list[ParseDiagnostic] = field(default_factory=list)
