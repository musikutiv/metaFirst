# Metadata-First RDM System

A proof-of-principle "metadata-first" Research Data Management (RDM) system for life sciences, implementing a centralized supervisor service with distributed ingestion capabilities.

## Overview

This system implements a **metadata-first** approach where:
- **Supervisor** is the single source of truth for all metadata
- **Raw data** is never duplicated; only referenced via storage roots + relative paths
- **RDMPs** (Research Data Management Plans) define required fields, roles, permissions, and visibility
- **Audit trail** captures all state changes with full provenance
- **Releases** create immutable snapshots; corrections via new releases

## Architecture

### Components

1. **Supervisor Service** (FastAPI + SQLite)
   - Central authoritative database for all projects
   - REST API for metadata management
   - Multi-tenant: stores metadata for multiple projects

2. **User Ingestion Helper** (Python + watchdog) - *Implemented*
   - Runs locally on user machines
   - Watches folders for new files
   - Submits metadata to supervisor via API
   - Links files to samples with optional metadata prompting

3. **Metadata Viewer UI** (React + Vite) - *Implemented*
   - Read-only table view of sample metadata
   - RDMP-driven dynamic columns
   - Project selection and completeness indicators

4. **Federated Discovery Index** (FastAPI + SQLite) - *API Implemented*
   - Cross-project metadata search via HTTP API
   - Respects RDMP-derived visibility policies (PUBLIC, REGISTERED, PRIVATE)
   - No web UI yet (see below)

## Quick Start

### Prerequisites

- Python 3.11 or later
- Node.js 18 or later (for UI)
- Git

### 1. Installation

```bash
# Clone the repository
cd /Users/tobiasst/Documents/metaFirst

# Set up supervisor backend
cd supervisor
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e ".[dev]"
```

### 2. Seed Demo Data

```bash
# From project root
python demo/seed.py
```

This creates:
- **5 users**: alice, bob, carol, david, eve (all with password: `demo123`)
- **4 RDMP templates**: qPCR, RNA-seq, Microscopy, Clinical Samples
- **3 projects** with 4 different RDMPs
- **4 sample records** (1 intentionally incomplete to demonstrate validation)

### 3. Start the Supervisor API

```bash
# From supervisor directory with venv activated
uvicorn supervisor.main:app --reload --port 8000
```

The API will be available at http://localhost:8000

- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

### 4. Start the Metadata Viewer UI (Optional)

```bash
# In a new terminal
cd supervisor-ui
npm install
npm run dev
```

The UI will be available at http://localhost:5173

- Login with any demo user (e.g., alice / demo123)
- Select a project to view its metadata table
- Columns are dynamically generated from RDMP field definitions

## Watched-Folder Ingestion

The user ingestion helper watches configured folders on user machines and automatically registers new raw data files in the supervisor.

### Setup

1. **Create Storage Roots via API**

   First, create a storage root for your project (requires `can_manage_rdmp` permission):

   ```bash
   # Login as Alice (PI in project 1)
   TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=alice&password=demo123" | jq -r .access_token)

   # Create a storage root
   curl -X POST http://localhost:8000/api/projects/1/storage-roots \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"name": "Lab NAS", "description": "Network attached storage"}'
   ```

2. **Create Storage Root Mapping**

   Each user maps the storage root to their local mount path:

   ```bash
   # Replace 1 with your storage_root_id
   curl -X POST http://localhost:8000/api/storage-roots/1/mappings \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"local_mount_path": "/Users/alice/data"}'
   ```

3. **Configure the Ingest Helper**

   ```bash
   cd ingest_helper
   pip install -r requirements.txt
   cp config.example.yaml config.yaml
   # Edit config.yaml with your settings
   ```

   Example `config.yaml`:

   ```yaml
   supervisor_url: http://localhost:8000
   ui_url: http://localhost:5173
   username: alice
   password: demo123
   compute_hash: false
   open_browser: true  # Auto-open browser when file detected
   watchers:
     - watch_path: /Users/alice/data/qpcr
       project_id: 1
       storage_root_id: 1
       sample_identifier_pattern: "^([A-Z]+-\\d+)"
   ```

4. **Run the Ingest Helper**

   ```bash
   python metafirst_ingest.py config.yaml
   ```

### Browser-Based Metadata Entry

When the ingest helper detects a new file, it creates a **pending ingest** in the supervisor
and optionally opens your browser to the ingest form. The output shows:

