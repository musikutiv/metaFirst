"""Storage roots, mappings, and raw data API."""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from supervisor.database import get_db
from supervisor.models.user import User
from supervisor.models.project import Project
from supervisor.models.membership import Membership
from supervisor.models.storage import StorageRoot, StorageRootMapping
from supervisor.models.raw_data import RawDataItem, PathChange
from supervisor.models.sample import Sample
from supervisor.schemas.storage import (
    StorageRoot as StorageRootSchema,
    StorageRootCreate,
    StorageRootMapping as StorageRootMappingSchema,
    StorageRootMappingCreate,
    RawDataItem as RawDataItemSchema,
    RawDataItemCreate,
    RawDataItemWithDetails,
    PathUpdateRequest,
    PathChange as PathChangeSchema,
)
from supervisor.api.deps import get_current_active_user
from supervisor.services.permission_service import check_permission
from supervisor.services.audit_service import (
    log_create,
    log_update,
    serialize_storage_root,
    serialize_storage_root_mapping,
    serialize_raw_data_item,
)

router = APIRouter()


# ============================================================================
# Storage Roots
# ============================================================================


@router.post(
    "/projects/{project_id}/storage-roots",
    response_model=StorageRootSchema,
    status_code=status.HTTP_201_CREATED,
)
def create_storage_root(
    project_id: int,
    storage_root_data: StorageRootCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Create a new storage root for a project."""
    # Check project exists
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )

    # Check permission (require can_manage_rdmp to create storage roots)
    if not check_permission(db, current_user, project_id, "can_manage_rdmp"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to create storage roots",
        )

    # Check if storage root name already exists in project
    existing = (
        db.query(StorageRoot)
        .filter(
            StorageRoot.project_id == project_id,
            StorageRoot.name == storage_root_data.name,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Storage root name already exists in this project",
        )

    # Create storage root
    storage_root = StorageRoot(
        project_id=project_id,
        name=storage_root_data.name,
        description=storage_root_data.description,
    )
    db.add(storage_root)
    db.flush()  # Get the ID before committing

    # Audit log
    log_create(
        db=db,
        project_id=project_id,
        actor_user_id=current_user.id,
        target_type="StorageRoot",
        target_id=storage_root.id,
        after_state=serialize_storage_root(storage_root),
    )

    db.commit()
    db.refresh(storage_root)

    return storage_root


@router.get("/projects/{project_id}/storage-roots", response_model=list[StorageRootSchema])
def list_storage_roots(
    project_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """List storage roots for a project."""
    # Check membership
    membership = (
        db.query(Membership)
        .filter(Membership.project_id == project_id, Membership.user_id == current_user.id)
        .first()
    )
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this project"
        )

    storage_roots = (
        db.query(StorageRoot).filter(StorageRoot.project_id == project_id).all()
    )
    return storage_roots


# ============================================================================
# Storage Root Mappings
# ============================================================================


@router.post(
    "/storage-roots/{storage_root_id}/mappings",
    response_model=StorageRootMappingSchema,
    status_code=status.HTTP_201_CREATED,
)
def create_or_update_mapping(
    storage_root_id: int,
    mapping_data: StorageRootMappingCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Create or update a storage root mapping for the current user."""
    # Get storage root and verify it exists
    storage_root = db.query(StorageRoot).filter(StorageRoot.id == storage_root_id).first()
    if not storage_root:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Storage root not found"
        )

    # Check membership in the storage root's project
    membership = (
        db.query(Membership)
        .filter(
            Membership.project_id == storage_root.project_id,
            Membership.user_id == current_user.id,
        )
        .first()
    )
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this project"
        )

    # Check if mapping already exists for this user
    existing = (
        db.query(StorageRootMapping)
        .filter(
            StorageRootMapping.storage_root_id == storage_root_id,
            StorageRootMapping.user_id == current_user.id,
        )
        .first()
    )

    if existing:
        # Update existing mapping
        before_state = serialize_storage_root_mapping(existing)
        existing.local_mount_path = mapping_data.local_mount_path
        db.flush()

        log_update(
            db=db,
            project_id=storage_root.project_id,
            actor_user_id=current_user.id,
            target_type="StorageRootMapping",
            target_id=existing.id,
            before_state=before_state,
            after_state=serialize_storage_root_mapping(existing),
        )

        db.commit()
        db.refresh(existing)
        return existing
    else:
        # Create new mapping
        mapping = StorageRootMapping(
            user_id=current_user.id,
            storage_root_id=storage_root_id,
            local_mount_path=mapping_data.local_mount_path,
        )
        db.add(mapping)
        db.flush()

        log_create(
            db=db,
            project_id=storage_root.project_id,
            actor_user_id=current_user.id,
            target_type="StorageRootMapping",
            target_id=mapping.id,
            after_state=serialize_storage_root_mapping(mapping),
        )

        db.commit()
        db.refresh(mapping)
        return mapping


