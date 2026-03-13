"""File annotation API — create/list/update/delete FileAnnotation records."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from supervisor.database import get_db
from supervisor.models.annotations import FileAnnotation
from supervisor.models.raw_data import RawDataItem
from supervisor.models.sample import Sample
from supervisor.models.user import User
from supervisor.schemas.annotations import (
    AnnotationCreateItem,
    AnnotationPatch,
    AnnotationResponse,
    AnnotationsBatchCreate,
)
from supervisor.api.deps import get_current_active_user, require_project_access
from supervisor.services.permission_service import check_permission

router = APIRouter()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _to_response(ann: FileAnnotation) -> AnnotationResponse:
    """Map a FileAnnotation ORM row to its response schema."""
    return AnnotationResponse(
        id=ann.id,
        raw_data_item_id=ann.raw_data_item_id,
        key=ann.key,
        sample_id=ann.sample_id,
        index=ann.index_json,
        value_json=ann.value_json,
        value_text=ann.value_text,
        created_at=ann.created_at,
        created_by=ann.created_by,
    )


def _get_raw_data_item_or_404(db: Session, raw_data_item_id: int) -> RawDataItem:
    item = db.query(RawDataItem).filter(RawDataItem.id == raw_data_item_id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Raw data item not found",
        )
    return item


def _get_annotation_or_404(db: Session, annotation_id: int) -> FileAnnotation:
    ann = db.query(FileAnnotation).filter(FileAnnotation.id == annotation_id).first()
    if not ann:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Annotation not found",
        )
    return ann


def _validate_sample_ids(
    db: Session,
    items: list[AnnotationCreateItem],
    project_id: int,
) -> None:
    """Check every sample_id in the batch belongs to the same project.

    Collects all errors before raising so the caller receives a complete
    per-item error list in a single 400 response.
    """
    errors: list[dict[str, Any]] = []
    for i, item in enumerate(items):
        if item.sample_id is None:
            continue
        sample = db.query(Sample).filter(Sample.id == item.sample_id).first()
        if not sample:
            errors.append({
                "index": i,
                "field": "sample_id",
                "error": f"Sample {item.sample_id} not found",
            })
        elif sample.project_id != project_id:
            errors.append({
                "index": i,
                "field": "sample_id",
                "error": (
                    f"Sample {item.sample_id} does not belong to the same project "
                    "as the raw data item"
                ),
            })
    if errors:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=errors)


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post(
    "/raw-data/{raw_data_item_id}/annotations",
    response_model=list[AnnotationResponse],
    status_code=status.HTTP_201_CREATED,
)
def create_annotations(
    raw_data_item_id: int,
    batch: AnnotationsBatchCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> list[AnnotationResponse]:
    """Atomically create one or more annotations for a raw data item.

    All items are validated before any rows are written; on any validation
    failure the entire batch is rejected with a 400 and per-item error detail.
    """
    item = _get_raw_data_item_or_404(db, raw_data_item_id)

    # Write permission check (also implicitly verifies project membership)
    if not check_permission(db, current_user, item.project_id, "can_edit_metadata"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to annotate raw data items",
        )

    # Business-logic validation: every sample_id must belong to the same project
    _validate_sample_ids(db, batch.annotations, item.project_id)

    # Atomic creation — flush all rows then commit once
    created: list[FileAnnotation] = []
    for ann_in in batch.annotations:
        ann = FileAnnotation(
            raw_data_item_id=raw_data_item_id,
            sample_id=ann_in.sample_id,
            key=ann_in.key,
            index_json=ann_in.index,
            value_json=ann_in.value_json,
            value_text=ann_in.value_text,
            created_by=current_user.id,
        )
        db.add(ann)
        created.append(ann)

    db.flush()
    db.commit()

    for ann in created:
        db.refresh(ann)

    return [_to_response(ann) for ann in created]


@router.get(
    "/raw-data/{raw_data_item_id}/annotations",
    response_model=list[AnnotationResponse],
)
def list_annotations(
    raw_data_item_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    key: str | None = Query(None, description="Filter by annotation key"),
    sample_id: int | None = Query(None, description="Filter by sample ID (0 = file-level only)"),
) -> list[AnnotationResponse]:
    """List annotations for a raw data item.

    Requires Lab membership.  Optionally filter by ``key`` and/or
    ``sample_id``.  Pass ``sample_id=0`` (or omit it) to include all;
    filtering by ``sample_id`` returns only that sample's annotations.
    File-level annotations (sample_id IS NULL) are always included unless
    an explicit non-zero ``sample_id`` filter is applied.
    """
    item = _get_raw_data_item_or_404(db, raw_data_item_id)

    # Read access: supervisor membership sufficient (mirrors list_raw_data_items)
    require_project_access(db, current_user, item.project_id)

    query = db.query(FileAnnotation).filter(
        FileAnnotation.raw_data_item_id == raw_data_item_id
    )
    if key is not None:
        query = query.filter(FileAnnotation.key == key)
    if sample_id is not None:
        # Explicit 0 is not a valid FK — treat as "file-level only" (NULL)
        if sample_id == 0:
            query = query.filter(FileAnnotation.sample_id.is_(None))
        else:
            query = query.filter(FileAnnotation.sample_id == sample_id)

    return [_to_response(ann) for ann in query.all()]


@router.patch(
    "/annotations/{annotation_id}",
    response_model=AnnotationResponse,
)
def patch_annotation(
    annotation_id: int,
    patch: AnnotationPatch,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> AnnotationResponse:
    """Partially update an annotation.

    Only fields present in the request body are applied; omitted fields are
    left unchanged.  Send ``null`` to clear a nullable field.
    """
    ann = _get_annotation_or_404(db, annotation_id)
    item = _get_raw_data_item_or_404(db, ann.raw_data_item_id)

    if not check_permission(db, current_user, item.project_id, "can_edit_metadata"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to update annotations",
        )

    changed = patch.model_fields_set

    if "sample_id" in changed:
        new_sid = patch.sample_id
        if new_sid is not None:
            sample = db.query(Sample).filter(Sample.id == new_sid).first()
            if not sample:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Sample {new_sid} not found",
                )
            if sample.project_id != item.project_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Sample does not belong to the same project as the raw data item",
                )
        ann.sample_id = new_sid

    if "index" in changed:
        ann.index_json = patch.index

    if "value_json" in changed:
        ann.value_json = patch.value_json

    if "value_text" in changed:
        ann.value_text = patch.value_text

    db.commit()
    db.refresh(ann)
    return _to_response(ann)


@router.delete(
    "/annotations/{annotation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_annotation(
    annotation_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> None:
    """Delete an annotation.  Returns 204 No Content on success."""
    ann = _get_annotation_or_404(db, annotation_id)
    item = _get_raw_data_item_or_404(db, ann.raw_data_item_id)

    if not check_permission(db, current_user, item.project_id, "can_edit_metadata"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to delete annotations",
        )

    db.delete(ann)
    db.commit()
