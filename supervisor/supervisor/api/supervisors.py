"""Supervisors API."""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from supervisor.database import get_db
from supervisor.models.user import User
from supervisor.models.supervisor import Supervisor
from supervisor.schemas.supervisor import (
    Supervisor as SupervisorSchema,
    SupervisorCreate,
    SupervisorUpdate,
)
from supervisor.api.deps import get_current_active_user, require_supervisor_role
from supervisor.models.supervisor_membership import SupervisorRole

router = APIRouter()


@router.get("/", response_model=list[SupervisorSchema])
def list_supervisors(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """List all active supervisors."""
    supervisors = db.query(Supervisor).filter(Supervisor.is_active == True).all()
    return supervisors


@router.get("/{supervisor_id}", response_model=SupervisorSchema)
def get_supervisor(
    supervisor_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """Get supervisor details."""
    supervisor = db.query(Supervisor).filter(Supervisor.id == supervisor_id).first()
    if not supervisor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supervisor not found")
    return supervisor


@router.post("/", response_model=SupervisorSchema, status_code=status.HTTP_201_CREATED)
def create_supervisor(
    supervisor_data: SupervisorCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """Create a new supervisor.

    Note: In a production system, this would require admin privileges.
    For now, any authenticated user can create a supervisor.
    """
    # Check if supervisor name already exists
    existing = db.query(Supervisor).filter(Supervisor.name == supervisor_data.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Supervisor name already exists"
        )

    # Create supervisor
    supervisor = Supervisor(
        name=supervisor_data.name,
        description=supervisor_data.description,
        supervisor_db_dsn=supervisor_data.supervisor_db_dsn,
    )
    db.add(supervisor)
    db.commit()
    db.refresh(supervisor)

    return supervisor


@router.patch("/{supervisor_id}", response_model=SupervisorSchema)
def update_supervisor(
    supervisor_id: int,
    supervisor_data: SupervisorUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """Update a supervisor.

    Requires STEWARD or PI role for the supervisor.
    """
    supervisor = db.query(Supervisor).filter(Supervisor.id == supervisor_id).first()
    if not supervisor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supervisor not found")

    # Require STEWARD or PI role for supervisor updates
    require_supervisor_role(db, current_user, supervisor_id, [SupervisorRole.STEWARD, SupervisorRole.PI])

    # Update fields if provided
    if supervisor_data.name is not None:
        # Check for name conflict
        existing = db.query(Supervisor).filter(
            Supervisor.name == supervisor_data.name,
            Supervisor.id != supervisor_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Supervisor name already exists"
            )
        supervisor.name = supervisor_data.name

    if supervisor_data.description is not None:
        supervisor.description = supervisor_data.description

    if supervisor_data.supervisor_db_dsn is not None:
        supervisor.supervisor_db_dsn = supervisor_data.supervisor_db_dsn

    db.commit()
    db.refresh(supervisor)

    return supervisor
