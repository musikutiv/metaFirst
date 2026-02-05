"""Lab status aggregation service.

Computes lab-scoped operational summary and surfaces conditions that
require Steward or PI attention. All aggregation is strictly lab-scoped
and reflects current DB state only (no caching).

This is a read-only, advisory service — it does not enforce anything.

## Needs-attention conditions (v0.5, append-only)

Each condition has a fixed severity. New conditions may be appended
in future versions without changing the semantics of existing ones.

    Type                                    Severity
    ----                                    --------
    project_operational_without_active_rdmp high
    unresolved_remediation_high             high
    unresolved_remediation_warning          warning
    project_with_superseded_rdmp            warning
    project_without_rdmp                    info

## Remediation severity mapping

Remediation tasks derive their severity from issue_type:

    retention_exceeded → high
    embargo_active     → warning
    (unknown)          → info
"""

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from supervisor.models.project import Project
from supervisor.models.rdmp import RDMPVersion, RDMPStatus
from supervisor.models.remediation import RemediationTask


# Unresolved remediation statuses (not yet resolved via dismiss/execute)
_UNRESOLVED_STATUSES = ("PENDING", "ACKED")

# Issue type → severity mapping for remediation tasks.
# Unknown types default to "info".
_ISSUE_SEVERITY: dict[str, str] = {
    "retention_exceeded": "high",
    "embargo_active": "warning",
}

# Maximum entity_ids returned per needs_attention item.
_MAX_ENTITY_IDS = 10


@dataclass
class NeedsAttentionItem:
    type: str
    severity: str  # "info" | "warning" | "high"
    count: int
    entity_type: str  # "lab" | "project"
    entity_ids: list[int]
    message: str


@dataclass
class ProjectSummary:
    total_projects: int
    by_operational_state: dict[str, int]
    by_rdmp_status: dict[str, int]


@dataclass
class RemediationSummary:
    total_open: int
    by_severity: dict[str, int]


@dataclass
class LabStatusSummary:
    projects: ProjectSummary
    needs_attention: list[NeedsAttentionItem]
    remediation_summary: RemediationSummary


def _get_remediation_severity(issue_type: str) -> str:
    return _ISSUE_SEVERITY.get(issue_type, "info")