@router.get(
    "/storage-roots/{storage_root_id}/mappings",
    response_model=list[StorageRootMappingSchema],
)
def list_mappings(
    storage_root_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """List storage root mappings. Users can only see their own mappings unless they can manage RDMP."""
    # Get storage root and verify it exists
    storage_root = db.query(StorageRoot).filter(StorageRoot.id == storage_root_id).first()
    if not storage_root:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Storage root not found"
        )

    # Check membership
    membership = (
        db.query(Membership)
        .filter(
            Membership.project_id == storage_root.project_id,
            Membership.user_id == current_user.id,
        )
        .first()
    )
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this project"
        )

    # Check if user can see all mappings (has can_manage_rdmp permission)
    can_see_all = check_permission(
        db, current_user, storage_root.project_id, "can_manage_rdmp"
    )

    if can_see_all:
        mappings = (
            db.query(StorageRootMapping)
            .filter(StorageRootMapping.storage_root_id == storage_root_id)
            .all()
        )
    else:
        # Users can only see their own mappings
        mappings = (
            db.query(StorageRootMapping)
            .filter(
                StorageRootMapping.storage_root_id == storage_root_id,
                StorageRootMapping.user_id == current_user.id,
            )
            .all()
        )

    return mappings


# ============================================================================
# Raw Data Items
# ============================================================================


@router.post(
    "/projects/{project_id}/raw-data",
    response_model=RawDataItemSchema,
    status_code=status.HTTP_201_CREATED,
)
def create_raw_data_item(
    project_id: int,
    raw_data: RawDataItemCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Register a new raw data item (file reference)."""
    # Check project exists
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )

    # Check permission (require can_edit_paths to register raw data)
    if not check_permission(db, current_user, project_id, "can_edit_paths"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to register raw data",
        )

    # Verify storage root exists and belongs to this project
    storage_root = (
        db.query(StorageRoot).filter(StorageRoot.id == raw_data.storage_root_id).first()
    )
    if not storage_root:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Storage root not found"
        )
    if storage_root.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Storage root does not belong to this project",
        )

    # Verify sample exists (if provided) and belongs to this project
    if raw_data.sample_id:
        sample = db.query(Sample).filter(Sample.id == raw_data.sample_id).first()
        if not sample:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Sample not found"
            )
        if sample.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sample does not belong to this project",
            )

    # Check if this path already exists in the storage root
    existing = (
        db.query(RawDataItem)
        .filter(
            RawDataItem.storage_root_id == raw_data.storage_root_id,
            RawDataItem.relative_path == raw_data.relative_path,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This path is already registered in the storage root",
        )

    # Determine storage owner (default to current user)
    storage_owner_id = raw_data.storage_owner_user_id or current_user.id

    # Create raw data item
    raw_data_item = RawDataItem(
        project_id=project_id,
        sample_id=raw_data.sample_id,
        storage_root_id=raw_data.storage_root_id,
        relative_path=raw_data.relative_path,
        storage_owner_user_id=storage_owner_id,
        file_size_bytes=raw_data.file_size_bytes,
        file_hash_sha256=raw_data.file_hash_sha256,
        created_by=current_user.id,
    )
    db.add(raw_data_item)
    db.flush()

    # Audit log
    log_create(
        db=db,
        project_id=project_id,
        actor_user_id=current_user.id,
        target_type="RawDataItem",
        target_id=raw_data_item.id,
        after_state=serialize_raw_data_item(raw_data_item),
    )

    db.commit()
    db.refresh(raw_data_item)

    return raw_data_item


@router.get("/projects/{project_id}/raw-data", response_model=list[RawDataItemWithDetails])
def list_raw_data_items(
    project_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    sample_id: int | None = Query(None, description="Filter by sample ID"),
    storage_root_id: int | None = Query(None, description="Filter by storage root ID"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """List raw data items in a project."""
    # Check membership
    membership = (
        db.query(Membership)
        .filter(Membership.project_id == project_id, Membership.user_id == current_user.id)
        .first()
    )
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this project"
        )

    # Build query
    query = db.query(RawDataItem).filter(RawDataItem.project_id == project_id)

    if sample_id is not None:
        query = query.filter(RawDataItem.sample_id == sample_id)
    if storage_root_id is not None:
        query = query.filter(RawDataItem.storage_root_id == storage_root_id)

    raw_data_items = query.offset(offset).limit(limit).all()

    # Enrich with details
    result = []
    for item in raw_data_items:
        storage_root_name = item.storage_root.name if item.storage_root else None
        sample_identifier = item.sample.sample_identifier if item.sample else None

        result.append(
            RawDataItemWithDetails(
                id=item.id,
                project_id=item.project_id,
                sample_id=item.sample_id,
                storage_root_id=item.storage_root_id,
                relative_path=item.relative_path,
                storage_owner_user_id=item.storage_owner_user_id,
                file_size_bytes=item.file_size_bytes,
                file_hash_sha256=item.file_hash_sha256,
                created_at=item.created_at,
                created_by=item.created_by,
                storage_root_name=storage_root_name,
                sample_identifier=sample_identifier,
            )
        )

    return result


@router.get("/raw-data/{raw_data_item_id}", response_model=RawDataItemWithDetails)
def get_raw_data_item(
    raw_data_item_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Get a specific raw data item."""
    item = db.query(RawDataItem).filter(RawDataItem.id == raw_data_item_id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Raw data item not found"
        )

    # Check membership
    membership = (
        db.query(Membership)
        .filter(
            Membership.project_id == item.project_id,
            Membership.user_id == current_user.id,
        )
        .first()
    )
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this project"
        )

    storage_root_name = item.storage_root.name if item.storage_root else None
    sample_identifier = item.sample.sample_identifier if item.sample else None

    return RawDataItemWithDetails(
        id=item.id,
        project_id=item.project_id,
        sample_id=item.sample_id,
        storage_root_id=item.storage_root_id,
        relative_path=item.relative_path,
        storage_owner_user_id=item.storage_owner_user_id,
        file_size_bytes=item.file_size_bytes,
        file_hash_sha256=item.file_hash_sha256,
        created_at=item.created_at,
        created_by=item.created_by,
        storage_root_name=storage_root_name,
        sample_identifier=sample_identifier,
    )


