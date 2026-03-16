---
title: Glossary — metaFirst
---

# Glossary

Quick reference for terms used in the [Researcher Guide](researcher-guide).

| Term | Meaning |
|------|---------|
| **Lab** | Your research group in metaFirst. The Lab is the top-level container for projects, members, and watch folders. |
| **Project** | A container for a set of related experiments. Belongs to exactly one Lab. |
| **Protocol (RDMP)** | A Research Data Management Plan. Defines the metadata fields for a project, who can edit them, and what is visible outside the Lab. Has three states: Draft, Active, Superseded. |
| **Ingest / ingest helper** | The background process that watches a folder on your machine. When a new file appears, it creates a pending entry and (optionally) opens a browser tab for metadata entry. |
| **Watch folder** | A local folder monitored by the ingest helper. Saving a file here triggers metadata entry. |
| **Storage root** | A named device or storage location registered in a project (e.g. `NovaSeq output NAS`, `Microscope workstation`). The ingest helper links each file to a storage root using the `storage_root_name` in its config. Each user can set a personal **local path mapping** so the UI can display the full reconstructed file path. |
| **Pending entry** | A file detected by the ingest helper that has not yet had its metadata filled in. Visible in the project overview. |
| **Metadata visibility** | Controls who can see the project's metadata: PRIVATE (Lab only), INSTITUTION, or PUBLIC. Files are never transferred regardless of this setting. |
| **PI** | Principal Investigator. Highest role in a Lab. Can activate protocols and manage Lab membership. |
| **Steward** | Mid-level role. Can create projects and draft protocol revisions. |
| **Researcher** | Standard role. Can add data, complete metadata forms, and browse project history. |
| **Superseded** | A protocol that has been replaced by a newer active version. Superseded protocols and their entries remain in the history. |