def compute_lab_status(db: Session, supervisor_id: int) -> LabStatusSummary:
    """Compute lab status summary from current DB state.

    All queries are scoped to the given supervisor_id.
    """
    # ------------------------------------------------------------------
    # 1. Project aggregation
    # ------------------------------------------------------------------
    projects = (
        db.query(Project)
        .filter(Project.supervisor_id == supervisor_id)
        .all()
    )

    total_projects = len(projects)
    operational_count = sum(1 for p in projects if p.is_active)
    non_operational_count = total_projects - operational_count

    # For each project, determine its RDMP category.
    # Categories are mutually exclusive per project:
    #   active     — has at least one ACTIVE RDMP
    #   draft      — has DRAFT but no ACTIVE
    #   superseded — has SUPERSEDED but no ACTIVE and no DRAFT
    #   no_rdmp    — no RDMP records at all
    rdmp_counts = {"no_rdmp": 0, "draft": 0, "active": 0, "superseded": 0}
    project_ids = [p.id for p in projects]

    # Fetch all RDMP statuses grouped by project in one query
    rdmp_status_by_project: dict[int, set[str]] = {}
    if project_ids:
        rdmp_rows = (
            db.query(RDMPVersion.project_id, RDMPVersion.status)
            .filter(RDMPVersion.project_id.in_(project_ids))
            .all()
        )
        for pid, st in rdmp_rows:
            rdmp_status_by_project.setdefault(pid, set()).add(
                st.value if hasattr(st, "value") else st
            )

    for p in projects:
        statuses = rdmp_status_by_project.get(p.id, set())
        if not statuses:
            rdmp_counts["no_rdmp"] += 1
        elif "ACTIVE" in statuses:
            rdmp_counts["active"] += 1
        elif "DRAFT" in statuses:
            rdmp_counts["draft"] += 1
        else:
            rdmp_counts["superseded"] += 1

    project_summary = ProjectSummary(
        total_projects=total_projects,
        by_operational_state={
            "operational": operational_count,
            "non_operational": non_operational_count,
        },
        by_rdmp_status=rdmp_counts,
    )

    # ------------------------------------------------------------------
    # 2. Needs-attention conditions
    # ------------------------------------------------------------------
    needs_attention: list[NeedsAttentionItem] = []

    # 2a. project_operational_without_active_rdmp (high)
    #     Project is_active=True but has no ACTIVE RDMP.
    op_without_active = [
        p.id for p in projects
        if p.is_active and "ACTIVE" not in rdmp_status_by_project.get(p.id, set())
    ]
    if op_without_active:
        needs_attention.append(NeedsAttentionItem(
            type="project_operational_without_active_rdmp",
            severity="high",
            count=len(op_without_active),
            entity_type="project",
            entity_ids=op_without_active[:_MAX_ENTITY_IDS],
            message=(
                f"{len(op_without_active)} operational project(s) lack an active RDMP."
            ),
        ))

    # 2b. project_with_superseded_rdmp (warning)
    #     Project has SUPERSEDED RDMP(s) but no ACTIVE (regardless of is_active).
    superseded_no_active = [
        p.id for p in projects
        if "SUPERSEDED" in rdmp_status_by_project.get(p.id, set())
        and "ACTIVE" not in rdmp_status_by_project.get(p.id, set())
    ]
    if superseded_no_active:
        needs_attention.append(NeedsAttentionItem(
            type="project_with_superseded_rdmp",
            severity="warning",
            count=len(superseded_no_active),
            entity_type="project",
            entity_ids=superseded_no_active[:_MAX_ENTITY_IDS],
            message=(
                f"{len(superseded_no_active)} project(s) have only superseded RDMPs."
            ),
        ))

    # 2c. project_without_rdmp (info)
    no_rdmp = [
        p.id for p in projects
        if not rdmp_status_by_project.get(p.id, set())
    ]
    if no_rdmp:
        needs_attention.append(NeedsAttentionItem(
            type="project_without_rdmp",
            severity="info",
            count=len(no_rdmp),
            entity_type="project",
            entity_ids=no_rdmp[:_MAX_ENTITY_IDS],
            message=(
                f"{len(no_rdmp)} project(s) have no RDMP."
            ),
        ))

    # 2d–2e. Unresolved remediation tasks by derived severity
    unresolved_tasks = (
        db.query(RemediationTask)
        .filter(
            RemediationTask.supervisor_id == supervisor_id,
            RemediationTask.status.in_(_UNRESOLVED_STATUSES),
        )
        .all()
    )

    # Group by derived severity
    remediation_by_severity: dict[str, list[int]] = {}
    for task in unresolved_tasks:
        sev = _get_remediation_severity(task.issue_type)
        remediation_by_severity.setdefault(sev, []).append(task.project_id)

    high_project_ids = remediation_by_severity.get("high", [])
    if high_project_ids:
        unique_ids = list(dict.fromkeys(high_project_ids))  # dedupe, preserve order
        needs_attention.append(NeedsAttentionItem(
            type="unresolved_remediation_high",
            severity="high",
            count=len(high_project_ids),
            entity_type="project",
            entity_ids=unique_ids[:_MAX_ENTITY_IDS],
            message=(
                f"{len(high_project_ids)} high-severity remediation task(s) unresolved."
            ),
        ))

    warning_project_ids = remediation_by_severity.get("warning", [])
    if warning_project_ids:
        unique_ids = list(dict.fromkeys(warning_project_ids))
        needs_attention.append(NeedsAttentionItem(
            type="unresolved_remediation_warning",
            severity="warning",
            count=len(warning_project_ids),
            entity_type="project",
            entity_ids=unique_ids[:_MAX_ENTITY_IDS],
            message=(
                f"{len(warning_project_ids)} warning-severity remediation task(s) unresolved."
            ),
        ))

    # ------------------------------------------------------------------
    # 3. Remediation summary
    # ------------------------------------------------------------------
    total_open = len(unresolved_tasks)
    severity_counts: dict[str, int] = {"high": 0, "warning": 0, "info": 0}
    for task in unresolved_tasks:
        sev = _get_remediation_severity(task.issue_type)
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    remediation_summary = RemediationSummary(
        total_open=total_open,
        by_severity=severity_counts,
    )

    return LabStatusSummary(
        projects=project_summary,
        needs_attention=needs_attention,
        remediation_summary=remediation_summary,
    )
