"""Supervisors API."""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from supervisor.database import get_db
from supervisor.models.user import User
from supervisor.models.supervisor import Supervisor
from supervisor.models.supervisor_membership import SupervisorMembership, SupervisorRole
from supervisor.schemas.supervisor import (
    Supervisor as SupervisorSchema,
    SupervisorCreate,
    SupervisorUpdate,
)
from supervisor.api.deps import get_current_active_user, require_supervisor_role


class SupervisorMemberResponse(BaseModel):
    """Supervisor member response."""
    user_id: int
    username: str
    display_name: str | None
    role: str

    class Config:
        from_attributes = True


class SupervisorMemberCreate(BaseModel):
    """Create supervisor member."""
    username: str
    role: str  # PI, STEWARD, or RESEARCHER


class SupervisorMemberUpdate(BaseModel):
    """Update supervisor member role."""
    role: str  # PI, STEWARD, or RESEARCHER

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


# ============================================================================
# Supervisor Member Management
# ============================================================================

@router.get("/{supervisor_id}/members", response_model=list[SupervisorMemberResponse])
def list_supervisor_members(
    supervisor_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """List members of a supervisor.

    Any supervisor member can view the member list.
    """
    supervisor = db.query(Supervisor).filter(Supervisor.id == supervisor_id).first()
    if not supervisor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supervisor not found")

    # Any member can view the list
    require_supervisor_role(db, current_user, supervisor_id, [SupervisorRole.PI, SupervisorRole.STEWARD, SupervisorRole.RESEARCHER])

    # Get all memberships with user info
    memberships = (
        db.query(SupervisorMembership, User)
        .join(User, SupervisorMembership.user_id == User.id)
        .filter(SupervisorMembership.supervisor_id == supervisor_id)
        .all()
    )

    return [
        SupervisorMemberResponse(
            user_id=m.user_id,
            username=u.username,
            display_name=u.display_name,
            role=m.role.value
        )
        for m, u in memberships
    ]


@router.post("/{supervisor_id}/members", response_model=SupervisorMemberResponse, status_code=status.HTTP_201_CREATED)
def add_supervisor_member(
    supervisor_id: int,
    member_data: SupervisorMemberCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """Add a member to a supervisor.

    Requires STEWARD or PI role.
    """
    supervisor = db.query(Supervisor).filter(Supervisor.id == supervisor_id).first()
    if not supervisor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supervisor not found")

    # Require STEWARD or PI role
    require_supervisor_role(db, current_user, supervisor_id, [SupervisorRole.STEWARD, SupervisorRole.PI])

    # Validate role
    try:
        role = SupervisorRole(member_data.role.upper())
    except ValueError:
        valid_roles = [r.value for r in SupervisorRole]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Must be one of: {', '.join(valid_roles)}"
        )

    # Find user by username
    user = db.query(User).filter(User.username == member_data.username).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Check if already a member
    existing = (
        db.query(SupervisorMembership)
        .filter(
            SupervisorMembership.supervisor_id == supervisor_id,
            SupervisorMembership.user_id == user.id
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member of this supervisor"
        )

    # Create membership
    membership = SupervisorMembership(
        supervisor_id=supervisor_id,
        user_id=user.id,
        role=role,
        created_by=current_user.id
    )
    db.add(membership)
    db.commit()

    return SupervisorMemberResponse(
        user_id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=role.value
    )


@router.patch("/{supervisor_id}/members/{user_id}", response_model=SupervisorMemberResponse)
def update_supervisor_member(
    supervisor_id: int,
    user_id: int,
    member_data: SupervisorMemberUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """Update a member's role in a supervisor.

    Requires PI role (only PI can change roles).
    """
    supervisor = db.query(Supervisor).filter(Supervisor.id == supervisor_id).first()
    if not supervisor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supervisor not found")

    # Only PI can change roles
    require_supervisor_role(db, current_user, supervisor_id, [SupervisorRole.PI])

    # Validate role
    try:
        new_role = SupervisorRole(member_data.role.upper())
    except ValueError:
        valid_roles = [r.value for r in SupervisorRole]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Must be one of: {', '.join(valid_roles)}"
        )

    # Find membership
    membership = (
        db.query(SupervisorMembership)
        .filter(
            SupervisorMembership.supervisor_id == supervisor_id,
            SupervisorMembership.user_id == user_id
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    # Get user info
    user = db.query(User).filter(User.id == user_id).first()

    # Update role
    membership.role = new_role
    db.commit()

    return SupervisorMemberResponse(
        user_id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=new_role.value
    )


@router.delete("/{supervisor_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_supervisor_member(
    supervisor_id: int,
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """Remove a member from a supervisor.

    Requires PI role.
    Cannot remove yourself if you're the last PI.
    """
    supervisor = db.query(Supervisor).filter(Supervisor.id == supervisor_id).first()
    if not supervisor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supervisor not found")

    # Only PI can remove members
    require_supervisor_role(db, current_user, supervisor_id, [SupervisorRole.PI])

    # Find membership
    membership = (
        db.query(SupervisorMembership)
        .filter(
            SupervisorMembership.supervisor_id == supervisor_id,
            SupervisorMembership.user_id == user_id
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    # Prevent removing the last PI
    if membership.role == SupervisorRole.PI:
        pi_count = (
            db.query(SupervisorMembership)
            .filter(
                SupervisorMembership.supervisor_id == supervisor_id,
                SupervisorMembership.role == SupervisorRole.PI
            )
            .count()
        )
        if pi_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove the last PI from a supervisor"
            )

    db.delete(membership)
    db.commit()
