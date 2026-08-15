# ADR0001: Core Architecture and Deployment Model

**Date:** 2026-08-14  
**Status:** Accepted  
**Deciders:** Satabdo Dhar (Pandeyji), Grok  
**Tags:** architecture, deployment, ibm-i, on-prem, product-positioning

---

## Context

Nuvyoday was created to solve a real and painful problem: organizations still running critical business logic on legacy IBM i (AS/400) green-screen systems often cannot modernize because the knowledge is locked inside undocumented CL, RPG, and related source members. The original workforce is aging, protective, and frequently unwilling or unable to produce clean technical and functional specifications.

The product needs to:

- Connect to real IBM i systems
- Inventory and extract source (QCLSRC, QRPGSRC, QDDSSRC, etc.)
- Build mapping diagrams and dependency information
- Generate usable technical + functional specifications that unblock migration projects (especially toward modern ERPs such as Microsoft Dynamics)

At the same time, the product must fit naturally into the existing iVistaar ecosystem and the way customers already operate.

## Decision

### 1. Product Name
**Nuvyoday** (“a new sunrise”).

The name deliberately signals a fresh start for teams stuck with green-screen systems.

### 2. Primary Runtime & Stack
- **Language / Framework:** Python 3.11+ with Flask
- **Persistence:** SQLite (local, per-installation)
- **IBM i Connectivity:** JT400 (IBM Toolbox for Java / JTOpen) accessed from Python via **JPype**
- **Credential Storage:** Encrypted at rest using Fernet (key derived from `FLASK_SECRET_KEY`)

This combination gives us:
- Full power of JT400 (ObjectList, CommandCall, source member access, program references, etc.)
- A lightweight, easy-to-deploy Python web application
- No external database dependency for the initial product

### 3. Deployment Model (Critical Decision)

| Mode              | Purpose                                      | Where it runs                                      |
|-------------------|----------------------------------------------|----------------------------------------------------|
| **Real Product**  | Full functionality + live IBM i connectivity | Customer premises via **iVistaar** on IIS (or local `python run.py`) |
| **Public Demo**   | UI preview only                              | Static site on Cloudflare Pages (`nuvyoday.ivistaar.com`) |

**Key principle:**  
Nuvyoday is an **on-premises tool**. It is designed to run *inside* the customer’s network so it can reach internal IBM i systems securely. It is **not** a multi-tenant public SaaS.

This decision was driven by:
- Network reality (most IBM i systems are not internet-exposed)
- Security and compliance expectations
- Alignment with iVistaar’s existing “deploy on your IIS” model
- The need for a JVM (JT400 via JPype), which is impractical on Cloudflare Workers / Pages

### 4. Public Demo Strategy
A pure static HTML/CSS version lives in the `/demo` folder.  
It re-uses the same visual design language and shows realistic sample data, but contains no backend, no JT400, and no real credentials.

Cloudflare Pages is configured with:
- Build output directory = `demo`
- No build command required

### 5. Visual Identity
The UI color system is deliberately matched to iVistaar:

- Primary / Brand: Deep burgundy (`#9B1B1B`)
- Accent / CTA: Warm orange (`#F97316`)
- Background: Soft cream (`#FFF7ED`)

This keeps Nuvyoday visually consistent with the parent product family.

### 6. Repository & Packaging
- GitHub: `https://github.com/vikkp/nuvyoday`
- The real Flask application is the primary artifact
- The static demo is a secondary, lightweight artifact for marketing and early feedback

## Consequences

### Positive
- Clear separation of concerns (real product vs. public demo)
- Strong alignment with how customers already deploy software via iVistaar
- JT400 gives us the richest possible access to IBM i objects and source
- Simple local development and testing experience
- Easy to explain the value proposition: “It runs where your IBM i lives”

### Negative / Trade-offs
- Cannot offer a true multi-tenant hosted version without significant architectural change
- Customers must have Java available (for JPype + JT400)
- SQLite is excellent for single-tenant on-prem use but would need replacement for any future multi-user hosted scenario
- Public demo cannot demonstrate live IBM i connectivity (by design)

### Neutral
- Future inventory, harvesting, and specification-generation features will be built only in the real (Flask) application
- The static demo will be updated only when we want to show new UI concepts

## Alternatives Considered

| Alternative                        | Why Rejected                                                                 |
|------------------------------------|------------------------------------------------------------------------------|
| Full SaaS on Cloudflare / Render   | IBM i systems are almost never internet-reachable; JT400 + JVM not viable on Cloudflare Workers |
| Pure ODBC / pyodbc only            | Insufficient for reliable source-member extraction and rich object metadata  |
| Electron / desktop app             | Overkill; browser-based local app via iVistaar is simpler and fits existing tooling |
| Hosted multi-tenant with VPN tunnels | High complexity and support burden; not required for the current market     |

## Follow-up Decisions (Future ADRs)
- Source harvesting strategy and data model
- Call-graph / dependency analysis approach
- Specification generation format and templates
- How Nuvyoday will be packaged and distributed through iVistaar

---

*This ADR records the foundational decisions made during the initial design sessions on 2026-08-14.*
