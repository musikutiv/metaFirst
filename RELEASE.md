# Release Notes

## v0.6.0 — CI and Smoke Test

**Release date:** 2026-02-09

**Operational / Hardening:**
- CI workflow: GitHub Actions runs production build and full test suite on PRs to `main` and `release/*`
- App smoke test: verifies the React tree mounts and renders non-blank UI (prevents blank-page regressions)

---

## v0.5.1 — Patch: Stability and Production Guards

**Release date:** 2026-02-08

Patch release addressing a production blank-page bug and adding minimal
production-readiness guards.

**Fixes:**
- React hooks order violation causing blank page after login (ccb91b7)

**Hardening:**
- Backend startup guard rejects default dev secret key in production mode
- React Error Boundary at app root prevents blank-page failures
- Dev-mode visual banner makes Vite dev usage immediately visible

---

## v0.5.0 — Auditability, Multi-Sample Ingestion, Lab Status

**Release date:** 2026-02-04

**Highlights:**
- Lab Activity Log with required reasons for sensitive actions
- Multi-sample ingestion: one raw file to many samples via RDMP-derived CSV template, with preview, confirm, and transactional creation
- Lab status summary endpoint with needs-attention panel
- Authority hints for role-appropriate action guidance

---

## v0.4.0 — Usability, Onboarding, Remediation UX Polish

**Release date:** 2026-02-04

This release focuses on improving user experience, clarity, and discoverability throughout the application.

**Highlights:**
- Lab terminology consistency (replaced "Supervisor" with "Lab" in all user-facing text)
- Role clarity surfaces with RoleBadge and PermissionHint components
- Project state & RDMP visibility with StatusBadge and ProjectStatusCallout
- Lab onboarding checklist for PI/STEWARD roles
- Advisory remediation tasks with grouped priorities (Urgent/Recommended/Completed)
- Accessibility improvements (keyboard navigation, ARIA attributes, screen reader support)
- Enhanced documentation for roles, RDMP lifecycle, and remediation workflow

**New Components:**
- `RoleBadge` — displays user's current role
- `PermissionHint` — explains restricted actions
- `StatusBadge` — RDMP status indicator
- `ProjectStatusCallout` — actionable guidance based on project state
- `LabOnboardingChecklist` — setup progress tracker
- `RemediationTaskList` — advisory task management
- `ConfirmDialog` — accessible confirmation dialogs

**Testing:**
- 54 tests covering all new components

---

## v0.3.1 — Project Lifecycle and Governance UI

**Release date:** 2026-02-02

Completes the project lifecycle and governance UI.

**Highlights:**
- Create Project wizard with RDMP setup
- Project Settings and RDMP Management pages
- Supervisor member management UI
- Projects Overview dashboard
- Supervisor-scoped project visibility and access
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
