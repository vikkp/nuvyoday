# ADR0002: Source Inventory and Harvesting Strategy

**Date:** 2026-08-14  
**Status:** Accepted  
**Deciders:** Satabdo Dhar (Pandeyji), Grok  
**Tags:** ibm-i, harvesting, data-model, jt400, inventory

---

## Context

Nuvyoday’s core value is turning opaque IBM i source into usable documentation.  
Before we can generate specifications or diagrams we must reliably:

1. Discover libraries and source physical files
2. List members (QCLSRC, QRPGSRC, QDDSSRC, etc.)
3. Extract member source content and key metadata
4. Persist the results so the rest of the application can work offline from the live system

We already decided (ADR0001) to use JT400 via JPype. This ADR defines *how* we use it for inventory and harvesting.

## Decision

### 1. Discovery Approach

We use JT400’s high-level object APIs (not raw CL or SQL catalogs) as the primary path:

- `ObjectList` to list libraries (filtered to user libraries of interest)
- `ObjectList` / `MemberList` to list source physical files (`*FILE` with attribute `PF-SRC`) and their members
- `AS400File` / member APIs (or `IFSFile` where appropriate) to retrieve source content

**Preferred libraries** recorded on the Connection record are used as the starting scope.  
If none are specified, the user can choose libraries interactively.

### 2. Data Model (SQLite)

We keep the model simple and explicit:

| Table            | Purpose                                      |
|------------------|----------------------------------------------|
| `connections`    | Already exists (ADR0001)                     |
| `libraries`      | Discovered libraries for a connection        |
| `source_files`   | Source physical files (`QCLSRC`, etc.)       |
| `source_members` | Individual members + optional source content |

Key fields on `source_members`:

- library, source_file, member, source_type
- text_description, last_changed (from IBM i)
- source_content (nullable – stored after explicit harvest)
- fetched_at, content_hash (for change detection later)
- connection_id (FK)

We deliberately **do not** store the entire system in one go. Harvesting is scoped and on-demand.

### 3. Harvesting Semantics

- **Inventory** = discover libraries → source files → members (metadata only). Fast.
- **Harvest** = pull the actual source text of selected members into SQLite. Explicit action.
- Harvesting is **synchronous** for the MVP (small number of members).  
  A background job model can be added later if customers need bulk overnight runs.
- We always treat the connection as **read-only**. No objects are created or changed on the IBM i side.

### 4. Authority Expectations

The IBM i user profile used by Nuvyoday needs at minimum:

- `*USE` authority on the target libraries and source files
- Ability to open members for read

We document this clearly in the UI and in future packaging notes. We do **not** attempt to escalate authority.

### 5. Change Detection (Lightweight)

For the first version we store `last_changed` from IBM i and a simple content hash when source is harvested.  
Future work can use these fields for incremental re-harvest; we do not implement full incremental logic yet.

## Consequences

### Positive
- Clear separation between “see what exists” (inventory) and “bring the source in” (harvest)
- Data model is easy to query for later call-graph and documentation features
- JT400 ObjectList / MemberList is the most robust and officially supported approach
- Keeps the MVP simple (no job queue required yet)

### Trade-offs
- Full source content can make the SQLite database large on systems with tens of thousands of members → users must choose what to harvest
- Synchronous harvest will feel slow for very large selections → acceptable for MVP; we will revisit with background jobs if needed
- We are dependent on JT400’s object model behaviour across different IBM i releases

### Rejected Alternatives

| Alternative                         | Why rejected                                      |
|-------------------------------------|---------------------------------------------------|
| SQL-only via QSYS2 catalogs         | Incomplete for reliable member source retrieval   |
| Screen-scraping / 5250              | Fragile and unnecessary                           |
| Store every member automatically    | Database bloat and long run times                 |
| Complex job queue in MVP            | Premature complexity                              |

## Implementation Notes

- Extend `app/connection.py` with inventory helpers (`list_libraries`, `list_source_files`, `list_members`, `get_member_source`)
- Add `Library` and `SourceFile` models; evolve `SourceMember`
- New routes under `/inventory` and `/harvest`
- UI: library browser → source file browser → member list with “Harvest” action

---

*Next: implement the inventory + harvesting layer against this decision.*
