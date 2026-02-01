# Architecture

This document describes the system design, components, and interaction flows of the metaFirst Research Data Management system.

## Overview

metaFirst implements a **metadata-first** approach to research data management:

- **Metadata is centralized**: A single supervisor service stores and manages all project metadata, sample records, and field values.
- **Raw data is decentralized**: Files remain on user machines or lab storage. The system tracks file locations via storage roots and relative paths but never moves, copies, or accesses raw data.
- **RDMPs are authoritative**: Research Data Management Plans define required fields, roles, permissions, and visibility policies. All enforcement derives from the active RDMP.
- **Federation is metadata-only**: Cross-project discovery operates on indexed metadata. Raw data locations are never exposed to the discovery layer.

## Components

### Supervisor Service

The central backend service (FastAPI + SQLite).

**Responsibilities:**
- Store and serve project metadata, samples, and field values
- Enforce RDMP-defined validation and permissions
- Manage user authentication (JWT) and project memberships
- Track raw data references (storage roots, relative paths)
- Maintain audit logs for all state changes
- Host the federated discovery index (currently embedded, extractable later)

**Key APIs:**
- `/api/auth` — authentication
- `/api/projects` — project and membership management
- `/api/rdmp` — RDMP templates and versioning
- `/api/samples` — sample and field value CRUD
- `/api/storage-roots`, `/api/raw-data` — storage root mappings and raw data references
- `/api/discovery` — federated metadata search (API-only)

### Supervisor UI

A React + Vite frontend for metadata viewing and entry.

**Capabilities:**
- Project selection and sample table view
- RDMP-driven dynamic columns
- Completeness indicators for required fields
- Pending ingest form for browser-based metadata entry

### User Machines and Ingest Helper

Raw data files reside on user machines (workstations, lab servers, NAS). The system does not control or access these machines directly.

**Ingest Helper** is a Python tool that runs locally on user machines:
- Watches configured folders for new files (using watchdog)
- Creates pending ingest records in the supervisor when files appear
- Optionally opens the browser for metadata entry
- Resolves project/storage root by name or ID

The ingest helper is a convenience tool, not a required component. Users can also register files via direct API calls.

**Supervisor Scoping (v0.2+)**: Each ingestor instance is bound to exactly one supervisor. Projects from other supervisors are rejected at ingest time. To ingest for multiple supervisors, run separate ingestor instances with different configs.

### Storage Roots

A **storage root** is a named reference to a storage location (e.g., "Lab NAS", "Local SSD"). Each user maps storage roots to their local mount paths.

**Example:**
- Storage root "Lab NAS" exists in project 1
- Alice maps it to `/Volumes/labnas/`
- Bob maps it to `/mnt/nas/`
- A file at `/Volumes/labnas/experiment1/data.csv` on Alice's machine is stored as `relative_path: experiment1/data.csv` with `storage_root_id: 1`

This indirection allows the same logical file reference to resolve to different physical paths on different machines.

### Federated Discovery Index

A metadata-only search index for cross-project discovery.

**Current implementation:**
- Embedded within the supervisor as a separate SQLite database (`discovery.db`)
- Push API accepts metadata records with visibility levels (PUBLIC, REGISTERED, PRIVATE)
- Search API returns matching records respecting visibility policies
- No web UI yet (API-only by design for validation phase)

**Design intent:**
- Can be extracted to a standalone service later
- Multiple supervisor instances can push to a shared discovery index
- Raw data is never indexed or accessible via discovery

## Interaction Flows

### Ingest Flow

1. User drops a file into a watched folder on their machine
2. Ingest helper detects the file and computes its relative path from the storage root
3. Ingest helper calls `POST /api/projects/{id}/pending-ingests` with file metadata
4. Supervisor creates a pending ingest record
5. User completes metadata entry via browser (or API)
6. Supervisor finalizes the ingest, creating a raw data item linked to a sample

### Local Metadata Management

