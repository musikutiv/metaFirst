# Release Notes

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
