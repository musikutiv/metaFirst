"""Storage root and raw data schemas."""

from datetime import datetime
from pydantic import BaseModel, Field, field_validator
import re


class StorageRootBase(BaseModel):
    """Base storage root schema."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None


class StorageRootCreate(StorageRootBase):
    """Storage root creation schema."""

    pass


class StorageRoot(StorageRootBase):
    """Storage root response schema."""

    id: int
    project_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class StorageRootMappingBase(BaseModel):
    """Base storage root mapping schema."""

    local_mount_path: str = Field(..., min_length=1, max_length=1024)


class StorageRootMappingCreate(StorageRootMappingBase):
    """Storage root mapping creation schema."""

    pass


class StorageRootMapping(StorageRootMappingBase):
    """Storage root mapping response schema."""

    id: int
    user_id: int
    storage_root_id: int
    created_at: datetime
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class RawDataItemBase(BaseModel):
    """Base raw data item schema."""

    storage_root_id: int
    relative_path: str = Field(..., min_length=1, max_length=2048)
    sample_id: int | None = None
    storage_owner_user_id: int | None = None  # Defaults to current user if not provided
    file_size_bytes: int | None = None
    file_hash_sha256: str | None = Field(None, max_length=64)
    notes: str | None = None

    @field_validator("relative_path")
    @classmethod
    def validate_relative_path(cls, v: str) -> str:
        """Validate relative path: no absolute paths, no .., normalize separators."""
        # Reject absolute paths (Unix or Windows style)
        if v.startswith("/") or v.startswith("\\") or (len(v) > 1 and v[1] == ":"):
            raise ValueError("Path must be relative, not absolute")

        # Reject path traversal
        parts = re.split(r"[/\\]", v)
        if ".." in parts:
            raise ValueError("Path traversal (..) is not allowed")

        # Normalize separators to forward slashes
        normalized = "/".join(p for p in parts if p)
        if not normalized:
            raise ValueError("Path cannot be empty")

        return normalized


class RawDataItemCreate(RawDataItemBase):
    """Raw data item creation schema."""

    pass


class RawDataItem(BaseModel):
    """Raw data item response schema."""

    id: int
    project_id: int
    sample_id: int | None
    storage_root_id: int
    relative_path: str
    storage_owner_user_id: int
    file_size_bytes: int | None
    file_hash_sha256: str | None
    created_at: datetime
    created_by: int

    class Config:
        from_attributes = True


class RawDataItemWithDetails(RawDataItem):
    """Raw data item with storage root details."""

    storage_root_name: str | None = None
    sample_identifier: str | None = None


class PathUpdateRequest(BaseModel):
    """Path update request schema."""

    new_storage_root_id: int
    new_relative_path: str = Field(..., min_length=1, max_length=2048)
    reason: str | None = None

    @field_validator("new_relative_path")
    @classmethod
    def validate_relative_path(cls, v: str) -> str:
        """Validate relative path: no absolute paths, no .., normalize separators."""
        if v.startswith("/") or v.startswith("\\") or (len(v) > 1 and v[1] == ":"):
            raise ValueError("Path must be relative, not absolute")

        parts = re.split(r"[/\\]", v)
        if ".." in parts:
            raise ValueError("Path traversal (..) is not allowed")

        normalized = "/".join(p for p in parts if p)
        if not normalized:
            raise ValueError("Path cannot be empty")

        return normalized


class PathChange(BaseModel):
    """Path change response schema."""

    id: int
    raw_data_item_id: int
    old_storage_root_id: int
    old_relative_path: str
    new_storage_root_id: int
    new_relative_path: str
    changed_at: datetime
    changed_by: int
    reason: str | None

    class Config:
        from_attributes = True