```
[NEW FILE] /Users/alice/data/qpcr/QPCR-001_results.csv
  Relative path: qpcr/QPCR-001_results.csv
  Inferred sample identifier: QPCR-001
  Created pending ingest: 1
  Complete metadata entry in browser at: http://localhost:5173/ingest/1
  Opening browser: http://localhost:5173/ingest/1
```

**Manual Testing:**
1. Start the supervisor and UI
2. Run the ingest helper with `open_browser: true` in config
3. Drop a file into the watched folder
4. Verify the browser opens to `/ingest/{id}` with the correct pending ingest form

### Demo: Watch a Folder and Ingest Files

1. **Start the supervisor** (in one terminal):
   ```bash
   cd supervisor
   source venv/bin/activate
   uvicorn supervisor.main:app --reload --port 8000
   ```

2. **Seed demo data** (if not already done):
   ```bash
   python demo/seed.py
   ```

3. **Create storage root and mapping** (using the API commands above)

4. **Create a test data folder**:
   ```bash
   mkdir -p /Users/alice/data/qpcr
   ```

5. **Start the ingest helper** (in another terminal):
   ```bash
   cd ingest_helper
   python metafirst_ingest.py config.yaml
   ```

6. **Drop a file into the watched folder**:
   ```bash
   echo "gene,expression" > /Users/alice/data/qpcr/QPCR-001_results.csv
   ```

7. **Observe the ingest helper**:
   - It will detect the new file
   - Extract sample identifier (e.g., `QPCR-001` from the filename)
   - Create a pending ingest in the supervisor
   - Open browser to the ingest form (if `open_browser: true`)

8. **Complete metadata entry in browser**:
   - Select or create the sample
   - Fill in required RDMP fields
   - Submit to finalize the ingest

9. **Verify in supervisor**:
   ```bash
   # List raw data items
   curl -X GET "http://localhost:8000/api/projects/1/raw-data" \
     -H "Authorization: Bearer $TOKEN"

   # Get sample details (shows linked raw data)
   curl -X GET "http://localhost:8000/api/samples/1" \
     -H "Authorization: Bearer $TOKEN"
   ```

### API Endpoints for Storage and Raw Data

#### Storage Roots (`/api`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/projects/{id}/storage-roots` | Create storage root |
| GET | `/projects/{id}/storage-roots` | List storage roots |

#### Storage Root Mappings (`/api`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/storage-roots/{id}/mappings` | Create/update user mapping |
| GET | `/storage-roots/{id}/mappings` | List mappings |

#### Raw Data Items (`/api`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/projects/{id}/raw-data` | Register raw data item |
| GET | `/projects/{id}/raw-data` | List raw data (filter by sample_id) |
| GET | `/raw-data/{id}` | Get raw data item details |
| PUT | `/raw-data/{id}/path` | Update path (audited) |
| GET | `/raw-data/{id}/path-history` | Get path change history |

## Federated Discovery Index (Current Status)

A metadata-only discovery index is implemented, enabling cross-project search via HTTP API. The index stores sample metadata with visibility enforcement based on RDMP-derived policies. Raw data files are never indexed or accessed by the discovery system.

### What Is Available

- **Push API**: Authenticated endpoint to index sample metadata from supervisor instances
- **Search API**: Query indexed samples with visibility filtering
- **Record detail API**: Retrieve full metadata for individual indexed records

### What Is NOT Available Yet

- **No browser-based search UI**: Discovery is currently API-driven only

At this stage, discovery is intentionally exposed via API only. A web UI is trivial to add, but is deferred until discovery scope and visibility semantics are fully validated.

### API Usage

**Search public samples:**
```bash
curl -s "http://localhost:8000/api/discovery/search?q=QPCR&visibility=PUBLIC"
```

**Search with authentication (for REGISTERED/PRIVATE visibility):**
```bash
curl -s "http://localhost:8000/api/discovery/search?q=sample&visibility=REGISTERED" \
  -H "Authorization: ApiKey YOUR_DISCOVERY_API_KEY"
```

**Parameters:**
- `q`: Search query (substring match against indexed text)
- `visibility`: Comma-separated list of visibility levels (PUBLIC, REGISTERED, PRIVATE)
- `from`: Pagination offset (default: 0)
- `size`: Results per page (default: 20, max: 100)

