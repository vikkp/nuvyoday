"""Orchestrate analysis runs and persist dependency graph (ADR0003)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from .. import db
from ..models import (
    AnalysisRun,
    DependencyEdge,
    DependencyNode,
    SourceMember,
)
from .cl_extractor import extract_cl_dependencies, is_cl_source_type
from .facts import DependencyFact


def _identity_key(
    object_type: str,
    library: Optional[str],
    name: str,
    resolved: bool,
) -> str:
    lib = (library or "").upper()
    return f"{object_type}|{lib}|{name.upper()}|{'1' if resolved else '0'}"


def _get_or_create_node(
    connection_id: int,
    object_type: str,
    library: Optional[str],
    name: str,
    resolved: bool,
) -> DependencyNode:
    key = _identity_key(object_type, library, name, resolved)
    node = DependencyNode.query.filter_by(
        connection_id=connection_id,
        identity_key=key,
    ).first()
    if node:
        return node
    node = DependencyNode(
        connection_id=connection_id,
        object_library=(library.upper() if library else None),
        object_name=name.upper() if resolved else name,
        object_type=object_type,
        is_resolved=resolved,
        identity_key=key,
    )
    db.session.add(node)
    db.session.flush()
    return node


def _facts_for_member(member: SourceMember) -> list[DependencyFact]:
    content = member.source_content or ""
    if is_cl_source_type(member.source_type, member.source_file):
        return extract_cl_dependencies(content)
    if member.source_file and member.source_file.upper() == "QCLSRC":
        return extract_cl_dependencies(content)
    return extract_cl_dependencies(content) if content else []


def analyze_member(member: SourceMember) -> AnalysisRun:
    """
    Run extractors on one harvested member and store nodes/edges.
    Replaces previous edges for this member from older runs (simple MVP strategy).
    """
    if not member.is_harvested:
        raise ValueError("Member has not been harvested yet")

    run = AnalysisRun(
        connection_id=member.connection_id,
        scope_type="member",
        library=member.library,
        source_file=member.source_file,
        member=member.member,
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    db.session.add(run)
    db.session.flush()

    try:
        old_edges = DependencyEdge.query.filter_by(
            connection_id=member.connection_id,
            source_member_id=member.id,
        ).all()
        for e in old_edges:
            db.session.delete(e)
        db.session.flush()

        from_node = _get_or_create_node(
            member.connection_id,
            "PGM",
            member.library,
            member.member,
            True,
        )

        facts = _facts_for_member(member)
        edge_count = 0
        for fact in facts:
            to_node = _get_or_create_node(
                member.connection_id,
                fact.target_object_type,
                fact.target_library,
                fact.target_name,
                fact.resolved,
            )
            edge = DependencyEdge(
                connection_id=member.connection_id,
                analysis_run_id=run.id,
                from_node_id=from_node.id,
                to_node_id=to_node.id,
                edge_type=fact.edge_type,
                source_member_id=member.id,
                evidence_line_no=fact.evidence_line_no,
                evidence_text=(fact.evidence_text or "")[:256],
                resolved=fact.resolved,
            )
            db.session.add(edge)
            edge_count += 1

        run.status = "completed"
        run.finished_at = datetime.now(timezone.utc)
        run.stats_json = json.dumps(
            {
                "facts": edge_count,
                "extractor": "cl",
                "source_type": member.source_type,
            }
        )
        db.session.commit()
        return run
    except Exception as e:
        run.status = "failed"
        run.finished_at = datetime.now(timezone.utc)
        run.error_message = str(e)[:1000]
        db.session.commit()
        raise
