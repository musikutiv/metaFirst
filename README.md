# metaFirst

A metadata-first Research Data Management system for life sciences. Metadata is collected centrally via RDMP-guided forms; raw data remains on user machines and lab storage.

## Core Ideas

- **Metadata-first, sample-centric** — samples are the unit of organization; metadata is captured before or during data acquisition
- **RDMPs as enforceable schemas** — Research Data Management Plans define fields, roles, permissions, and visibility
- **No central control of raw data** — files stay where they are; the system tracks references, not copies
- **Event-driven ingest** — file watchers detect new data and prompt for metadata entry in the browser
- **Federated discovery** — cross-project search operates on metadata only; raw data is never exposed

## Status

Active proof-of-principle. Core functionality is implemented; some features (releases, discovery UI) are planned.

## Installation

Install scripts automate setup on macOS/Linux. Run from the repository root.

### Supervisor (group leader / lab admin)

```bash
./scripts/install_supervisor.sh
```

Sets up Python venv, installs dependencies, and seeds demo data if the database is missing. Prints commands to start the backend API and web UI.

Requirements: Python 3.11+, Node.js 18+ (for web UI)

### User (researcher / data steward)

```bash
./scripts/install_user.sh
```

Sets up Python venv for the ingest helper and creates `config.yaml` from the example if missing. Edit `config.yaml` with your supervisor URL, credentials, and watch paths before running.

The ingest helper is optional. Raw data stays on your machine.

## Quick Start

After installation, start the services:

```bash
# Supervisor backend (terminal 1)
cd supervisor && source venv/bin/activate
uvicorn supervisor.main:app --reload --port 8000

# Web UI (terminal 2)
cd supervisor-ui && npm install && npm run dev

# Ingest helper (terminal 3, on user machine)
cd ingest_helper && source venv/bin/activate
python metafirst_ingest.py config.yaml
```

- API docs: http://localhost:8000/docs
- Web UI: http://localhost:5173
- Demo users: alice, bob, carol, david, eve (password: `demo123`)

## Common Issues

**Python too old**
The install scripts require Python 3.11+. If your system Python is older:
- Homebrew (macOS): `brew install python@3.12`
- Conda: `conda create -n metafirst python=3.12 && conda activate metafirst`
- Override: `PYTHON_BIN=/path/to/python3.12 ./scripts/install_supervisor.sh`

**Cannot reach supervisor from another machine**
By default uvicorn binds to localhost only. To allow external connections:
```bash
uvicorn supervisor.main:app --reload --host 0.0.0.0 --port 8000
```

**Ingest helper 404 on /api/projects**
Fixed in latest version. Pull the latest code and reinstall:
```bash
git pull && ./scripts/install_user.sh
```

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — system design, components, interaction flows
- [ingest_helper/README.md](ingest_helper/README.md) — ingest helper configuration and usage
- [supervisor/supervisor/discovery/](supervisor/supervisor/discovery/) — federated discovery index module
