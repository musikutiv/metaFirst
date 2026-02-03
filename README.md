# metaFirst

A metadata-first Research Data Management system for life sciences. Metadata is collected centrally via RDMP-guided forms; raw data remains on user machines and lab storage.

Licensed under the [MIT License](LICENSE).

## Core Ideas

- **Metadata-first, sample-centric** — samples are the unit of organization; metadata is captured before or during data acquisition
- **RDMPs as enforceable schemas** — Research Data Management Plans define fields, roles, permissions, and visibility
- **No central control of raw data** — files stay where they are; the system tracks references, not copies
- **Event-driven ingest** — file watchers detect new data and prompt for metadata entry in the browser
- **Federated discovery** — cross-project search operates on metadata only; raw data is never exposed

## Concepts

### Labs and Projects

A **lab** represents a research group or organizational unit (e.g., a PI's lab). Projects belong to labs.

- Users are members of labs with roles: **PI**, **STEWARD**, or **RESEARCHER**
- Project visibility is lab-scoped: users only see projects from their labs
- PIs can create projects and manage lab membership
- STEWARDs can create projects and manage operational state
- RESEARCHERs can trigger ingests and access project data

### RDMPs (Research Data Management Plans)

RDMPs define the data governance rules for a project:

- **Fields**: What metadata to collect (name, type, required)
- **Roles**: Who can do what (edit samples, manage RDMP, view data)
- **Visibility**: Per-field access levels (private, collaborators, public_index)

RDMP lifecycle: `DRAFT → ACTIVE → SUPERSEDED`

- Only one ACTIVE RDMP per project at any time
- PI approval required to activate a draft
- New activations move the previous ACTIVE to SUPERSEDED

### Samples and Ingest

A **sample** is the fundamental unit of metadata. Samples are created via:

1. **Manual entry**: Create samples directly in the UI
2. **Ingest workflow**: File watcher detects new data, creates pending ingest, user completes metadata

The ingest helper watches folders for new files and creates pending ingests. Users finalize them via browser, optionally creating or linking samples.

## Status

Active proof-of-principle. Core functionality is implemented; some features (releases, discovery UI) are planned.

## Installation

Install scripts automate setup on macOS/Linux. Run from the repository root.

### Server Setup (group leader / lab admin)

```bash
./scripts/install_supervisor.sh
```

Sets up Python venv, installs dependencies, and seeds demo data if the database is missing. The database is created at `supervisor/supervisor.db`. Prints commands to start the backend API and web UI.

Requirements: Python 3.11+. Node.js 18+ is required only for the web UI (backend works without it).

### User (researcher / data steward)

```bash
./scripts/install_user.sh
```

Sets up Python venv for the ingest helper and creates `config.yaml` from the example if missing. Edit `config.yaml` with your server URL, credentials, and watch paths before running.

The ingest helper is optional. Raw data stays on your machine.

## Quick Start

After installation, start the services:

```bash
# Backend server (terminal 1)
cd supervisor && source venv/bin/activate
uvicorn supervisor.main:app --reload --host 0.0.0.0 --port 8000

# Web UI (terminal 2)
cd supervisor-ui && npm install && npm run dev

# Ingest helper (terminal 3, on user machine)
cd ingest_helper && source venv/bin/activate
python metafirst_ingest.py config.yaml
```

The `--host 0.0.0.0` flag allows access from other machines (required for ingest helpers on user laptops). Use `--host 127.0.0.1` for local-only access.

- API docs: http://localhost:8000/docs
- Web UI: http://localhost:5173
- Demo users: alice, bob, carol, david, eve (password: `demo123`)

## Web UI (local vs remote)

**Local development** (same machine):
```bash
cd supervisor-ui && npm install && npm run dev
```

**Remote access** (other machines connect to the UI):
```bash
cd supervisor-ui && npm install
export VITE_ALLOWED_HOSTS="<HOSTNAME_OR_IP>"
npm run dev -- --host 0.0.0.0 --port 5173
```

Or use the helper script:
```bash
./scripts/start_ui_remote.sh <HOSTNAME_OR_IP>
```

Set `VITE_ALLOWED_HOSTS` to the hostname/IP clients use to connect. Without it, Vite blocks requests with "host not allowed". Ensure port 5173 is reachable (firewall/network).

## Storage Roots

Storage roots are defined per project and represent logical storage locations (e.g., a shared drive, local folder). Ingest watchers reference a storage root by name (preferred) or ID.

Demo seeding creates a `LOCAL_DATA` storage root for each project. For real deployments, create storage roots via the API:
```bash
# List storage roots for a project
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/projects/1/storage-roots/

# Create a new storage root
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name": "LAB_NAS", "description": "Lab network storage"}' \
  http://localhost:8000/api/projects/1/storage-roots/
```

## Common Pitfalls

- **Python too old** — Install scripts require Python 3.11+. Use `PYTHON_BIN=/path/to/python3.12` to override.
- **Server not reachable** — Start uvicorn with `--host 0.0.0.0` for remote access; check firewall on port 8000.
- **Web UI "host not allowed"** — Set `VITE_ALLOWED_HOSTS` to the hostname clients use, or use `./scripts/start_ui_remote.sh`.
- **Login fails (401)** — Check DB exists at `supervisor/supervisor.db`; run `./scripts/install_supervisor.sh --seed` to reseed.
- **Multiple DB files** — The canonical DB is `supervisor/supervisor.db`. Delete any stale `./supervisor.db` in repo root.
- **Storage root not found** — Storage roots are per-project. Demo seeding creates `LOCAL_DATA`; for real projects, create via API.
- **Re-seeding is destructive** — Running `--seed` on existing DB deletes and recreates it. Stop uvicorn first.
- **Discovery push fails** — Set `DISCOVERY_API_KEY` env var before pushing to the discovery index.

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — system design, components, interaction flows
- [ingest_helper/README.md](ingest_helper/README.md) — ingest helper configuration and usage
- [supervisor/supervisor/discovery/](supervisor/supervisor/discovery/) — federated discovery index module
