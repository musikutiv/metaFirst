# Upgrading metaFirst

This document provides upgrade guidance for each major release.

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
