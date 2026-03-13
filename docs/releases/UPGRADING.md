# Upgrading metaFirst

This document provides upgrade guidance for each major release.

## Upgrading to v0.7.0

### Prerequisites

- Python 3.11+
- Node.js 18+ (for UI)
- Existing v0.5.x or v0.6.x installation

### Database Migration

v0.7.0 introduces the `file_annotations` table. Run Alembic migrations after updating:

```bash
cd supervisor
source venv/bin/activate
DATABASE_URL=sqlite:///supervisor.db alembic upgrade head
```

> **Note:** The `DATABASE_URL` environment variable is required to target the correct database file. Without it, Alembic uses the path in `alembic.ini` which may differ from your deployment path.

### Backend Update

```bash
cd supervisor
source venv/bin/activate
pip install -e .
# Restart uvicorn
```

### Frontend Update

```bash
cd supervisor-ui
npm install
npm run build  # For production
# Or: npm run dev  # For development
```

### Breaking Changes

None. All existing API endpoints remain compatible. Multi-sample file support is additive: existing raw data items with a direct `sample_id` link continue to work unchanged.

### New Features

- **File annotations**: `POST /api/raw-data/{id}/annotations`, `GET /api/raw-data/{id}/annotations`, `PATCH /api/annotations/{id}`, `DELETE /api/annotations/{id}`
- **File Detail UI**: Click any linked file in Sample Detail to open the File Detail view with a measured-sample table and Add Measurement form
- **Multi-sample files**: Create raw data items with `sample_id = null`; link samples via `FileAnnotation` rows

### Rollback

1. Stop services
2. Checkout previous tag: `git checkout v0.6.2`
3. Downgrade database: `DATABASE_URL=sqlite:///supervisor.db alembic downgrade -1`
4. Reinstall dependencies and restart services

---

## Upgrading to v0.6.x

v0.6.0, v0.6.1, and v0.6.2 are documentation-only releases (CI hardening, GitHub Pages, researcher user manual). No database migrations, no API changes, no configuration changes.

```bash
# Pull latest and reinstall UI dependencies if desired
cd supervisor-ui && npm install
```

---

## Upgrading to v0.5.0

### Prerequisites

- Python 3.11+
- Node.js 18+ (for UI)
- Existing v0.4.x installation

### Database Migration

v0.5.0 introduces new tables for the audit log. Run migrations after updating:

```bash
cd supervisor
source venv/bin/activate
alembic upgrade head
```

### Backend Update

```bash
cd supervisor
source venv/bin/activate
pip install -e .
# Restart uvicorn
```

### Frontend Update

```bash
cd supervisor-ui
npm install
npm run build  # For production
# Or: npm run dev  # For development
```

### Breaking Changes

None. All existing API endpoints remain compatible.

### New Features to Enable

- **Lab Status API**: Available immediately at `GET /supervisors/{id}/status-summary` (PI/Steward only)
- **CSV Import**: Access via `GET /projects/{id}/ingest-template` endpoints
- **Authority hints**: Automatically visible in the UI for users with insufficient permissions

### Configuration Changes

No new environment variables or configuration changes required.

### Rollback

If issues occur, revert to v0.4.x:

1. Stop services
2. Checkout v0.4.x tag: `git checkout v0.4.0`
3. Downgrade database: `alembic downgrade -1` (repeat as needed)
4. Reinstall dependencies
5. Restart services

### Verification

After upgrade, verify the installation:

```bash
# Backend health check
curl http://localhost:8000/docs

# Run tests
cd supervisor && pytest

# UI tests
cd supervisor-ui && npm test
```
