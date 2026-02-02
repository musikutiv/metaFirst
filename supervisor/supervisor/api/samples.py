"""Samples and field values API."""

from typing import Annotated, Any
import json
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from supervisor.database import get_db
from supervisor.models.user import User
from supervisor.models.project import Project
from supervisor.models.sample import Sample, SampleFieldValue, MetadataVisibility
from supervisor.models.membership import Membership
from supervisor.models.supervisor_membership import SupervisorRole
from supervisor.schemas.sample import (
    Sample as SampleSchema,
    SampleCreate,
    SampleWithFields,
    FieldValueSet,
)
from supervisor.api.deps import get_current_active_user, require_supervisor_role
from supervisor.services.rdmp_service import get_current_rdmp, check_sample_completeness, validate_field_value
from supervisor.services.permission_service import check_permission


class VisibilityUpdate(BaseModel):
    """Schema for updating sample visibility."""
    visibility: str

router = APIRouter()


@router.get("/projects/{project_id}/samples", response_model=list[SampleWithFields])
def list_samples(
    project_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    limit: int = 100,
    offset: int = 0
):
    """List samples in a project."""
    # Check membership
    membership = (
        db.query(Membership)
        .filter(Membership.project_id == project_id, Membership.user_id == current_user.id)
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this project")

    # Get samples
    samples = (
        db.query(Sample)
        .filter(Sample.project_id == project_id)
        .offset(offset)
        .limit(limit)
        .all()
    )

    # Get RDMP for completeness checking
    rdmp = get_current_rdmp(db, project_id)

    # Build response with fields
    result = []
    for sample in samples:
        fields_dict = {
            fv.field_key: json.loads(fv.value_json) if fv.value_json else None
            for fv in sample.field_values
        }

        completeness = check_sample_completeness(sample, rdmp) if rdmp else {}

        result.append({
            **sample.__dict__,
            "fields": fields_dict,
            "completeness": completeness
        })

    return result


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

    # Check membership
    membership = (
        db.query(Membership)
        .filter(Membership.project_id == sample.project_id, Membership.user_id == current_user.id)
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this project")

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
