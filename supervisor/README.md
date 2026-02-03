# metaFirst Backend

A metadata-first Research Data Management (RDM) system with multi-tenant architecture, policy-driven data governance, and federated discovery.

## Overview

metaFirst backend provides:
- **Multi-tenant isolation**: Each lab operates independently with its own operational database
- **Role-based access control**: Researcher, Steward, and PI roles with granular permissions
- **RDMP-driven governance**: Research Data Management Plans define metadata schemas, retention policies, and visibility rules
- **Federated discovery**: Cross-lab metadata search with visibility-based access control
- **Soft enforcement**: Policy compliance monitoring with remediation task workflows

## Architecture

### Tenant Model

A **Lab** represents a tenant boundary (e.g., a research lab or group). Internally called "Supervisor" for backward compatibility.
- Each lab has its own operational database for isolated state (runs, heartbeats, logs)
- Projects belong to exactly one lab
- Users can be members of multiple labs with different roles

### Roles

| Role | Scope | Capabilities |
|------|-------|--------------|
| **Researcher** | Lab | View projects, edit metadata, run ingests |
| **Steward** | Lab | All Researcher permissions + manage RDMPs, set visibility, approve remediation tasks |
| **PI** | Lab | All Steward permissions + create projects, manage lab settings |

### RDMPs (Research Data Management Plans)

RDMPs are **project-scoped** and follow a lifecycle:
1. **DRAFT**: Initial state, can be edited
2. **ACTIVE**: Approved and in use; recorded on ingest runs for provenance
3. **SUPERSEDED**: Replaced by a newer active version

RDMPs define:
- Metadata fields and validation rules
- Role-based permissions within the project
- **Retention policy** (`retention_days`): How long data should be retained
- **Embargo period** (`embargo_until`): Date until which data is under embargo

### Metadata Visibility (v0.3)

Samples have a visibility level controlling discovery access:

| Level | Description | Who Can See |
|-------|-------------|-------------|
| **PRIVATE** | Restricted to lab members | Only members of the owning lab |
| **INSTITUTION** | Visible to authenticated users | Any authenticated user |
| **PUBLIC** | Open access | Anyone (no authentication required) |

### Remediation Tasks (v0.3)

Remediation tasks implement **soft enforcement** of RDMP policies. The system detects policy violations and creates tasks for human review:

**Issue Types:**
- `retention_exceeded`: Sample data is older than the RDMP's retention period
- `embargo_active`: Project data is still under embargo

**Task Workflow:**
```
PENDING → ACKED → APPROVED → EXECUTED
              ↘ DISMISSED ↙
```

**Important**: Automatic execution is **disabled by default**. The `/execute` endpoint returns 403 unless `supervisor.enable_automated_execution = true`. No automatic deletion occurs.

## Quickstart

### Set Sample Visibility

```bash
# Set a sample's visibility to INSTITUTION (requires Steward/PI role)
curl -X PATCH "http://localhost:8000/api/samples/123/visibility" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"visibility": "INSTITUTION"}'
```

### Run Remediation Detection

```bash
# Dry run - report issues without creating tasks
python -m supervisor.cli.remediation run --dry-run

# Dry run for a specific lab
python -m supervisor.cli.remediation run --dry-run --supervisor 1

# Create tasks for detected issues
python -m supervisor.cli.remediation run --supervisor 1

# Note: CLI uses --supervisor flag for backward compatibility
```

### Remediation Task API

```bash
# List tasks for a lab (Steward/PI only)
curl "http://localhost:8000/api/remediation/tasks?supervisor_id=1" \
  -H "Authorization: Bearer $TOKEN"

# Acknowledge a task (any member)
curl -X POST "http://localhost:8000/api/remediation/tasks/1/ack" \
  -H "Authorization: Bearer $TOKEN"

# Approve a task (Steward/PI only)
curl -X POST "http://localhost:8000/api/remediation/tasks/1/approve" \
  -H "Authorization: Bearer $TOKEN"

# Dismiss a task (Steward/PI only)
curl -X POST "http://localhost:8000/api/remediation/tasks/1/dismiss" \
  -H "Authorization: Bearer $TOKEN"

# Execute a task (Steward/PI, requires enable_automated_execution=true)
curl -X POST "http://localhost:8000/api/remediation/tasks/1/execute" \
  -H "Authorization: Bearer $TOKEN"
```

## API Reference

### Authentication
- `POST /api/auth/login` - Get JWT token
- `GET /api/auth/me` - Get current user info

### Labs
- `GET /api/supervisors` - List labs (endpoint uses `supervisors` for backward compatibility)
- `POST /api/supervisors` - Create lab (admin)
- `PATCH /api/supervisors/{id}` - Update lab (Steward/PI)

### Projects
- `GET /api/projects` - List projects
- `POST /api/projects` - Create project (Steward/PI)
- `GET /api/projects/{id}` - Get project details

### Samples
- `GET /api/projects/{id}/samples` - List samples
- `POST /api/projects/{id}/samples` - Create sample
- `GET /api/samples/{id}` - Get sample with fields
- `PUT /api/samples/{id}/fields/{key}` - Set field value
- `PATCH /api/samples/{id}/visibility` - Set visibility (Steward/PI)

### RDMPs
- `GET /api/projects/{id}/rdmp/versions` - List RDMP versions
- `POST /api/projects/{id}/rdmp/versions` - Create RDMP draft
- `POST /api/projects/{id}/rdmp/versions/{v}/activate` - Activate RDMP (Steward/PI)

### Remediation
- `GET /api/remediation/tasks?supervisor_id=` - List tasks (Steward/PI)
- `GET /api/remediation/tasks/{id}` - Get task details (any member)
- `POST /api/remediation/tasks/{id}/ack` - Acknowledge (any member)
- `POST /api/remediation/tasks/{id}/approve` - Approve (Steward/PI)
- `POST /api/remediation/tasks/{id}/dismiss` - Dismiss (Steward/PI)
- `POST /api/remediation/tasks/{id}/execute` - Execute (Steward/PI, gated)

### Discovery
- `POST /api/discovery/push` - Push records to index (API key)
- `GET /api/discovery/search` - Search indexed records
- `GET /api/discovery/records/{id}` - Get record details

## Development

### Setup

```bash
cd supervisor
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Run Tests

```bash
python -m pytest tests/ -q
```

### Run Server

```bash
uvicorn supervisor.main:app --reload
```

## Version History

- **v0.3.0**: Metadata visibility (PRIVATE/INSTITUTION/PUBLIC), remediation tasks with soft enforcement
- **v0.4.0**: Terminology migration: Supervisor → Lab (backward compatible)
- **v0.2.0**: Multi-tenant architecture, lab-scoped roles, project-only RDMPs with activation workflow
- **v0.1.0**: Foundational proof of principle

## License

MIT License - see LICENSE file for details.
