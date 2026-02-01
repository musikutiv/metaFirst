"""Operational state API endpoints.

Provides access to per-supervisor operational data: runs, heartbeats, etc.
"""

from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from supervisor.database import get_db
from supervisor.models.user import User
from supervisor.models.project import Project
from supervisor.models.membership import Membership
from supervisor.api.deps import get_current_active_user, require_supervisor_role, require_any_supervisor_role
from supervisor.models.supervisor_membership import SupervisorRole
from supervisor.services.operational_service import OperationalService
from supervisor.operational import MissingDSNError, OperationalDBError
from supervisor.operational.models import RunStatus, HeartbeatStatus

router = APIRouter()


# -------------------------------------------------------------------------
# Schemas
# -------------------------------------------------------------------------

class IngestRunCreate(BaseModel):
    """Schema for creating an ingest run."""
    triggered_by: str = Field(default="api", description="How the run was triggered")
    ingestor_id: str | None = Field(default=None, description="Ingestor instance ID")


class IngestRunUpdate(BaseModel):
    """Schema for updating an ingest run."""
    status: str | None = Field(default=None, description="New status")
    file_count: int | None = Field(default=None, ge=0)
    total_bytes: int | None = Field(default=None, ge=0)
    error_count: int | None = Field(default=None, ge=0)
    message: str | None = None
    finished: bool = Field(default=False, description="Mark run as finished")


class IngestRunResponse(BaseModel):
    """Schema for ingest run response."""
    id: int
    project_id: int
    status: str
    file_count: int | None = None
    total_bytes: int | None = None
    error_count: int | None = None
    message: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    triggered_by: str | None = None
    ingestor_id: str | None = None


class HeartbeatCreate(BaseModel):
    """Schema for recording a heartbeat."""
    ingestor_id: str = Field(..., min_length=1)
    hostname: str | None = None
    status: str = Field(default="HEALTHY")
    message: str | None = None
    watched_paths: list[str] | None = None
    version: str | None = None


class HeartbeatResponse(BaseModel):
    """Schema for heartbeat response."""
    ingestor_id: str
    hostname: str | None = None
    status: str
    last_seen_at: str | None = None
    message: str | None = None
    watched_paths: list[str] | None = None
    version: str | None = None


# -------------------------------------------------------------------------
# Helper functions
# -------------------------------------------------------------------------

def _get_supervisor_id_for_project(db: Session, project_id: int, user: User) -> int:
    """Get supervisor_id for a project, validating user access."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # Check membership
    membership = db.query(Membership).filter(
        Membership.project_id == project_id,
        Membership.user_id == user.id
    ).first()
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this project")

    return project.supervisor_id


def _handle_operational_error(e: Exception):
    """Convert operational errors to HTTP exceptions."""
    if isinstance(e, MissingDSNError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )
    elif isinstance(e, OperationalDBError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    raise


# -------------------------------------------------------------------------
# Ingest Runs API
# -------------------------------------------------------------------------

@router.post(
    "/projects/{project_id}/runs",
    response_model=IngestRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_ingest_run(
    project_id: int,
    run_data: IngestRunCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Create a new ingest run for a project.

    Requires RESEARCHER, STEWARD, or PI role at the supervisor level.
    """
    supervisor_id = _get_supervisor_id_for_project(db, project_id, current_user)

    # Require any supervisor role to trigger ingest runs
    require_supervisor_role(db, current_user, supervisor_id, [SupervisorRole.RESEARCHER, SupervisorRole.STEWARD, SupervisorRole.PI])

    try:
        service = OperationalService(db)
        run = service.create_ingest_run(
            supervisor_id=supervisor_id,
            project_id=project_id,
            triggered_by=run_data.triggered_by,
            ingestor_id=run_data.ingestor_id,
        )
        return run
    except Exception as e:
        _handle_operational_error(e)


@router.get(
    "/projects/{project_id}/runs",
    response_model=list[IngestRunResponse],
)
def list_ingest_runs(
    project_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    limit: int = Query(default=10, ge=1, le=100),
):
    """List recent ingest runs for a project."""
    supervisor_id = _get_supervisor_id_for_project(db, project_id, current_user)

    try:
        service = OperationalService(db)
        runs = service.get_recent_runs(
            supervisor_id=supervisor_id,
            project_id=project_id,
            limit=limit,
        )
        return runs
    except Exception as e:
        _handle_operational_error(e)


@router.patch(
    "/runs/{run_id}",
    response_model=IngestRunResponse,
)
def update_ingest_run(
    run_id: int,
    run_data: IngestRunUpdate,
    supervisor_id: int = Query(..., description="Supervisor ID for the operational DB"),
    db: Annotated[Session, Depends(get_db)] = None,
    current_user: Annotated[User, Depends(get_current_active_user)] = None,
):
    """Update an ingest run.

    Note: Requires supervisor_id as query param since run_id alone
    doesn't identify which operational DB to use.
    """
    try:
        service = OperationalService(db)

        # Convert status string to enum if provided
        status_enum = None
        if run_data.status:
            try:
                status_enum = RunStatus(run_data.status)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status: {run_data.status}"
                )

        run = service.update_ingest_run(
            supervisor_id=supervisor_id,
            run_id=run_id,
            status=status_enum,
            file_count=run_data.file_count,
            total_bytes=run_data.total_bytes,
            error_count=run_data.error_count,
            message=run_data.message,
            finished=run_data.finished,
        )
        return run
    except Exception as e:
        _handle_operational_error(e)


# -------------------------------------------------------------------------
# Heartbeats API
# -------------------------------------------------------------------------

@router.post(
    "/supervisors/{supervisor_id}/heartbeats",
    response_model=HeartbeatResponse,
)
def record_heartbeat(
    supervisor_id: int,
    heartbeat_data: HeartbeatCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Record an ingestor heartbeat.

    Requires membership in the supervisor (any role).
    """
    # Require any supervisor membership
    require_any_supervisor_role(db, current_user, supervisor_id)

    try:
        # Convert status string to enum
        try:
            status_enum = HeartbeatStatus(heartbeat_data.status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {heartbeat_data.status}"
            )

        service = OperationalService(db)
        heartbeat = service.record_heartbeat(
            supervisor_id=supervisor_id,
            ingestor_id=heartbeat_data.ingestor_id,
            hostname=heartbeat_data.hostname,
            status=status_enum,
            message=heartbeat_data.message,
            watched_paths=heartbeat_data.watched_paths,
            version=heartbeat_data.version,
        )
        return heartbeat
    except Exception as e:
        _handle_operational_error(e)


@router.get(
    "/supervisors/{supervisor_id}/heartbeats",
    response_model=list[HeartbeatResponse],
)
def list_heartbeats(
    supervisor_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    include_offline: bool = Query(default=False),
):
    """List ingestor heartbeats for a supervisor.

    Requires membership in the supervisor (any role).
    """
    # Require any supervisor membership
    require_any_supervisor_role(db, current_user, supervisor_id)

    try:
        service = OperationalService(db)
        heartbeats = service.get_heartbeats(
            supervisor_id=supervisor_id,
            include_offline=include_offline,
        )
        return heartbeats
    except Exception as e:
        _handle_operational_error(e)
