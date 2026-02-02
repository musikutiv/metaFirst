"""Projects and memberships API."""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from supervisor.database import get_db
from supervisor.models.user import User
from supervisor.models.project import Project
from supervisor.models.membership import Membership
from supervisor.models.supervisor import Supervisor
from supervisor.schemas.project import (
    Project as ProjectSchema,
    ProjectCreate,
    ProjectUpdate,
    Membership as MembershipSchema,
    MembershipCreate,
    MembershipUpdate,
)
from supervisor.api.deps import get_current_active_user, require_supervisor_role
from supervisor.models.supervisor_membership import SupervisorRole
from supervisor.services.permission_service import check_permission

router = APIRouter()


# Projects

@router.get("/", response_model=list[ProjectSchema])
def list_projects(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """List projects where user is a member."""
    # Get projects through memberships
    memberships = db.query(Membership).filter(Membership.user_id == current_user.id).all()
    project_ids = [m.project_id for m in memberships]

    projects = db.query(Project).filter(Project.id.in_(project_ids), Project.is_active == True).all()
    return projects


@router.post("/", response_model=ProjectSchema, status_code=status.HTTP_201_CREATED)
def create_project(
    project_data: ProjectCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """Create a new project.

    Requires STEWARD or PI role for the supervisor.
    """
    # Validate supervisor exists
    supervisor = db.query(Supervisor).filter(Supervisor.id == project_data.supervisor_id).first()
    if not supervisor:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Supervisor not found"
        )
    if not supervisor.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Supervisor is not active"
        )

    # Require STEWARD or PI role to create projects
    require_supervisor_role(db, current_user, project_data.supervisor_id, [SupervisorRole.STEWARD, SupervisorRole.PI])

    # Check if project name already exists
    existing = db.query(Project).filter(Project.name == project_data.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project name already exists"
        )

    # Create project
    project = Project(
        name=project_data.name,
        description=project_data.description,
        created_by=current_user.id,
        supervisor_id=project_data.supervisor_id
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    return project


@router.get("/{project_id}", response_model=ProjectSchema)
def get_project(
    project_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """Get project details."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # Check membership
    membership = (
        db.query(Membership)
        .filter(Membership.project_id == project_id, Membership.user_id == current_user.id)
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this project")

    return project


@router.patch("/{project_id}", response_model=ProjectSchema)
def update_project(
    project_id: int,
    project_data: ProjectUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """Update project settings.

    Requires STEWARD or PI role for the project's supervisor.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # Require STEWARD or PI role to update projects
    require_supervisor_role(db, current_user, project.supervisor_id, [SupervisorRole.STEWARD, SupervisorRole.PI])

    # Update fields if provided
    if project_data.name is not None:
        # Check if new name conflicts
        existing = db.query(Project).filter(
            Project.name == project_data.name,
            Project.id != project_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Project name already exists"
            )
        project.name = project_data.name

    if project_data.description is not None:
        project.description = project_data.description

    if project_data.sample_id_rule_type is not None:
        project.sample_id_rule_type = project_data.sample_id_rule_type

    if project_data.sample_id_regex is not None:
        project.sample_id_regex = project_data.sample_id_regex

    db.commit()
    db.refresh(project)

    return project


# Memberships

@router.get("/{project_id}/memberships", response_model=list[MembershipSchema])
def list_memberships(
    project_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """List project memberships."""
    # Check user has access to project
    membership = (
        db.query(Membership)
        .filter(Membership.project_id == project_id, Membership.user_id == current_user.id)
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this project")

    memberships = db.query(Membership).filter(Membership.project_id == project_id).all()
    return memberships


@router.post("/{project_id}/memberships", response_model=MembershipSchema, status_code=status.HTTP_201_CREATED)
def create_membership(
    project_id: int,
    membership_data: MembershipCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """Add a member to a project."""
    # Check if user can manage RDMP (required to add members)
    if not check_permission(db, current_user, project_id, "can_manage_rdmp"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to add members"
        )

    # Check if membership already exists
    existing = (
        db.query(Membership)
        .filter(
            Membership.project_id == project_id,
            Membership.user_id == membership_data.user_id
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member"
        )

    # Create membership
    membership = Membership(
        project_id=project_id,
        user_id=membership_data.user_id,
        role_name=membership_data.role_name,
        created_by=current_user.id
    )
    db.add(membership)
    db.commit()
    db.refresh(membership)

    return membership
