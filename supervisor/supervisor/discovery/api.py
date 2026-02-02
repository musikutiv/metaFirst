"""FastAPI router for discovery index API."""

import json
import logging
import os
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Query, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from supervisor.discovery.db import (
    get_discovery_db,
    upsert_indexed_sample,
    search_samples,
    get_sample_by_id,
)
from supervisor.discovery.models import Visibility
from supervisor.database import get_db
from supervisor.models.user import User
from supervisor.models.supervisor_membership import SupervisorMembership
from supervisor.utils.security import decode_access_token

logger = logging.getLogger(__name__)

router = APIRouter()

# Optional OAuth2 scheme for discovery endpoints
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


# --- Schemas ---


class PushRecord(BaseModel):
    """A single record to push to the index."""
    origin_supervisor_id: int | None = None  # For PRIVATE visibility filtering
    origin_project_id: int
    origin_sample_id: int
    sample_identifier: str | None = None
    rdmp_version: int | None = None
    release_id: str | None = None
    visibility: str = Field(default="PUBLIC")
    metadata: dict | None = None


class PushPayload(BaseModel):
    """Payload for pushing records to the index."""
    origin: str = Field(..., description="Origin identifier (e.g., hostname)")
    records: list[PushRecord] = Field(..., min_length=1)


class PushResponse(BaseModel):
    """Response from push operation."""
    upserted: int
    errors: list[str] = []


class SearchHit(BaseModel):
    """A single search result."""
    id: int
    origin: str
    origin_project_id: int
    origin_sample_id: int
    visibility: str
    sample_identifier: str | None = None
    indexed_at: str | None = None

    model_config = ConfigDict(from_attributes=True)


class SearchResponse(BaseModel):
    """Response from search operation."""
    total: int
    hits: list[SearchHit]


class RecordDetail(BaseModel):
    """Full detail of an indexed record."""
    id: int
    origin: str
    origin_project_id: int
    origin_sample_id: int
    rdmp_version: int | None
    release_id: str | None
    visibility: str
    metadata: dict | None
    indexed_at: str | None
    updated_at: str | None

    model_config = ConfigDict(from_attributes=True)


# --- Auth helpers ---


def get_api_key() -> str | None:
    """Get the discovery API key from environment."""
    return os.environ.get("DISCOVERY_API_KEY")


def verify_api_key(authorization: str | None = Header(default=None)) -> bool:
    """Verify API key from Authorization header.

    Returns True if valid, raises HTTPException if invalid.
    """
    api_key = get_api_key()

    if not api_key:
        logger.warning("DISCOVERY_API_KEY not set - rejecting authenticated request")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Discovery push API not configured (missing API key)",
        )

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    # Expect "ApiKey <key>" format
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0] != "ApiKey":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected: ApiKey <key>",
        )

    if parts[1] != api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )

    return True


def get_optional_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme_optional)],
    db: Annotated[Session, Depends(get_db)],
) -> User | None:
    """Get current user from JWT token if provided, otherwise return None."""
    if not token:
        return None

    try:
        payload = decode_access_token(token)
        if payload is None:
            return None
        username = payload.get("username")
        if username is None:
            return None
        user = db.query(User).filter(User.username == username).first()
        return user
    except Exception:
        return None


def get_user_supervisor_ids(db: Session, user: User | None) -> list[int]:
    """Get list of supervisor IDs the user is a member of."""
    if not user:
        return []

    memberships = db.query(SupervisorMembership.supervisor_id).filter(
        SupervisorMembership.user_id == user.id
    ).all()

    return [m.supervisor_id for m in memberships]


# --- Endpoints ---


@router.post("/push", response_model=PushResponse, status_code=status.HTTP_200_OK)
def push_records(
    payload: PushPayload,
    db: Annotated[Session, Depends(get_discovery_db)],
    _auth: Annotated[bool, Depends(verify_api_key)],
):
    """Push records to the discovery index (requires API key).

    Upserts records based on (origin, origin_project_id, origin_sample_id).
    """
    upserted = 0
    errors = []

    for record in payload.records:
        try:
            # Build search text from metadata and sample identifier
            search_parts = []
            if record.sample_identifier:
                search_parts.append(record.sample_identifier)
            if record.metadata:
                # Flatten metadata values for search
                for key, value in record.metadata.items():
                    if isinstance(value, str):
                        search_parts.append(value)
                    elif value is not None:
                        search_parts.append(str(value))

            search_text = " ".join(search_parts) if search_parts else None

            upsert_indexed_sample(db, {
                "origin": payload.origin,
                "origin_supervisor_id": record.origin_supervisor_id,
                "origin_project_id": record.origin_project_id,
                "origin_sample_id": record.origin_sample_id,
                "rdmp_version": record.rdmp_version,
                "release_id": record.release_id,
                "visibility": record.visibility,
                "metadata_json": json.dumps(record.metadata) if record.metadata else None,
                "search_text": search_text,
            })
            upserted += 1
        except Exception as e:
            errors.append(
                f"Failed to upsert sample {record.origin_sample_id}: {str(e)}"
            )
            logger.exception(f"Error upserting record: {e}")

    return PushResponse(upserted=upserted, errors=errors)


