# Release Notes

## v0.4.0 — Lab Terminology (WIP)

**Status:** In development

**Summary:** Terminology migration: Supervisor → Lab (backward compatible)

- All user-facing text now uses "Lab" instead of "Supervisor"
- Documentation updated to use "Lab" terminology
- API endpoints, config keys, and CLI flags remain unchanged for backward compatibility
- Legacy `supervisor*` inputs continue to work with deprecation warnings

---

## v0.3.1 — Project Lifecycle and Governance UI

**Release date:** 2026-02-02

Completes the project lifecycle and governance UI. See [RELEASE_NOTES_v0.3.1.md](RELEASE_NOTES_v0.3.1.md) for full details.

**Highlights:**
- Create Project wizard with RDMP setup
- Project Settings and RDMP Management pages
- Lab member management UI
- Projects Overview dashboard
- Lab-scoped project visibility and access
- Sample ID extraction rules with detection panel
- Paginated samples API with performance improvements
- Demo seed creates operational projects with ACTIVE RDMPs

---

## v0.3.0 — Metadata Visibility and Soft Enforcement

**Release date:** 2026-01-31

Adds metadata visibility controls and RDMP soft enforcement with remediation tasks.

**Highlights:**
- Per-field visibility levels (private, collaborators, public_index)
- Discovery access control respects visibility settings
- RDMP soft enforcement flags incomplete samples
- Remediation task workflow for data stewards

---

## v0.2.0 — Multi-Tenant Architecture

**Release date:** 2026-01-30

Introduces supervisor-scoped roles and project-only RDMPs.

**Highlights:**
- Supervisor entity with PI/STEWARD/RESEARCHER roles
- Per-supervisor operational databases
- Project-only RDMPs with lifecycle (DRAFT → ACTIVE → SUPERSEDED)
- Ingest run provenance with RDMP link

---

## v0.1.0 — Foundational Proof of Principle

**Release date:** 2025-01-30

This is the first tagged release of metaFirst, a metadata-first Research Data Management system for life sciences.

### What Works

- **Supervisor backend** (FastAPI + SQLite)
  - JWT authentication with role-based access
  - Project and membership management
  - RDMP templates with versioning
  - Sample and field value CRUD with validation
  - Storage roots and raw data references
  - Pending ingest workflow for browser-based metadata entry
  - Federated discovery index (API-only)

- **Web UI** (React + Vite)
  - Project selection and sample table
  - RDMP-driven dynamic columns
  - Pending ingest form

- **Ingest helper** (Python)
  - Folder watching with watchdog
  - Name-based project/storage root resolution
  - Browser deep-linking for metadata entry

- **Installation scripts**
  - Automated setup for supervisor and user environments
  - Demo data seeding with storage roots

### What Is Intentionally Missing

- **Release management** — Immutable snapshots and release corrections are planned but not implemented.
- **Discovery web UI** — The discovery index has API endpoints only; no web interface yet.
- **Production deployment** — This is a proof-of-principle; hardening for production is future work.

### Known Limitations (PoP / Unstable)

- SQLite is the only supported database (suitable for single-node deployment).
- No automated backup or migration tooling.
- Discovery index is embedded in the supervisor; extraction to standalone service is planned.
- RDMP field validation is basic; complex constraints are not enforced.

### Getting Started

```bash
# Clone and install
git clone <repo-url>
cd metaFirst
./scripts/install_supervisor.sh

# Start supervisor
cd supervisor && source venv/bin/activate
uvicorn supervisor.main:app --reload --host 0.0.0.0 --port 8000

# Start UI (separate terminal)
cd supervisor-ui && npm install && npm run dev

# Demo login: alice / demo123
```

See [README.md](README.md) for full documentation.
