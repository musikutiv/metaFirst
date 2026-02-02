"""Database setup and helpers for discovery index."""

import os
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from supervisor.discovery.models import DiscoveryBase, IndexedSample

logger = logging.getLogger(__name__)

# Default DB path (relative to supervisor directory)
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "discovery.db"


def get_discovery_db_url() -> str:
    """Get discovery database URL from env or use default."""
    db_path = os.environ.get("DISCOVERY_DB_PATH", str(DEFAULT_DB_PATH))
    return f"sqlite:///{db_path}"


# Create engine and session factory
_engine = None
_SessionLocal = None


def get_engine():
    """Get or create the discovery database engine."""
    global _engine
    if _engine is None:
        db_url = get_discovery_db_url()
        _engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False},
        )
        # Create tables if they don't exist
        DiscoveryBase.metadata.create_all(bind=_engine)
        logger.info(f"Discovery database initialized at {db_url}")
    return _engine


def get_session_factory():
    """Get or create the session factory."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _SessionLocal


def get_discovery_db():
    """Dependency for getting discovery database session."""
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def upsert_indexed_sample(db: Session, record: dict) -> IndexedSample:
    """Upsert an indexed sample record.

    Args:
        db: Database session
        record: Dict with origin, origin_project_id, origin_sample_id, and other fields

    Returns:
        The upserted IndexedSample instance
    """
    # Find existing record
    existing = db.query(IndexedSample).filter(
        IndexedSample.origin == record["origin"],
        IndexedSample.origin_project_id == record["origin_project_id"],
        IndexedSample.origin_sample_id == record["origin_sample_id"],
    ).first()

    if existing:
        # Update existing record
        for key in ["rdmp_version", "release_id", "visibility", "metadata_json", "search_text", "origin_supervisor_id"]:
            if key in record:
                setattr(existing, key, record[key])
        existing.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        return existing
    else:
        # Create new record
        sample = IndexedSample(
            origin=record["origin"],
            origin_supervisor_id=record.get("origin_supervisor_id"),
            origin_project_id=record["origin_project_id"],
            origin_sample_id=record["origin_sample_id"],
            rdmp_version=record.get("rdmp_version"),
            release_id=record.get("release_id"),
            visibility=record.get("visibility", "PUBLIC"),
            metadata_json=record.get("metadata_json"),
            search_text=record.get("search_text"),
        )
        db.add(sample)
        db.commit()
        db.refresh(sample)
        return sample


def search_samples(
    db: Session,
    query: str,
    visibility_list: list[str],
    offset: int = 0,
    limit: int = 20,
    user_supervisor_ids: list[int] | None = None,
) -> tuple[list[IndexedSample], int]:
    """Search indexed samples using SQL LIKE with visibility filtering.

    Args:
        db: Database session
        query: Search query string
        visibility_list: List of visibility levels to include
        offset: Pagination offset
        limit: Max results to return
        user_supervisor_ids: List of supervisor IDs the user is a member of (for PRIVATE filtering)

    Returns:
        Tuple of (list of matching samples, total count)
    """
    from sqlalchemy import or_

    # Build visibility filter
    # PUBLIC and INSTITUTION: include all matching records
    # PRIVATE: only include if user is member of origin_supervisor_id
    vis_conditions = []

    for vis in visibility_list:
        if vis == "PRIVATE":
            if user_supervisor_ids:
                # User can see PRIVATE records from their supervisors
                vis_conditions.append(
                    (IndexedSample.visibility == "PRIVATE") &
                    (IndexedSample.origin_supervisor_id.in_(user_supervisor_ids))
                )
            # If no supervisor IDs, user can't see any PRIVATE records
        else:
            # PUBLIC and INSTITUTION: include all
            vis_conditions.append(IndexedSample.visibility == vis)

    if not vis_conditions:
        # No valid visibility conditions, return empty
        return [], 0

    base_query = db.query(IndexedSample).filter(or_(*vis_conditions))

    if query:
        search_pattern = f"%{query}%"
        base_query = base_query.filter(IndexedSample.search_text.like(search_pattern))

    total = base_query.count()
    results = base_query.offset(offset).limit(limit).all()

    return results, total


def get_sample_by_id(db: Session, sample_id: int) -> IndexedSample | None:
    """Get a single indexed sample by ID."""
    return db.query(IndexedSample).filter(IndexedSample.id == sample_id).first()