**Push samples to index (requires API key):**
```bash
export DISCOVERY_API_KEY=your-secret-key

curl -X POST "http://localhost:8000/api/discovery/push" \
  -H "Authorization: ApiKey $DISCOVERY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "origin": "supervisor-a.example.com",
    "records": [
      {
        "origin_project_id": 1,
        "origin_sample_id": 100,
        "sample_identifier": "QPCR-001",
        "visibility": "PUBLIC",
        "metadata": {"organism": "Homo sapiens", "tissue": "blood"}
      }
    ]
  }'
```

A CLI helper is also available: `python tools/discovery_push.py --project-id 1 --visibility PUBLIC`

### Design Rationale

- **Validate semantics before UX**: Ensure discovery scope and visibility rules are correct before committing to a UI
- **Avoid freezing assumptions**: Global visibility policies may evolve; API-only allows iteration without UI rework
- **Keep discovery loosely coupled**: The index is a separate SQLite database (`discovery.db`), making it easy to extract to a standalone service later

### Planned Next Steps

- Minimal web-based search page
- Deep links back to originating supervisor instances
- No backend architecture changes required

## Demo Data Structure

### Users (all password: `demo123`)

| Username | Display Name    | Role in Projects                                    |
|----------|----------------|-----------------------------------------------------|
| alice    | Alice Smith    | PI in Project 1, Researcher in Project 3          |
| bob      | Bob Johnson    | Researcher in Project 1                            |
| carol    | Carol Williams | Researcher in Project 1, PI in Project 2           |
| david    | David Brown    | Researcher in Project 2                            |
| eve      | Eve Davis      | Steward in Projects 2 and 3                        |

### Projects & RDMPs

| Project ID | Project Name                    | RDMP Used        | Members                           |
|------------|--------------------------------|------------------|-----------------------------------|
| 1          | Gene Expression Study 2024     | qPCR Standard    | Alice (PI), Bob, Carol            |
| 2          | Transcriptomics Analysis       | RNA-seq Standard | Carol (PI), David, Eve (steward)  |
| 3          | Cellular Imaging Core          | Microscopy Standard | Eve (steward), Alice            |

### RDMP Templates

1. **qPCR Standard**
   - Fields: gene_name, primer_batch, cell_line (categorical), replicate_number, experiment_date, notes
   - Roles: PI, researcher, viewer
   - File patterns: *.csv, *.xlsx

2. **RNA-seq Standard**
   - Fields: library_prep_kit, sequencing_platform, read_length, tissue_type, treatment_condition, rna_quality_rin
   - Roles: PI, researcher, steward
   - File patterns: *.fastq.gz, *.fq.gz

3. **Microscopy Standard**
   - Fields: microscope_type, objective, fluorophore, exposure_time_ms, z_stack_depth, sample_type
   - Roles: steward, researcher
   - File patterns: *.tif, *.tiff, *.nd2, *.czi

4. **Clinical Samples** (synthetic demo data only)
   - Fields: patient_id, collection_date, sample_type, storage_temperature, consent_status
   - Roles: PI, data_manager, analyst
   - File patterns: *.csv, *.xlsx

## API Usage Examples

### 1. Authentication

```bash
# Login as Alice
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=alice&password=demo123"

# Response: {"access_token": "eyJ...", "token_type": "bearer"}
```

Save the access token for subsequent requests.

### 2. List Projects

```bash
curl -X GET http://localhost:8000/api/projects \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

### 3. Get Project RDMP

```bash
# Get current RDMP for project 1
curl -X GET http://localhost:8000/api/rdmp/projects/1/rdmp \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

### 4. List Samples

```bash
# List samples in project 1
curl -X GET http://localhost:8000/api/projects/1/samples \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

### 5. Create a Sample

```bash
# Create a new sample in project 1
curl -X POST http://localhost:8000/api/projects/1/samples \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{"sample_identifier": "QPCR-003"}'
```

### 6. Set Field Values

```bash
# Set gene_name field for sample
curl -X PUT http://localhost:8000/api/samples/1/fields/gene_name \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{"value": "ACTB"}'
```

### 7. List RDMP Templates

```bash
curl -X GET http://localhost:8000/api/rdmp/templates \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

## Key Features Demonstrated

### 1. Multi-Project Stewards

- **Carol**: Member of projects 1 and 2
- **Eve**: Member of projects 2 and 3
- **Alice**: Member of projects 1 and 3

