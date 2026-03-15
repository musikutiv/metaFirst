---
title: Project Setup Guide — metaFirst
---

# Project Setup Guide

This guide covers the full lifecycle of a metaFirst project from creation through
active data ingestion. It is intended for **Principal Investigators** and **Lab Stewards**
who are responsible for setting up projects.

Researchers who only need to ingest data once a project is ready should read the
[Researcher Guide](researcher-guide.md) instead.

**Contents**

- [Concepts Overview](#concepts-overview)
- [Step 1 — Create a Project](#step-1--create-a-project)
- [Step 2 — Create and Activate an RDMP](#step-2--create-and-activate-an-rdmp)
- [Step 3 — Configure a Storage Root](#step-3--configure-a-storage-root)
- [Step 4 — Ingest Data](#step-4--ingest-data)
- [Metadata Model Reference](#metadata-model-reference)
- [Permissions Model](#permissions-model)
- [Audit Logging](#audit-logging)

---

## Concepts Overview

The diagram below shows the dependency chain for a project to be operational.

```
Lab (Supervisor)
└── Project
    ├── RDMP (active)          ← defines metadata fields and permissions
    ├── Storage Root           ← where raw files live
    └── Members                ← who can do what
```

A project cannot accept ingested data until all three of RDMP, Storage Root, and
at least one Member with `can_edit_paths` are in place. The setup workflow in this
guide satisfies all three.

---

## Step 1 — Create a Project

### Who can do this

Any user with a **PI** or **Steward** role in the Lab.

### How

1. Click **New Project** in the top bar of the web interface.
   The three-step New Project Setup wizard opens.

2. **Step 1 — Project details**

   | Field | Notes |
   |---|---|
   | Lab | Select the Lab this project belongs to. Only Labs in which you are a PI or Steward appear. |
   | Project Name | Must be unique across all projects. Choose a name that is meaningful outside your immediate team — it appears in metadata exports and audit logs. |
   | Description | Optional. A sentence describing the experiment class or purpose. |

   Click **Create Project**.

3. The wizard advances automatically to Step 2 (RDMP) once the project is saved.

### What happens automatically

When a project is created, the creating user is **automatically added as a PI member**
of that project. This means permission checks work immediately after the project
is created — you do not need to add yourself manually.

---

## Step 2 — Create and Activate an RDMP

### What is an RDMP

An **RDMP** (Research Data Management Plan) is a JSON document attached to a project
that defines three things:

1. **Metadata fields** — what information must or can be recorded for each sample.
2. **Roles and permissions** — what each project role is allowed to do.
3. **Ingest behaviour** — whether files contain data from one sample or many.

Without an active RDMP the project accepts no data and all permission checks deny access.

### How

Continuing from the wizard:

4. **Step 2 — Create RDMP Draft**

   - The **RDMP Title** is pre-filled as `RDMP <project name> v1`. You can change it.
   - The **Content** textarea holds the RDMP JSON. Paste or type your RDMP definition here.
     See [RDMP Structure](#rdmp-structure) below for what to include.

   Click **Create RDMP Draft**.

5. **Step 3 — Activate RDMP**

   - Enter a short reason for activation (e.g. `Initial project setup`).
   - Click **Activate RDMP**.

   > **Note:** Only users whose project membership matches a role with
   > `can_manage_rdmp: true` in the RDMP can activate it. Because the project
   > creator is automatically assigned the `PI` role, and the standard PI role
   > includes `can_manage_rdmp: true`, activation works immediately for the
   > project creator as long as the RDMP defines a role named `PI`.

   If activation returns an error, click **Finish Later**. You will be taken to
   the RDMP management page where you can revisit the draft once the role
   configuration is corrected.

### RDMP Structure

The RDMP content is a JSON object with three required top-level keys:
`roles`, `fields`, and optionally `ingest`.

#### Minimal valid RDMP

```json
{
  "name": "My Project RDMP v1",
  "roles": [
    {
      "name": "PI",
      "permissions": {
        "can_edit_metadata": true,
        "can_edit_paths": true,
        "can_create_release": true,
        "can_manage_rdmp": true
      }
    },
    {
      "name": "researcher",
      "permissions": {
        "can_edit_metadata": true,
        "can_edit_paths": true,
        "can_create_release": false,
        "can_manage_rdmp": false
      }
    }
  ],
  "fields": [
    {
      "key": "genotype",
      "label": "Genotype",
      "type": "string",
      "required": true,
      "description": "Genetic background of the sample.",
      "visibility": "collaborators"
    }
  ]
}
```

#### `roles` array

Each role entry specifies a **name** (a free string that must match project membership
role assignments) and a **permissions** object with four boolean flags.

| Permission flag | Controls |
|---|---|
| `can_edit_metadata` | Edit sample metadata fields in the UI |
| `can_edit_paths` | Submit and complete ingests (add files) |
| `can_create_release` | Create data releases |
| `can_manage_rdmp` | Activate RDMPs, add project members, create storage roots |

You may define as many roles as you need. Common role sets: `PI / researcher / viewer`,
`PI / steward / researcher`.

#### `fields` array

Each field defines one piece of sample-level metadata.

| Property | Required | Notes |
|---|---|---|
| `key` | Yes | Machine identifier. Used in exports and the API. Lowercase, no spaces. |
| `label` | Yes | Human-readable label shown in forms. |
| `type` | Yes | `string`, `number`, `date`, or `categorical` |
| `required` | Yes | `true` or `false`. Required fields drive completeness tracking. |
| `description` | No | Help text shown under the field in forms. |
| `visibility` | Yes | `private`, `collaborators`, or `public_index` |
| `allowed_values` | For `categorical` only | List of accepted values, e.g. `["Blood", "Tissue"]` |

**Visibility levels:**

| Value | Who can see this field's data |
|---|---|
| `private` | Project members only |
| `collaborators` | Lab members (including cross-project) |
| `public_index` | Anyone (metadata only — files are never shared) |

#### `ingest` key (optional)

Controls how files relate to samples during ingest.

**Single-sample mode** (default — omit the `ingest` key or set
`measured_samples_mode: "single"`):
Each file is linked to one sample.

**Multi-sample mode** (for instruments that produce one output file per run
containing measurements for many samples, such as a qPCR plate reader):

```json
"ingest": {
  "measured_samples_mode": "multi",
  "multi": {
    "annotation_key": "observation",
    "index_fields": ["position", "target"],
    "run_fields": [
      {
        "key": "primer_batch",
        "label": "Primer batch",
        "type": "string",
        "required": true
      }
    ]
  }
}
```

| Key | Meaning |
|---|---|
| `annotation_key` | The label stored with each per-sample measurement record. |
| `index_fields` | Column headers shown in the measured-samples grid (e.g. well position, gene target). |
| `run_fields` | Metadata about the run as a whole (e.g. reagent batch, instrument ID). |

### Updating an RDMP

When the experiment protocol changes — new fields required, roles revised — create
a new RDMP version rather than editing the active one:

1. Go to **RDMPs** in the project sidebar.
2. Click **Create RDMP**.
3. Paste the revised JSON.
4. Have a PI activate it.

The previous RDMP is marked **Superseded**. All entries created under the old RDMP
retain their original field definitions in the history.

---

## Step 3 — Configure a Storage Root

### Why storage roots are required

A **storage root** is a named storage location — a filesystem path, network share,
or cloud prefix — that metaFirst knows about. Every ingested file is recorded relative
to a storage root. The system does not copy or move files; it records the path only.

The ingest helper and the permission system both require at least one storage root to
exist before files can be submitted to a project.

### How

1. In the project, click **Go to Settings** (or navigate to the **Settings** tab).

2. Scroll to the **Storage Roots** section.

3. Fill in:
   - **Name** — a short identifier used in the ingest helper config file and in the UI.
     Example: `LOCAL_DATA`, `LAB_NAS_2024`.
   - **Description** — optional. A note about what this storage location is.

4. Click **Add Storage Root**.

   The root appears in the list immediately. You can add more than one root if your
   project spans multiple storage locations.

   > Storage root creation requires the `can_manage_rdmp` permission. As the project
   > creator you have this automatically. If you see a permission error, verify that
   > the RDMP has been activated and that it defines a `PI` role with
   > `can_manage_rdmp: true`.

### Relation to local watch folders

The ingest helper config references a storage root by its **exact name**:

```yaml
watchers:
  - watch_path: /Users/alice/data/qpcr_runs
    project_name: "qPCR Oncology 2026"
    storage_root_name: "LOCAL_DATA"
```

The name in `storage_root_name` must match the name you entered in the Settings page
exactly, including capitalisation. If the names do not match the helper exits at
startup with a "storage root not found" error.

---

## Step 4 — Ingest Data

### Watch-folder based ingestion

The **ingest helper** (`ingest_helper/metafirst_ingest.py`) runs on the machine where
your data files are saved. It monitors one or more local folders and notifies the
metaFirst server when a new file appears.

Setup is a one-time process per machine:

```bash
# Install dependencies
cd ingest_helper && pip install -r requirements.txt

# Edit the config
cp config.example.yaml config.yaml
# Set server URL, credentials, and watcher paths

# Start the helper
python metafirst_ingest.py config.yaml
```

Once running, saving any new file into a watched folder triggers the ingest flow
automatically.

### The finalize ingest screen

When the helper detects a file it creates a **pending ingest** entry on the server.
If `open_browser: true` is set in the config, a browser tab opens directly to the
**Add Data** screen for that file.

The screen shows:
- File path, storage root, size, and SHA-256 hash.
- Any sample identifier automatically extracted from the filename (if a filename
  regex rule is configured in project Settings).

#### Single-sample mode

1. Choose **Create new sample** or **Link to existing sample**.
   - If creating, type a sample identifier (e.g. `SAMPLE-001`).
   - If an identifier was auto-detected from the filename, it is pre-filled.
2. If creating a new sample, required metadata fields from the RDMP appear below.
   Fill them in now or leave them for later.
3. Click **Add Data**.

The file is linked to the sample and the pending entry is marked complete.

#### Multi-sample mode (qPCR and similar instruments)

1. **Run details** — fill in any `run_fields` defined in the RDMP (e.g. primer batch).
2. **Measured samples grid** — add one row per sample measured in this run:
   - Select the sample from the dropdown.
   - Fill in the index fields (e.g. plate position, gene target).
   - Click **+ Add row** for additional samples.
3. Click **Save measurements**.

   > In multi-sample mode, samples must already exist in the project before you can
   > link them here. Create samples in advance from the **Samples** view, or link
   > them after ingest via the sample detail panel.

### Completing metadata after ingest

Metadata does not have to be complete at ingest time. You can fill in or correct
field values later:

1. Open the project and click on any sample in the metadata table.
2. The sample detail panel opens, showing all RDMP fields as editable inputs.
3. Edit any field value and click **Save** next to that field.
   The completeness indicator in the table updates immediately.

The project overview flags samples with missing required fields so nothing is
overlooked before a data release.

---

## Metadata Model Reference

### Sample metadata fields

**Sample metadata** is information that describes a biological sample — what it is,
where it came from, what was done to it. These fields are defined in the RDMP
`fields` array and appear in the sample detail panel and the metadata table.

Examples: `genotype`, `tissue_type`, `treatment_condition`, `collection_date`.

Each field value is stored per-sample. If you have ten samples and the `genotype`
field is defined, each sample has its own genotype value.

### System fields

Two fields are present in every project regardless of the RDMP:

| Field | Meaning |
|---|---|
| `sample_identifier` | The unique name for a sample within a project. Set at creation time. |
| `visibility` | Controls metadata visibility for this sample. Defaults to `PRIVATE`. |

### Run-level and measurement annotations

In multi-sample mode, two additional types of metadata are captured per file:

- **Run fields** — data that applies to the whole file (e.g. which reagent batch was
  used for the entire qPCR plate). Stored once per file.
- **Measurement annotations** — per-sample records inside a file (e.g. which well
  contained which sample, and what the measured value was). One annotation row
  per sample per file.

These are visible in the sample detail panel under **Measurements**.

---

## Permissions Model

### Two levels of roles

metaFirst uses **two separate role systems** that work together.

**Lab-level roles** (set by the Lab PI in Lab membership management):

| Role | Typical capabilities |
|---|---|
| PI | Full access to all Lab projects; can activate RDMPs; can manage Lab membership |
| Steward | Can create and manage projects; can draft RDMPs |
| Researcher | Can add data and edit metadata |

Lab-level roles control access to Lab-wide operations (creating projects, viewing
Lab activity logs, adding Lab members).

**Project-level roles** (defined inside the RDMP `roles` array, assigned per member
in each project):

The four permission flags in the RDMP control all project operations:

| Flag | What it allows |
|---|---|
| `can_edit_metadata` | Edit sample field values |
| `can_edit_paths` | Submit pending ingests; add files to a project |
| `can_create_release` | Package project data for release |
| `can_manage_rdmp` | Activate RDMPs; add project members; create storage roots |

### How permissions are resolved

When a user takes an action (e.g. saving a metadata field), the system:

1. Looks up the user's **project membership** — the role name they were assigned.
2. Looks up the **active RDMP** — finds the role entry whose name matches.
3. Reads the permission flag for the action from that role entry.

This means permissions are entirely determined by what is written in the RDMP.
Changing the RDMP (and activating the revision) is the only way to change what
a role can do.

### Example

A project has this RDMP role definition:

```json
{
  "name": "researcher",
  "permissions": {
    "can_edit_metadata": true,
    "can_edit_paths": true,
    "can_create_release": false,
    "can_manage_rdmp": false
  }
}
```

A user assigned the `researcher` project role can edit metadata and add files,
but cannot activate RDMPs or create storage roots. If the PI wants to grant
release creation to researchers, they update this entry in the RDMP and activate
the revision.

### Adding a project member

1. Go to the project.
2. Open **Members** (or use the Lab settings page for Lab-wide role changes).
3. Enter the username and assign a project role name.
   The role name must match a role defined in the active RDMP exactly (case-sensitive).

---

## Audit Logging

### What is logged

Every state change in a project is recorded in an append-only audit log. The following
actions are always logged:

| Action | What is recorded |
|---|---|
| File added (ingest finalised) | File path, storage root, sample it was linked to, who added it |
| Sample metadata edited (UI) | Field key, value before the change, value after the change, who made the change |
| Sample metadata set during ingest | Same as above — ingest-time field values are audited the same way as manual edits |
| RDMP created or activated | RDMP content before and after, who triggered it, activation reason |
| Storage root created | Storage root name and description, who created it |
| Storage root mapping updated | Local path mapping, user, before/after state |
| File path changed | Old and new storage root and path, who changed it |

Each audit record includes the timestamp, the acting user, and the project context.

### Why this matters

The audit log provides a continuous, tamper-evident record of data provenance. This
supports:

- **Reproducibility** — you can reconstruct the exact state of a sample's metadata at
  any point in time.
- **Accountability** — every change is attributed to a specific user.
- **Protocol compliance** — for projects involving regulated or sensitive data, the
  audit trail documents that access controls and data handling procedures were followed.

The audit log cannot be edited or deleted through the web interface. It is separate
from the editable metadata.

### Viewing the audit log

The Lab-level **Activity** view (accessible to PIs and Stewards) shows a timeline of
events across all projects in the Lab, with filtering by event type, date range, and
keyword search.

Project-level audit history is accessible from the **History** tab within a project.
