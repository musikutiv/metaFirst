"""Samples and field values API."""

from typing import Annotated, Any
import json
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from supervisor.database import get_db
from supervisor.models.user import User
from supervisor.models.project import Project
from supervisor.models.sample import Sample, SampleFieldValue, MetadataVisibility
from supervisor.models.supervisor_membership import SupervisorRole
from supervisor.schemas.sample import (
    Sample as SampleSchema,
    SampleCreate,
    SampleWithFields,
    FieldValueSet,
)
from supervisor.api.deps import get_current_active_user, require_supervisor_role, require_project_access
from supervisor.services.rdmp_service import get_current_rdmp, check_sample_completeness, validate_field_value
from supervisor.services.permission_service import check_permission


class VisibilityUpdate(BaseModel):
    """Schema for updating sample visibility."""
    visibility: str


class SampleListResponse(BaseModel):
    """Paginated sample list response."""
    items: list[SampleWithFields]
    total: int
    limit: int
    offset: int


class SampleSummary(BaseModel):
    """Lightweight sample summary for list views."""
    id: int
    project_id: int
    sample_identifier: str
    visibility: str
    created_at: Any
    is_complete: bool | None = None

    class Config:
        from_attributes = True


class SampleListSummaryResponse(BaseModel):
    """Paginated lightweight sample list response."""
    items: list[SampleSummary]
    total: int
    limit: int
    offset: int


router = APIRouter()


@router.get("/projects/{project_id}/samples", response_model=SampleListResponse)
def list_samples(
    project_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    limit: int = 50,
    offset: int = 0
):
    """List samples in a project with pagination.

    Returns paginated samples with field values and completeness info.
    Default limit is 50 for performance.
    """
    # Verify access via supervisor membership
    require_project_access(db, current_user, project_id)

    # Get total count (single query)
    total = db.query(func.count(Sample.id)).filter(Sample.project_id == project_id).scalar()

    # Get samples with eager loading of field_values to avoid N+1
    samples = (
        db.query(Sample)
        .options(joinedload(Sample.field_values))
        .filter(Sample.project_id == project_id)
        .order_by(Sample.id)
        .offset(offset)
        .limit(limit)
        .all()
    )

    # Get RDMP for completeness checking
    rdmp = get_current_rdmp(db, project_id)

    # Build response with fields
    items = []
    for sample in samples:
        fields_dict = {
            fv.field_key: json.loads(fv.value_json) if fv.value_json else None
            for fv in sample.field_values
        }

        completeness = check_sample_completeness(sample, rdmp) if rdmp else {}

        items.append({
            **sample.__dict__,
            "fields": fields_dict,
            "completeness": completeness
        })

    return SampleListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/projects/{project_id}/samples/summary", response_model=SampleListSummaryResponse)
def list_samples_summary(
    project_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    limit: int = 100,
    offset: int = 0
):
    """List samples with minimal data (no field values).

    Use this endpoint for fast initial loading of sample lists.
    Fetch full sample details via GET /samples/{id} when needed.
    """
    # Verify access via supervisor membership
    require_project_access(db, current_user, project_id)

    # Get total count
    total = db.query(func.count(Sample.id)).filter(Sample.project_id == project_id).scalar()

    # Get samples without field values (lightweight)
    samples = (
        db.query(Sample)
        .filter(Sample.project_id == project_id)
        .order_by(Sample.id)
        .offset(offset)
        .limit(limit)
        .all()
    )

    items = [
        SampleSummary(
            id=s.id,
            project_id=s.project_id,
            sample_identifier=s.sample_identifier,
            visibility=s.visibility.value if s.visibility else "PRIVATE",
            created_at=s.created_at,
            is_complete=None  # Not computed for performance
        )
        for s in samples
    ]

    return SampleListSummaryResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/projects/{project_id}/samples", response_model=SampleSchema, status_code=status.HTTP_201_CREATED)