### 2. Missing Required Fields

Sample `QPCR-002` is intentionally incomplete (missing `cell_line` field). Check completeness:

```bash
curl -X GET http://localhost:8000/api/samples/2 \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

The response includes a `completeness` object showing missing fields.

### 3. Role-Based Permissions

Roles are defined in each RDMP with specific permissions:
- `can_edit_metadata`: Can create/edit samples and field values
- `can_edit_paths`: Can update raw data file paths
- `can_create_release`: Can create project releases
- `can_manage_rdmp`: Can create new RDMP versions and manage members

Example: `viewer` role in qPCR RDMP cannot edit metadata.

### 4. Field Visibility

Fields have three visibility levels:
- `private`: Only visible to project members
- `collaborators`: Visible to project collaborators
- `public_index`: Searchable in federated index

### 5. RDMP Append-Only Semantics

RDMPs are versioned and append-only. Creating a new RDMP version:

```bash
curl -X POST http://localhost:8000/api/rdmp/projects/1/rdmp \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d @new_rdmp_version.json
```

Old samples remain valid even with new required fields (flagged as incomplete).

## Database Schema

### Core Models

- **User**: id, username, hashed_password, display_name
- **Project**: id, name, description, created_at, created_by
- **Membership**: project_id, user_id, role_name

### RDMP Management

- **RDMPTemplate**: id, name, description
- **RDMPTemplateVersion**: id, template_id, version_int, template_json
- **RDMPVersion**: id, project_id, version_int, rdmp_json, provenance_json

### Sample & Metadata

- **Sample**: id, project_id, sample_identifier, created_at, created_by
- **SampleFieldValue**: id, sample_id, field_key, value_json, value_text, updated_at, updated_by

### Storage & Raw Data (Models only - API not yet implemented)

- **StorageRoot**: id, project_id, name, description
- **StorageRootMapping**: id, user_id, storage_root_id, local_mount_path
- **RawDataItem**: id, project_id, sample_id, storage_root_id, relative_path, storage_owner_user_id
- **PathChange**: id, raw_data_item_id, old_path, new_path, changed_at, changed_by, reason

### Audit & Releases (Models only - API not yet implemented)

- **AuditLog**: id, project_id, actor_user_id, action_type, target_type, target_id, before_json, after_json, timestamp
- **Release**: id, project_id, release_tag, rdmp_version_id, parent_release_id, snapshot_json

## Project Structure

```
metaFirst/
├── supervisor/                 # Central FastAPI + SQLite service
│   ├── supervisor/
│   │   ├── models/            # SQLAlchemy ORM models
│   │   ├── schemas/           # Pydantic request/response models
│   │   ├── api/               # FastAPI route handlers
│   │   ├── discovery/         # Federated discovery index module
│   │   ├── services/          # Business logic (RDMP, permissions, audit)
│   │   └── utils/             # Security, validation utilities
│   ├── tools/                 # CLI utilities (discovery_push.py)
│   ├── tests/                 # Test suite
│   ├── alembic/               # Database migrations
│   └── pyproject.toml         # Dependencies
│
├── ingest_helper/             # User-side file watcher
│   ├── metafirst_ingest.py    # Main ingest script
│   ├── config.example.yaml    # Example configuration
│   └── requirements.txt       # Dependencies
│
├── supervisor-ui/             # React frontend
│   ├── src/
│   │   ├── api/client.ts      # API client
│   │   ├── components/        # React components
│   │   ├── types.ts           # TypeScript types
│   │   ├── App.tsx            # Main app component
│   │   └── main.tsx           # Entry point
│   ├── package.json           # Dependencies
│   └── vite.config.ts         # Vite configuration
│
├── demo/                      # Demo data seeding
│   ├── seed.py                # Seeding script
│   └── rdmp_templates/        # 4 RDMP template JSON files
│
└── README.md                  # This file
```

## Implementation Status

### ✅ Implemented

- [x] Database models for all entities
- [x] JWT authentication
- [x] RDMP template management
- [x] RDMP versioning (append-only)
- [x] Project and membership management
- [x] Sample and field value management
- [x] RDMP validation
- [x] Permission-based access control
- [x] Field completeness checking
- [x] 4 RDMP template examples
- [x] Demo data seeding (5 users, 3 projects, 4 samples)

### 🚧 Planned

- [ ] Release management (freeze snapshots)
- [ ] Release corrections (linked new releases)
- [ ] Discovery web UI (search page with deep links)

### ✅ Recently Implemented

- [x] Storage roots and mappings API
- [x] Raw data reference management API
- [x] Path change tracking with audit
- [x] Audit logging service
- [x] User ingestion helper (watchdog-based file watcher)
- [x] Read-only metadata table UI (React + Vite)
- [x] Federated discovery index (API-only, no web UI yet)

## API Endpoints

### Authentication (`/api/auth`)
- `POST /login` - Login and get JWT token
- `GET /me` - Get current user info

### Projects (`/api/projects`)
- `GET /` - List user's projects
- `POST /` - Create project
- `GET /{project_id}` - Get project details
- `GET /{project_id}/memberships` - List members
- `POST /{project_id}/memberships` - Add member

### RDMP (`/api/rdmp`)
- `GET /templates` - List RDMP templates
- `POST /templates` - Create template
- `GET /templates/{id}/versions` - Template version history
- `POST /templates/{id}/versions` - Create new template version
- `GET /projects/{id}/rdmp` - Get current project RDMP
- `GET /projects/{id}/rdmp/versions` - Project RDMP version history
- `POST /projects/{id}/rdmp` - Create new project RDMP version

### Samples (`/api`)
- `GET /projects/{id}/samples` - List samples
- `POST /projects/{id}/samples` - Create sample
- `GET /samples/{id}` - Get sample with fields
- `PUT /samples/{id}/fields/{key}` - Set field value

## Testing Walkthrough

### 1. Check Sample Completeness

```bash
# Login as Bob (researcher in project 1)
TOKEN=$(curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=bob&password=demo123" | jq -r .access_token)

# Check incomplete sample
curl -X GET http://localhost:8000/api/samples/2 \
  -H "Authorization: Bearer $TOKEN" | jq .completeness
```

Expected output shows `cell_line` is missing.

### 2. Fix Missing Field

```bash
# Add missing cell_line field
curl -X PUT http://localhost:8000/api/samples/2/fields/cell_line \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"value": "HEK293"}'

# Verify sample is now complete
curl -X GET http://localhost:8000/api/samples/2 \
  -H "Authorization: Bearer $TOKEN" | jq .completeness
```

### 3. Test Permission Enforcement

```bash
# Login as viewer (no edit permissions)
# Note: Demo data doesn't include a viewer user - you'd need to add one with viewer role
# Bob (researcher) can edit metadata
curl -X PUT http://localhost:8000/api/samples/1/fields/notes \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"value": "Updated notes"}'
```

### 4. Explore RDMP Structure

```bash
# Get qPCR RDMP
curl -X GET http://localhost:8000/api/rdmp/projects/1/rdmp \
  -H "Authorization: Bearer $TOKEN" | jq .rdmp_json
```

This shows:
- Roles and their permissions
- Field definitions with types and requirements
- Visibility policies for each field

## Development

### Running Tests

```bash
cd supervisor
pytest
```

### Database Migrations

```bash
# Create migration
alembic revision --autogenerate -m "Description"

# Apply migration
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Resetting Demo Data

```bash
# Delete database
rm supervisor.db

# Re-seed
python demo/seed.py
```

## Design Principles

1. **Metadata-First**: Raw data is never moved/copied; only referenced
2. **RDMP is Authoritative**: Defines all rules for metadata, roles, and visibility
3. **Append-Only RDMPs**: New versions never invalidate old metadata
4. **Last-Write-Wins**: No distributed locking; conflicts resolved via timestamps
5. **Audit Everything**: Full provenance for all state changes
6. **Immutable Releases**: Snapshots are frozen; corrections via new releases
7. **Privacy by Design**: Visibility policies enforced at RDMP level

## Requirements Satisfied

- ✅ Supervisor joint DB (single multi-tenant database)
- ✅ 5 users (alice, bob, carol, david, eve)
- ✅ 4 different RDMPs (qPCR, RNA-seq, Microscopy, Clinical)
- ✅ Multi-project stewards (Carol, Eve, Alice)
- ✅ Missing required fields flagged
- ✅ Role-based permissions enforced
- ✅ RDMP append-only semantics
- ✅ Project-local sample identity
- ✅ Scale: hundreds of samples (supported, demo shows 4)

## License

This is a proof-of-principle demonstration project.

## Contact

For questions about this implementation, refer to the code and documentation.
