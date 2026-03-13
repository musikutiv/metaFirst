---
title: Researcher Guide — metaFirst
---

# Researcher Guide

metaFirst records what you collected and when — without moving your files.
This guide walks through the full workflow, from planning an experiment to
browsing your data history.

**Contents**

- [Your Lab](#your-lab)
- [Projects](#projects)
- [The Protocol (RDMP)](#the-protocol-rdmp)
- [Setting Up a Watch Folder](#setting-up-a-watch-folder)
- [Add Data](#add-data)
- [Overview and History](#overview-and-history)
- [Metadata Visibility](#metadata-visibility)
- [Worked Example: Western Blot](#worked-example-western-blot)
- [Known Issues](#known-issues)


---

## Your Lab

In metaFirst, **Lab** is the name for your research group.
Every project, member, and watch folder belongs to exactly one Lab.
Your Lab lead (PI) sets up the Lab and invites you as a member.

Your role within the Lab determines what you can do:

| Role | Can do |
|----------|--------------------------------------------------|
| PI | Manage Lab membership, activate protocols, create projects |
| Steward | Create and manage projects, write and revise protocols |
| Researcher | Add data, complete metadata forms, browse project history |

Roles are Lab-scoped. If you are in two Labs, you may have a different role in each.


---

## Projects

A **project** is a container for a set of related experiments and the metadata that goes with them.
It belongs to one Lab, and you can only see projects from Labs you are a member of.

To start working in a project:

- Open the web interface at the URL your Lab lead shared.
- Select your Lab from the sidebar.
- Pick an existing project, or ask your Steward or PI to create one.

A project has no data until you add some (see [Add Data](#add-data)).
It also needs an active protocol before the metadata form appears — see the next section.


---

## The Protocol (RDMP)

Before a project can accept data, it needs an active **protocol**.
In metaFirst, this is called an RDMP (Research Data Management Plan).

Think of it as the methods-section header that defines:

- **Metadata fields** — what to fill in for each file or sample (e.g. antibody, date, gel type, notes)
- **Who can edit** those fields
- **What is visible** outside the Lab (see [Metadata Visibility](#metadata-visibility))

### Protocol states

| State | Meaning |
|------------|---------------------------------------------------|
| Draft | Being written; project does not yet accept data |
| Active | In use; the metadata form reflects these fields |
| Superseded | Replaced by a newer version; history is preserved |

Only one protocol is active per project at any time.
When a new protocol is activated, the previous one moves to superseded — old entries keep their original fields in the history.

### What you need to do

You usually do not write the protocol yourself.
Your PI or Steward drafts it; the PI activates it.

If a metadata field is missing or wrong for your experiment, let your Steward know.
They can draft a revision. Your PI activates the revision and the project continues with the new fields.


---

## Setting Up a Watch Folder

A **watch folder** is a local folder on your machine (or on lab storage) that metaFirst monitors.
When you save a new file there, the ingest helper detects it and opens a browser tab so you can fill in the metadata straight away.

This is a one-time setup, done by you or whoever manages your machine.

### Step 1 — Install the ingest helper

```
cd metaFirst
./scripts/install_user.sh
```

### Step 2 — Edit the config file

Open `ingest_helper/config.yaml` and fill in your details:

```yaml
supervisor_url: http://<lab-server>:8000
username: alice
password: your_password
ui_url: http://<lab-server>:5173
open_browser: true

watchers:
  - watch_path: /Users/alice/data/western_blot
    project_name: "Membrane Proteins 2026"
    storage_root_name: "LOCAL_DATA"
```

Replace `<lab-server>` with the address your Lab lead gave you.
Use the project name exactly as it appears in the web interface (case-sensitive).

### Step 3 — Start the helper

```
cd ingest_helper
python metafirst_ingest.py config.yaml
```

Leave this terminal open.
The helper prints a startup banner confirming which project and storage location it resolved:

```
Bound to supervisor: Membrane Proteins Lab (id=1)
Resolved watcher mappings:
  /Users/alice/data/western_blot
    -> project: Membrane Proteins 2026 (id=3)
    -> storage_root: LOCAL_DATA (id=7)
```

If the banner shows an error, see [Known Issues](#known-issues).


---

## Add Data

Save your raw data file into the watch folder as you normally would.

```
/Users/alice/data/western_blot/
└── gel_2026-03-13_GAPDH.tif
```

Within a few seconds the helper detects the file.
If `open_browser: true`, a browser tab opens with a metadata form.
Fill in the fields and save.

That's it. The file path is recorded in metaFirst; the file itself stays on your machine.

If the browser does not open automatically, go to the web interface, open your project, and look for pending entries in the overview.


---

## Overview and History

Open the project in the web interface to see everything that has been recorded.

- **Overview** — the current list of files and samples: what is present, what fields have been filled in.
- **History** — a full log of all entries in order of when they were added.

You can search by any metadata field, see who entered what, and check whether a field value is present or missing for a given entry.

Nothing is deleted automatically. Superseded protocol versions and their entries remain in the history.


---

## Metadata Visibility

Each project has a **visibility** setting that controls who can see its metadata.

| Setting | Who can see it |
|-------------|-----------------------------------------------|
| PRIVATE | Lab members only |
| INSTITUTION | Your institution (metadata only) |
| PUBLIC | Anyone (metadata only — files are never shared) |

Your PI or Steward sets this on the project.
Files are never transferred or exposed regardless of the visibility setting.
If you are unsure of the current setting, check the project overview or ask your Steward.


---

## Worked Example: Western Blot

**Scenario.** You run a western blot with one gel image and four lanes: two conditions, each in duplicate.

**Watch folder contents after the experiment:**

```
/Users/alice/data/western_blot/
└── gel_2026-03-13_GAPDH.tif
```

**Steps:**

1. Save `gel_2026-03-13_GAPDH.tif` into the watch folder.
2. The browser opens. Fill in the metadata form (fields defined by your project protocol):
   - **Date:** 2026-03-13
   - **Target:** GAPDH
   - **Antibody:** anti-GAPDH (Abcam ab9484, 1:5000)
   - **Gel type:** SDS-PAGE 12%
   - **Notes:** Lane 1 — WT untreated; Lane 2 — WT +dox 24 h; Lane 3 — KO untreated; Lane 4 — KO +dox 24 h. Duplicate blot, n = 2 biological replicates.
3. Save the form.

**One file, multiple samples.** metaFirst creates one record linked to the image file.
The lane-to-sample mapping goes in the **Notes** field (or whichever free-text field your protocol defines) as plain text.
This is a documentation pattern — keep the format consistent within your project so it is searchable later.

If your protocol has dedicated per-lane fields, use those instead.
If those fields are missing and you need them, ask your Steward to draft a protocol revision that adds them.


---

## Known Issues

These are factual notes about common situations. None of them prevent you from recording data.

**Filenames.** The watch folder records the exact file path at the moment of detection.
Renaming a file after it has been ingested creates a new entry; the original path remains in the history.
Use consistent, descriptive filenames before saving to the watch folder.

**Permissions.** The ingest helper authenticates with the credentials in `config.yaml`.
If your password changes, update the config file and restart the helper.
If your account is not a member of the project listed in the config, the helper logs a rejection and skips the file.

**Multiple samples per file.** There is no dedicated multi-sample-per-file feature.
Record the sample mapping in a notes or free-text field (see the western blot example above).

**Protocol in draft.** If the project protocol has not been activated yet, the metadata form does not appear.
The file is still detected and a pending entry is created — it shows up in the project overview.
Return to the web interface to complete the entry once the protocol is active.

**Watch folder not running.** If the ingest helper is not running when you save a file, that file is not detected automatically.
Start the helper and add the entry manually via the web interface.

**Multiple Labs.** If you belong to more than one Lab, each Lab's projects appear separately in the sidebar.
Each Lab needs its own config file and its own running instance of the helper.

**Project or storage root not found at startup.** Names in `config.yaml` must match exactly, including capitalisation.
The error message lists the name it could not resolve.
Check the project name in the web interface, correct the config, and restart the helper.
