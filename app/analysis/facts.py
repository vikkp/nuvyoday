"""Shared dependency fact structure emitted by extractors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class DependencyFact:
    """One directed dependency found in source text."""

    edge_type: str  # CALL, CMD, FILE_READ, FILE_WRITE, FILE_REF, INCLUDE
    target_name: str
    target_library: Optional[str] = None
    target_object_type: str = "UNKNOWN"  # PGM, FILE, CMD, ...
    resolved: bool = True
    evidence_line_no: Optional[int] = None
    evidence_text: str = ""
