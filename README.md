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

Sets up Python venv, installs dependencies, and seeds demo data if the database is missing. The database is created at `supervisor/supervisor.db`. Prints commands to start the backend API and web UI.

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

## Common Issues

**Python too old**
The install scripts require Python 3.11+. If your system Python is older:
- Homebrew (macOS): `brew install python@3.12`
- Conda: `conda create -n metafirst python=3.12 && conda activate metafirst`
- Override: `PYTHON_BIN=/path/to/python3.12 ./scripts/install_supervisor.sh`

**Cannot reach supervisor from another machine**
If login works on the supervisor host but not from another machine, check:
- uvicorn is started with `--host 0.0.0.0` (not `127.0.0.1` or omitted)
- Firewall allows incoming connections on port 8000

**Ingest helper 404 on /api/projects**
Fixed in latest version. Pull the latest code and reinstall:
```bash
git pull && ./scripts/install_user.sh
```

**Login fails with 401 after installation**
The database lives at `supervisor/supervisor.db`. If login fails:
1. Check the DB exists: `ls -la supervisor/supervisor.db`
2. Verify users were seeded: run `./scripts/install_supervisor.sh --seed`
3. Start uvicorn from the `supervisor/` directory (the default)

To use a different database location, set `DATABASE_URL`:
```bash
DATABASE_URL=sqlite:///path/to/my.db uvicorn supervisor.main:app --reload --port 8000
```

**Multiple database files / wrong database used**
Older versions used a relative path that created `supervisor.db` in whichever directory you ran uvicorn from. The current version uses an absolute path to `supervisor/supervisor.db` regardless of working directory. If you have a stale `./supervisor.db` in the repo root, delete it:
```bash
rm -f ./supervisor.db  # Remove stale DB at repo root (if any)
```

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — system design, components, interaction flows
- [ingest_helper/README.md](ingest_helper/README.md) — ingest helper configuration and usage
- [supervisor/supervisor/discovery/](supervisor/supervisor/discovery/) — federated discovery index module
