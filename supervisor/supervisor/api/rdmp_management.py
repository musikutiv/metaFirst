"""RDMP management API - create, update, activate RDMPs for projects."""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from supervisor.database import get_db
from supervisor.models.user import User
from supervisor.models.project import Project
from supervisor.models.rdmp import RDMPVersion, RDMPStatus
from supervisor.models.supervisor_membership import SupervisorRole
from supervisor.api.deps import get_current_active_user, require_supervisor_role
from supervisor.services.lab_activity_service import log_rdmp_activated

router = APIRouter()


# -------------------------------------------------------------------------
# Schemas
# -------------------------------------------------------------------------

class RDMPCreate(BaseModel):
    """Schema for creating a new RDMP draft."""
    title: str = Field(..., min_length=1, max_length=255)
    content: dict = Field(default_factory=dict, description="RDMP content as JSON")


class RDMPUpdate(BaseModel):
    """Schema for updating an RDMP draft."""
    title: str | None = Field(default=None, min_length=1, max_length=255)
    content: dict | None = Field(default=None)


class RDMPActivateRequest(BaseModel):
    """Schema for activating an RDMP."""
    reason: str = Field(..., min_length=1, max_length=1000, description="Justification for activating this RDMP")


class RDMPRead(BaseModel):
    """Schema for RDMP response."""
    id: int
    project_id: int
    version: int
    status: str
    title: str
    content: dict
    created_at: str | None = None
    updated_at: str | None = None
    created_by: int | None = None
    approved_by: int | None = None

    class Config:
        from_attributes = True


# -------------------------------------------------------------------------
# Helper functions
# -------------------------------------------------------------------------

def _get_project_with_auth(
    db: Session,
    project_id: int,
    user: User,
    allowed_roles: list[SupervisorRole],
) -> Project:
    """Get project and verify user has required supervisor role."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    require_supervisor_role(db, user, project.supervisor_id, allowed_roles)
    return project


def _get_next_version(db: Session, project_id: int) -> int:
    """Get the next version number for a project's RDMP."""
    max_version = db.query(RDMPVersion.version_int).filter(
        RDMPVersion.project_id == project_id
    ).order_by(RDMPVersion.version_int.desc()).first()
    return (max_version[0] + 1) if max_version else 1


def _get_active_rdmp(db: Session, project_id: int) -> RDMPVersion | None:
    """Get the currently active RDMP for a project."""
    return db.query(RDMPVersion).filter(
        RDMPVersion.project_id == project_id,
        RDMPVersion.status == RDMPStatus.ACTIVE,
    ).first()


# -------------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------------