@router.get("/search", response_model=SearchResponse)
def search(
    discovery_db: Annotated[Session, Depends(get_discovery_db)],
    central_db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_current_user)],
    q: str = Query(default="", description="Search query"),
    visibility: str = Query(default="PUBLIC", description="Visibility filter (comma-separated)"),
    offset: int = Query(default=0, alias="from", ge=0, description="Pagination offset"),
    size: int = Query(default=20, ge=1, le=100, description="Results per page"),
):
    """Search the discovery index.

    Visibility filtering:
    - PUBLIC: No authentication required
    - INSTITUTION: Requires authenticated user (any user)
    - PRIVATE: Requires authenticated user who is member of the record's supervisor
    """
    # Parse visibility list
    vis_list = [v.strip().upper() for v in visibility.split(",")]

    # Validate visibility values
    valid_vis = {v.value for v in Visibility}
    for v in vis_list:
        if v not in valid_vis:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid visibility: {v}. Must be one of: {', '.join(valid_vis)}",
            )

    # Check auth requirements
    requires_auth = any(v != Visibility.PUBLIC.value for v in vis_list)
    if requires_auth and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required for non-PUBLIC visibility",
        )

    # Get user's supervisor IDs for PRIVATE filtering
    user_supervisor_ids = get_user_supervisor_ids(central_db, current_user)

    results, total = search_samples(discovery_db, q, vis_list, offset, size, user_supervisor_ids)

    hits = []
    for sample in results:
        # Extract sample_identifier from metadata if available
        sample_identifier = None
        if sample.metadata_json:
            try:
                meta = json.loads(sample.metadata_json)
                sample_identifier = meta.get("sample_identifier")
            except json.JSONDecodeError:
                pass

        hits.append(SearchHit(
            id=sample.id,
            origin=sample.origin,
            origin_project_id=sample.origin_project_id,
            origin_sample_id=sample.origin_sample_id,
            visibility=sample.visibility,
            sample_identifier=sample_identifier,
            indexed_at=sample.indexed_at.isoformat() if sample.indexed_at else None,
        ))

    return SearchResponse(total=total, hits=hits)


@router.get("/records/{record_id}", response_model=RecordDetail)
def get_record(
    record_id: int,
    discovery_db: Annotated[Session, Depends(get_discovery_db)],
    central_db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_current_user)],
):
    """Get full details of an indexed record.

    Visibility filtering:
    - PUBLIC: No authentication required
    - INSTITUTION: Requires authenticated user
    - PRIVATE: Requires authenticated user who is member of the record's supervisor
    """
    sample = get_sample_by_id(discovery_db, record_id)

    if not sample:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Record not found",
        )

    # Check visibility
    if sample.visibility == Visibility.PUBLIC.value:
        pass  # No auth required
    elif sample.visibility == Visibility.INSTITUTION.value:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required for INSTITUTION records",
            )
    elif sample.visibility == Visibility.PRIVATE.value:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required for PRIVATE records",
            )
        # Check if user is member of the record's supervisor
        user_supervisor_ids = get_user_supervisor_ids(central_db, current_user)
        if sample.origin_supervisor_id not in user_supervisor_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: not a member of the record's supervisor",
            )

    # Parse metadata
    metadata = None
    if sample.metadata_json:
        try:
            metadata = json.loads(sample.metadata_json)
        except json.JSONDecodeError:
            pass

    return RecordDetail(
        id=sample.id,
        origin=sample.origin,
        origin_project_id=sample.origin_project_id,
        origin_sample_id=sample.origin_sample_id,
        rdmp_version=sample.rdmp_version,
        release_id=sample.release_id,
        visibility=sample.visibility,
        metadata=metadata,
        indexed_at=sample.indexed_at.isoformat() if sample.indexed_at else None,
        updated_at=sample.updated_at.isoformat() if sample.updated_at else None,
    )
