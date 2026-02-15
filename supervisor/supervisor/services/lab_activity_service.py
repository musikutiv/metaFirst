"""Lab activity logging service.

Provides functions for creating and querying lab activity log entries.
Activity logs track governance and operational events at the lab (supervisor) level.

## Adding New Event Types

To log a new event type:

1. Add the event type to `ActivityEventType` enum in `models/lab_activity.py`
2. Call `log_activity()` from your API endpoint after the mutation succeeds
3. For sensitive actions, require a reason parameter in your endpoint

Example:
```python
from supervisor.services.lab_activity_service import log_activity

# After a state change mutation
log_activity(
    db=db,
    lab_id=project.supervisor_id,
    actor_user_id=current_user.id,
    event_type="MY_NEW_EVENT",
    entity_type="PROJECT",
    entity_id=project.id,
    summary_text=f"User performed action on project '{project.name}'",
    reason_text=reason,  # Required for sensitive actions
    before_json={"status": "old"},
    after_json={"status": "new"},
)
```
"""

from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from supervisor.models.lab_activity import LabActivityLog, ActivityEventType, EntityType


def log_activity(
    db: Session,
    lab_id: int,
    actor_user_id: int,
    event_type: str,
    entity_type: str,
    entity_id: int,
    summary_text: str,
    reason_text: Optional[str] = None,
    before_json: Optional[dict] = None,
    after_json: Optional[dict] = None,
) -> LabActivityLog:
    """Create a lab activity log entry.

    Args:
        db: Database session
        lab_id: Supervisor/lab ID
        actor_user_id: User who performed the action
        event_type: Type of event (ActivityEventType value)
        entity_type: Type of entity affected (EntityType value)
        entity_id: ID of the affected entity
        summary_text: Human-readable summary of the action
        reason_text: Optional reason/justification (required for sensitive actions)
        before_json: State before the change (optional)
        after_json: State after the change (optional)

    Returns:
        The created LabActivityLog entry
    """
    activity = LabActivityLog(
        lab_id=lab_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        summary_text=summary_text,
        reason_text=reason_text,
        before_json=before_json,
        after_json=after_json,
    )
    db.add(activity)
    # Don't commit here - let the caller control the transaction
    return activity


def get_lab_activities(
    db: Session,
    lab_id: int,
    event_types: Optional[list[str]] = None,
    search_text: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[LabActivityLog]:
    """Query lab activity logs with filtering.

    Args:
        db: Database session
        lab_id: Supervisor/lab ID to filter by
        event_types: Optional list of event types to filter by
        search_text: Optional text to search in summary and reason
        limit: Maximum number of results
        offset: Pagination offset

    Returns:
        List of LabActivityLog entries, most recent first
    """
    query = db.query(LabActivityLog).filter(LabActivityLog.lab_id == lab_id)

    if event_types:
        query = query.filter(LabActivityLog.event_type.in_(event_types))

    if search_text:
        search_pattern = f"%{search_text}%"
        query = query.filter(
            or_(
                LabActivityLog.summary_text.ilike(search_pattern),
                LabActivityLog.reason_text.ilike(search_pattern),
            )
        )

    return (
        query
        .order_by(LabActivityLog.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def count_lab_activities(
    db: Session,
    lab_id: int,
    event_types: Optional[list[str]] = None,
    search_text: Optional[str] = None,
) -> int:
    """Count lab activity logs with filtering.

    Args:
        db: Database session
        lab_id: Supervisor/lab ID to filter by
        event_types: Optional list of event types to filter by
        search_text: Optional text to search in summary and reason

    Returns:
        Total count of matching entries
    """
    query = db.query(LabActivityLog).filter(LabActivityLog.lab_id == lab_id)

    if event_types:
        query = query.filter(LabActivityLog.event_type.in_(event_types))

    if search_text:
        search_pattern = f"%{search_text}%"
        query = query.filter(
            or_(
                LabActivityLog.summary_text.ilike(search_pattern),
                LabActivityLog.reason_text.ilike(search_pattern),
            )
        )

    return query.count()


# Convenience functions for specific event types

def log_member_added(
    db: Session,
    lab_id: int,
    actor_user_id: int,
    member_user_id: int,
    member_name: str,
    role: str,
    reason_text: Optional[str] = None,
) -> LabActivityLog:
    """Log a member being added to a lab."""
    return log_activity(
        db=db,
        lab_id=lab_id,
        actor_user_id=actor_user_id,
        event_type=ActivityEventType.MEMBER_ADDED.value,
        entity_type=EntityType.MEMBER.value,
        entity_id=member_user_id,
        summary_text=f"Added {member_name} as {role}",
        reason_text=reason_text,
        after_json={"role": role, "user_id": member_user_id},
    )


def log_member_role_changed(
    db: Session,
    lab_id: int,
    actor_user_id: int,
    member_user_id: int,
    member_name: str,
    old_role: str,
    new_role: str,
    reason_text: str,  # Required for role changes
) -> LabActivityLog:
    """Log a member's role being changed."""
    return log_activity(
        db=db,
        lab_id=lab_id,
        actor_user_id=actor_user_id,
        event_type=ActivityEventType.MEMBER_ROLE_CHANGED.value,
        entity_type=EntityType.MEMBER.value,
        entity_id=member_user_id,
        summary_text=f"Changed {member_name} role from {old_role} to {new_role}",
        reason_text=reason_text,
        before_json={"role": old_role},
        after_json={"role": new_role},
    )


def log_member_removed(
    db: Session,
    lab_id: int,
    actor_user_id: int,
    member_user_id: int,
    member_name: str,
    old_role: str,
    reason_text: Optional[str] = None,
) -> LabActivityLog:
    """Log a member being removed from a lab."""
    return log_activity(
        db=db,
        lab_id=lab_id,
        actor_user_id=actor_user_id,
        event_type=ActivityEventType.MEMBER_REMOVED.value,
        entity_type=EntityType.MEMBER.value,
        entity_id=member_user_id,
        summary_text=f"Removed {member_name} (was {old_role})",
        reason_text=reason_text,
        before_json={"role": old_role, "user_id": member_user_id},
    )


def log_rdmp_activated(
    db: Session,
    lab_id: int,
    actor_user_id: int,
    rdmp_id: int,
    project_name: str,
    rdmp_title: str,
    version: int,
    reason_text: str,  # Required for RDMP activation
    superseded_rdmp_id: Optional[int] = None,
) -> LabActivityLog:
    """Log an RDMP being activated."""
    summary = f"Activated RDMP '{rdmp_title}' (v{version}) for project '{project_name}'"
    if superseded_rdmp_id:
        summary += f" (superseded v{superseded_rdmp_id})"

    return log_activity(
        db=db,
        lab_id=lab_id,
        actor_user_id=actor_user_id,
        event_type=ActivityEventType.RDMP_ACTIVATED.value,
        entity_type=EntityType.RDMP.value,
        entity_id=rdmp_id,
        summary_text=summary,
        reason_text=reason_text,
        before_json={"status": "DRAFT"},
        after_json={"status": "ACTIVE", "version": version},
    )


def log_project_created(
    db: Session,
    lab_id: int,
    actor_user_id: int,
    project_id: int,
    project_name: str,
) -> LabActivityLog:
    """Log a project being created."""
    return log_activity(
        db=db,
        lab_id=lab_id,
        actor_user_id=actor_user_id,
        event_type=ActivityEventType.PROJECT_CREATED.value,
        entity_type=EntityType.PROJECT.value,
        entity_id=project_id,
        summary_text=f"Created project '{project_name}'",
        after_json={"name": project_name},
    )