1. User authenticates via `/api/auth/login`
2. User retrieves project RDMP via `/api/rdmp/projects/{id}/rdmp`
3. RDMP defines available fields, required fields, and user permissions
4. User creates/updates samples and field values via `/api/samples` endpoints
5. All changes are validated against RDMP rules and logged in the audit trail

### Federated Discovery

1. Supervisor (or CLI tool) pushes sample metadata to `/api/discovery/push` with visibility level
2. Discovery index stores metadata with origin tracking (origin, project_id, sample_id)
3. External users search via `/api/discovery/search?q=...&visibility=PUBLIC`
4. Search results include provenance (origin, IDs) for tracing back to source
5. Raw data is never exposed; only metadata is searchable

## Design Principles

### No Central Control Over Data or Machines

The supervisor manages metadata only. It has no access to user machines, cannot read raw data files, and does not control where data is stored. Users retain full ownership of their data.

### RDMP-Guided Metadata Enforcement

All validation, permissions, and visibility rules derive from the active RDMP:
- **Fields**: RDMPs define which fields exist, their types, and whether they're required
- **Roles**: RDMPs define roles (PI, researcher, steward, viewer) and their permissions
- **Visibility**: RDMPs define per-field visibility (private, collaborators, public_index)

Changing an RDMP creates a new version. Old samples remain valid; new requirements flag them as incomplete rather than invalid.

### Federation Via Metadata, Not Data

Cross-project discovery operates entirely on metadata:
- Only metadata marked with appropriate visibility is indexed
- Raw data locations are not exposed to discovery
- Discovery results link back to originating supervisors for data access
- No central authority controls what gets indexed; each supervisor decides what to push

### API-First Architecture

All functionality is exposed via REST APIs:
- The UI is a client of the API, not a privileged component
- External tools (ingest helper, CLI utilities) use the same APIs
- Federation uses standard HTTP push/pull patterns
- No proprietary protocols or binary formats

## Data Model Summary

### Core Entities

| Entity | Purpose |
|--------|---------|
| User | Authentication and identity |
| Project | Container for samples, RDMPs, and memberships |
| Membership | Links users to projects with roles |
| RDMPVersion | Versioned RDMP definitions per project |
| Sample | Individual sample records within a project |
| SampleFieldValue | EAV-style field values for samples |

### Storage Entities

| Entity | Purpose |
|--------|---------|
| StorageRoot | Named storage location within a project |
| StorageRootMapping | User-specific local path for a storage root |
| RawDataItem | Reference to a file (storage root + relative path) |
| PathChange | Audit trail for path updates |

### Discovery Entities

| Entity | Purpose |
|--------|---------|
| IndexedSample | Metadata record in the discovery index |

### Operational Entities (v0.2+)

| Entity | Purpose | Database |
|--------|---------|----------|
| Supervisor | Tenant/organization unit | Central |
| SupervisorMembership | Links users to supervisors with roles | Central |
| IngestRun | Record of ingest operations | Per-supervisor |
| Heartbeat | Ingestor health status | Per-supervisor |

## Authorization (v0.2+)

metaFirst uses a two-level authorization model:

### Supervisor-Level Roles

Users are assigned one of three roles per supervisor via `SupervisorMembership`:

| Role | Description | Permissions |
|------|-------------|-------------|
| **PI** | Principal Investigator | Full authority. Can update supervisor config, create projects, trigger ingest runs, assign primary steward, manage all roles. |
| **STEWARD** | Data Steward | Operational responsibility. Can update supervisor config, create projects, trigger ingest runs, manage operational state. |
| **RESEARCHER** | Researcher | Can trigger ingest runs, access supervisor resources. Cannot create projects or modify supervisor config. |

Each supervisor has exactly one **primary steward** (`primary_steward_user_id`), typically assigned the PI role. The primary steward has ultimate responsibility for data governance.

### Project-Level Roles

Within projects, roles are defined by RDMPs and managed via `Membership`:
- PI, researcher, steward, viewer (project-scoped)
- Permissions like `can_manage_rdmp`, `can_edit_paths` are derived from project memberships

### Authorization Flow