# ============================================================================
# Path Updates
# ============================================================================


@router.put("/raw-data/{raw_data_item_id}/path", response_model=RawDataItemSchema)
def update_raw_data_path(
    raw_data_item_id: int,
    path_update: PathUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Update the path of a raw data item. Creates PathChange and AuditLog entries."""
    # Get existing item
    item = db.query(RawDataItem).filter(RawDataItem.id == raw_data_item_id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Raw data item not found"
        )

    # Check permission
    if not check_permission(db, current_user, item.project_id, "can_edit_paths"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to update paths",
        )

    # Verify new storage root exists and belongs to the same project
    new_storage_root = (
        db.query(StorageRoot)
        .filter(StorageRoot.id == path_update.new_storage_root_id)
        .first()
    )
    if not new_storage_root:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="New storage root not found"
        )
    if new_storage_root.project_id != item.project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New storage root does not belong to the same project",
        )

    # Check if new path already exists (if different from current)
    if (
        path_update.new_storage_root_id != item.storage_root_id
        or path_update.new_relative_path != item.relative_path
    ):
        existing = (
            db.query(RawDataItem)
            .filter(
                RawDataItem.storage_root_id == path_update.new_storage_root_id,
                RawDataItem.relative_path == path_update.new_relative_path,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The new path is already registered",
            )

    # Store old values for audit
    before_state = serialize_raw_data_item(item)
    old_storage_root_id = item.storage_root_id
    old_relative_path = item.relative_path

    # Create PathChange record
    path_change = PathChange(
        raw_data_item_id=item.id,
        old_storage_root_id=old_storage_root_id,
        old_relative_path=old_relative_path,
        new_storage_root_id=path_update.new_storage_root_id,
        new_relative_path=path_update.new_relative_path,
        changed_by=current_user.id,
        reason=path_update.reason,
    )
    db.add(path_change)

    # Update the item
    item.storage_root_id = path_update.new_storage_root_id
    item.relative_path = path_update.new_relative_path
    db.flush()

    # Audit log
    log_update(
        db=db,
        project_id=item.project_id,
        actor_user_id=current_user.id,
        target_type="RawDataItem",
        target_id=item.id,
        before_state=before_state,
        after_state=serialize_raw_data_item(item),
    )

    db.commit()
    db.refresh(item)

    return item


@router.get(
    "/raw-data/{raw_data_item_id}/path-history",
    response_model=list[PathChangeSchema],
)
def get_path_history(
    raw_data_item_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Get the path change history for a raw data item."""
    # Get item
    item = db.query(RawDataItem).filter(RawDataItem.id == raw_data_item_id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Raw data item not found"
        )

    # Check membership
    membership = (
        db.query(Membership)
        .filter(
            Membership.project_id == item.project_id,
            Membership.user_id == current_user.id,
        )
        .first()
    )
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this project"
        )

    path_changes = (
        db.query(PathChange)
        .filter(PathChange.raw_data_item_id == raw_data_item_id)
        .order_by(PathChange.changed_at.desc())
        .all()
    )

    return path_changes
