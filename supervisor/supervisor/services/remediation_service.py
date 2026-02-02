"""Remediation service for detecting and creating remediation tasks."""

import json
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from supervisor.models.project import Project
from supervisor.models.sample import Sample
from supervisor.models.rdmp import RDMPVersion, RDMPStatus
from supervisor.models.remediation import RemediationTask, IssueType, TaskStatus


def detect_issues_for_project(
    db: Session,
    project_id: int,
    reference_date: Optional[datetime] = None,
) -> list[dict]:
    """Detect RDMP policy violations for a project.

    Args:
        db: Database session
        project_id: Project to check
        reference_date: Date to use for comparisons (default: now)

    Returns:
        List of detected issues, each a dict with:
        - issue_type: IssueType value
        - sample_id: Optional sample ID
        - description: Human-readable description
        - metadata: Additional context
    """
    if reference_date is None:
        reference_date = datetime.now(timezone.utc)

    issues = []

    # Get active RDMP for project
    rdmp = db.query(RDMPVersion).filter(
        RDMPVersion.project_id == project_id,
        RDMPVersion.status == RDMPStatus.ACTIVE,
    ).first()

    if not rdmp:
        return issues  # No active RDMP, no policy to enforce

    # Check embargo
    if rdmp.embargo_until:
        embargo_until = rdmp.embargo_until
        if embargo_until.tzinfo is None:
            embargo_until = embargo_until.replace(tzinfo=timezone.utc)
        if reference_date < embargo_until:
            issues.append({
                "issue_type": IssueType.EMBARGO_ACTIVE.value,
                "sample_id": None,
                "description": f"Project data under embargo until {rdmp.embargo_until.isoformat()}",
                "metadata": {
                    "embargo_until": rdmp.embargo_until.isoformat(),
                    "rdmp_version_id": rdmp.id,
                },
            })

    # Check retention - find samples past retention period
    if rdmp.retention_days:
        samples = db.query(Sample).filter(Sample.project_id == project_id).all()

        for sample in samples:
            if sample.created_at:
                # Make sample.created_at timezone-aware if needed
                sample_created = sample.created_at
                if sample_created.tzinfo is None:
                    sample_created = sample_created.replace(tzinfo=timezone.utc)

                days_old = (reference_date - sample_created).days
                if days_old > rdmp.retention_days:
                    issues.append({
                        "issue_type": IssueType.RETENTION_EXCEEDED.value,
                        "sample_id": sample.id,
                        "description": f"Sample '{sample.sample_identifier}' is {days_old} days old, exceeds retention of {rdmp.retention_days} days",
                        "metadata": {
                            "sample_identifier": sample.sample_identifier,
                            "days_old": days_old,
                            "retention_days": rdmp.retention_days,
                            "rdmp_version_id": rdmp.id,
                        },
                    })

    return issues


def create_task(
    db: Session,
    supervisor_id: int,
    project_id: int,
    issue_type: str,
    description: str,
    sample_id: Optional[int] = None,
    metadata: Optional[dict] = None,
) -> RemediationTask:
    """Create a new remediation task.

    Args:
        db: Database session
        supervisor_id: Supervisor ID
        project_id: Project ID
        issue_type: Type of issue
        description: Human-readable description
        sample_id: Optional sample ID
        metadata: Optional additional context

    Returns:
        Created RemediationTask
    """
    task = RemediationTask(
        supervisor_id=supervisor_id,
        project_id=project_id,
        sample_id=sample_id,
        issue_type=issue_type,
        status=TaskStatus.PENDING.value,
        description=description,
        metadata_json=json.dumps(metadata) if metadata else None,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def task_exists(
    db: Session,
    project_id: int,
    issue_type: str,
    sample_id: Optional[int] = None,
) -> bool:
    """Check if a similar open task already exists.

    Args:
        db: Database session
        project_id: Project ID
        issue_type: Type of issue
        sample_id: Optional sample ID

    Returns:
        True if an open task exists
    """
    query = db.query(RemediationTask).filter(
        RemediationTask.project_id == project_id,
        RemediationTask.issue_type == issue_type,
        RemediationTask.status.in_([TaskStatus.PENDING.value, TaskStatus.ACKED.value, TaskStatus.APPROVED.value]),
    )

    if sample_id:
        query = query.filter(RemediationTask.sample_id == sample_id)
    else:
        query = query.filter(RemediationTask.sample_id.is_(None))

    return query.first() is not None


def transition_task_status(
    db: Session,
    task: RemediationTask,
    new_status: TaskStatus,
    user_id: int,
) -> RemediationTask:
    """Transition a task to a new status.

    Args:
        db: Database session
        task: Task to update
        new_status: New status
        user_id: User performing the action

    Returns:
        Updated task

    Raises:
        ValueError: If transition is invalid
    """
    now = datetime.now(timezone.utc)
    current = TaskStatus(task.status)

    # Validate transitions
    valid_transitions = {
        TaskStatus.PENDING: [TaskStatus.ACKED, TaskStatus.DISMISSED],
        TaskStatus.ACKED: [TaskStatus.APPROVED, TaskStatus.DISMISSED],
        TaskStatus.APPROVED: [TaskStatus.EXECUTED, TaskStatus.DISMISSED],
        TaskStatus.DISMISSED: [],
        TaskStatus.EXECUTED: [],
    }

    if new_status not in valid_transitions.get(current, []):
        raise ValueError(f"Invalid transition from {current.value} to {new_status.value}")

    task.status = new_status.value

    if new_status == TaskStatus.ACKED:
        task.acked_by = user_id
        task.acked_at = now
    elif new_status == TaskStatus.APPROVED:
        task.approved_by = user_id
        task.approved_at = now
    elif new_status == TaskStatus.DISMISSED:
        task.dismissed_by = user_id
        task.dismissed_at = now
    elif new_status == TaskStatus.EXECUTED:
        task.executed_at = now

    db.commit()
    db.refresh(task)
    return task
