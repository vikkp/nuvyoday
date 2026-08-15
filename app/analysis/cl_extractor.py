"""
CL / CLP / CLLE dependency extractor (ADR0003).

Heuristic, line-oriented. Not a full CL parser.
"""

from __future__ import annotations

import re
from typing import List

from .facts import DependencyFact

_OBJ = r"[A-Z$#@][A-Z0-9_$#@]{0,9}"
_LIB = _OBJ

_RE_CALL_PGM = re.compile(
    rf"\bCALL\s+PGM\s*\(\s*((?:{_LIB}\s*/\s*)?{_OBJ})\s*\)",
    re.IGNORECASE,
)
_RE_CALL_BARE = re.compile(
    rf"\bCALL\s+((?:{_LIB}\s*/\s*)?{_OBJ})\b",
    re.IGNORECASE,
)
_RE_CALLPRC = re.compile(
    rf"\bCALLPRC\s+PRC\s*\(\s*([A-Z$#@][A-Z0-9_$#@]{{0,127}})\s*\)",
    re.IGNORECASE,
)
_RE_CALL_VAR = re.compile(
    r"\bCALL(?:PRC)?\s+(?:PGM\s*\(\s*)?(&[A-Z][A-Z0-9_]{0,31})",
    re.IGNORECASE,
)
_RE_INCLUDE = re.compile(
    rf"\bINCLUDE\s+(?:SRCFILE\s*\(\s*((?:{_LIB}\s*/\s*)?{_OBJ})\s*\)\s*)?"
    rf"(?:SRCMBR\s*\(\s*({_OBJ})\s*\))?",
    re.IGNORECASE,
)
_CMD_VERBS = (
    "SBMJOB", "CLRPFM", "OVRDBF", "DLTF", "CRTPF", "CRTLF", "CRTPRTF",
    "CHKOBJ", "DSPFFD", "DSPFD", "CPYF", "MOVOBJ", "CRTDUPOBJ",
)
_RE_CMD = re.compile(rf"\b({'|'.join(_CMD_VERBS)})\b", re.IGNORECASE)
_RE_FILE_PARM = re.compile(
    rf"\bFILE\s*\(\s*((?:{_LIB}\s*/\s*)?{_OBJ})\s*\)",
    re.IGNORECASE,
)


def _split_lib_name(token: str) -> tuple[str | None, str]:
    token = token.strip().upper().replace(" ", "")
    if "/" in token:
        lib, name = token.split("/", 1)
        return lib, name
    return None, token


def _is_comment(line: str) -> bool:
    s = line.lstrip()
    return s.startswith("/*") or s.startswith("//")


def extract_cl_dependencies(source: str) -> List[DependencyFact]:
    """Extract dependency facts from CL source text."""
    if not source:
        return []

    facts: List[DependencyFact] = []
    seen: set[tuple] = set()

    def add(fact: DependencyFact) -> None:
        key = (
            fact.edge_type,
            fact.target_library or "",
            fact.target_name,
            fact.evidence_line_no,
        )
        if key in seen:
            return
        seen.add(key)
        facts.append(fact)

    for line_no, raw in enumerate(source.splitlines(), start=1):
        line = raw.rstrip("\n")
        if not line.strip() or _is_comment(line):
            continue

        evidence = line.strip()[:256]

        for m in _RE_CALL_VAR.finditer(line):
            expr = m.group(1).upper()
            add(
                DependencyFact(
                    edge_type="CALL",
                    target_name=expr,
                    target_library=None,
                    target_object_type="UNKNOWN",
                    resolved=False,
                    evidence_line_no=line_no,
                    evidence_text=evidence,
                )
            )

        for m in _RE_CALL_PGM.finditer(line):
            lib, name = _split_lib_name(m.group(1))
            add(
                DependencyFact(
                    edge_type="CALL",
                    target_name=name,
                    target_library=lib,
                    target_object_type="PGM",
                    resolved=True,
                    evidence_line_no=line_no,
                    evidence_text=evidence,
                )
            )

        if "CALL PGM" not in line.upper() and "CALLPRC" not in line.upper():
            for m in _RE_CALL_BARE.finditer(line):
                token = m.group(1)
                if token.upper().startswith("PGM"):
                    continue
                lib, name = _split_lib_name(token)
                add(
                    DependencyFact(
                        edge_type="CALL",
                        target_name=name,
                        target_library=lib,
                        target_object_type="PGM",
                        resolved=True,
                        evidence_line_no=line_no,
                        evidence_text=evidence,
                    )
                )

        for m in _RE_CALLPRC.finditer(line):
            name = m.group(1).upper()
            add(
                DependencyFact(
                    edge_type="CALL",
                    target_name=name,
                    target_library=None,
                    target_object_type="MODULE",
                    resolved=True,
                    evidence_line_no=line_no,
                    evidence_text=evidence,
                )
            )

        for m in _RE_FILE_PARM.finditer(line):
            lib, name = _split_lib_name(m.group(1))
            upper = line.upper()
            if any(v in upper for v in ("CLRPFM", "CPYF", "OVRDBF", "DLTF")):
                edge = "FILE_WRITE" if any(v in upper for v in ("CLRPFM", "DLTF")) else "FILE_REF"
            else:
                edge = "FILE_REF"
            add(
                DependencyFact(
                    edge_type=edge,
                    target_name=name,
                    target_library=lib,
                    target_object_type="FILE",
                    resolved=True,
                    evidence_line_no=line_no,
                    evidence_text=evidence,
                )
            )

        m = _RE_CMD.search(line)
        if m:
            verb = m.group(1).upper()
            add(
                DependencyFact(
                    edge_type="CMD",
                    target_name=verb,
                    target_library=None,
                    target_object_type="CMD",
                    resolved=True,
                    evidence_line_no=line_no,
                    evidence_text=evidence,
                )
            )

        for m in _RE_INCLUDE.finditer(line):
            srcfile, srcmbr = m.group(1), m.group(2)
            if srcmbr:
                lib, file_name = (None, None)
                if srcfile:
                    lib, file_name = _split_lib_name(srcfile)
                label = srcmbr.upper()
                if file_name:
                    label = f"{file_name}({srcmbr.upper()})"
                add(
                    DependencyFact(
                        edge_type="INCLUDE",
                        target_name=label[:128],
                        target_library=lib,
                        target_object_type="UNKNOWN",
                        resolved=True,
                        evidence_line_no=line_no,
                        evidence_text=evidence,
                    )
                )

    return facts


def is_cl_source_type(source_type: str | None, source_file: str | None = None) -> bool:
    """Heuristic: is this member CL-like?"""
    st = (source_type or "").upper()
    sf = (source_file or "").upper()
    if st in ("CLP", "CLLE", "CL", "CLE"):
        return True
    if sf in ("QCLSRC",):
        return True
    if "CL" in st:
        return True
    return False