@router.post(
    "/projects/{project_id}/rdmps",
    response_model=RDMPRead,
    status_code=status.HTTP_201_CREATED,
)
def create_rdmp_draft(
    project_id: int,
    rdmp_data: RDMPCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Create a new RDMP draft for a project.

    Requires STEWARD or PI role at supervisor level.
    """
    project = _get_project_with_auth(
        db, project_id, current_user,
        [SupervisorRole.STEWARD, SupervisorRole.PI]
    )

    version_int = _get_next_version(db, project_id)

    rdmp = RDMPVersion(
        project_id=project_id,
        version_int=version_int,
        status=RDMPStatus.DRAFT,
        title=rdmp_data.title,
        rdmp_json=rdmp_data.content,
        created_by=current_user.id,
    )
    db.add(rdmp)
    db.commit()
    db.refresh(rdmp)

    return RDMPRead(
        id=rdmp.id,
        project_id=rdmp.project_id,
        version=rdmp.version_int,
        status=rdmp.status.value,
        title=rdmp.title,
        content=rdmp.rdmp_json or {},
        created_at=rdmp.created_at.isoformat() if rdmp.created_at else None,
        updated_at=rdmp.updated_at.isoformat() if rdmp.updated_at else None,
        created_by=rdmp.created_by,
        approved_by=rdmp.approved_by,
    )


@router.get(
    "/projects/{project_id}/rdmps",
    response_model=list[RDMPRead],
)
def list_rdmps(
    project_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """List all RDMPs for a project.

    Requires any supervisor role.
    """
    project = _get_project_with_auth(
        db, project_id, current_user,
        [SupervisorRole.RESEARCHER, SupervisorRole.STEWARD, SupervisorRole.PI]
    )

    rdmps = db.query(RDMPVersion).filter(
        RDMPVersion.project_id == project_id
    ).order_by(RDMPVersion.version_int.desc()).all()

    return [
        RDMPRead(
            id=r.id,
            project_id=r.project_id,
            version=r.version_int,
            status=r.status.value if r.status else "ACTIVE",
            title=r.title or "Untitled",
            content=r.rdmp_json or {},
            created_at=r.created_at.isoformat() if r.created_at else None,
            updated_at=r.updated_at.isoformat() if r.updated_at else None,
            created_by=r.created_by,
            approved_by=r.approved_by,
        )
        for r in rdmps
    ]


@router.get(
    "/projects/{project_id}/rdmps/active",
    response_model=RDMPRead | None,
)
def get_active_rdmp(
    project_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Get the currently active RDMP for a project.

    Returns null if no RDMP is active.
    """
    project = _get_project_with_auth(
        db, project_id, current_user,
        [SupervisorRole.RESEARCHER, SupervisorRole.STEWARD, SupervisorRole.PI]
    )

    rdmp = _get_active_rdmp(db, project_id)
    if not rdmp:
        return None

    return RDMPRead(
        id=rdmp.id,
        project_id=rdmp.project_id,
        version=rdmp.version_int,
        status=rdmp.status.value,
        title=rdmp.title or "Untitled",
        content=rdmp.rdmp_json or {},
        created_at=rdmp.created_at.isoformat() if rdmp.created_at else None,
        updated_at=rdmp.updated_at.isoformat() if rdmp.updated_at else None,
        created_by=rdmp.created_by,
        approved_by=rdmp.approved_by,
    )


@router.get(
    "/rdmps/{rdmp_id}",
    response_model=RDMPRead,
)
def get_rdmp(
    rdmp_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Get a specific RDMP by ID."""
    rdmp = db.query(RDMPVersion).filter(RDMPVersion.id == rdmp_id).first()
    if not rdmp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RDMP not found")

    # Verify access via project's supervisor
    project = db.query(Project).filter(Project.id == rdmp.project_id).first()
    require_supervisor_role(
        db, current_user, project.supervisor_id,
        [SupervisorRole.RESEARCHER, SupervisorRole.STEWARD, SupervisorRole.PI]
    )

    return RDMPRead(
        id=rdmp.id,
        project_id=rdmp.project_id,
        version=rdmp.version_int,
        status=rdmp.status.value if rdmp.status else "ACTIVE",
        title=rdmp.title or "Untitled",
        content=rdmp.rdmp_json or {},
        created_at=rdmp.created_at.isoformat() if rdmp.created_at else None,
        updated_at=rdmp.updated_at.isoformat() if rdmp.updated_at else None,
        created_by=rdmp.created_by,
        approved_by=rdmp.approved_by,
    )


@router.patch(
    "/rdmps/{rdmp_id}",
    response_model=RDMPRead,
)
def update_rdmp(
    rdmp_id: int,
    rdmp_data: RDMPUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Update an RDMP draft.

    Only DRAFT status RDMPs can be updated.
    Requires STEWARD or PI role.
    """
    rdmp = db.query(RDMPVersion).filter(RDMPVersion.id == rdmp_id).first()
    if not rdmp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RDMP not found")

    if rdmp.status != RDMPStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only DRAFT RDMPs can be updated"
        )

    project = db.query(Project).filter(Project.id == rdmp.project_id).first()
    require_supervisor_role(
        db, current_user, project.supervisor_id,
        [SupervisorRole.STEWARD, SupervisorRole.PI]
    )

    if rdmp_data.title is not None:
        rdmp.title = rdmp_data.title
    if rdmp_data.content is not None:
        rdmp.rdmp_json = rdmp_data.content

    db.commit()
    db.refresh(rdmp)

    return RDMPRead(
        id=rdmp.id,
        project_id=rdmp.project_id,
        version=rdmp.version_int,
        status=rdmp.status.value,
        title=rdmp.title,
        content=rdmp.rdmp_json or {},
        created_at=rdmp.created_at.isoformat() if rdmp.created_at else None,
        updated_at=rdmp.updated_at.isoformat() if rdmp.updated_at else None,
        created_by=rdmp.created_by,
        approved_by=rdmp.approved_by,
    )


@router.post(
    "/rdmps/{rdmp_id}/activate",
    response_model=RDMPRead,
)
def activate_rdmp(
    rdmp_id: int,
    activate_data: RDMPActivateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Activate an RDMP, making it the current active RDMP for the project.

    Only PI can activate RDMPs.
    Any previously ACTIVE RDMP becomes SUPERSEDED.
    Requires a reason/justification for the activation.
    """
    rdmp = db.query(RDMPVersion).filter(RDMPVersion.id == rdmp_id).first()
    if not rdmp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RDMP not found")

    if rdmp.status != RDMPStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only DRAFT RDMPs can be activated"
        )

    project = db.query(Project).filter(Project.id == rdmp.project_id).first()
    require_supervisor_role(db, current_user, project.supervisor_id, [SupervisorRole.PI])

    # Supersede any existing ACTIVE RDMP
    existing_active = _get_active_rdmp(db, rdmp.project_id)
    superseded_rdmp_id = existing_active.id if existing_active else None
    if existing_active:
        existing_active.status = RDMPStatus.SUPERSEDED

    # Activate this RDMP
    rdmp.status = RDMPStatus.ACTIVE
    rdmp.approved_by = current_user.id

    # Log activity
    log_rdmp_activated(
        db=db,
        lab_id=project.supervisor_id,
        actor_user_id=current_user.id,
        rdmp_id=rdmp.id,
        project_name=project.name,
        rdmp_title=rdmp.title or "Untitled",
        version=rdmp.version_int,
        reason_text=activate_data.reason,
        superseded_rdmp_id=superseded_rdmp_id,
    )

    db.commit()
    db.refresh(rdmp)

    return RDMPRead(
        id=rdmp.id,
        project_id=rdmp.project_id,
        version=rdmp.version_int,
        status=rdmp.status.value,
        title=rdmp.title,
        content=rdmp.rdmp_json or {},
        created_at=rdmp.created_at.isoformat() if rdmp.created_at else None,
        updated_at=rdmp.updated_at.isoformat() if rdmp.updated_at else None,
        created_by=rdmp.created_by,
        approved_by=rdmp.approved_by,
    )
