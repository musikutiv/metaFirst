"""Remediation tasks API endpoints."""

import json
from typing import Annotated, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from supervisor.database import get_db
from supervisor.models.user import User
from supervisor.models.supervisor import Supervisor
from supervisor.models.remediation import RemediationTask, TaskStatus
from supervisor.models.supervisor_membership import SupervisorRole
from supervisor.api.deps import get_current_active_user, require_supervisor_role, require_any_supervisor_role
from supervisor.services.remediation_service import transition_task_status


router = APIRouter()


# --- Schemas ---

class TaskResponse(BaseModel):
    """Remediation task response schema."""
    id: int
    supervisor_id: int
    project_id: int
    sample_id: Optional[int]
    issue_type: str
    status: str
    description: Optional[str]
    metadata: Optional[dict]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    acked_by: Optional[int]
    acked_at: Optional[datetime]
    approved_by: Optional[int]
    approved_at: Optional[datetime]
    dismissed_by: Optional[int]
    dismissed_at: Optional[datetime]
    executed_at: Optional[datetime]


class TaskListResponse(BaseModel):
    """List of remediation tasks."""
    tasks: list[TaskResponse]
    total: int


class StatusResponse(BaseModel):
    """Generic status response."""
    status: str
    task_id: int
    new_status: str


# --- Helper functions ---

def task_to_response(task: RemediationTask) -> TaskResponse:
    """Convert a task model to response schema."""
    metadata = None
    if task.metadata_json:
        try:
            metadata = json.loads(task.metadata_json)
        except json.JSONDecodeError:
            pass

    return TaskResponse(
        id=task.id,
        supervisor_id=task.supervisor_id,
        project_id=task.project_id,
        sample_id=task.sample_id,
        issue_type=task.issue_type,
        status=task.status,
        description=task.description,
        metadata=metadata,
        created_at=task.created_at,
        updated_at=task.updated_at,
        acked_by=task.acked_by,
        acked_at=task.acked_at,
        approved_by=task.approved_by,
        approved_at=task.approved_at,
        dismissed_by=task.dismissed_by,
        dismissed_at=task.dismissed_at,
        executed_at=task.executed_at,
    )


# --- Endpoints ---

@router.get("/remediation/tasks", response_model=TaskListResponse)
def list_tasks(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    supervisor_id: int = Query(..., description="Supervisor ID to list tasks for"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """List remediation tasks for a supervisor.

    Requires STEWARD or PI role.
    """
    # Check authorization - require steward or PI
    require_supervisor_role(db, current_user, supervisor_id, [SupervisorRole.STEWARD, SupervisorRole.PI])

    query = db.query(RemediationTask).filter(RemediationTask.supervisor_id == supervisor_id)

    if status_filter:
        query = query.filter(RemediationTask.status == status_filter.upper())

    total = query.count()
    tasks = query.order_by(RemediationTask.created_at.desc()).offset(offset).limit(limit).all()

    return TaskListResponse(
        tasks=[task_to_response(t) for t in tasks],
        total=total,
    )


@router.get("/remediation/tasks/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Get a specific remediation task.

    Requires membership in the task's supervisor.
    """
    task = db.query(RemediationTask).filter(RemediationTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    # Check authorization - require any membership
    require_any_supervisor_role(db, current_user, task.supervisor_id)

    return task_to_response(task)


@router.post("/remediation/tasks/{task_id}/ack", response_model=StatusResponse)
def acknowledge_task(
    task_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Acknowledge a remediation task.

    Requires any membership in the task's supervisor.
    """
    task = db.query(RemediationTask).filter(RemediationTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    # Check authorization - any member can ack
    require_any_supervisor_role(db, current_user, task.supervisor_id)

    try:
        task = transition_task_status(db, task, TaskStatus.ACKED, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return StatusResponse(status="success", task_id=task.id, new_status=task.status)


@router.post("/remediation/tasks/{task_id}/approve", response_model=StatusResponse)
def approve_task(
    task_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Approve a remediation task for execution.

    Requires STEWARD or PI role.
    """
    task = db.query(RemediationTask).filter(RemediationTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    # Check authorization - require steward or PI
    require_supervisor_role(db, current_user, task.supervisor_id, [SupervisorRole.STEWARD, SupervisorRole.PI])

    try:
        task = transition_task_status(db, task, TaskStatus.APPROVED, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return StatusResponse(status="success", task_id=task.id, new_status=task.status)


@router.post("/remediation/tasks/{task_id}/dismiss", response_model=StatusResponse)
def dismiss_task(
    task_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Dismiss a remediation task (no action needed).

    Requires STEWARD or PI role.
    """
    task = db.query(RemediationTask).filter(RemediationTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    # Check authorization - require steward or PI
    require_supervisor_role(db, current_user, task.supervisor_id, [SupervisorRole.STEWARD, SupervisorRole.PI])

    try:
        task = transition_task_status(db, task, TaskStatus.DISMISSED, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return StatusResponse(status="success", task_id=task.id, new_status=task.status)


@router.post("/remediation/tasks/{task_id}/execute", response_model=StatusResponse)
def execute_task(
    task_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Execute a remediation task.

    Requires STEWARD or PI role AND supervisor.enable_automated_execution must be True.
    Returns 403 if automated execution is disabled.
    """
    task = db.query(RemediationTask).filter(RemediationTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    # Check authorization - require steward or PI
    require_supervisor_role(db, current_user, task.supervisor_id, [SupervisorRole.STEWARD, SupervisorRole.PI])

    # Check if automated execution is enabled
    supervisor = db.query(Supervisor).filter(Supervisor.id == task.supervisor_id).first()
    if not supervisor or not supervisor.enable_automated_execution:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Automated execution is disabled for this supervisor. Enable it in supervisor settings.",
        )

    try:
        task = transition_task_status(db, task, TaskStatus.EXECUTED, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Note: Actual execution logic (e.g., deleting data) would go here
    # For now, we just mark the task as executed

    return StatusResponse(status="success", task_id=task.id, new_status=task.status)
