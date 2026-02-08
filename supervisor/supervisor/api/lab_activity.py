"""Lab activity log API endpoints."""

from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from supervisor.database import get_db
from supervisor.models.user import User
from supervisor.models.supervisor import Supervisor
from supervisor.models.supervisor_membership import SupervisorRole
from supervisor.models.lab_activity import LabActivityLog, ActivityEventType
from supervisor.api.deps import get_current_active_user, require_supervisor_role
from supervisor.services.lab_activity_service import (
    get_lab_activities,
    count_lab_activities,
)

router = APIRouter()


# -------------------------------------------------------------------------
# Schemas
# -------------------------------------------------------------------------

class ActivityLogResponse(BaseModel):
    """Response schema for an activity log entry."""
    id: int
    lab_id: int
    created_at: str
    actor_user_id: int
    actor_display_name: str | None = None
    event_type: str
    entity_type: str
    entity_id: int
    summary_text: str
    reason_text: str | None = None
    before_json: dict | None = None
    after_json: dict | None = None

    class Config:
        from_attributes = True


class ActivityLogListResponse(BaseModel):
    """Response schema for paginated activity log list."""
    items: list[ActivityLogResponse]
    total: int
    limit: int
    offset: int


class EventTypeOption(BaseModel):
    """Event type option for filtering."""
    value: str
    label: str


# -------------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------------

@router.get(
    "/supervisors/{supervisor_id}/activity",
    response_model=ActivityLogListResponse,
)
def list_lab_activity(
    supervisor_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    event_types: Optional[str] = Query(
        default=None,
        description="Comma-separated list of event types to filter by"
    ),
    search: Optional[str] = Query(
        default=None,
        description="Search text in summary and reason"
    ),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """List activity logs for a lab.

    Returns a chronological feed of governance and operational events.
    Any lab member can view the activity log.
    """
    # Verify lab exists
    supervisor = db.query(Supervisor).filter(Supervisor.id == supervisor_id).first()
    if not supervisor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lab not found"
        )

    # Any member can view activity
    require_supervisor_role(
        db, current_user, supervisor_id,
        [SupervisorRole.RESEARCHER, SupervisorRole.STEWARD, SupervisorRole.PI]
    )

    # Parse event types filter
    event_type_list = None
    if event_types:
        event_type_list = [t.strip() for t in event_types.split(",") if t.strip()]

    # Query activities
    activities = get_lab_activities(
        db=db,
        lab_id=supervisor_id,
        event_types=event_type_list,
        search_text=search,
        limit=limit,
        offset=offset,
    )

    total = count_lab_activities(
        db=db,
        lab_id=supervisor_id,
        event_types=event_type_list,
        search_text=search,
    )

    # Build response with actor display names
    items = []
    for activity in activities:
        actor_name = None
        if activity.actor:
            actor_name = activity.actor.display_name or activity.actor.username

        items.append(ActivityLogResponse(
            id=activity.id,
            lab_id=activity.lab_id,
            created_at=activity.created_at.isoformat() if activity.created_at else "",
            actor_user_id=activity.actor_user_id,
            actor_display_name=actor_name,
            event_type=activity.event_type,
            entity_type=activity.entity_type,
            entity_id=activity.entity_id,
            summary_text=activity.summary_text,
            reason_text=activity.reason_text,
            before_json=activity.before_json,
            after_json=activity.after_json,
        ))

    return ActivityLogListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/supervisors/{supervisor_id}/activity/event-types",
    response_model=list[EventTypeOption],
)
def list_event_types(
    supervisor_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """List available event types for filtering.

    Returns all event types with human-readable labels.
    """
    # Verify access
    supervisor = db.query(Supervisor).filter(Supervisor.id == supervisor_id).first()
    if not supervisor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lab not found"
        )

    require_supervisor_role(
        db, current_user, supervisor_id,
        [SupervisorRole.RESEARCHER, SupervisorRole.STEWARD, SupervisorRole.PI]
    )

    # Return all event types with labels
    event_type_labels = {
        ActivityEventType.MEMBER_ADDED: "Member Added",
        ActivityEventType.MEMBER_ROLE_CHANGED: "Role Changed",
        ActivityEventType.MEMBER_REMOVED: "Member Removed",
        ActivityEventType.RDMP_CREATED: "RDMP Created",
        ActivityEventType.RDMP_ACTIVATED: "RDMP Activated",
        ActivityEventType.RDMP_SUPERSEDED: "RDMP Superseded",
        ActivityEventType.PROJECT_CREATED: "Project Created",
        ActivityEventType.PROJECT_OPERATIONAL: "Project Made Operational",
        ActivityEventType.PROJECT_DISABLED: "Project Disabled",
        ActivityEventType.VISIBILITY_CHANGED: "Visibility Changed",
        ActivityEventType.STORAGE_ROOT_CREATED: "Storage Root Created",
        ActivityEventType.STORAGE_ROOT_UPDATED: "Storage Root Updated",
        ActivityEventType.STORAGE_ROOT_DISABLED: "Storage Root Disabled",
    }

    return [
        EventTypeOption(value=et.value, label=label)
        for et, label in event_type_labels.items()
    ]
