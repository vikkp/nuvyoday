# ADR0003: Call Graph and Dependency Mapping

**Date:** 2026-08-14  
**Status:** Accepted  
**Deciders:** Satabdo Dhar (Pandeyji), Grok  
**Tags:** ibm-i, call-graph, dependencies, parsing, cl, rpg

---

## Context

After inventory and harvesting (ADR0002), Nuvyoday has member metadata and optional source text in SQLite. The next value step is understanding **how programs relate to each other** and to files — the call graph and dependency map that domain experts carry in their heads.

Migration and documentation projects need answers such as:

- What does this CL program call?
- Which RPG programs update this file?
- What is the blast radius if we change program X?
- What is a sensible order for reverse-engineering a subsystem?

We need a strategy that works on real legacy source (often messy, multi-dialect, decades old) without requiring a perfect IBM i compiler frontend.

## Decision

### 1. Goal

Build a **directed dependency graph** from harvested source:

- **Nodes:** programs, modules, service programs, commands, and data objects (files, data areas) referenced in source
- **Edges:** typed relationships (calls, file use, includes, etc.) with optional evidence (source line, member)

The graph is stored in SQLite and queryable for UI and later specification generation (ADR0004).

### 2. Analysis is offline and harvest-driven

- Analysis runs **only on source already harvested** into SQLite (no live IBM i required at analysis time).
- Trigger: explicit user action (“Analyze” on a member, library, or connection scope) for MVP.
- Re-run when source is re-harvested (content hash change can mark edges stale later).

### 3. Language coverage (phased)

| Phase | Source types | Priority |
|-------|----------------|----------|
| **MVP** | CL / CLP / CLLE | Highest — orchestration layer, easy patterns |
| **MVP** | RPG / RPGLE (free + fixed, best-effort) | High — business logic |
| **Later** | DDS (PF/LF/DSPF/PRTF) for file/record structure | Medium |
| **Later** | CMD, SQLRPGLE, CBL, etc. | As needed |

MVP optimizes for **useful, explainable edges**, not 100% language coverage.

### 4. Extraction approach: structured heuristics, not a full compiler

**MVP uses line-oriented / regex-assisted extractors** per source type, not a full RPG/CL parser.

Rationale:

- Legacy source mixes fixed and free form, copy books, and non-standard style
- Full parsers are large, version-sensitive, and slow to productize
- Spec generation needs “good enough” maps with **evidence lines**, not formal verification

Each extractor:

1. Reads `source_members.source_content`
2. Emits zero or more **dependency facts** (from → to, type, evidence)
3. Is deterministic and side-effect free

We accept false positives/negatives and document confidence later if needed.

### 5. Edge types (MVP)

| Type | Meaning | Typical sources |
|------|---------|-----------------|
| `CALL` | Program / procedure call | CL `CALL`, `CALLPRC`; RPG `CALL`, `CALLB`, `CALLP` |
| `CMD` | Command invocation | CL command lines (best-effort) |
| `FILE_READ` | File used for input | RPG F-spec / `dcl-f` with input-ish mode |
| `FILE_WRITE` | File used for output/update | RPG F-spec / `dcl-f` with output/update |
| `FILE_REF` | File referenced, mode unclear | Fallback |
| `INCLUDE` | Copy book / include | `/COPY`, `/INCLUDE`, CL `INCLUDE` where visible |

Unresolved targets (variables used as program names) are stored as **unresolved** with the expression text; we do not invent library/object names.

### 6. Data model

New tables (conceptual):

**`analysis_runs`**
- id, connection_id, scope (member / source_file / library), started_at, finished_at, status, stats JSON

**`dependency_nodes`**
- id, connection_id
- object_library (nullable), object_name, object_type (`PGM`, `MODULE`, `SRVPGM`, `FILE`, `CMD`, `UNKNOWN`)
- unique per connection + identity key

**`dependency_edges`**
- id, connection_id, analysis_run_id
- from_node_id, to_node_id
- edge_type (see above)
- source_member_id (FK to `source_members`)
- evidence_line_no, evidence_text
- resolved (bool) — whether target was a literal object name

Graph queries join these tables; UI can show “callers of X” and “callees of X”.

### 7. Resolution rules (MVP)

- Literal names in quotes or bare tokens that look like IBM i object names (≤10 chars, valid charset) → **resolved** nodes.
- Library qualification (`LIB/OBJ` or `*LIBL`) recorded when present; otherwise library null / `*LIBL`.
- Dynamic calls (`CALL &PGM`) → edge to an **unresolved** node labeled with the expression; no fake PGM node.

### 8. UI (MVP)

- On a harvested member: **Analyze** → show outbound dependencies for that member.
- Simple list first (type, target, evidence). Graph visualization can follow.
- Optional: “Analyze all harvested members in this source file / library”.

### 9. Non-goals (MVP)

- Exact ILE binding directory expansion
- Runtime call stack / debug-based graphs
- Guaranteed completeness for all RPG fixed-form edge cases
- Automatic impact analysis workflows (can build on this graph later)

## Consequences

### Positive

- Unblocks documentation and migration questions without live compiler integration
- Works entirely from harvested SQLite data (fits on-prem / offline analysis)
- Incremental: CL extractor first, then RPG, then DDS
- Evidence lines keep results auditable for skeptical IBM i experts

### Trade-offs

- Heuristic parsing will miss or misclassify some constructs
- Dynamic calls remain unresolved by design
- Large codebases need batch analysis UX (progress, partial results) later

### Rejected alternatives

| Alternative | Why rejected for now |
|-------------|----------------------|
| Full RPG/CL compiler frontend | Cost and complexity too high for current stage |
| Live IBM i cross-reference (OUTFILE / DSPPGMREF only) | Useful complement later; does not replace source-level evidence and fails when objects are missing; we may add as **enrichment** in a future ADR |
| Only DSPPGMREF / object-level xref | Misses source-only insight and requires broader object authority; keep as optional later enhancement |
| Store graph only in memory | Must persist for specs and repeated UI queries |

## Implementation notes

1. Package under `app/analysis/` (e.g. `cl_extractor.py`, `rpg_extractor.py`, `service.py`).
2. Persist nodes/edges via new SQLAlchemy models.
3. Route: analyze member / scope; template for dependency list.
4. Prefer testable pure functions: `extract_cl_dependencies(text) -> list[Fact]`.
5. After MVP extractors are stable, revisit visualization and DSPPGMREF enrichment.

## Follow-ups

- ADR0004 — Specification generation (consumes inventory + this graph)
- Future ADR — Object-level xref enrichment (DSPPGMREF / similar) as optional second channel
- Future ADR — Graph visualization and impact “blast radius” views

---

*Next: implement MVP CL (then RPG) extractors and dependency storage against this decision.*
