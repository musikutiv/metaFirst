"""RDMP-derived sample template API endpoints.

Provides endpoints for:
- Downloading CSV template derived from project's RDMP
- Uploading and previewing CSV for multi-sample ingestion
- Confirming multi-sample creation from validated CSV
"""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import io
import json

from supervisor.database import get_db
from supervisor.models.user import User
from supervisor.models.project import Project
from supervisor.models.sample import Sample
from supervisor.models.raw_data import RawDataItem
from supervisor.models.audit import AuditLog
from supervisor.api.deps import get_current_active_user, require_project_access
from supervisor.services.permission_service import check_permission
from supervisor.services.ingest_template_service import (
    get_rdmp_for_template,
    generate_template_metadata,
    generate_template_csv,
    derive_template_columns,
    parse_and_validate_csv,
    create_samples_bulk,
    MAX_IMPORT_ROWS,
    RowValidationError,
)


router = APIRouter()


# -------------------------------------------------------------------------
# Schemas
# -------------------------------------------------------------------------

class TemplateColumnSchema(BaseModel):
    """Column definition in the template."""
    key: str
    label: str
    required: bool
    source: str  # 'system' or 'rdmp'
    field_type: str | None = None
    allowed_values: list[str] | None = None


class TemplateInfoResponse(BaseModel):
    """Information about the template (without downloading)."""
    rdmp_id: int
    rdmp_version: int
    rdmp_status: str
    columns: list[TemplateColumnSchema]
    template_hash: str


class RowErrorSchema(BaseModel):
    """Error in a CSV row."""
    row_number: int
    column: str
    message: str


class CSVPreviewResponse(BaseModel):
    """Response for CSV preview."""
    total_rows: int
    valid_rows: int
    errors: list[RowErrorSchema]
    template_hash: str
    can_import: bool


class CSVImportResponse(BaseModel):
    """Response for CSV import."""
    created_count: int
    sample_ids: list[int]
    template_hash: str


# -------------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------------

@router.get(
    "/projects/{project_id}/ingest/sample-template",
    responses={
        200: {
            "content": {"text/csv": {}},
            "description": "CSV template file",
        },
    },
)
def download_sample_template(
    project_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    format: str = Query(default="csv", description="Template format (only 'csv' supported)"),
):
    """Download a sample ingestion template derived from the project's RDMP.

    The template contains:
    - sample_name (required): Unique identifier for each sample
    - visibility (optional): PRIVATE, INSTITUTION, or PUBLIC
    - RDMP field columns: Based on fields defined in the RDMP

    Requires ACTIVE RDMP, or uses DRAFT if no ACTIVE exists.
    Returns 409 if no RDMP exists for the project.

    Response headers include:
    - X-RDMP-ID: ID of the RDMP used
    - X-RDMP-Version: Version of the RDMP
    - X-RDMP-Status: ACTIVE or DRAFT
    - X-Template-Hash: Hash of the template structure
    """
    # Verify access
    require_project_access(db, current_user, project_id)

    # Verify project exists
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    # Get RDMP
    rdmp, rdmp_status = get_rdmp_for_template(db, project_id)
    if not rdmp:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="RDMP required to generate ingestion template. Create and activate an RDMP first."
        )

    # Generate template
    metadata = generate_template_metadata(rdmp)
    csv_content = generate_template_csv(metadata.columns)

    # Log audit event
    audit_entry = AuditLog(
        project_id=project_id,
        actor_user_id=current_user.id,
        action_type="INGEST_TEMPLATE_GENERATED",
        target_type="PROJECT",
        target_id=project_id,
        after_json={
            "rdmp_id": rdmp.id,
            "rdmp_version": rdmp.version_int,
            "rdmp_status": rdmp_status,
            "template_hash": metadata.template_hash,
            "columns": [c.key for c in metadata.columns],
        },
    )
    db.add(audit_entry)
    db.commit()

    # Return CSV file
    filename = f"{project.name.replace(' ', '_')}_sample_template.csv"
    return StreamingResponse(
        io.BytesIO(csv_content.encode("utf-8")),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-RDMP-ID": str(rdmp.id),
            "X-RDMP-Version": str(rdmp.version_int),
            "X-RDMP-Status": rdmp_status,
            "X-Template-Hash": metadata.template_hash,
        },
    )