def create_sample(
    project_id: int,
    sample_data: SampleCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """Create a new sample."""
    # Check permission
    if not check_permission(db, current_user, project_id, "can_edit_metadata"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to create samples"
        )

    # Check if sample identifier already exists in project
    existing = (
        db.query(Sample)
        .filter(
            Sample.project_id == project_id,
            Sample.sample_identifier == sample_data.sample_identifier
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sample identifier already exists in this project"
        )

    # Create sample
    sample = Sample(
        project_id=project_id,
        sample_identifier=sample_data.sample_identifier,
        created_by=current_user.id
    )
    db.add(sample)
    db.commit()
    db.refresh(sample)

    return sample


@router.get("/samples/{sample_id}", response_model=SampleWithFields)
def get_sample(
    sample_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """Get sample details with field values."""
    sample = db.query(Sample).filter(Sample.id == sample_id).first()
    if not sample:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sample not found")

    # Verify access via supervisor membership
    require_project_access(db, current_user, sample.project_id)

    # Build fields dict
    fields_dict = {
        fv.field_key: json.loads(fv.value_json) if fv.value_json else None
        for fv in sample.field_values
    }

    # Check completeness
    rdmp = get_current_rdmp(db, sample.project_id)
    completeness = check_sample_completeness(sample, rdmp) if rdmp else {}

    return {
        **sample.__dict__,
        "fields": fields_dict,
        "completeness": completeness
    }


@router.put("/samples/{sample_id}/fields/{field_key}")
def set_field_value(
    sample_id: int,
    field_key: str,
    field_data: FieldValueSet,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """Set a field value for a sample."""
    # Get sample
    sample = db.query(Sample).filter(Sample.id == sample_id).first()
    if not sample:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sample not found")

    # Check permission
    if not check_permission(db, current_user, sample.project_id, "can_edit_metadata"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to edit metadata"
        )

    # Get RDMP and validate field
    rdmp = get_current_rdmp(db, sample.project_id)
    if rdmp:
        field_config = next(
            (f for f in rdmp.rdmp_json.get("fields", []) if f["key"] == field_key),
            None
        )
        if not field_config:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Field '{field_key}' not defined in RDMP"
            )

        # Validate value
        is_valid, error = validate_field_value(field_config, field_data.value)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error
            )

    # Update or create field value
    field_value = (
        db.query(SampleFieldValue)
        .filter(SampleFieldValue.sample_id == sample_id, SampleFieldValue.field_key == field_key)
        .first()
    )

    if field_value:
        field_value.value_json = json.dumps(field_data.value)
        field_value.value_text = str(field_data.value)
        field_value.updated_by = current_user.id
    else:
        field_value = SampleFieldValue(
            sample_id=sample_id,
            field_key=field_key,
            value_json=json.dumps(field_data.value),
            value_text=str(field_data.value),
            updated_by=current_user.id
        )
        db.add(field_value)

    db.commit()

    return {"status": "success", "field_key": field_key, "value": field_data.value}


@router.patch("/samples/{sample_id}/visibility")
def set_sample_visibility(
    sample_id: int,
    visibility_data: VisibilityUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """Set metadata visibility for a sample.

    Requires STEWARD or PI role at the supervisor level.

    Visibility levels:
    - PRIVATE: Only visible to members of the owning supervisor
    - INSTITUTION: Visible to any authenticated user
    - PUBLIC: Visible to anyone (no auth required)
    """
    # Get sample
    sample = db.query(Sample).filter(Sample.id == sample_id).first()
    if not sample:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sample not found")

    # Get project to find supervisor
    project = db.query(Project).filter(Project.id == sample.project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # Require STEWARD or PI role at supervisor level
    require_supervisor_role(db, current_user, project.supervisor_id, [SupervisorRole.STEWARD, SupervisorRole.PI])

    # Validate visibility value
    try:
        new_visibility = MetadataVisibility(visibility_data.visibility.upper())
    except ValueError:
        valid_values = [v.value for v in MetadataVisibility]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid visibility. Must be one of: {', '.join(valid_values)}"
        )

    # Update visibility
    sample.visibility = new_visibility
    db.commit()
    db.refresh(sample)

    return {
        "status": "success",
        "sample_id": sample.id,
        "visibility": sample.visibility.value
    }
