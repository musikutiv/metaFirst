# metaFirst Ingest Helper

A watchdog-based tool that monitors folders on user machines and creates pending ingests in the metaFirst supervisor for browser-based metadata entry.

## Overview

The Ingest Helper watches specified folders for new files. When a file is detected:
1. It creates a "pending ingest" record in the supervisor
2. Optionally opens your browser to complete metadata entry
3. The file is then fully registered with project and sample associations

## Installation

1. Ensure Python 3.10+ is installed
2. Install dependencies:

```bash
cd ingest_helper
pip install -r requirements.txt
```

## Configuration

Copy `config.example.yaml` to `config.yaml` and customize:

```bash
cp config.example.yaml config.yaml
```

### Basic Configuration

```yaml
supervisor_url: http://localhost:8000
username: alice
password: demo123
ui_url: http://localhost:5173
open_browser: true
compute_hash: false

# Supervisor binding (required if multiple supervisors exist)
supervisor_id: 1

watchers:
  - watch_path: /Users/alice/data/qpcr
    project_id: 1
    storage_root_id: 1
```

**Note:** The supervisor must be started with `--host 0.0.0.0` for ingest helpers running on other machines to connect.

## Supervisor Scoping (v0.2+)

Each ingestor instance is bound to **exactly one supervisor**. This ensures operational isolation between different supervisors (labs, departments, etc.).

### How It Works

- If `supervisor_id` is specified in config, that supervisor is used
- If omitted and exactly one supervisor exists, auto-binds to it
- If omitted and multiple supervisors exist, fails with a clear error listing available supervisors

### Cross-Supervisor Rejection

When a file is detected, the ingestor validates that the project belongs to its configured supervisor. If mismatched:

```
[NEW FILE] /data/qpcr/sample.fastq
  [REJECT] Project 5 belongs to supervisor 2 but this ingestor is configured
           for supervisor 1. Start a separate ingestor instance for supervisor 2.
```

### Running Multiple Ingestors

To ingest data for projects across multiple supervisors, run separate ingestor instances:

```bash
# Terminal 1: Ingestor for Lab A (supervisor_id: 1)
python metafirst_ingest.py config_lab_a.yaml

# Terminal 2: Ingestor for Lab B (supervisor_id: 2)
python metafirst_ingest.py config_lab_b.yaml
```

Example configs:

**config_lab_a.yaml:**
```yaml
supervisor_url: http://localhost:8000
username: alice
password: demo123
supervisor_id: 1
watchers:
  - watch_path: /data/lab_a/samples
    project_name: "Lab A Project"
    storage_root_name: "LOCAL_DATA"
```

**config_lab_b.yaml:**
```yaml
supervisor_url: http://localhost:8000
username: bob
password: demo123
supervisor_id: 2
watchers:
  - watch_path: /data/lab_b/samples
    project_name: "Lab B Project"
    storage_root_name: "LOCAL_DATA"
```

### Watcher Configuration Options

Each watcher entry supports:

| Field | Required | Description |
|-------|----------|-------------|
| `watch_path` | Yes | Local folder to monitor |
| `project_id` | Yes* | Numeric project ID |
| `project_name` | Yes* | Project name (resolved at startup) |
| `storage_root_id` | Yes* | Numeric storage root ID |
| `storage_root_name` | Yes* | Storage root name (resolved at startup) |
| `base_path_for_relative` | No | Base path for computing relative paths (defaults to watch_path) |
| `sample_identifier_pattern` | No | Regex to extract sample ID from filename |

*Either the numeric ID or name must be provided for project and storage root.

## Using project_name / storage_root_name

Instead of hard-coding numeric IDs that can change after database reseeds, you can use names:

```yaml
watchers:
  - watch_path: /Users/alice/data/rnaseq
    project_name: "RNA-seq Demo Project"
    storage_root_name: "LOCAL_DATA"
```

### How Name Resolution Works

At startup, the helper:
1. Fetches available projects via `GET /api/projects`
2. For each watcher using `project_name`, finds the matching project
3. For each watcher using `storage_root_name`, fetches storage roots for the resolved project via `GET /api/projects/{id}/storage-roots`
4. Caches resolved IDs for the session duration

### Resolution Rules

- If both numeric ID and name are provided, **numeric ID takes precedence**
- Names must match exactly (case-sensitive)
- If a name matches zero or multiple entries, the watcher is skipped with an error

### Startup Banner

The helper prints resolved mappings at startup:

```
============================================================
metaFirst Ingest Helper
============================================================
Config file: config.yaml
Connected to supervisor at http://localhost:8000
Bound to supervisor: Demo Lab (id=1)
UI URL: http://localhost:5173
Auto-open browser: true
------------------------------------------------------------
Resolving 2 watcher configuration(s)...
------------------------------------------------------------
Resolved watcher mappings:
  /Users/alice/data/rnaseq
    -> project: RNA-seq Demo Project (id=3)
    -> storage_root: LOCAL_DATA (id=7)
  /Users/alice/data/qpcr
    -> project: id=1
    -> storage_root: id=2
------------------------------------------------------------
[NOTE] Resolved names to IDs at startup.
       After database reseed, re-run helper if projects/storage roots change.
============================================================
```

## Running

```bash
python metafirst_ingest.py config.yaml
```

The helper will:
1. Connect to the supervisor and authenticate
2. Resolve any name-based configurations
3. Start watching configured folders
4. Create pending ingests when new files appear

Press `Ctrl+C` to stop.

## Troubleshooting

### Name Resolution Failures

If a watcher fails to resolve, check:

1. **Project membership**: You must be a member of the project
2. **Exact name match**: Names are case-sensitive

List your projects:
```bash
# Get a token first
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -d "username=alice&password=demo123" | jq -r .access_token)

# List projects
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/projects
```

List storage roots for a project:
```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/projects/1/storage-roots
```

### Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `Project not found: 'X'` | Project name doesn't exist or you're not a member | Check spelling and membership |
| `Storage root not found: 'X'` | Storage root doesn't exist in the project | Verify storage root name in project |
| `Ambiguous project_name` | Multiple projects match (shouldn't happen) | Contact admin |
| `Authentication failed` | Invalid credentials | Check username/password |
| `Multiple supervisors found` | No supervisor_id in config, multiple exist | Add `supervisor_id: N` to config |
| `Project belongs to supervisor X` | Project's supervisor differs from ingestor's | Use separate config/instance for that supervisor |

## Sample Identifier Extraction

Use regex to extract sample IDs from filenames:

```yaml
watchers:
  - watch_path: /data/samples
    project_id: 1
    storage_root_id: 1
    sample_identifier_pattern: "^([A-Z]+-\\d+)"
```

For filename `ABC-001_run1.fastq`, this extracts `ABC-001` as the sample identifier.

## Testing

Run unit tests:
```bash
cd ingest_helper
python -m pytest tests/ -v
```

## Requirements

- Python 3.10+
- watchdog >= 3.0.0
- httpx >= 0.26.0
- pyyaml >= 6.0