@router.get(
    "/projects/{project_id}/ingest/sample-template/info",
    response_model=TemplateInfoResponse,
)
def get_template_info(
    project_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Get information about the template without downloading.

    Useful for UI to display column information before download.
    """
    require_project_access(db, current_user, project_id)

    rdmp, rdmp_status = get_rdmp_for_template(db, project_id)
    if not rdmp:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="RDMP required to generate ingestion template"
        )

    metadata = generate_template_metadata(rdmp)

    return TemplateInfoResponse(
        rdmp_id=metadata.rdmp_id,
        rdmp_version=metadata.rdmp_version,
        rdmp_status=metadata.rdmp_status,
        columns=[
            TemplateColumnSchema(
                key=c.key,
                label=c.label,
                required=c.required,
                source=c.source,
                field_type=c.field_type,
                allowed_values=c.allowed_values,
            )
            for c in metadata.columns
        ],
        template_hash=metadata.template_hash,
    )


@router.post(
    "/projects/{project_id}/raw-data/{raw_data_id}/samples:import-csv",
    response_model=CSVPreviewResponse | CSVImportResponse,
)
async def import_samples_from_csv(
    project_id: int,
    raw_data_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    file: UploadFile = File(..., description="CSV file to import"),
    confirm: bool = Query(default=False, description="Set to true to confirm import"),
):
    """Import samples from a CSV file and link them to a raw data item.

    Two-stage process:
    1. Preview (confirm=false): Parse and validate CSV, return preview with errors
    2. Import (confirm=true): Create samples in a single transaction

    Validation rules:
    - sample_name column is required and must be unique
    - visibility must be PRIVATE, INSTITUTION, or PUBLIC
    - RDMP field types are validated
    - Maximum {MAX_IMPORT_ROWS} rows per import

    Returns CSVPreviewResponse for preview, CSVImportResponse for confirmed import.
    """
    # Verify access and permission
    require_project_access(db, current_user, project_id)

    if not check_permission(db, current_user, project_id, "can_edit_metadata"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to create samples"
        )

    # Verify project exists
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    # Verify raw data item exists and belongs to project
    raw_data_item = db.query(RawDataItem).filter(RawDataItem.id == raw_data_id).first()
    if not raw_data_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Raw data item not found"
        )
    if raw_data_item.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Raw data item does not belong to this project"
        )

    # Get RDMP for validation
    rdmp, rdmp_status = get_rdmp_for_template(db, project_id)
    if not rdmp:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="RDMP required for CSV import"
        )

    # Read and parse CSV
    try:
        content = await file.read()
        csv_content = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file encoding. CSV must be UTF-8 encoded."
        )

    # Get template columns and existing sample names
    columns = derive_template_columns(rdmp)
    existing_samples = (
        db.query(Sample.sample_identifier)
        .filter(Sample.project_id == project_id)
        .all()
    )
    existing_names = {s[0] for s in existing_samples}

    # Parse and validate
    preview_result = parse_and_validate_csv(csv_content, columns, existing_names)

    # If preview mode, return preview
    if not confirm:
        return CSVPreviewResponse(
            total_rows=preview_result.total_rows,
            valid_rows=preview_result.valid_rows,
            errors=[
                RowErrorSchema(
                    row_number=e.row_number,
                    column=e.column,
                    message=e.message,
                )
                for e in preview_result.errors
            ],
            template_hash=preview_result.template_hash,
            can_import=len(preview_result.errors) == 0 and preview_result.valid_rows > 0,
        )

    # Confirm mode: check for errors
    if preview_result.errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "CSV validation failed. Fix errors and retry.",
                "errors": [
                    {"row": e.row_number, "column": e.column, "message": e.message}
                    for e in preview_result.errors
                ],
            }
        )

    if not preview_result.parsed_rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid rows to import"
        )

    # Create samples in transaction
    try:
        created_samples = create_samples_bulk(
            db=db,
            project_id=project_id,
            raw_data_item_id=raw_data_id,
            parsed_rows=preview_result.parsed_rows,
            user_id=current_user.id,
        )

        # Log audit event
        audit_entry = AuditLog(
            project_id=project_id,
            actor_user_id=current_user.id,
            action_type="INGEST_SAMPLES_CREATED",
            target_type="SAMPLE",
            target_id=raw_data_id,  # Reference raw data item
            after_json={
                "count": len(created_samples),
                "method": "csv",
                "template_hash": preview_result.template_hash,
                "rdmp_id": rdmp.id,
                "rdmp_version": rdmp.version_int,
                "sample_ids": [s.id for s in created_samples],
            },
        )
        db.add(audit_entry)

        db.commit()

        return CSVImportResponse(
            created_count=len(created_samples),
            sample_ids=[s.id for s in created_samples],
            template_hash=preview_result.template_hash,
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create samples: {str(e)}"
        )