1. **Supervisor operations** (update supervisor config) check supervisor memberships
2. **Project operations** (create samples, edit fields) check project memberships
3. **Creating projects** requires STEWARD or PI role at supervisor level
4. **Triggering ingest runs** requires RESEARCHER, STEWARD, or PI role at supervisor level
5. **Updating supervisor config** requires STEWARD or PI role

### Authorization Helpers

The API uses helper functions in `supervisor/api/deps.py`:

```python
# Check user has any role for a supervisor
require_any_supervisor_role(db, user, supervisor_id)

# Check user has specific roles
require_supervisor_role(db, user, supervisor_id, [SupervisorRole.PI, SupervisorRole.STEWARD])
```

## Database Architecture (v0.2+)

metaFirst uses a two-tier database architecture:

### Central Database

Stores core metadata shared across the system:
- Users, authentication, memberships
- Supervisors and their configuration
- Projects, samples, field values
- Storage roots and raw data references
- RDMPs and templates
- Audit logs

Location: `supervisor/supervisor.db` (SQLite)

### Per-Supervisor Operational Databases

Each supervisor has its own operational database for runtime state:
- Ingest run history (start/end times, file counts, errors)
- Ingestor heartbeats (health status, last seen)
- Log pointers (future: links to detailed log files)

Location: Configured via `supervisor.supervisor_db_dsn`
- Default: `supervisor/supervisor_{id}_ops.db`
- Can be any SQLite file or PostgreSQL database

### Why Separate Databases?

1. **Operational isolation**: One supervisor's runtime state doesn't affect another
2. **Scalability**: High-frequency operational writes don't compete with metadata reads
3. **Security**: Operational access can be restricted per-supervisor
4. **Maintenance**: Operational DBs can be cleared/archived independently

### CLI Commands

```bash
# List all supervisors and their operational DB status
python -m supervisor.cli supervisor-db list

# Check status of a supervisor's operational DB
python -m supervisor.cli supervisor-db status --supervisor 1

# Initialize a supervisor's operational DB
python -m supervisor.cli supervisor-db init --supervisor 1
python -m supervisor.cli supervisor-db init --supervisor 1 --dsn "postgresql://user:pass@host/db"
```

### API Endpoints

Operational state is accessed via `/api/ops/`:
- `POST /api/ops/projects/{id}/runs` - Create ingest run
- `GET /api/ops/projects/{id}/runs` - List ingest runs
- `POST /api/ops/supervisors/{id}/heartbeats` - Record heartbeat
- `GET /api/ops/supervisors/{id}/heartbeats` - List heartbeats

## Project Structure

```
metaFirst/
├── supervisor/                 # Central FastAPI service
│   ├── supervisor/
│   │   ├── api/               # REST API endpoints
│   │   ├── models/            # SQLAlchemy ORM models
│   │   ├── schemas/           # Pydantic request/response schemas
│   │   ├── services/          # Business logic
│   │   ├── discovery/         # Federated discovery module
│   │   └── utils/             # Security, validation
│   ├── tools/                 # CLI utilities
│   └── tests/                 # Test suite
│
├── supervisor-ui/             # React frontend
│   └── src/
│       ├── components/        # UI components
│       └── api/               # API client
│
├── ingest_helper/             # User-side file watcher
│   ├── metafirst_ingest.py    # Main script
│   └── config.example.yaml    # Configuration template
│
└── demo/                      # Demo data and seeding
    ├── seed.py
    └── rdmp_templates/
```

## Implementation Status

### Implemented

- JWT authentication and authorization
- Project, membership, and RDMP management
- Sample and field value CRUD with validation
- Storage roots, mappings, and raw data references
- Path change tracking with audit
- Ingest helper with browser-based metadata entry
- Metadata viewer UI
- Federated discovery index (API-only)
- Supervisor-scoped roles (PI, STEWARD, RESEARCHER)
- Primary steward designation per supervisor
- Per-supervisor operational databases (ingest runs, heartbeats)

### Planned

- Release management (immutable snapshots)
- Release corrections (linked new releases)
- Discovery web UI
