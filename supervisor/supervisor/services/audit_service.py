"""Audit logging service for tracking all state changes."""

from typing import Any
from sqlalchemy.orm import Session

from supervisor.models.audit import AuditLog


def create_audit_log(
    db: Session,
    project_id: int,
    actor_user_id: int,
    action_type: str,
    target_type: str,
    target_id: int,
    before_json: dict[str, Any] | None = None,
    after_json: dict[str, Any] | None = None,
    source_device: str | None = None,
) -> AuditLog:
    """Create an audit log entry for a state change.

    Args:
        db: Database session
        project_id: ID of the project this action belongs to
        actor_user_id: ID of the user performing the action
        action_type: Type of action (CREATE, UPDATE, DELETE)
        target_type: Type of entity being modified (StorageRoot, RawDataItem, etc.)
        target_id: ID of the entity being modified
        before_json: State before the change (for UPDATE/DELETE)
        after_json: State after the change (for CREATE/UPDATE)
        source_device: Optional device identifier

    Returns:
        The created AuditLog entry
    """
    audit_log = AuditLog(
        project_id=project_id,
        actor_user_id=actor_user_id,
        action_type=action_type,
        target_type=target_type,
        target_id=target_id,
        before_json=before_json,
        after_json=after_json,
        source_device=source_device,
    )
    db.add(audit_log)
    # Note: caller should commit the transaction
    return audit_log


def log_create(
    db: Session,
    project_id: int,
    actor_user_id: int,
    target_type: str,
    target_id: int,
    after_state: dict[str, Any],
    source_device: str | None = None,
) -> AuditLog:
    """Log a CREATE action."""
    return create_audit_log(
        db=db,
        project_id=project_id,
        actor_user_id=actor_user_id,
        action_type="CREATE",
        target_type=target_type,
        target_id=target_id,
        before_json=None,
        after_json=after_state,
        source_device=source_device,
    )


def log_update(
    db: Session,
    project_id: int,
    actor_user_id: int,
    target_type: str,
    target_id: int,
    before_state: dict[str, Any],
    after_state: dict[str, Any],
    source_device: str | None = None,
) -> AuditLog:
    """Log an UPDATE action."""
    return create_audit_log(
        db=db,
        project_id=project_id,
        actor_user_id=actor_user_id,
        action_type="UPDATE",
        target_type=target_type,
        target_id=target_id,
        before_json=before_state,
        after_json=after_state,
        source_device=source_device,
    )


def log_delete(
    db: Session,
    project_id: int,
    actor_user_id: int,
    target_type: str,
    target_id: int,
    before_state: dict[str, Any],
    source_device: str | None = None,
) -> AuditLog:
    """Log a DELETE action."""
    return create_audit_log(
        db=db,
        project_id=project_id,
        actor_user_id=actor_user_id,
        action_type="DELETE",
        target_type=target_type,
        target_id=target_id,
        before_json=before_state,
        after_json=None,
        source_device=source_device,
    )


def serialize_storage_root(storage_root) -> dict[str, Any]:
    """Serialize a StorageRoot for audit logging."""
    return {
        "id": storage_root.id,
        "project_id": storage_root.project_id,
        "name": storage_root.name,
        "description": storage_root.description,
    }


def serialize_storage_root_mapping(mapping) -> dict[str, Any]:
    """Serialize a StorageRootMapping for audit logging."""
    return {
        "id": mapping.id,
        "user_id": mapping.user_id,
        "storage_root_id": mapping.storage_root_id,
        "local_mount_path": mapping.local_mount_path,
    }


def serialize_raw_data_item(item) -> dict[str, Any]:
    """Serialize a RawDataItem for audit logging."""
    return {
        "id": item.id,
        "project_id": item.project_id,
        "sample_id": item.sample_id,
        "storage_root_id": item.storage_root_id,
        "relative_path": item.relative_path,
        "storage_owner_user_id": item.storage_owner_user_id,
        "file_size_bytes": item.file_size_bytes,
        "file_hash_sha256": item.file_hash_sha256,
    }
